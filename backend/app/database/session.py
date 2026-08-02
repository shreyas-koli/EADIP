"""
SQLAlchemy 2.0 session management module.

Provides a configured ``SessionLocal`` factory and a FastAPI-compatible
dependency (``get_db``) that yields a session per request and guarantees
cleanup on exit.
"""

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session, sessionmaker

from app.database.connection import engine

# ── Session factory ──────────────────────────────────────────────
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# ── FastAPI dependency ───────────────────────────────────────────
def get_db() -> Generator[Session, None, None]:
    """
    Yield a database session for the lifetime of a single request.

    Usage in a route::

        @router.get("/items")
        def list_items(db: DBSession):
            return db.execute(select(Item)).scalars().all()

    The session is **always** closed after the response is sent,
    regardless of whether the request succeeded or raised an
    exception.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Convenience type alias for dependency injection ──────────────
DBSession = Annotated[Session, Depends(get_db)]
