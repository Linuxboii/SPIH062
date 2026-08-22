"""Entity resolution.

The component that makes this domain-specific rather than generic text RAG.
`Tagrisso`, `AZD9291` and `osimertinib` are three strings for one molecule; a
text-RAG system fails on the first two because the literature says the third.
Queries are normalised to ChEMBL identifiers before anything is retrieved.
"""
from __future__ import annotations

import re
from functools import lru_cache

from ..db import fetch_all

_NORM = re.compile(r"[^a-z0-9]+")

# Words that normalise into short tokens and would otherwise match a compound
# synonym by accident.
STOPWORDS = {
    "what", "which", "where", "when", "does", "with", "from", "that", "this",
    "have", "about", "there", "their", "been", "were", "into", "than", "then",
    "cancer", "tumor", "tumour", "patient", "patients", "study", "studies",
    "treatment", "therapy", "clinical", "trial", "trials", "data", "known",
    "show", "shown", "report", "reported", "resistance", "mutation", "inhibitor",
    "inhibitors", "compound", "compounds", "target", "targets", "drug", "drugs",
    "recent", "findings", "summarise", "summarize", "corpus", "potent", "how",
}


def norm(s: str) -> str:
    return _NORM.sub("", (s or "").lower())


@lru_cache(maxsize=1)
def _synonym_index() -> dict[str, dict]:
    """Load the synonym table once. Small enough to hold in memory and it makes
    resolution a dict lookup instead of a query per candidate token."""
    rows = fetch_all(
        """SELECT s.synonym, s.synonym_norm, s.kind, s.chembl_id, s.target_id,
                  c.pref_name AS compound_name, t.gene_symbol
           FROM synonyms s
           LEFT JOIN compounds c ON c.chembl_id = s.chembl_id
           LEFT JOIN targets   t ON t.chembl_id = s.target_id
           WHERE length(s.synonym_norm) >= 3"""
    )
    idx: dict[str, dict] = {}
    for r in rows:
        n = r["synonym_norm"]
        # targets win ties — a gene symbol is the more useful resolution
        if n not in idx or (r["kind"] == "target" and idx[n]["kind"] != "target"):
            idx[n] = r
    return idx


def reset_cache() -> None:
    _synonym_index.cache_clear()


def _ngrams(tokens: list[str], n: int) -> list[tuple[int, list[str]]]:
    return [(i, tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def resolve(query: str) -> list[dict]:
    """Return resolved entities, longest match first, no overlaps."""
    idx = _synonym_index()
    raw = [t for t in re.split(r"[^A-Za-z0-9\-]+", query) if t]
    if not raw:
        return []

    found: list[dict] = []
    consumed: set[int] = set()

    # try 3-grams, then 2-grams, then single tokens — longest wins
    for n in (3, 2, 1):
        for start, toks in _ngrams(raw, n):
            span = set(range(start, start + n))
            if span & consumed:
                continue
            phrase = " ".join(toks)
            key = norm(phrase)
            if len(key) < 3:
                continue
            if n == 1 and (toks[0].lower() in STOPWORDS or len(key) < 4):
                continue
            hit = idx.get(key)
            if not hit:
                continue
            consumed |= span
            found.append({
                "text": phrase,
                "type": hit["kind"],
                "id": hit["chembl_id"] or hit["target_id"],
                "name": hit["compound_name"] or hit["gene_symbol"] or phrase,
            })

    return found


def synonyms_for(chembl_id: str) -> list[str]:
    rows = fetch_all(
        "SELECT synonym FROM synonyms WHERE chembl_id = %s ORDER BY length(synonym) LIMIT 12",
        (chembl_id,),
    )
    return [r["synonym"] for r in rows]


def expansion_terms(entities: list[dict]) -> list[str]:
    """Extra lexical terms for the BM25 lane: every known alias of what the user
    named, so 'Tagrisso' also searches for 'osimertinib'."""
    terms: list[str] = []
    for e in entities:
        if e["type"] == "compound":
            terms.extend(synonyms_for(e["id"]))
        else:
            terms.append(e["name"])
    seen, out = set(), []
    for t in terms:
        k = norm(t)
        if k and k not in seen and len(t) > 2:
            seen.add(k)
            out.append(t)
    return out[:8]
