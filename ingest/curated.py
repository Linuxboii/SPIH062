"""Curated oncology drug layer.

The activity-derived compound set is dominated by unnamed screening compounds:
of 12k compounds only ~300 carry a real name, and clinically important drugs
fall outside the per-target activity cap. That is fine for training data but
useless for a demo — a user asking about Tagrisso must find osimertinib.

This resolves a curated list of oncology drugs BY NAME through ChEMBL search
(no hardcoded IDs to get wrong), then pulls full molecule records, every
synonym, and their measured activities against the 15 targets.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from chembl import CHEMBL, get_json, norm, pubchem_props
from common import TARGETS, client, connect, log

DRUGS = [
    # EGFR
    "osimertinib", "erlotinib", "gefitinib", "afatinib", "dacomitinib", "lazertinib",
    "mobocertinib", "amivantamab",
    # ALK / ROS1
    "crizotinib", "alectinib", "ceritinib", "brigatinib", "lorlatinib", "entrectinib",
    "repotrectinib",
    # BRAF / MEK
    "vemurafenib", "dabrafenib", "encorafenib", "trametinib", "cobimetinib",
    "binimetinib", "selumetinib",
    # KRAS
    "sotorasib", "adagrasib",
    # HER2
    "lapatinib", "neratinib", "tucatinib", "trastuzumab", "pertuzumab",
    # VEGFR
    "sunitinib", "sorafenib", "pazopanib", "axitinib", "lenvatinib", "regorafenib",
    "cabozantinib", "nintedanib", "vandetanib",
    # CDK4/6
    "palbociclib", "ribociclib", "abemaciclib",
    # PARP
    "olaparib", "niraparib", "rucaparib", "talazoparib", "veliparib",
    # BCR-ABL
    "imatinib", "dasatinib", "nilotinib", "bosutinib", "ponatinib", "asciminib",
    # BTK
    "ibrutinib", "acalabrutinib", "zanubrutinib", "pirtobrutinib",
    # mTOR / PI3K
    "everolimus", "temsirolimus", "sirolimus", "alpelisib", "idelalisib",
    "copanlisib", "duvelisib",
    # PD-L1 / PD-1
    "atezolizumab", "durvalumab", "avelumab", "pembrolizumab", "nivolumab",
]


def search_drug(c, name: str) -> dict | None:
    d = get_json(c, f"{CHEMBL}/molecule/search", {"q": name, "format": "json", "limit": 5})
    mols = (d or {}).get("molecules", [])
    if not mols:
        return None
    n = norm(name)
    # prefer an exact synonym/pref_name match over ChEMBL's relevance order
    for m in mols:
        if norm(m.get("pref_name") or "") == n:
            return m
        for s in m.get("molecule_synonyms") or []:
            if norm(s.get("molecule_synonym") or "") == n:
                return m
    return mols[0]


def main():
    with client(timeout=90) as c:
        log("curated", f"resolving {len(DRUGS)} drugs by name")
        with ThreadPoolExecutor(max_workers=6) as ex:
            found = list(ex.map(lambda n: (n, search_drug(c, n)), DRUGS))

        compounds, synonyms = [], []
        id_by_name = {}
        for name, m in found:
            if not m:
                log("curated", f"  MISS {name}")
                continue
            mid = m.get("molecule_chembl_id")
            if not mid:
                continue
            id_by_name[name] = mid
            props = m.get("molecule_properties") or {}
            struct = m.get("molecule_structures") or {}

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

            fa = m.get("first_approval")
            compounds.append({
                "chembl_id": mid,
                "pref_name": (m.get("pref_name") or name).title(),
                "smiles": struct.get("canonical_smiles"),
                "inchikey": struct.get("standard_inchi_key"),
                "mol_formula": props.get("full_molformula"),
                "mol_weight": num("full_mwt"),
                "xlogp": num("alogp"),
                "hbd": integer("hbd"),
                "hba": integer("hba"),
                "tpsa": num("psa"),
                "ro5_violations": integer("num_ro5_violations"),
                "max_phase": (float(m["max_phase"]) if m.get("max_phase") not in (None, "") else None),
                "first_approval": int(fa) if fa and str(fa).isdigit() else None,
                "pubchem_cid": None,
            })

            seen = set()
            for syn in [m.get("pref_name"), name] + [
                s.get("molecule_synonym") for s in (m.get("molecule_synonyms") or [])
            ]:
                if not syn:
                    continue
                k = norm(syn)
                if not k or k in seen or len(k) < 3:
                    continue
                seen.add(k)
                synonyms.append({"chembl_id": mid, "synonym": syn,
                                 "synonym_norm": k, "source": "chembl-curated"})

        log("curated", f"resolved {len(compounds)} drugs, {len(synonyms)} synonyms")

        # ---- upsert compounds (these OVERRIDE, they are the good records) ----
        with connect() as conn, conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO compounds (chembl_id,pref_name,smiles,inchikey,mol_formula,
                       mol_weight,xlogp,hbd,hba,tpsa,ro5_violations,max_phase,first_approval,pubchem_cid)
                   VALUES (%(chembl_id)s,%(pref_name)s,%(smiles)s,%(inchikey)s,%(mol_formula)s,
                           %(mol_weight)s,%(xlogp)s,%(hbd)s,%(hba)s,%(tpsa)s,%(ro5_violations)s,
                           %(max_phase)s,%(first_approval)s,%(pubchem_cid)s)
                   ON CONFLICT (chembl_id) DO UPDATE SET
                     pref_name=EXCLUDED.pref_name, smiles=COALESCE(EXCLUDED.smiles,compounds.smiles),
                     inchikey=COALESCE(EXCLUDED.inchikey,compounds.inchikey),
                     mol_formula=COALESCE(EXCLUDED.mol_formula,compounds.mol_formula),
                     mol_weight=COALESCE(EXCLUDED.mol_weight,compounds.mol_weight),
                     xlogp=COALESCE(EXCLUDED.xlogp,compounds.xlogp),
                     hbd=COALESCE(EXCLUDED.hbd,compounds.hbd),
                     hba=COALESCE(EXCLUDED.hba,compounds.hba),
                     tpsa=COALESCE(EXCLUDED.tpsa,compounds.tpsa),
                     ro5_violations=COALESCE(EXCLUDED.ro5_violations,compounds.ro5_violations),
                     max_phase=COALESCE(EXCLUDED.max_phase,compounds.max_phase),
                     first_approval=COALESCE(EXCLUDED.first_approval,compounds.first_approval)""",
                compounds)
            cur.executemany(
                """INSERT INTO synonyms (chembl_id,target_id,synonym,synonym_norm,source,kind)
                   VALUES (%(chembl_id)s, NULL, %(synonym)s, %(synonym_norm)s, %(source)s, 'compound')""",
                synonyms)
            conn.commit()

        # ---- activities for these drugs against our 15 targets ----
        ids = list(id_by_name.values())
        tids = [t["chembl"] for t in TARGETS]
        log("curated", "fetching activities for curated drugs")

        acts = []
        for i in range(0, len(ids), 20):
            batch = ids[i:i + 20]
            d = get_json(c, f"{CHEMBL}/activity", {
                "molecule_chembl_id__in": ",".join(batch),
                "target_chembl_id__in": ",".join(tids),
                "standard_type__in": "IC50,Ki,Kd,EC50",
                "pchembl_value__isnull": "false",
                "limit": 1000, "format": "json",
            })
            for a in (d or {}).get("activities", []):
                try:
                    val = float(a["standard_value"]) if a.get("standard_value") else None
                    pch = float(a["pchembl_value"]) if a.get("pchembl_value") else None
                except (TypeError, ValueError):
                    continue
                acts.append({
                    "compound_id": a.get("molecule_chembl_id"),
                    "target_id": a.get("target_chembl_id"),
                    "standard_type": a.get("standard_type"),
                    "standard_value": val, "standard_units": a.get("standard_units"),
                    "pchembl_value": pch, "assay_chembl_id": a.get("assay_chembl_id"),
                    "source_doc_id": a.get("document_chembl_id"),
                })

        log("curated", f"{len(acts)} curated-drug activities")

        # ---- PubChem enrichment ----
        with ThreadPoolExecutor(max_workers=6) as ex:
            enriched = list(ex.map(
                lambda cp: (cp["chembl_id"], pubchem_props(c, cp["pref_name"])), compounds))

    with connect() as conn, conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO activities (compound_id,target_id,standard_type,standard_value,
                   standard_units,pchembl_value,assay_chembl_id,source_doc_id)
               SELECT %(compound_id)s,%(target_id)s,%(standard_type)s,%(standard_value)s,
                      %(standard_units)s,%(pchembl_value)s,%(assay_chembl_id)s,%(source_doc_id)s
               WHERE EXISTS (SELECT 1 FROM compounds WHERE chembl_id=%(compound_id)s)
                 AND EXISTS (SELECT 1 FROM targets   WHERE chembl_id=%(target_id)s)""", acts)

        ups = [{"chembl_id": cid, "pubchem_cid": str(p.get("CID")) if p.get("CID") else None,
                "xlogp": p.get("XLogP"), "tpsa": p.get("TPSA"),
                "hbd": p.get("HBondDonorCount"), "hba": p.get("HBondAcceptorCount"),
                "smiles": p.get("ConnectivitySMILES")}
               for cid, p in enriched if p]
        cur.executemany(
            """UPDATE compounds SET
                 pubchem_cid=COALESCE(%(pubchem_cid)s,pubchem_cid),
                 xlogp=COALESCE(xlogp,%(xlogp)s), tpsa=COALESCE(tpsa,%(tpsa)s),
                 hbd=COALESCE(hbd,%(hbd)s), hba=COALESCE(hba,%(hba)s),
                 smiles=COALESCE(smiles,%(smiles)s)
               WHERE chembl_id=%(chembl_id)s""", ups)
        conn.commit()

        cur.execute("SELECT count(*) FROM compounds WHERE max_phase >= 4")
        log("curated", f"approved compounds now: {cur.fetchone()[0]}")
        cur.execute("SELECT count(*) FROM synonyms")
        log("curated", f"synonyms now: {cur.fetchone()[0]}")
        cur.execute("SELECT count(*) FROM activities")
        log("curated", f"activities now: {cur.fetchone()[0]}")


if __name__ == "__main__":
    main()
