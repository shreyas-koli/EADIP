"""
Metadata inspector service.

Uses SQLAlchemy's ``inspect()`` API to extract schema, table, and
column metadata from an external data warehouse.  All heavy lifting
is delegated to :class:`WarehouseConnector` for engine creation.
"""

from typing import Any

from sqlalchemy import inspect

from app.models.warehouse import Warehouse
from app.warehouse.connector import WarehouseConnector


class MetadataInspector:
    """
    Introspects the structure of a remote database.

    Usage::

        inspector = MetadataInspector()
        schemas   = inspector.get_schemas(warehouse)
        full_meta = inspector.inspect_database(warehouse)
    """

    def __init__(self) -> None:
        self._connector = WarehouseConnector()

    # ── Helpers ──────────────────────────────────────────────────

    def _get_inspector(self, warehouse: Warehouse):
        """
        Build a SQLAlchemy ``Inspector`` bound to the warehouse.

        The engine is created via ``WarehouseConnector.connect()``
        and immediately inspected.
        """
        engine = self._connector.connect(warehouse)
        return inspect(engine), engine

    # ── Schema introspection ─────────────────────────────────────

    def get_schemas(self, warehouse: Warehouse) -> list[str]:
        """
        Return all schema names available in the warehouse.

        Parameters
        ──────────
        warehouse : Warehouse
            A registered ``Warehouse`` ORM instance.

        Returns
        ───────
        list[str]
            Schema names (e.g. ``["public", "analytics", "staging"]``).
        """
        insp, engine = self._get_inspector(warehouse)
        try:
            return insp.get_schema_names()
        finally:
            engine.dispose()

    # ── Table introspection ──────────────────────────────────────

    def get_tables(self, warehouse: Warehouse, schema: str) -> list[str]:
        """
        Return all table names within a given schema.

        Parameters
        ──────────
        warehouse : Warehouse
            A registered ``Warehouse`` ORM instance.
        schema    : str
            The target schema name (e.g. ``"public"``).

        Returns
        ───────
        list[str]
            Table names (e.g. ``["employees", "departments"]``).
        """
        insp, engine = self._get_inspector(warehouse)
        try:
            return insp.get_table_names(schema=schema)
        finally:
            engine.dispose()

    # ── Column introspection ─────────────────────────────────────

    def get_columns(
        self,
        warehouse: Warehouse,
        schema: str,
        table: str,
    ) -> list[dict[str, Any]]:
        """
        Return column metadata for a specific table.

        Parameters
        ──────────
        warehouse : Warehouse
            A registered ``Warehouse`` ORM instance.
        schema    : str
            The schema containing the table.
        table     : str
            The target table name.

        Returns
        ───────
        list[dict[str, Any]]
            Each dict contains keys such as ``name``, ``type``,
            ``nullable``, ``default``, and ``primary_key`` as
            returned by SQLAlchemy's ``Inspector.get_columns()``.
        """
        insp, engine = self._get_inspector(warehouse)
        try:
            columns = insp.get_columns(table, schema=schema)
            return [
                {
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col.get("nullable", True),
                    "default": col.get("default"),
                }
                for col in columns
            ]
        finally:
            engine.dispose()

    # ── Full database inspection ─────────────────────────────────

    def inspect_database(self, warehouse: Warehouse) -> dict[str, Any]:
        """
        Return a complete metadata snapshot of the warehouse.

        Walks every schema → table → column and assembles a nested
        dictionary suitable for caching, diffing, or feeding into
        AI agents.

        Parameters
        ──────────
        warehouse : Warehouse
            A registered ``Warehouse`` ORM instance.

        Returns
        ───────
        dict
            Structure::

                {
                    "schemas": {
                        "public": {
                            "tables": {
                                "employees": {
                                    "columns": [
                                        {"name": "id", "type": "INTEGER", ...},
                                        ...
                                    ]
                                }
                            }
                        }
                    }
                }
        """
        insp, engine = self._get_inspector(warehouse)
        try:
            result: dict[str, Any] = {"schemas": {}}

            for schema_name in insp.get_schema_names():
                tables: dict[str, Any] = {}

                for table_name in insp.get_table_names(schema=schema_name):
                    columns = [
                        {
                            "name": col["name"],
                            "type": str(col["type"]),
                            "nullable": col.get("nullable", True),
                            "default": col.get("default"),
                        }
                        for col in insp.get_columns(table_name, schema=schema_name)
                    ]
                    tables[table_name] = {"columns": columns}

                result["schemas"][schema_name] = {"tables": tables}

            return result
        finally:
            engine.dispose()
