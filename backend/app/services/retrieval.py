"""Lane A — literature retrieval.

Hybrid, because pure dense retrieval smears rare lexical tokens: `G12C` and
`T790M` are exact strings that BM25 catches and embeddings blur. Dense catches
paraphrase. Reciprocal Rank Fusion combines the two ranked lists without needing
their scores to be on a comparable scale.
"""
from __future__ import annotations

from openai import OpenAI

from ..config import settings
from ..db import fetch_all

_client: OpenAI | None = None


def _openai() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def embed_query(q: str) -> list[float] | None:
    try:
        r = _openai().embeddings.create(model=settings.embedding_model, input=[q])
        return r.data[0].embedding
    except Exception:
        return None


def lexical(query: str, terms: list[str], k: int) -> list[dict]:
    """BM25 over chunk tsvectors. websearch_to_tsquery tolerates arbitrary user
    text; alias terms are OR-ed in so brand names reach generic-name passages."""
    q = query
    if terms:
        q = f"{query} {' '.join(terms)}"
    rows = fetch_all(
        """SELECT c.id, c.pmid, c.text,
                  ts_rank_cd(c.tsv, websearch_to_tsquery('english', %s)) AS score
           FROM chunks c
           WHERE c.tsv @@ websearch_to_tsquery('english', %s)
           ORDER BY score DESC
           LIMIT %s""",
        (q, q, k),
    )
    return rows


def dense(vec: list[float], k: int) -> list[dict]:
    lit = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
    return fetch_all(
        """SELECT c.id, c.pmid, c.text,
                  1 - (c.embedding <=> %s::vector) AS score
           FROM chunks c
           WHERE c.embedding IS NOT NULL
           ORDER BY c.embedding <=> %s::vector
           LIMIT %s""",
        (lit, lit, k),
    )


def rrf(lists: list[list[dict]], k: int = 60) -> dict[int, float]:
    """Reciprocal Rank Fusion: score = sum over lists of 1/(k + rank)."""
    scores: dict[int, float] = {}
    for lst in lists:
        for rank, row in enumerate(lst, start=1):
            scores[row["id"]] = scores.get(row["id"], 0.0) + 1.0 / (k + rank)
    return scores


def search(query: str, terms: list[str] | None = None, top_k: int | None = None,
           embed_text: str | None = None) -> list[dict]:
    """`embed_text` is the canonicalised query — brand names replaced by the
    generic names the literature actually uses. Embedding the raw string instead
    means a query for 'Tagrisso' is matched against a corpus that only ever says
    'osimertinib', which retrieves confidently wrong neighbours."""
    top_k = top_k or settings.retrieval_top_k
    cand = settings.candidate_k
    terms = terms or []

    lex = lexical(query, terms, cand)
    vec = embed_query(embed_text or query)
    den = dense(vec, cand) if vec else []

    fused = rrf([lex, den], settings.rrf_k)
    if not fused:
        return []

    by_id = {r["id"]: r for r in lex + den}
    best = max(fused.values()) or 1.0

    # per-lane raw scores, for transparency in the UI
    lex_rank = {r["id"]: i + 1 for i, r in enumerate(lex)}
    den_score = {r["id"]: r["score"] for r in den}

    ordered = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[: top_k * 2]
    ids = [i for i, _ in ordered]
    if not ids:
        return []

    meta = {
        r["id"]: r
        for r in fetch_all(
            """SELECT c.id, c.pmid, c.text, p.title, p.journal, p.year, p.url
               FROM chunks c JOIN papers p ON p.pmid = c.pmid
               WHERE c.id = ANY(%s)""",
            (ids,),
        )
    }

    # one chunk per paper — several chunks of the same abstract is not
    # independent evidence, and it crowds the evidence panel
    out, seen_pmid = [], set()
    for cid, score in ordered:
        m = meta.get(cid)
        if not m or m["pmid"] in seen_pmid:
            continue
        seen_pmid.add(m["pmid"])
        out.append({
            "chunk_id": cid,
            "id": f"PMID:{m['pmid']}",
            "pmid": m["pmid"],
            "type": "pubmed",
            "title": m["title"],
            "journal": m["journal"],
            "year": m["year"],
            "url": m["url"],
            "snippet": m["text"],
            "retrieval_score": round(score / best, 4),
            "lexical_rank": lex_rank.get(cid),
            "semantic_score": round(den_score[cid], 4) if cid in den_score else None,
        })
        if len(out) >= top_k:
            break

    return out
