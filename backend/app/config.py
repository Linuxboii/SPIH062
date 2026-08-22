"""Configuration. Everything overridable by environment; safe defaults for local dev."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---- database ----
    database_url: str = "postgresql://oncolens:oncolens@localhost:5434/oncolens"

    # ---- OpenAI ----
    openai_api_key: str = ""
    openai_model: str = "gpt-5-nano"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    openai_max_tokens: int = 6000
    openai_reasoning_effort: str = "low"

    # ---- retrieval ----
    retrieval_top_k: int = 8
    candidate_k: int = 30          # per-lane candidates before RRF fusion
    rrf_k: int = 60
    chunk_tokens: int = 220
    chunk_overlap: int = 40

    # ---- confidence thresholds (§4.5 of the PRD) ----
    abstain_below: float = 0.35
    low_confidence_below: float = 0.60
    similarity_floor: float = 0.42   # absolute cosine, not RRF

    # ---- app ----
    cors_origins: str = "*"
    dti_model_path: str = "models/dti_model.pkl"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
