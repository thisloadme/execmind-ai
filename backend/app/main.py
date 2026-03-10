"""ExecMind - FastAPI application entry point.

Initializes the FastAPI app with all routers, CORS middleware,
lifespan events, and health check endpoints.
"""

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.kb import router as kb_router
from app.api.v1.users import router as users_router
from app.api.v1.audit import router as audit_router
from app.core.config import settings
from app.utils.logging import get_logger, setup_logging

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # Startup
    setup_logging()
    logger.info(
        "app_starting",
        app_name=settings.APP_NAME,
        environment=settings.APP_ENV,
    )
    yield
    # Shutdown
    logger.info("app_shutting_down")


app = FastAPI(
    title=settings.APP_NAME,
    description="Private AI Knowledge Assistant for Institutional Executives",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

# ─── CORS Middleware ──────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Register API Routers ────────────────────────

API_V1_PREFIX = "/api/v1"

app.include_router(auth_router, prefix=API_V1_PREFIX)
app.include_router(chat_router, prefix=API_V1_PREFIX)
app.include_router(kb_router, prefix=API_V1_PREFIX)
app.include_router(users_router, prefix=API_V1_PREFIX)
app.include_router(audit_router, prefix=API_V1_PREFIX)


# ─── Health Check Endpoints ──────────────────────

@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check — returns 200 if service is running."""
    return {"status": "healthy", "service": settings.APP_NAME}


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """Readiness probe — checks connectivity to PostgreSQL, Qdrant, and Ollama."""
    checks = {
        "database": False,
        "qdrant": False,
        "ollama": False,
    }

    # Check PostgreSQL
    try:
        from app.core.database import engine
        from sqlalchemy import text

        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as e:
        logger.warning("readiness_db_failed", error=str(e))

    # Check Qdrant
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.QDRANT_URL}/collections")
            checks["qdrant"] = response.status_code == 200
    except Exception as e:
        logger.warning("readiness_qdrant_failed", error=str(e))

    # Check Ollama
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.OLLAMA_URL}/api/tags")
            checks["ollama"] = response.status_code == 200
    except Exception as e:
        logger.warning("readiness_ollama_failed", error=str(e))

    all_ready = all(checks.values())
    return {
        "status": "ready" if all_ready else "degraded",
        "checks": checks,
    }


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.APP_NAME,
        "version": "2.0.0",
        "description": "Private AI Knowledge Assistant",
        "docs": "/docs" if settings.is_development else None,
        "api": f"{API_V1_PREFIX}/",
    }
