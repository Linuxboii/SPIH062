"""Ingest PubMed abstracts for the target set via NCBI E-utilities.

Rate limit: 3 req/s without an API key. We stay under it with a token-bucket
sleep and batch efetch in groups of 200.
"""
from __future__ import annotations

import re
import sys
import time
import xml.etree.ElementTree as ET

from common import TARGETS, client, connect, log

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PER_QUERY = int(sys.argv[1]) if len(sys.argv) > 1 else 900
BATCH = 200
MIN_INTERVAL = 0.36  # ~2.8 req/s

_last = 0.0


def throttle():
    global _last
    dt = time.time() - _last
    if dt < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - dt)
    _last = time.time()


def esearch(c, term: str, retmax: int) -> list[str]:
    throttle()
    r = c.get(
        f"{EUTILS}/esearch.fcgi",
        params={
            "db": "pubmed", "term": term, "retmax": retmax,
            "retmode": "json", "sort": "relevance",
        },
    )
    r.raise_for_status()
    return r.json().get("esearchresult", {}).get("idlist", [])


def _text(node) -> str:
    """Flatten an AbstractText/ArticleTitle node including inline markup."""
    if node is None:
        return ""
    return re.sub(r"\s+", " ", "".join(node.itertext())).strip()


def efetch(c, pmids: list[str]) -> list[dict]:
    throttle()
    r = c.post(
        f"{EUTILS}/efetch.fcgi",
        data={"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"},
    )
    r.raise_for_status()
    root = ET.fromstring(r.content)

    out = []
    for art in root.findall(".//PubmedArticle"):
        pmid_el = art.find(".//PMID")
        if pmid_el is None or not pmid_el.text:
            continue
        pmid = pmid_el.text.strip()

        title = _text(art.find(".//ArticleTitle"))

        # Structured abstracts have several AbstractText children with labels.
        parts = []
        for at in art.findall(".//Abstract/AbstractText"):
            label = at.get("Label")
            body = _text(at)
            if not body:
                continue
            parts.append(f"{label}: {body}" if label else body)
        abstract = " ".join(parts)
        if not abstract or len(abstract) < 120:
            continue  # no usable text to ground on

        journal = _text(art.find(".//Journal/ISOAbbreviation")) or _text(
            art.find(".//Journal/Title")
        )

        year = None
        for path in (".//JournalIssue/PubDate/Year", ".//JournalIssue/PubDate/MedlineDate"):
            el = art.find(path)
            if el is not None and el.text:
                m = re.search(r"(19|20)\d{2}", el.text)
                if m:
                    year = int(m.group(0))
                    break

        authors = []
        for a in art.findall(".//AuthorList/Author")[:12]:
            ln, fn = a.find("LastName"), a.find("ForeName")
            if ln is not None and ln.text:
                authors.append(f"{ln.text}{' ' + fn.text if fn is not None and fn.text else ''}")

        mesh = [
            _text(m.find("DescriptorName"))
            for m in art.findall(".//MeshHeadingList/MeshHeading")
        ]
        mesh = [m for m in mesh if m]

        doi = None
        for aid in art.findall(".//ArticleId"):
            if aid.get("IdType") == "doi" and aid.text:
                doi = aid.text.strip()
                break

        out.append({
            "pmid": pmid, "title": title, "abstract": abstract,
            "journal": journal, "year": year, "authors": authors,
            "mesh_terms": mesh[:25], "doi": doi,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        })
    return out


def main():
    pmids: set[str] = set()
    with client() as c:
        for t in TARGETS:
            for q in t["queries"]:
                per = max(1, PER_QUERY // len(t["queries"]))
                try:
                    ids = esearch(c, q, per)
                    pmids.update(ids)
                    log("pubmed", f"{t['gene']:7s} '{q[:44]}' -> {len(ids)} (total {len(pmids)})")
                except Exception as e:
                    log("pubmed", f"search failed '{q[:40]}': {e}")

        all_ids = sorted(pmids)
        log("pubmed", f"fetching {len(all_ids)} unique abstracts")

        rows = []
        for i in range(0, len(all_ids), BATCH):
            chunk = all_ids[i:i + BATCH]
            for attempt in range(3):
                try:
                    rows.extend(efetch(c, chunk))
                    break
                except Exception as e:
                    if attempt == 2:
                        log("pubmed", f"batch {i} failed permanently: {e}")
                    else:
                        time.sleep(2 * (attempt + 1))
            log("pubmed", f"fetched {min(i + BATCH, len(all_ids))}/{len(all_ids)} -> {len(rows)} usable")

    with connect() as conn, conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO papers (pmid,title,abstract,journal,year,authors,mesh_terms,doi,url)
               VALUES (%(pmid)s,%(title)s,%(abstract)s,%(journal)s,%(year)s,
                       %(authors)s,%(mesh_terms)s,%(doi)s,%(url)s)
               ON CONFLICT (pmid) DO NOTHING""",
            rows,
        )
        conn.commit()
        cur.execute("SELECT count(*) FROM papers")
        log("pubmed", f"DONE — papers in db: {cur.fetchone()[0]}")


if __name__ == "__main__":
    main()
