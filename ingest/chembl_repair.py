"""Repair pass: load activities + synonyms.

The first chembl.py run inserted compounds, then aborted on the synonyms
statement (`WHERE %(param)s IS NULL` gives Postgres no type to infer), which
rolled the activities back with it. Compounds survived because they committed
first.

This re-fetches only what is missing, and uses the bulk
`molecule_chembl_id__in` endpoint rather than 12k single-molecule requests.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from chembl import CHEMBL, fetch_activities, get_json, norm
from common import TARGETS, client, connect, log

BULK = 50   # ids per bulk molecule request


def bulk_synonyms(c, ids: list[str]) -> list[dict]:
    d = get_json(c, f"{CHEMBL}/molecule", {
        "molecule_chembl_id__in": ",".join(ids),
        "limit": len(ids), "format": "json",
    })
    out = []
    for m in (d or {}).get("molecules", []):
        mid = m.get("molecule_chembl_id")
        if not mid:
            continue
        names = [m.get("pref_name")] + [
            s.get("molecule_synonym") for s in (m.get("molecule_synonyms") or [])
        ]
        seen = set()
        for syn in names:
            if not syn:
                continue
            n = norm(syn)
            if not n or n in seen or len(n) < 3:
                continue
            seen.add(n)
            out.append({"chembl_id": mid, "synonym": syn,
                        "synonym_norm": n, "source": "chembl"})
    return out


def main():
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT chembl_id FROM compounds")
        ids = [r[0] for r in cur.fetchall()]
    log("repair", f"{len(ids)} compounds already stored")

    with client(timeout=90) as c:
        # ---- activities ----
        log("repair", "re-fetching activities")
        with ThreadPoolExecutor(max_workers=5) as ex:
            results = list(ex.map(lambda t: (t, fetch_activities(c, t["chembl"])), TARGETS))

        activities = []
        for t, acts in results:
            log("repair", f"{t['gene']:7s} {len(acts)}")
            for a in acts:
                mid = a.get("molecule_chembl_id")
                if not mid:
                    continue
                try:
                    val = float(a["standard_value"]) if a.get("standard_value") else None
                    pch = float(a["pchembl_value"]) if a.get("pchembl_value") else None
                except (TypeError, ValueError):
                    continue
                activities.append({
                    "compound_id": mid, "target_id": t["chembl"],
                    "standard_type": a.get("standard_type"),
                    "standard_value": val, "standard_units": a.get("standard_units"),
                    "pchembl_value": pch, "assay_chembl_id": a.get("assay_chembl_id"),
                    "source_doc_id": a.get("document_chembl_id"),
                })

        # ---- synonyms in bulk ----
        batches = [ids[i:i + BULK] for i in range(0, len(ids), BULK)]
        log("repair", f"bulk-fetching synonyms in {len(batches)} requests")
        syns: list[dict] = []
        with ThreadPoolExecutor(max_workers=8) as ex:
            for i, part in enumerate(ex.map(lambda b: bulk_synonyms(c, b), batches)):
                syns.extend(part)
                if i % 40 == 0:
                    log("repair", f"  {i}/{len(batches)} batches, {len(syns)} synonyms")

    log("repair", f"writing {len(activities)} activities, {len(syns)} compound synonyms")

    with connect() as conn, conn.cursor() as cur:
        for i in range(0, len(activities), 2000):
            cur.executemany(
                """INSERT INTO activities (compound_id,target_id,standard_type,standard_value,
                       standard_units,pchembl_value,assay_chembl_id,source_doc_id)
                   SELECT %(compound_id)s,%(target_id)s,%(standard_type)s,%(standard_value)s,
                          %(standard_units)s,%(pchembl_value)s,%(assay_chembl_id)s,%(source_doc_id)s
                   WHERE EXISTS (SELECT 1 FROM compounds WHERE chembl_id=%(compound_id)s)""",
                activities[i:i + 2000])
            conn.commit()

        for i in range(0, len(syns), 2000):
            cur.executemany(
                """INSERT INTO synonyms (chembl_id,target_id,synonym,synonym_norm,source,kind)
                   VALUES (%(chembl_id)s, NULL, %(synonym)s, %(synonym_norm)s, %(source)s, 'compound')""",
                syns[i:i + 2000])
            conn.commit()

        # target synonyms — gene symbol and full name both resolve
        tsyn = []
        for t in TARGETS:
            for s in {t["gene"], t["name"]}:
                tsyn.append({"target_id": t["chembl"], "synonym": s, "synonym_norm": norm(s)})
        cur.executemany(
            """INSERT INTO synonyms (chembl_id,target_id,synonym,synonym_norm,source,kind)
               VALUES (NULL, %(target_id)s, %(synonym)s, %(synonym_norm)s, 'chembl', 'target')""",
            tsyn)
        conn.commit()

        for tbl in ("compounds", "activities", "synonyms"):
            cur.execute(f"SELECT count(*) FROM {tbl}")
            log("repair", f"{tbl}: {cur.fetchone()[0]}")


if __name__ == "__main__":
    main()
