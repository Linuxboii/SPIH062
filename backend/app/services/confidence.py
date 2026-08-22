"""Retrieval confidence, computed BEFORE generation.

Below the abstain threshold no generation runs at all — we decline rather than
generate-then-filter. That is cheaper, and it removes the temptation to ship a
hedged guess dressed up as an answer.
"""
from __future__ import annotations

from ..config import settings


def score(sources: list[dict], structured: dict) -> dict:
    if not sources and not structured.get("compounds") and not structured.get("activities"):
        return {"score": 0.0, "band": "none", "signals": {
            "top_score": 0.0, "above_floor": 0, "source_agreement": 0.0}}

    # signal 1 — how good is the single best match (weight .4).
    # Uses ABSOLUTE cosine similarity, not the RRF score: RRF is normalised so the
    # top hit is always 1.0, which would make this signal constant and stop
    # retrieval-side abstention from ever firing.
    sims = [s.get("semantic_score") for s in sources if s.get("semantic_score") is not None]
    raw_top = max(sims) if sims else 0.0
    # text-embedding-3-small puts relevant biomedical matches around .45-.70 and
    # unrelated text around .10-.30; rescale that band onto 0..1.
    top = max(0.0, min(1.0, (raw_top - 0.25) / 0.35))

    # signal 2 — how many chunks clear the similarity floor (weight .3)
    above = sum(1 for v in sims if v >= settings.similarity_floor)
    breadth = min(above / 5.0, 1.0)

    # signal 3 — agreement across independent records (weight .3).
    # Distinct PMIDs, plus a bonus when structured facts corroborate the text.
    distinct = len({s["pmid"] for s in sources if s.get("pmid")})
    agreement = min(distinct / 4.0, 1.0)
    if structured.get("activities"):
        agreement = min(1.0, agreement + 0.25)

    total = 0.4 * top + 0.3 * breadth + 0.3 * agreement

    band = (
        "none" if total < settings.abstain_below
        else "low" if total < settings.low_confidence_below
        else "high"
    )
    return {
        "score": round(total, 4),
        "band": band,
        "signals": {
            "top_score": round(top, 4),
            "top_similarity": round(raw_top, 4),
            "above_floor": above,
            "source_agreement": round(agreement, 4),
        },
    }


def gaps(query: str, sources: list[dict], structured: dict, conf: dict) -> list[str]:
    out = []
    if not sources:
        out.append("No passages in the indexed literature matched this question.")
    elif conf["signals"]["above_floor"] == 0:
        out.append(
            "Passages were found but none cleared the similarity threshold, so none "
            "were treated as supporting evidence."
        )
    if not structured.get("compounds") and not structured.get("activities"):
        out.append(
            "No compound or target in the corpus was recognised in the question, so no "
            "structured records could be consulted."
        )
    if conf["signals"]["source_agreement"] < 0.5 and sources:
        out.append(
            "The few matching passages come from too small a set of independent sources "
            "to corroborate one another."
        )
    out.append(
        "The corpus covers 15 oncology targets. Questions outside that scope will not "
        "retrieve supporting evidence."
    )
    return out
