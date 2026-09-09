"""
CareerMail AI — FastAPI Application Entry Point.

Starts the API server with:
  • CORS (configurable)
  • Health endpoint
  • All Milestone 1 routers mounted
  • Database tables auto-created at startup
  • Exception handlers for clean error responses
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import create_tables
from app.api.auth import router as auth_router
from app.api.accounts import router as accounts_router
from app.api.emails import router as emails_router
from app.api.extraction import router as extraction_router
from app.api.opportunities import router as opportunities_router
from app.api.deadlines import router as deadlines_router
from app.api.digest import router as digest_router
from app.api.devices import router as devices_router
from app.api.notifications import router as notifications_router
from app.api.scheduler import router as scheduler_router
from app.api.email_composer import router as email_composer_router
from app.schemas.common import HealthResponse
from app.utils.logging import get_logger, log_event

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Startup / shutdown lifecycle."""
    settings = get_settings()

    # Create database tables.
    create_tables()
    log_event(logger, "DATABASE_READY")

    # Log configuration status (never log actual secrets).
    log_event(
        logger,
        "APP_STARTED",
        environment=settings.ENVIRONMENT,
        google_oauth=str(settings.google_oauth_configured),
        encryption=str(settings.encryption_configured),
        gemini=str(settings.gemini_configured),
        firebase=str(settings.firebase_configured),
    )

    if not settings.google_oauth_configured:
        logger.warning(
            "GOOGLE_OAUTH_NOT_CONFIGURED | "
            "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env to enable Gmail."
        )
    if not settings.encryption_configured:
        logger.warning(
            "ENCRYPTION_NOT_CONFIGURED | "
            "Set ENCRYPTION_KEY in .env to enable secure token storage."
        )

    # Start background scheduler only if active (safe condition: disabled in tests)
    scheduler = None
    if settings.scheduler_active:
        from app.services.scheduler import get_scheduler
        scheduler = get_scheduler()
        scheduler.start()

    yield

    if scheduler is not None:
        scheduler.shutdown(wait=False)

    log_event(logger, "APP_SHUTDOWN")


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title="CareerMail AI",
        description=(
            "Intelligent email analysis for hackathons, internships, "
            "placements, and college opportunities."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────
    allowed_origins = (
        ["http://localhost:3000", "http://localhost:8080"]
        if not settings.is_production
        else []  # Configure explicitly for production.
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handlers ────────────────────────────

    @app.exception_handler(RuntimeError)
    async def runtime_error_handler(request: Request, exc: RuntimeError):
        """Handle configuration errors gracefully."""
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc)},
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        """Catch-all: never expose stack traces in production."""
        if settings.is_production:
            return JSONResponse(
                status_code=500,
                content={"detail": "An internal error occurred."},
            )
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc)},
        )

    # ── Health ────────────────────────────────────────

    @app.get("/health", response_model=HealthResponse, tags=["Health"])
    def health_check():
        """Application health and configuration status."""
        return HealthResponse(
            status="ok",
            environment=settings.ENVIRONMENT,
            google_oauth_configured=settings.google_oauth_configured,
            encryption_configured=settings.encryption_configured,
            gemini_configured=settings.gemini_configured,
            firebase_configured=settings.firebase_configured,
            scheduler_active=settings.scheduler_active,
        )

    # ── Routers ───────────────────────────────────────
    app.include_router(auth_router)
    app.include_router(accounts_router)
    app.include_router(emails_router)
    app.include_router(extraction_router)
    app.include_router(opportunities_router)
    app.include_router(deadlines_router)
    app.include_router(digest_router)
    app.include_router(devices_router)
    app.include_router(notifications_router)
    app.include_router(scheduler_router)
    app.include_router(email_composer_router)

    return app




# Module-level app instance used by uvicorn.
app = create_app()
