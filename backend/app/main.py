"""
AetherArchive — Application entry point.

Bootstraps the FastAPI application, registers routers, and defines
top-level health / info endpoints.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.warehouse import router as warehouse_router
from app.api.discovery import router as discovery_router
from app.api.automation import router as automation_router
from app.api.recommendation_history import router as recommendation_history_router
from app.core.config import settings


# ── Lifespan (startup / shutdown hooks) ──────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Execute logic on application startup and shutdown."""
    # ── Startup ──────────────────────────────────────────────────
    import logging
    from app.database.init_db import init_db

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger(__name__)

    # Initialize the database schema for deployment compatibility
    try:
        init_db()
        logger.info("📦  Database initialized successfully")
    except Exception as e:
        logger.error(f"❌  Failed to initialize database: {e}")
        
    logger.info("🚀  AetherArchive Backend Started Successfully")
    yield
    # ── Shutdown (add cleanup logic here if needed) ──────────────


# ── Application factory ─────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# ── Middleware ───────────────────────────────────────────────────

# Configure CORS for frontend communication
if settings.BACKEND_CORS_ORIGINS:
    origins = [str(origin).rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# ── Exception Handlers ───────────────────────────────────────────

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

@app.exception_handler(OperationalError)
async def db_operational_error_handler(request: Request, exc: OperationalError):
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Database connection failure. Please check your local PostgreSQL service status and password in backend/.env."
        },
    )

# ── Routers ──────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(warehouse_router)
app.include_router(discovery_router)
app.include_router(automation_router)
app.include_router(recommendation_history_router)


# ── Root endpoints ───────────────────────────────────────────────


@app.get("/", tags=["General"])
def root():
    """Welcome endpoint — confirms the API is reachable."""
    return {
        "message": "Welcome to AetherArchive 🚀",
    }


@app.get("/health", tags=["General"])
def health():
    """Lightweight health check for load-balancers and probes."""
    return {
        "status": "healthy",
    }