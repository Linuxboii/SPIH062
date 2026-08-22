from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..db import fetch_all, fetch_one
from ..services import entities, structured

router = APIRouter()


@router.get("/compound/{query}")
def compound(query: str):
    c = structured.resolve_compound(query)
    if not c:
        raise HTTPException(404, f"No compound matching '{query}' in the corpus")

    cid = c["chembl_id"]
    return {
        **c,
        "synonyms": entities.synonyms_for(cid),
        "activities": structured.activities_for_compound(cid),
        "predictions": structured.predictions_for_compound(cid),
        "trials": structured.trials_for_compound(cid),
        "papers": structured.papers_for_compound(cid),
    }


@router.get("/compound/{chembl_id}/targets")
def compound_targets(chembl_id: str):
    return {
        "measured": structured.activities_for_compound(chembl_id),
        "predicted": structured.predictions_for_compound(chembl_id),
    }


@router.get("/target/{gene}")
def target(gene: str):
    t = fetch_one(
        """SELECT chembl_id, pref_name, gene_symbol, organism, target_type FROM targets
           WHERE upper(gene_symbol) = upper(%s) OR chembl_id = upper(%s)""",
        (gene, gene),
    )
    if not t:
        raise HTTPException(404, f"No target '{gene}' in the corpus")
    return {**t, "activities": structured.activities_for_target(t["chembl_id"])}


@router.get("/source/{stype}/{sid}")
def source(stype: str, sid: str):
    if stype == "pubmed":
        p = fetch_one(
            "SELECT pmid, title, abstract, journal, year, authors, mesh_terms, doi, url "
            "FROM papers WHERE pmid = %s", (sid,))
        if not p:
            raise HTTPException(404, "Not found")
        return {"type": "pubmed", **p}
    if stype == "chembl":
        c = structured.compound_by_id(sid)
        if c:
            return {"type": "chembl", **c}
    raise HTTPException(404, "Not found")


@router.get("/search/suggest")
def suggest(q: str = ""):
    q = q.strip()
    if len(q) < 2:
        return {"results": []}
    rows = fetch_all(
        """SELECT DISTINCT ON (COALESCE(s.chembl_id, s.target_id))
                  s.synonym AS label,
                  COALESCE(s.chembl_id, s.target_id) AS id,
                  s.kind,
                  COALESCE(c.pref_name, t.gene_symbol) AS note,
                  c.max_phase
           FROM synonyms s
           LEFT JOIN compounds c ON c.chembl_id = s.chembl_id
           LEFT JOIN targets   t ON t.chembl_id = s.target_id
           WHERE s.synonym ILIKE %s
           ORDER BY COALESCE(s.chembl_id, s.target_id),
                    length(s.synonym)
           LIMIT 40""",
        (f"{q}%",),
    )
    rows.sort(key=lambda r: (r["kind"] != "target", -(r.get("max_phase") or 0), len(r["label"])))
    return {"results": rows[:10]}


@router.get("/stats")
def stats():
    s = structured.stats()
    genes = fetch_all("SELECT gene_symbol FROM targets ORDER BY gene_symbol")
    approved = fetch_one("SELECT count(*) AS n FROM compounds WHERE max_phase >= 4")
    preds = fetch_one("SELECT count(*) AS n FROM dti_predictions")
    model = fetch_one(
        """SELECT round(avg(roc_auc)::numeric, 3) AS mean_roc_auc,
                  round(min(roc_auc)::numeric, 3) AS min_roc_auc,
                  round(max(roc_auc)::numeric, 3) AS max_roc_auc,
                  count(*) AS targets_modelled, max(split) AS split
           FROM dti_metrics"""
    )
    return {
        **s,
        "approved_compounds": (approved or {}).get("n", 0),
        "predictions": (preds or {}).get("n", 0),
        "target_list": [g["gene_symbol"] for g in genes],
        "dti_model": {k: (float(v) if k.endswith("auc") and v is not None else v)
                      for k, v in (model or {}).items()},
    }
