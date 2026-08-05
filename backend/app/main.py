"""
app/main.py

FastAPI application factory.
Use create_app() to build the app — this pattern makes the app
easy to test (each test can get a fresh instance).
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, health, research, users, settings as settings_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.utils.exceptions import register_exception_handlers

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""

    # ── Logging must be first ─────────────────────────────────────────────────
    setup_logging()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Production-grade API for the Apcotex R&D "
            "Patent Research & Polymer Recipe Simulation platform."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], # Allow all origins for local development (e.g., ports 5173, 5174)
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception Handlers ────────────────────────────────────────────────────
    register_exception_handlers(app)

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(research.router)
    app.include_router(settings_router.router, prefix="/api/v1/settings", tags=["Settings"])

    logger.info("Application startup complete — %s v%s", settings.APP_NAME, settings.APP_VERSION)
    return app


# Module-level app instance used by uvicorn
app: FastAPI = create_app()
