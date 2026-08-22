from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import fetch_one, pool
from .routers import chat, data


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open()
    yield
    pool.close()


app = FastAPI(
    title="OncoLens API",
    description=(
        "Grounded biomedical retrieval for oncology drug discovery. "
        "Research use only — not medical advice."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(data.router, prefix="/api", tags=["data"])


@app.get("/api/health")
def health():
    db_ok, counts = True, {}
    try:
        counts = fetch_one(
            """SELECT (SELECT count(*) FROM papers) AS papers,
                      (SELECT count(*) FROM chunks WHERE embedding IS NOT NULL) AS embedded,
                      (SELECT count(*) FROM compounds) AS compounds"""
        ) or {}
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "embedding_key": bool(settings.openai_api_key),
        "model": settings.openai_model,
        **counts,
        "disclaimer": "Research tool. Not medical advice.",
    }
