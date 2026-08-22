"""Grounded generation + citation validation.

The model must return claims in a strict JSON schema, each listing the source
IDs it relies on. The backend then checks every ID against the set actually
retrieved for THIS query. IDs that were not retrieved are stripped and the claim
is downgraded to unsourced.

That is the load-bearing idea: a fabricated citation cannot survive the check,
so it can never reach the user looking real.
"""
from __future__ import annotations

import json

from openai import OpenAI

from ..config import settings

_client: OpenAI | None = None


def _openai() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


CLAIM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["claims", "abstained", "gaps"],
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "source_ids", "confidence"],
                "properties": {
                    "text": {"type": "string"},
                    "source_ids": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
            },
        },
        "abstained": {"type": "boolean"},
        "gaps": {"type": "array", "items": {"type": "string"}},
    },
}

SYSTEM = """You are OncoLens, a biomedical research assistant for oncology drug discovery.

ABSOLUTE RULES
1. Use ONLY the numbered SOURCES and STRUCTURED RECORDS provided. Never use prior knowledge \
to state a fact.
2. Every claim must list the source IDs that support it, copied EXACTLY as given \
(e.g. "PMID:31825714", "CHEMBL:CHEMBL3353410"). Never invent an ID. Never cite an ID that \
is not in the provided list.
3. If you make a statement the sources do not support — a synthesis, a caveat, an inference \
— return it with an EMPTY source_ids array. Do not attach an unrelated citation to make it \
look grounded. An honest empty array is always correct; a wrong citation is never.
4. Never state numeric values (potencies, doses, weights) unless they appear verbatim in \
STRUCTURED RECORDS. Structured values are authoritative; do not recompute or round them.
5. Break the answer into 2-6 short claims, each one self-contained and separately checkable.
6. This is a research tool. Never give clinical, diagnostic or treatment advice.
7. If the sources genuinely do not answer the question, set abstained=true, return no \
claims, and list what is missing in gaps."""


def _context(sources: list[dict], structured: dict, entities: list[dict] | None = None) -> str:
    parts = []

    # The entity resolver already established these identities from the synonym
    # tables. Without stating them, the model correctly refuses to assert that
    # "Tagrisso" is osimertinib, because no abstract says so in those words.
    if entities:
        parts.append("RESOLVED ENTITIES (authoritative — established by database lookup)")
        for e in entities:
            kind = "compound" if e["type"] == "compound" else "target"
            parts.append(
                f'[CHEMBL:{e["id"]}] "{e["text"]}" is a known name for the '
                f'{kind} {e.get("name") or e["id"]} (ChEMBL id {e["id"]}). '
                f'Cite this as CHEMBL:{e["id"]}.'
            )
        parts.append("")

    if sources:
        parts.append("SOURCES")
        for s in sources:
            head = f"[{s['id']}] {s.get('title') or ''}"
            meta = " · ".join(str(x) for x in (s.get("journal"), s.get("year")) if x)
            parts.append(f"{head}\n({meta})\n{s['snippet']}\n")

    comps = structured.get("compounds") or []
    acts = structured.get("activities") or []

    if comps:
        parts.append("STRUCTURED RECORDS — COMPOUNDS (authoritative, quote verbatim)")
        for c in comps:
            parts.append(
                f"[CHEMBL:{c['chembl_id']}] {c.get('pref_name')} | "
                f"formula {c.get('mol_formula')} | MW {c.get('mol_weight')} | "
                f"XLogP {c.get('xlogp')} | TPSA {c.get('tpsa')} | "
                f"Ro5 violations {c.get('ro5_violations')} | max phase {c.get('max_phase')}"
            )

    if acts:
        parts.append("\nSTRUCTURED RECORDS — MEASURED BIOACTIVITY (authoritative)")
        for a in acts[:25]:
            name = a.get("compound_name") or a.get("compound_id") or ""
            parts.append(
                f"[CHEMBL:{a.get('target_id')}] {name} vs {a.get('gene_symbol')}: "
                f"{a.get('standard_type')} {a.get('standard_value')} "
                f"{a.get('standard_units') or ''} (pChEMBL {a.get('pchembl_value')})"
            )

    return "\n".join(parts)


def generate(query: str, sources: list[dict], structured: dict,
             entities: list[dict] | None = None) -> dict:
    ctx = _context(sources, structured, entities)
    try:
        r = _openai().chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"{ctx}\n\nQUESTION: {query}"},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "grounded_answer", "strict": True,
                                "schema": CLAIM_SCHEMA},
            },
            # gpt-5-nano is a reasoning model: reasoning tokens are drawn from the
            # same budget as output. With a full context it will spend the whole
            # allowance thinking and emit nothing unless effort is capped and the
            # budget is generous.
            reasoning_effort=settings.openai_reasoning_effort,
            max_completion_tokens=settings.openai_max_tokens,
        )
        choice = r.choices[0]
        content = (choice.message.content or "").strip()
        if not content:
            return {
                "claims": [], "abstained": True,
                "gaps": [f"The model returned no output (finish_reason="
                         f"{choice.finish_reason}). Retrieved sources are shown below."],
                "_error": "empty_completion",
            }
        return json.loads(content)
    except Exception as e:
        return {
            "claims": [],
            "abstained": True,
            "gaps": [f"Answer generation failed: {type(e).__name__}. "
                     "Retrieved sources are shown below and remain usable."],
            "_error": str(e),
        }


def validate(raw: dict, sources: list[dict], structured: dict,
             entities: list[dict] | None = None) -> tuple[list[dict], dict]:
    """Strip every citation that was not actually retrieved for this query.

    Returns (claims, audit). The audit records what was removed so the behaviour
    can be demonstrated rather than merely asserted.
    """
    allowed: dict[str, dict] = {s["id"]: s for s in sources}
    for e in entities or []:
        allowed[f"CHEMBL:{e['id']}"] = {
            "id": f"CHEMBL:{e['id']}", "type": "chembl",
            "title": e.get("name") or e["id"],
        }
    for c in structured.get("compounds") or []:
        allowed[f"CHEMBL:{c['chembl_id']}"] = {
            "id": f"CHEMBL:{c['chembl_id']}", "type": "chembl",
            "title": c.get("pref_name"), "url":
                f"https://www.ebi.ac.uk/chembl/compound_report_card/{c['chembl_id']}/",
        }
    for a in structured.get("activities") or []:
        tid = a.get("target_id")
        if tid:
            allowed[f"CHEMBL:{tid}"] = {
                "id": f"CHEMBL:{tid}", "type": "chembl",
                "title": a.get("target_name") or a.get("gene_symbol"),
                "url": f"https://www.ebi.ac.uk/chembl/target_report_card/{tid}/",
            }

    claims, removed = [], []
    for c in raw.get("claims", []):
        text = (c.get("text") or "").strip()
        if not text:
            continue
        valid, bad = [], []
        for sid in c.get("source_ids", []):
            sid = (sid or "").strip()
            if sid in allowed:
                valid.append(allowed[sid])
            elif sid:
                bad.append(sid)
        if bad:
            removed.append({"claim": text[:120], "rejected": bad})
        claims.append({
            "text": text,
            "sources": [{"id": v["id"], "type": v["type"], "title": v.get("title")}
                        for v in valid],
            "unsourced": len(valid) == 0,
            "confidence": c.get("confidence", "low"),
        })

    audit = {
        "citations_offered": sum(len(c.get("source_ids", [])) for c in raw.get("claims", [])),
        "citations_validated": sum(len(c["sources"]) for c in claims),
        "citations_rejected": sum(len(r["rejected"]) for r in removed),
        "rejected_detail": removed,
    }
    return claims, audit
