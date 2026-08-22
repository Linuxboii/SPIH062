from __future__ import annotations

import time

from fastapi import APIRouter

from ..config import settings
from ..schemas import ChatRequest, ChatResponse
from ..services import confidence, entities, generator, retrieval, structured

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    t0 = time.time()
    q = req.query.strip()

    # 1 — resolve entities before retrieving anything
    ents = entities.resolve(q)
    terms = entities.expansion_terms(ents)

    # 2 — two lanes. The dense lane sees a canonicalised query: brand names and
    # research codes replaced by the generic name the literature uses.
    canonical = q
    for e in ents:
        if e.get("name") and e["name"].lower() != e["text"].lower():
            canonical = canonical.replace(e["text"], e["name"])
    sources = retrieval.search(q, terms, embed_text=canonical)
    facts = structured.structured_for_entities(ents)

    route = (
        "hybrid" if sources and (facts["compounds"] or facts["activities"])
        else "literature" if sources
        else "structured" if (facts["compounds"] or facts["activities"])
        else "none"
    )

    # 3 — confidence BEFORE generation
    conf = confidence.score(sources, facts)

    if conf["score"] < settings.abstain_below:
        return ChatResponse(
            query=q,
            resolved_entities=ents,
            route=route,
            confidence=conf,
            abstained=True,
            claims=[],
            structured=facts,
            sources=sources,
            gaps=confidence.gaps(q, sources, facts, conf),
            validation={"generation_skipped": True,
                        "reason": "retrieval confidence below abstain threshold"},
            elapsed_ms=int((time.time() - t0) * 1000),
        )

    # 4 — generate under the strict claim contract
    raw = generator.generate(q, sources, facts, ents)

    # 5 — validate every citation against what was actually retrieved
    claims, audit = generator.validate(raw, sources, facts, ents)

    abstained = bool(raw.get("abstained")) or not claims
    gaps = raw.get("gaps") or []
    if abstained and not gaps:
        gaps = confidence.gaps(q, sources, facts, conf)

    return ChatResponse(
        query=q,
        resolved_entities=ents,
        route=route,
        confidence=conf,
        abstained=abstained,
        claims=claims,
        structured=facts,
        sources=sources,
        gaps=gaps,
        validation=audit,
        elapsed_ms=int((time.time() - t0) * 1000),
    )
