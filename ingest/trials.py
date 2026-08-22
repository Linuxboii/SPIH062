"""Ingest ClinicalTrials.gov studies and link them to compounds by synonym match."""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor

from common import TARGETS, client, connect, log
from chembl import norm

API = "https://clinicaltrials.gov/api/v2/studies"
PER_TERM = 120


def fetch(c, term: str) -> list[dict]:
    out, token = [], None
    while len(out) < PER_TERM:
        params = {
            "query.term": term,
            "filter.overallStatus": "RECRUITING|ACTIVE_NOT_RECRUITING|COMPLETED|ENROLLING_BY_INVITATION",
            "pageSize": min(100, PER_TERM - len(out)),
        }
        if token:
            params["pageToken"] = token
        try:
            r = c.get(API, params=params)
            r.raise_for_status()
            d = r.json()
        except Exception:
            break
        out.extend(d.get("studies", []))
        token = d.get("nextPageToken")
        if not token:
            break
        time.sleep(0.2)
    return out


def parse(s: dict) -> dict | None:
    p = s.get("protocolSection", {})
    ident = p.get("identificationModule", {})
    nct = ident.get("nctId")
    if not nct:
        return None
    design = p.get("designModule", {})
    status = p.get("statusModule", {})
    arms = p.get("armsInterventionsModule", {})
    cond = p.get("conditionsModule", {})

    phases = design.get("phases") or []
    enroll = (design.get("enrollmentInfo") or {}).get("count")

    return {
        "nct_id": nct,
        "title": ident.get("briefTitle") or ident.get("officialTitle"),
        "phase": ", ".join(ph.replace("PHASE", "Phase ") for ph in phases) or None,
        "status": status.get("overallStatus"),
        "conditions": (cond.get("conditions") or [])[:8],
        "interventions": [
            i.get("name") for i in (arms.get("interventions") or []) if i.get("name")
        ][:10],
        "enrollment": int(enroll) if isinstance(enroll, int) else None,
        "start_date": (status.get("startDateStruct") or {}).get("date"),
        "url": f"https://clinicaltrials.gov/study/{nct}",
    }


def main():
    terms = []
    for t in TARGETS:
        terms.append(f"{t['gene']} cancer")
    terms += ["EGFR inhibitor lung cancer", "PARP inhibitor ovarian cancer",
              "CDK4/6 inhibitor breast cancer", "KRAS G12C solid tumor"]

    with client(timeout=90) as c:
        with ThreadPoolExecutor(max_workers=5) as ex:
            batches = list(ex.map(lambda t: (t, fetch(c, t)), terms))

    seen, rows = set(), []
    for term, studies in batches:
        log("trials", f"{term[:38]:40s} {len(studies)}")
        for s in studies:
            row = parse(s)
            if row and row["nct_id"] not in seen:
                seen.add(row["nct_id"])
                rows.append(row)

    log("trials", f"{len(rows)} unique studies")

    with connect() as conn, conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO trials (nct_id,title,phase,status,conditions,interventions,
                                   enrollment,start_date,url)
               VALUES (%(nct_id)s,%(title)s,%(phase)s,%(status)s,%(conditions)s,
                       %(interventions)s,%(enrollment)s,%(start_date)s,%(url)s)
               ON CONFLICT (nct_id) DO NOTHING""", rows)
        conn.commit()

        # link trials to compounds via normalised synonym match on intervention names
        cur.execute("SELECT synonym_norm, chembl_id FROM synonyms WHERE kind='compound'")
        syn_map: dict[str, str] = {}
        for n, cid in cur.fetchall():
            if len(n) >= 5:            # short tokens produce false positives
                syn_map.setdefault(n, cid)

        links = set()
        for r in rows:
            for iv in r["interventions"]:
                n = norm(iv)
                if not n:
                    continue
                if n in syn_map:
                    links.add((r["nct_id"], syn_map[n]))
                    continue
                # interventions are often "Osimertinib 80mg tablet"
                for token in re.split(r"[^A-Za-z0-9]+", iv):
                    tn = norm(token)
                    if len(tn) >= 6 and tn in syn_map:
                        links.add((r["nct_id"], syn_map[tn]))
                        break

        cur.executemany(
            """INSERT INTO trial_compounds (nct_id, chembl_id) VALUES (%s,%s)
               ON CONFLICT DO NOTHING""", sorted(links))
        conn.commit()
        cur.execute("SELECT count(*) FROM trials")
        n_t = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM trial_compounds")
        log("trials", f"DONE — trials: {n_t}, compound links: {cur.fetchone()[0]}")


if __name__ == "__main__":
    main()
