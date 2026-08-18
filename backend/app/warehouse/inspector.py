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


_SYSTEM_SCHEMAS: frozenset[str] = frozenset({"information_schema", "pg_catalog", "pg_toast"})

def _is_system_schema(schema_name: str) -> bool:
    """Check if a schema is a known PostgreSQL system schema."""
    return schema_name in _SYSTEM_SCHEMAS or schema_name.startswith("pg_temp")


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

    def get_schemas(self, warehouse: Warehouse, include_system_schemas: bool = False) -> list[str]:
        """
        Return all schema names available in the warehouse.

        Parameters
        ──────────
        warehouse : Warehouse
            A registered ``Warehouse`` ORM instance.
        include_system_schemas : bool
            If True, includes internal system schemas. Defaults to False.

        Returns
        ───────
        list[str]
            Schema names (e.g. ``["public", "analytics", "staging"]``).
        """
        insp, engine = self._get_inspector(warehouse)
        try:
            schemas = insp.get_schema_names()
            if not include_system_schemas:
                schemas = [s for s in schemas if not _is_system_schema(s)]
            return schemas
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
            Each dict contains keys ``name``, ``type``, ``nullable``,
            ``default``, and ``primary_key``.  ``primary_key`` is
            derived from ``Inspector.get_pk_constraint()`` — not from
            the per-column dict — to ensure dialect-independent
            accuracy.
        """
        insp, engine = self._get_inspector(warehouse)
        try:
            pk_constraint = insp.get_pk_constraint(table, schema=schema)
            pk_columns: set[str] = set(
                pk_constraint.get("constrained_columns", [])
            )
            return [
                {
                    "name":        col["name"],
                    "type":        str(col["type"]),
                    "nullable":    col.get("nullable", True),
                    "default":     col.get("default"),
                    "primary_key": col["name"] in pk_columns,
                }
                for col in insp.get_columns(table, schema=schema)
            ]
        finally:
            engine.dispose()

    # ── Full database inspection ─────────────────────────────────

    def inspect_database(
        self, 
        warehouse: Warehouse, 
        include_system_schemas: bool = False,
        progress_callback: Any = None
    ) -> dict[str, Any]:
        """
        Return a complete metadata snapshot of the warehouse.

        Walks every schema → table → column and assembles a nested
        dictionary suitable for caching, diffing, or feeding into
        AI agents.

        Parameters
        ──────────
        warehouse : Warehouse
            A registered ``Warehouse`` ORM instance.
        include_system_schemas : bool
            If True, includes internal system schemas. Defaults to False.

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
                                        {
                                            "name":        "id",
                                            "type":        "INTEGER",
                                            "nullable":    False,
                                            "default":     None,
                                            "primary_key": True,
                                        },
                                        ...
                                    ]
                                }
                            }
                        }
                    }
                }

            ``primary_key`` is derived from
            ``Inspector.get_pk_constraint()`` per table, ensuring
            dialect-independent accuracy.
        """
        insp, engine = self._get_inspector(warehouse)
        try:
            if progress_callback: progress_callback("Inspecting schemas...")
            result: dict[str, Any] = {"schemas": {}}
            
            schema_names = insp.get_schema_names()
            for schema_name in schema_names:
                if not include_system_schemas and _is_system_schema(schema_name):
                    continue

                tables: dict[str, Any] = {}

                if progress_callback: progress_callback("Reading table definitions...")
                table_names = insp.get_table_names(schema=schema_name)
                
                for table_name in table_names:
                    if progress_callback: progress_callback("Inspecting primary/foreign keys...")
                    pk_constraint = insp.get_pk_constraint(
                        table_name, schema=schema_name
                    )
                    pk_columns: set[str] = set(
                        pk_constraint.get("constrained_columns", [])
                    )
                    
                    if progress_callback: progress_callback("Inspecting columns...")
                    columns = [
                        {
                            "name":        col["name"],
                            "type":        str(col["type"]),
                            "nullable":    col.get("nullable", True),
                            "default":     col.get("default"),
                            "primary_key": col["name"] in pk_columns,
                        }
                        for col in insp.get_columns(table_name, schema=schema_name)
                    ]
                    tables[table_name] = {"columns": columns}

                result["schemas"][schema_name] = {"tables": tables}

            return result
        finally:
            engine.dispose()
