"""
Digital Ecosystem Platform — FastAPI Backend
============================================
Run locally:
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

Swagger UI:    http://localhost:8000/docs
ReDoc:         http://localhost:8000/redoc
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.core.config import get_settings
from backend.core.database import create_all_tables, AsyncSessionLocal
from backend.core.events import get_event_bus
from backend.routers import alerts, agents, auth, cmms, data, energy, finance, users, workflow
from backend.services.agent_service import get_orchestrator
from backend.services.user_service import ensure_default_admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


# ── Application lifespan ───────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────────
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)

    # Create DB tables (no-op if already exist)
    await create_all_tables()
    logger.info("Database tables ready")

    # Bootstrap default admin
    async with AsyncSessionLocal() as db:
        await ensure_default_admin(db)
        await db.commit()

    # Initialise agent orchestrator (registers all agents and event bus wiring)
    get_orchestrator()
    logger.info("Agent orchestrator initialised")

    # Log event bus backend
    bus = get_event_bus()
    logger.info("Event bus ready (%s backend, %d topic handlers registered)",
                settings.EVENT_BUS_BACKEND, len(bus._handlers))

    yield

    # ── Shutdown ───────────────────────────────────────────────────────────────
    logger.info("Shutting down %s", settings.APP_NAME)


# ── App factory ────────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Industrial Digital Ecosystem Platform — REST API.\n\n"
            "Provides CMMS, AI Agent Orchestration, Energy Management, "
            "Financial Engine, Alert System, and Data Integration."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ───────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ────────────────────────────────────────────────────────────────
    api_prefix = "/api/v1"
    app.include_router(auth.router,     prefix=api_prefix)
    app.include_router(users.router,    prefix=api_prefix)
    app.include_router(data.router,     prefix=api_prefix)
    app.include_router(alerts.router,   prefix=api_prefix)
    app.include_router(cmms.router,     prefix=api_prefix)
    app.include_router(agents.router,   prefix=api_prefix)
    app.include_router(finance.router,  prefix=api_prefix)
    app.include_router(energy.router,   prefix=api_prefix)
    app.include_router(workflow.router, prefix=api_prefix)

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/health", tags=["Health"], include_in_schema=True)
    async def health():
        return {
            "status": "ok",
            "app":    settings.APP_NAME,
            "version": settings.APP_VERSION,
        }

    # ── Global exception handler ──────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    return app


app = create_app()
