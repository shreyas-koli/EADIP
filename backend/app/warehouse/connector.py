"""
Warehouse connector service.

Builds SQLAlchemy engines on-the-fly for registered external
data warehouses and provides lightweight connectivity checks.

Currently supports **PostgreSQL** only; additional dialects can
be added by extending the driver mapping in ``_DRIVER_MAP``.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL

from app.models.warehouse import Warehouse

# ── Supported database drivers ───────────────────────────────────
# Maps the user-facing ``db_type`` value (lowercased) to the
# SQLAlchemy dialect+driver string.
_DRIVER_MAP: dict[str, str] = {
    "postgresql": "postgresql+psycopg2",
}


class WarehouseConnector:
    """
    Factory for on-demand SQLAlchemy engines targeting external
    data warehouses.

    Usage::

        connector = WarehouseConnector()
        engine    = connector.connect(warehouse)
        ok        = connector.test_connection(warehouse)
    """

    # ── Connect ──────────────────────────────────────────────────

    @staticmethod
    def connect(warehouse: Warehouse) -> Engine:
        """
        Build and return a SQLAlchemy ``Engine`` for the given warehouse.

        Parameters
        ──────────
        warehouse : Warehouse
            A ``Warehouse`` ORM instance containing connection details.

        Returns
        ───────
        Engine
            A new SQLAlchemy engine bound to the warehouse.

        Raises
        ──────
        ValueError
            If the warehouse's ``db_type`` is not yet supported.
        """
        driver = _DRIVER_MAP.get(warehouse.db_type.lower())

        if driver is None:
            raise ValueError(
                f"Unsupported database type: '{warehouse.db_type}'. "
                f"Supported types: {', '.join(_DRIVER_MAP.keys())}."
            )

        url = URL.create(
            drivername=driver,
            username=warehouse.username,
            password=warehouse.encrypted_password,
            host=warehouse.host,
            port=warehouse.port,
            database=warehouse.database_name,
        )

        return create_engine(
            url,
            pool_pre_ping=True,
            future=True,
        )

    # ── Test connection ──────────────────────────────────────────

    @staticmethod
    def test_connection(warehouse: Warehouse) -> bool:
        """
        Attempt a lightweight connectivity check against the warehouse.

        Executes ``SELECT 1`` to verify that the connection parameters
        are valid and the database is reachable.

        Parameters
        ──────────
        warehouse : Warehouse
            A ``Warehouse`` ORM instance containing connection details.

        Returns
        ───────
        bool
            ``True`` if the connection succeeds, ``False`` otherwise.
        """
        try:
            engine = WarehouseConnector.connect(warehouse)
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            engine.dispose()
            return True
        except Exception:
            return False
