"""
EADIP — Application entry point.

Bootstraps the FastAPI application, registers routers, and defines
top-level health / info endpoints.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.warehouse import router as warehouse_router
from app.core.config import settings


# ── Lifespan (startup / shutdown hooks) ──────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Execute logic on application startup and shutdown."""
    # ── Startup ──────────────────────────────────────────────────
    print("🚀  EADIP Backend Started Successfully")
    yield
    # ── Shutdown (add cleanup logic here if needed) ──────────────


# ── Application factory ─────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)


# ── Routers ──────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(warehouse_router)


# ── Root endpoints ───────────────────────────────────────────────


@app.get("/", tags=["General"])
def root():
    """Welcome endpoint — confirms the API is reachable."""
    return {
        "message": "Welcome to EADIP 🚀",
    }


@app.get("/health", tags=["General"])
def health():
    """Lightweight health check for load-balancers and probes."""
    return {
        "status": "healthy",
    }