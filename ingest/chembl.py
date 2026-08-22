"""Ingest ChEMBL targets, compounds, bioactivities; enrich from PubChem.

Structured facts land in relational tables and are never embedded — a molecular
weight is a number, and a number that passes through a language model can come
out wrong.
"""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor

from common import TARGETS, client, connect, log

CHEMBL = "https://www.ebi.ac.uk/chembl/api/data"
PUBCHEM = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

MAX_ACT_PER_TARGET = 1200
PAGE = 1000


def norm(s: str) -> str:
    """Normalise a synonym for lookup: lowercase, strip punctuation/space."""
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def get_json(c, url, params=None, tries=4):
    for a in range(tries):
        try:
            r = c.get(url, params=params)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
        except Exception:
            if a == tries - 1:
                return None
            time.sleep(1.5 * (a + 1))
    return None


def fetch_activities(c, target_chembl: str) -> list[dict]:
    """Potency measurements for one target, best-quality types only."""
    out, offset = [], 0
    while len(out) < MAX_ACT_PER_TARGET:
        d = get_json(c, f"{CHEMBL}/activity", {
            "target_chembl_id": target_chembl,
            "standard_type__in": "IC50,Ki,Kd,EC50",
            "pchembl_value__isnull": "false",
            "limit": PAGE, "offset": offset, "format": "json",
        })
        if not d:
            break
        acts = d.get("activities", [])
        if not acts:
            break
        out.extend(acts)
        if len(acts) < PAGE:
            break
        offset += PAGE
    return out[:MAX_ACT_PER_TARGET]


def fetch_molecule(c, chembl_id: str):
    return get_json(c, f"{CHEMBL}/molecule/{chembl_id}", {"format": "json"})


def pubchem_props(c, name: str):
    d = get_json(c, f"{PUBCHEM}/compound/name/{name}/property/"
                    "MolecularFormula,MolecularWeight,XLogP,TPSA,"
                    "HBondDonorCount,HBondAcceptorCount,InChIKey,ConnectivitySMILES/JSON")
    if not d:
        return None
    props = d.get("PropertyTable", {}).get("Properties", [])
    return props[0] if props else None


def main():
    with client(timeout=90) as c:
        # ---- targets ----
        target_rows = []
        for t in TARGETS:
            d = get_json(c, f"{CHEMBL}/target/{t['chembl']}", {"format": "json"})
            target_rows.append({
                "chembl_id": t["chembl"],
                "pref_name": (d or {}).get("pref_name") or t["name"],
                "gene_symbol": t["gene"],
                "organism": (d or {}).get("organism") or "Homo sapiens",
                "target_type": (d or {}).get("target_type") or "SINGLE PROTEIN",
            })
            log("chembl", f"target {t['gene']}")

        with connect() as conn, conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO targets (chembl_id,pref_name,gene_symbol,organism,target_type)
                   VALUES (%(chembl_id)s,%(pref_name)s,%(gene_symbol)s,%(organism)s,%(target_type)s)
                   ON CONFLICT (chembl_id) DO NOTHING""", target_rows)
            conn.commit()

        # ---- activities (parallel across targets) ----
        log("chembl", "fetching bioactivities…")
        with ThreadPoolExecutor(max_workers=5) as ex:
            results = list(ex.map(lambda t: (t, fetch_activities(c, t["chembl"])), TARGETS))

        activities, mol_ids = [], set()
        for t, acts in results:
            log("chembl", f"{t['gene']:7s} {len(acts)} activities")
            for a in acts:
                mid = a.get("molecule_chembl_id")
                if not mid:
                    continue
                mol_ids.add(mid)
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

        log("chembl", f"{len(mol_ids)} unique compounds referenced")

        # ---- molecules (parallel) ----
        mol_list = sorted(mol_ids)
        with ThreadPoolExecutor(max_workers=8) as ex:
            mols = list(ex.map(lambda m: fetch_molecule(c, m), mol_list))

        compounds, synonyms = [], []
        for mid, m in zip(mol_list, mols):
            if not m:
                continue
            props = m.get("molecule_properties") or {}
            struct = m.get("molecule_structures") or {}
            name = m.get("pref_name")

            def num(k):
                v = props.get(k)
                try:
                    return float(v) if v is not None else None
                except (TypeError, ValueError):
                    return None

            def integer(k):
                v = props.get(k)
                try:
                    return int(v) if v is not None else None
                except (TypeError, ValueError):
                    return None

            compounds.append({
                "chembl_id": mid,
                "pref_name": name or mid,
                "smiles": struct.get("canonical_smiles"),
                "inchikey": struct.get("standard_inchi_key"),
                "mol_formula": props.get("full_molformula"),
                "mol_weight": num("full_mwt"),
                "xlogp": num("alogp"),
                "hbd": integer("hbd"),
                "hba": integer("hba"),
                "tpsa": num("psa"),
                "ro5_violations": integer("num_ro5_violations"),
                "max_phase": num("max_phase"),
                "first_approval": integer("first_approval") if m.get("first_approval") is None
                                  else (int(m["first_approval"]) if str(m["first_approval"]).isdigit() else None),
                "pubchem_cid": None,
            })

            seen = set()
            for syn in ([name] if name else []) + [
                s.get("molecule_synonym") for s in (m.get("molecule_synonyms") or [])
            ]:
                if not syn:
                    continue
                n = norm(syn)
                if not n or n in seen:
                    continue
                seen.add(n)
                synonyms.append({
                    "chembl_id": mid, "target_id": None, "synonym": syn,
                    "synonym_norm": n, "source": "chembl", "kind": "compound",
                })

        # target synonyms feed the entity resolver too
        for t in TARGETS:
            for syn in {t["gene"], t["name"]}:
                synonyms.append({
                    "chembl_id": None, "target_id": t["chembl"], "synonym": syn,
                    "synonym_norm": norm(syn), "source": "chembl", "kind": "target",
                })

        log("chembl", f"writing {len(compounds)} compounds, {len(activities)} activities, {len(synonyms)} synonyms")

        with connect() as conn, conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO compounds (chembl_id,pref_name,smiles,inchikey,mol_formula,mol_weight,
                       xlogp,hbd,hba,tpsa,ro5_violations,max_phase,first_approval,pubchem_cid)
                   VALUES (%(chembl_id)s,%(pref_name)s,%(smiles)s,%(inchikey)s,%(mol_formula)s,
                           %(mol_weight)s,%(xlogp)s,%(hbd)s,%(hba)s,%(tpsa)s,%(ro5_violations)s,
                           %(max_phase)s,%(first_approval)s,%(pubchem_cid)s)
                   ON CONFLICT (chembl_id) DO NOTHING""", compounds)
            conn.commit()
            # activities reference compounds, so insert after
            cur.executemany(
                """INSERT INTO activities (compound_id,target_id,standard_type,standard_value,
                       standard_units,pchembl_value,assay_chembl_id,source_doc_id)
                   SELECT %(compound_id)s,%(target_id)s,%(standard_type)s,%(standard_value)s,
                          %(standard_units)s,%(pchembl_value)s,%(assay_chembl_id)s,%(source_doc_id)s
                   WHERE EXISTS (SELECT 1 FROM compounds WHERE chembl_id=%(compound_id)s)""",
                activities)
            cur.executemany(
                """INSERT INTO synonyms (chembl_id,target_id,synonym,synonym_norm,source,kind)
                   SELECT %(chembl_id)s,%(target_id)s,%(synonym)s,%(synonym_norm)s,%(source)s,%(kind)s
                   WHERE %(chembl_id)s IS NULL
                      OR EXISTS (SELECT 1 FROM compounds WHERE chembl_id=%(chembl_id)s)""",
                synonyms)
            conn.commit()

            # ---- PubChem enrichment for the notable compounds ----
            cur.execute("""SELECT chembl_id, pref_name FROM compounds
                           WHERE max_phase >= 3 AND pref_name IS NOT NULL
                           ORDER BY max_phase DESC NULLS LAST LIMIT 400""")
            notable = cur.fetchall()

        log("chembl", f"enriching {len(notable)} approved/late-phase compounds from PubChem")
        with ThreadPoolExecutor(max_workers=6) as ex:
            enriched = list(ex.map(lambda r: (r[0], pubchem_props(c, r[1])), notable))

        updates = []
        for cid, p in enriched:
            if not p:
                continue
            updates.append({
                "chembl_id": cid,
                "pubchem_cid": str(p.get("CID")) if p.get("CID") else None,
                "xlogp": p.get("XLogP"),
                "tpsa": p.get("TPSA"),
                "hbd": p.get("HBondDonorCount"),
                "hba": p.get("HBondAcceptorCount"),
            })

        with connect() as conn, conn.cursor() as cur:
            cur.executemany(
                """UPDATE compounds SET
                     pubchem_cid = COALESCE(%(pubchem_cid)s, pubchem_cid),
                     xlogp       = COALESCE(%(xlogp)s, xlogp),
                     tpsa        = COALESCE(%(tpsa)s, tpsa),
                     hbd         = COALESCE(%(hbd)s, hbd),
                     hba         = COALESCE(%(hba)s, hba)
                   WHERE chembl_id = %(chembl_id)s""", updates)
            conn.commit()
            for tbl in ("targets", "compounds", "activities", "synonyms"):
                cur.execute(f"SELECT count(*) FROM {tbl}")
                log("chembl", f"{tbl}: {cur.fetchone()[0]}")


if __name__ == "__main__":
    main()
