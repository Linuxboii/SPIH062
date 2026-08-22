"""Chunk abstracts and embed them with OpenAI text-embedding-3-small.

Chosen over a local model because the deployment host has ~1GB free RAM and
cannot hold PyTorch without risking OOM kills against co-resident production
services. Cost for the whole corpus is roughly $0.20.
"""
from __future__ import annotations

import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from openai import OpenAI

from common import OPENAI_KEY, connect, log

MODEL = "text-embedding-3-small"
DIM = 1536
CHUNK_CHARS = 900        # ~220 tokens
OVERLAP_SENTS = 1
BATCH = 96               # inputs per embedding request
WORKERS = 4              # keeps us under the 1M tokens/min org limit

client = OpenAI(api_key=OPENAI_KEY)

_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")


def chunk(title: str, abstract: str) -> list[str]:
    """Split on sentence boundaries, never mid-sentence. Title is prepended to
    every chunk so an isolated chunk still carries what it is about."""
    sents = [s.strip() for s in _SENT.split(abstract) if s.strip()]
    if not sents:
        return []

    chunks, cur = [], []
    size = 0
    for s in sents:
        if size + len(s) > CHUNK_CHARS and cur:
            chunks.append(" ".join(cur))
            cur = cur[-OVERLAP_SENTS:] if OVERLAP_SENTS else []
            size = sum(len(x) for x in cur)
        cur.append(s)
        size += len(s)
    if cur:
        chunks.append(" ".join(cur))

    return [f"{title}\n\n{c}" if title else c for c in chunks]


def embed_batch(texts: list[str]) -> list[list[float]] | None:
    """Returns None on permanent failure. Never fabricates vectors: a zero
    vector is not 'no answer', it is a point in the index that matches
    everything equally, which silently corrupts retrieval."""
    for attempt in range(8):
        try:
            r = client.embeddings.create(model=MODEL, input=texts)
            return [d.embedding for d in r.data]
        except Exception as e:
            msg = str(e)
            if "rate_limit" in msg or "429" in msg:
                delay = min(60, 4 * (attempt + 1))
            else:
                delay = min(30, 2 ** attempt)
            if attempt == 7:
                log("embed", f"batch failed permanently, chunks skipped: {type(e).__name__}")
                return None
            time.sleep(delay)
    return None


def main():
    if not OPENAI_KEY:
        log("embed", "FATAL: no OPENAI_API_KEY")
        sys.exit(1)

    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT p.pmid, p.title, p.abstract FROM papers p
                       WHERE NOT EXISTS (SELECT 1 FROM chunks c WHERE c.pmid = p.pmid)""")
        papers = cur.fetchall()

    log("embed", f"{len(papers)} papers to chunk")

    rows = []
    for pmid, title, abstract in papers:
        for i, text in enumerate(chunk(title or "", abstract or "")):
            rows.append({"pmid": pmid, "ord": i, "text": text})

    log("embed", f"{len(rows)} chunks — embedding in batches of {BATCH} across {WORKERS} workers")

    batches = [rows[i:i + BATCH] for i in range(0, len(rows), BATCH)]
    done = 0

    def run(b):
        return embed_batch([r["text"] for r in b])

    failed = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for b, vecs in zip(batches, ex.map(run, batches)):
            if vecs is None:
                failed += len(b)
                for r in b:
                    r["embedding"] = None
                continue
            for r, v in zip(b, vecs):
                r["embedding"] = "[" + ",".join(f"{x:.6f}" for x in v) + "]"
            done += len(b)
            if done % (BATCH * 10) < BATCH:
                log("embed", f"{done}/{len(rows)}")

    rows = [r for r in rows if r.get("embedding")]
    if failed:
        log("embed", f"WARNING: {failed} chunks dropped (no embedding); they are not indexed")

    log("embed", "writing chunks")
    with connect() as conn, conn.cursor() as cur:
        for i in range(0, len(rows), 500):
            cur.executemany(
                """INSERT INTO chunks (pmid, ord, text, embedding)
                   VALUES (%(pmid)s, %(ord)s, %(text)s, %(embedding)s)
                   ON CONFLICT (pmid, ord) DO NOTHING""",
                rows[i:i + 500])
            conn.commit()

        log("embed", "building HNSW index (cosine)")
        cur.execute("SET maintenance_work_mem = '512MB'")
        cur.execute("""CREATE INDEX IF NOT EXISTS chunks_embedding_idx
                       ON chunks USING hnsw (embedding vector_cosine_ops)
                       WITH (m = 16, ef_construction = 64)""")
        conn.commit()
        cur.execute("SELECT count(*) FROM chunks WHERE embedding IS NOT NULL")
        log("embed", f"DONE — embedded chunks: {cur.fetchone()[0]}")


if __name__ == "__main__":
    main()
