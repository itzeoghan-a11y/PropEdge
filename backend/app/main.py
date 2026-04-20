"""
PropEdge Pro — FastAPI application entry point.
"""

from __future__ import annotations

import logging

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.config import get_settings
from app.database import create_tables
from app.services.modeling.ml_model import get_ml_model
from app.routers import analytics, auth, players, props

settings = get_settings()

# ── Structured logging ────────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

app = FastAPI(
    title="PropEdge Pro",
    description="Production-grade player prop analytics platform",
    version="1.0.0",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

# ── Middleware ─────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


log = structlog.get_logger(__name__)


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup() -> None:
    # In production the schema is owned by Alembic migrations; running
    # create_all against an already-migrated DB can stall or conflict.
    if settings.environment != "production":
        try:
            await create_tables()
        except Exception as exc:
            log.error("create_tables failed at startup", error=str(exc))

    # ML model load must never block the healthcheck — it's optional at runtime.
    try:
        get_ml_model()
    except Exception as exc:
        log.error("ml_model load failed at startup", error=str(exc))


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(props.router)
app.include_router(players.router)
app.include_router(analytics.router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
