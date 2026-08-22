from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..db import fetch_all, fetch_one
from ..services import entities, structured

router = APIRouter()


# Sort keys are whitelisted rather than interpolated — ORDER BY cannot be
# parameterised, so anything reaching the query string must be a fixed literal.
_SORTS = {
    "evidence": "activity_count DESC, c.pref_name ASC",
    "potency":  "best_pchembl DESC NULLS LAST, activity_count DESC",
    "weight":   "c.mol_weight ASC NULLS LAST",
    "name":     "c.pref_name ASC",
}
_PHASES = {
    "approved":    "c.max_phase >= 4",
    "trials":      "c.max_phase > 0 AND c.max_phase < 4",
    "preclinical": "COALESCE(c.max_phase, 0) = 0",
}


@router.get("/compounds")
def compounds(
    q: str = "",
    target: str = "",
    phase: str = "approved",
    sort: str = "evidence",
    limit: int = Query(24, ge=1, le=60),
    offset: int = Query(0, ge=0),
):
    """Browsable index over the compound corpus.

    The detail route resolves one molecule; this is the list behind it. The
    counts a caller needs to build a filter UI (how many are approved, how
    many are in trials) are returned alongside the page, so the client does
    not have to issue four more requests to label its own controls.
    """
    where, params = ["TRUE"], []

    if q.strip():
        like = f"%{q.strip()}%"
        where.append(
            """(c.pref_name ILIKE %s
                OR c.chembl_id ILIKE %s
                OR EXISTS (SELECT 1 FROM synonyms s
                           WHERE s.chembl_id = c.chembl_id AND s.synonym ILIKE %s))"""
        )
        params += [like, f"{q.strip()}%", like]

    if phase in _PHASES:
        where.append(_PHASES[phase])


    if target.strip():
        where.append(
            """EXISTS (SELECT 1 FROM activities x
                       JOIN targets t ON t.chembl_id = x.target_id
                       WHERE x.compound_id = c.chembl_id
                         AND upper(t.gene_symbol) = upper(%s))"""
        )
        params.append(target.strip())

    clause = " AND ".join(where)
    # resolve before use AND before echoing — the response should report what
    # the query actually did, never reflect an unrecognised value back
    sort = sort if sort in _SORTS else "evidence"
    phase = phase if phase in _PHASES else "all"
    order = _SORTS[sort]

    rows = fetch_all(
        f"""SELECT c.chembl_id, c.pref_name, c.smiles, c.mol_formula,
                   c.mol_weight, c.ro5_violations, c.max_phase, c.first_approval,
                   COALESCE(a.n, 0) AS activity_count,
                   a.best_pchembl
            FROM compounds c
            LEFT JOIN (SELECT compound_id,
                              count(*) AS n,
                              max(pchembl_value) AS best_pchembl
                       FROM activities GROUP BY compound_id) a
                   ON a.compound_id = c.chembl_id
            WHERE {clause}
            ORDER BY {order}
            LIMIT %s OFFSET %s""",
        (*params, limit, offset),
    )

    total = fetch_one(
        f"""SELECT count(*) AS n FROM compounds c WHERE {clause}""", tuple(params)
    )

    # facet counts for the phase control, honouring the search and target
    # filters but not the phase filter itself — otherwise every tab reads 0
    facet_where = [w for w in where if w not in _PHASES.values()]
    # the phase predicates carry no bind params, so dropping them from the
    # WHERE list leaves the remaining params correctly ordered
    facet_params = list(params)
    facets = fetch_one(
        f"""SELECT count(*) FILTER (WHERE c.max_phase >= 4)                       AS approved,
                   count(*) FILTER (WHERE c.max_phase > 0 AND c.max_phase < 4)    AS trials,
                   count(*) FILTER (WHERE COALESCE(c.max_phase, 0) = 0)           AS preclinical,
                   count(*)                                                       AS all
            FROM compounds c WHERE {' AND '.join(facet_where)}""",
        tuple(facet_params),
    )

    return {
        "items": rows,
        "total": (total or {}).get("n", 0),
        "limit": limit,
        "offset": offset,
        "facets": facets or {},
        "sort": sort,
        "phase": phase,
        "target": target.strip().upper(),
    }


@router.get("/targets")
def targets():
    """The 15 modelled targets, with how many compounds have measured
    activity against each — enough to build the target filter."""
    return {
        "items": fetch_all(
            """SELECT t.gene_symbol, t.chembl_id, t.pref_name,
                      count(DISTINCT a.compound_id) AS compound_count
               FROM targets t
               LEFT JOIN activities a ON a.target_id = t.chembl_id
               GROUP BY t.gene_symbol, t.chembl_id, t.pref_name
               ORDER BY t.gene_symbol"""
        )
    }


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
