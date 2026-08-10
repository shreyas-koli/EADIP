"""
Database initialisation module.

Creates all tables registered against the declarative ``Base`` metadata.
Run directly with ``python -m app.database.init_db`` or call
``init_db()`` from application startup hooks.
"""

from app.database.base import Base
from app.database.connection import engine
import logging

logger = logging.getLogger(__name__)

# ── Import every ORM model so Base.metadata is fully populated ───
from app.models.user import User  # noqa: F401
# Future models should be imported here:
# from app.models.document import Document  # noqa: F401
# from app.models.agent import Agent        # noqa: F401

from app.models.warehouse import Warehouse  # noqa: F401
from app.models.execution import DiscoverySession, AgentExecution  # noqa: F401


def init_db() -> None:
    """
    Create all database tables that do not yet exist.

    This is a synchronous, idempotent operation — safe to call
    repeatedly without duplicating tables.
    """
    Base.metadata.create_all(bind=engine)
    logger.info("✅  Database tables created successfully.")


# ── Allow direct execution ───────────────────────────────────────
if __name__ == "__main__":
    init_db()
