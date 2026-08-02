"""
SQLAlchemy 2.0 database connection module.

Creates and exposes a production-ready ``Engine`` instance configured
from the application settings.  All downstream modules (session factory,
Alembic, etc.) should import ``engine`` from here.
"""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.core.config import settings


def build_engine() -> Engine:
    """
    Construct a SQLAlchemy ``Engine`` bound to the configured DATABASE_URL.

    Key behaviours
    ──────────────
    * **pool_pre_ping** – issues a lightweight ``SELECT 1`` before handing
      out a connection so stale / dropped connections are recycled
      automatically.
    * **echo** – mirrors emitted SQL to stdout when ``DEBUG`` is enabled
      (controlled via ``.env``).
    * **future** – opts into the SQLAlchemy 2.0 execution style so all
      queries go through the modern ``Connection.execute()`` API.
    """
    return create_engine(
        url=settings.DATABASE_URL,
        pool_pre_ping=True,
        echo=settings.DEBUG,
        future=True,
    )


# ── Module-level singleton ───────────────────────────────────────
engine: Engine = build_engine()
