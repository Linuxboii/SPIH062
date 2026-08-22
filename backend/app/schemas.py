from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)


class SourceRef(BaseModel):
    id: str
    type: str
    title: str | None = None


class Claim(BaseModel):
    text: str
    sources: list[SourceRef] = []
    unsourced: bool = False
    confidence: str = "low"


class Source(BaseModel):
    id: str
    type: str
    title: str | None = None
    journal: str | None = None
    year: int | None = None
    url: str | None = None
    snippet: str | None = None
    retrieval_score: float | None = None
    lexical_rank: int | None = None
    semantic_score: float | None = None


class ResolvedEntity(BaseModel):
    text: str
    type: str
    id: str
    name: str | None = None


class Confidence(BaseModel):
    score: float
    band: str
    signals: dict = {}


class ChatResponse(BaseModel):
    query: str
    resolved_entities: list[ResolvedEntity] = []
    route: str
    confidence: Confidence
    abstained: bool
    claims: list[Claim] = []
    structured: dict = {}
    sources: list[Source] = []
    gaps: list[str] = []
    validation: dict = {}
    elapsed_ms: int | None = None
