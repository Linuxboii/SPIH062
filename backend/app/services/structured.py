"""Lane B — structured retrieval.

Compound properties, bioactivities and trials are relational and read by SQL.
They are never embedded and never paraphrased: they go to the frontend as typed
JSON so the UI can table them independently of anything the model says.
"""
from __future__ import annotations

from ..db import fetch_all, fetch_one


def compound_by_id(chembl_id: str) -> dict | None:
    return fetch_one(
        """SELECT chembl_id, pref_name, smiles, inchikey, mol_formula, mol_weight,
                  xlogp, hbd, hba, tpsa, ro5_violations, max_phase, first_approval,
                  pubchem_cid
           FROM compounds WHERE chembl_id = %s""",
        (chembl_id,),
    )


def resolve_compound(query: str) -> dict | None:
    """Accept a ChEMBL id, an exact synonym, or a fuzzy name."""
    if query.upper().startswith("CHEMBL"):
        c = compound_by_id(query.upper())
        if c:
            return c

    from .entities import norm

    row = fetch_one(
        """SELECT c.chembl_id, c.pref_name, c.smiles, c.inchikey, c.mol_formula,
                  c.mol_weight, c.xlogp, c.hbd, c.hba, c.tpsa, c.ro5_violations,
                  c.max_phase, c.first_approval, c.pubchem_cid
           FROM synonyms s JOIN compounds c ON c.chembl_id = s.chembl_id
           WHERE s.synonym_norm = %s
           ORDER BY c.max_phase DESC NULLS LAST LIMIT 1""",
        (norm(query),),
    )
    if row:
        return row

    return fetch_one(
        """SELECT chembl_id, pref_name, smiles, inchikey, mol_formula, mol_weight,
                  xlogp, hbd, hba, tpsa, ro5_violations, max_phase, first_approval,
                  pubchem_cid FROM compounds
           WHERE pref_name ILIKE %s
           ORDER BY max_phase DESC NULLS LAST, length(pref_name) LIMIT 1""",
        (f"%{query}%",),
    )


def activities_for_compound(chembl_id: str, limit: int = 40) -> list[dict]:
    return fetch_all(
        """SELECT a.standard_type, a.standard_value, a.standard_units, a.pchembl_value,
                  a.assay_chembl_id, t.gene_symbol, t.pref_name AS target_name,
                  t.chembl_id AS target_id
           FROM activities a JOIN targets t ON t.chembl_id = a.target_id
           WHERE a.compound_id = %s
           ORDER BY a.pchembl_value DESC NULLS LAST
           LIMIT %s""",
        (chembl_id, limit),
    )


def activities_for_target(target_id: str, limit: int = 40) -> list[dict]:
    return fetch_all(
        """SELECT a.standard_type, a.standard_value, a.standard_units, a.pchembl_value,
                  c.chembl_id AS compound_id, c.pref_name AS compound_name,
                  c.max_phase, t.gene_symbol, t.chembl_id AS target_id,
                  t.pref_name AS target_name
           FROM activities a
           JOIN compounds c ON c.chembl_id = a.compound_id
           JOIN targets   t ON t.chembl_id = a.target_id
           WHERE a.target_id = %s AND a.pchembl_value IS NOT NULL
           ORDER BY a.pchembl_value DESC NULLS LAST
           LIMIT %s""",
        (target_id, limit),
    )


def trials_for_compound(chembl_id: str, limit: int = 12) -> list[dict]:
    return fetch_all(
        """SELECT t.nct_id, t.title, t.phase, t.status, t.conditions, t.enrollment, t.url
           FROM trial_compounds tc JOIN trials t ON t.nct_id = tc.nct_id
           WHERE tc.chembl_id = %s
           ORDER BY t.phase DESC NULLS LAST LIMIT %s""",
        (chembl_id, limit),
    )


def predictions_for_compound(chembl_id: str, limit: int = 8) -> list[dict]:
    return fetch_all(
        """SELECT d.probability, d.is_known, d.model_version,
                  t.gene_symbol, t.chembl_id AS target_id, t.pref_name AS target_name,
                  m.roc_auc, m.pr_auc, m.split
           FROM dti_predictions d
           JOIN targets t ON t.chembl_id = d.target_id
           LEFT JOIN dti_metrics m
                  ON m.target_id = d.target_id AND m.model_version = d.model_version
           WHERE d.compound_id = %s
           ORDER BY d.probability DESC LIMIT %s""",
        (chembl_id, limit),
    )


def papers_for_compound(chembl_id: str, limit: int = 6) -> list[dict]:
    """Recent abstracts mentioning any alias of the compound."""
    syns = fetch_all(
        "SELECT synonym FROM synonyms WHERE chembl_id = %s AND length(synonym) > 4 LIMIT 6",
        (chembl_id,),
    )
    names = [s["synonym"] for s in syns]
    if not names:
        return []
    pattern = "|".join(n.replace("%", "") for n in names)
    return fetch_all(
        """SELECT pmid, title, journal, year, url
           FROM papers
           WHERE title ~* %s OR abstract ~* %s
           ORDER BY year DESC NULLS LAST LIMIT %s""",
        (pattern, pattern, limit),
    )


def structured_for_entities(entities: list[dict]) -> dict:
    """Facts relevant to whatever the query resolved to."""
    compounds, activities = [], []
    for e in entities[:3]:
        if e["type"] == "compound":
            c = compound_by_id(e["id"])
            if c:
                compounds.append(c)
                activities.extend(activities_for_compound(e["id"], 12))
        elif e["type"] == "target":
            activities.extend(activities_for_target(e["id"], 15))
    return {"compounds": compounds, "activities": activities}


def stats() -> dict:
    row = fetch_one(
        """SELECT (SELECT count(*) FROM papers)     AS papers,
                  (SELECT count(*) FROM chunks)     AS chunks,
                  (SELECT count(*) FROM compounds)  AS compounds,
                  (SELECT count(*) FROM activities) AS activities,
                  (SELECT count(*) FROM trials)     AS trials,
                  (SELECT count(*) FROM targets)    AS targets"""
    )
    return row or {}
