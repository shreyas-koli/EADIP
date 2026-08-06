"""
Warehouse statistics analyser.

Collects structural and volumetric statistics from a remote data
warehouse by executing lightweight SQL queries against the
information schema and PostgreSQL system catalogues.

Each statistic category lives in its own private helper method so
individual concerns can evolve independently:

* ``_get_database_summary()``   — schema / table / view / column counts
* ``_get_table_statistics()``   — per-table row counts and column counts
* ``_get_index_statistics()``   — per-schema index counts
* ``_get_constraint_statistics()`` — per-schema constraint counts
* ``_calculate_summary()``      — pure aggregation, no SQL

Currently supports **PostgreSQL** only; additional dialects can be
introduced by adding dialect-specific helper variants and routing
via the warehouse's ``db_type``.

No orchestration logic, no FastAPI, no SharedContext.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.models.warehouse import Warehouse
from app.warehouse.connector import WarehouseConnector


class StatisticsAnalyzer:
    """
    Computes structural statistics for an external data warehouse.

    The analyser connects via :class:`WarehouseConnector`, executes
    SQL queries scoped to the target dialect, and returns a single
    aggregated dictionary.

    Usage::

        analyzer   = StatisticsAnalyzer()
        statistics = analyzer.analyse(warehouse)
    """

    def __init__(self) -> None:
        """Initialise the analyser with a ``WarehouseConnector``."""
        self._connector = WarehouseConnector()

    # ── Public API ───────────────────────────────────────────────

    def analyse(self, warehouse: Warehouse, include_system_schemas: bool = False) -> dict[str, Any]:
        """
        Collect and return structural statistics for a warehouse.

        Parameters
        ──────────
        warehouse : Warehouse
            A registered ``Warehouse`` ORM instance.
        include_system_schemas : bool
            If True, includes statistics for system schemas. Defaults to False.

        Returns
        ───────
        dict[str, Any]
            Structure::

                {
                    "summary": { ... },
                    "tables":  [ ... ],
                    "indexes": [ ... ],
                    "constraints": [ ... ]
                }
        """
        engine = self._connect(warehouse)

        try:
            db_summary = self._get_database_summary(engine, include_system_schemas)
            table_stats = self._get_table_statistics(engine, include_system_schemas)
            index_stats = self._get_index_statistics(engine, include_system_schemas)
            constraint_stats = self._get_constraint_statistics(engine, include_system_schemas)
            summary = self._calculate_summary(
                db_summary, table_stats, index_stats, constraint_stats,
            )

            return {
                "summary": summary,
                "tables": table_stats,
                "indexes": index_stats,
                "constraints": constraint_stats,
            }
        finally:
            engine.dispose()

    # ── Connection helper ────────────────────────────────────────

    def _connect(self, warehouse: Warehouse) -> Engine:
        """
        Establish a SQLAlchemy engine for the target warehouse.

        Parameters
        ──────────
        warehouse : Warehouse
            The warehouse to connect to.

        Returns
        ───────
        Engine
            A SQLAlchemy engine bound to the warehouse.
        """
        return self._connector.connect(warehouse)

    # ── SQL helper ───────────────────────────────────────────────

    @staticmethod
    def _get_schema_filter(column_name: str, include_system_schemas: bool) -> str:
        """Helper to generate SQL schema exclusion clauses."""
        if include_system_schemas:
            return ""
        return f"AND {column_name} NOT IN ('pg_catalog', 'information_schema', 'pg_toast') " \
               f"AND {column_name} NOT LIKE 'pg_temp%' " \
               f"AND {column_name} NOT LIKE 'pg_toast_temp%'"

    # ── Database-level summary ───────────────────────────────────

    def _get_database_summary(self, engine: Engine, include_system_schemas: bool) -> dict[str, int]:
        """
        Collect high-level counts: schemas, tables, views, columns.

        Parameters
        ──────────
        engine : Engine
            An active SQLAlchemy engine.

        Returns
        ───────
        dict[str, int]
            Aggregated counts keyed by metric name.
        """
        queries: dict[str, str] = {
            "total_schemas": f"""
                SELECT COUNT(DISTINCT schema_name)
                FROM information_schema.schemata
                WHERE 1=1 {self._get_schema_filter('schema_name', include_system_schemas)};
            """,
            "total_tables": f"""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_type = 'BASE TABLE'
                {self._get_schema_filter('table_schema', include_system_schemas)};
            """,
            "total_views": f"""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_type = 'VIEW'
                {self._get_schema_filter('table_schema', include_system_schemas)};
            """,
            "total_columns": f"""
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE 1=1 {self._get_schema_filter('table_schema', include_system_schemas)};
            """,
        }

        result: dict[str, int] = {}

        with engine.connect() as conn:
            for metric, sql in queries.items():
                row = conn.execute(text(sql)).scalar()
                result[metric] = int(row) if row is not None else 0

        return result

    # ── Table-level statistics ───────────────────────────────────

    def _get_table_statistics(self, engine: Engine, include_system_schemas: bool) -> list[dict[str, Any]]:
        """
        Collect per-table statistics: schema, name, estimated row
        count, and column count.

        Uses ``pg_class.reltuples`` for fast estimated row counts
        (avoids full table scans).

        Parameters
        ──────────
        engine : Engine
            An active SQLAlchemy engine.

        Returns
        ───────
        list[dict[str, Any]]
            One entry per table, sorted by estimated rows descending.
        """
        sql = f"""
            SELECT
                t.table_schema                            AS schema_name,
                t.table_name                              AS table_name,
                COALESCE(c.reltuples, 0)::BIGINT          AS estimated_row_count,
                COUNT(col.column_name)::INT               AS total_columns
            FROM information_schema.tables AS t
            LEFT JOIN pg_class AS c
                ON c.relname = t.table_name
            LEFT JOIN pg_namespace AS n
                ON n.oid = c.relnamespace
                AND n.nspname = t.table_schema
            LEFT JOIN information_schema.columns AS col
                ON col.table_schema = t.table_schema
                AND col.table_name = t.table_name
            WHERE t.table_type = 'BASE TABLE'
            {self._get_schema_filter('t.table_schema', include_system_schemas)}
            GROUP BY
                t.table_schema,
                t.table_name,
                c.reltuples
            ORDER BY
                estimated_row_count DESC;
        """

        tables: list[dict[str, Any]] = []

        with engine.connect() as conn:
            rows = conn.execute(text(sql)).fetchall()

            for row in rows:
                tables.append({
                    "schema": row[0],
                    "table_name": row[1],
                    "estimated_row_count": max(int(row[2]), 0),
                    "total_columns": int(row[3]),
                })

        return tables

    # ── Index statistics ─────────────────────────────────────────

    def _get_index_statistics(self, engine: Engine, include_system_schemas: bool) -> list[dict[str, Any]]:
        """
        Collect per-schema index details.

        Parameters
        ──────────
        engine : Engine
            An active SQLAlchemy engine.

        Returns
        ───────
        list[dict[str, Any]]
            Each entry contains ``schema``, ``table_name``,
            ``index_name``, and ``index_definition``.
        """
        sql = f"""
            SELECT
                schemaname   AS schema_name,
                tablename    AS table_name,
                indexname    AS index_name,
                indexdef     AS index_definition
            FROM pg_indexes
            WHERE 1=1 {self._get_schema_filter('schemaname', include_system_schemas)}
            ORDER BY
                schemaname,
                tablename,
                indexname;
        """

        indexes: list[dict[str, Any]] = []

        with engine.connect() as conn:
            rows = conn.execute(text(sql)).fetchall()

            for row in rows:
                indexes.append({
                    "schema": row[0],
                    "table_name": row[1],
                    "index_name": row[2],
                    "index_definition": row[3],
                })

        return indexes

    # ── Constraint statistics ────────────────────────────────────

    def _get_constraint_statistics(
        self,
        engine: Engine,
        include_system_schemas: bool,
    ) -> list[dict[str, Any]]:
        """
        Collect per-schema constraint details.

        Parameters
        ──────────
        engine : Engine
            An active SQLAlchemy engine.

        Returns
        ───────
        list[dict[str, Any]]
            Each entry contains ``schema``, ``table_name``,
            ``constraint_name``, and ``constraint_type``.
        """
        sql = f"""
            SELECT
                constraint_schema   AS schema_name,
                table_name          AS table_name,
                constraint_name     AS constraint_name,
                constraint_type     AS constraint_type
            FROM information_schema.table_constraints
            WHERE 1=1 {self._get_schema_filter('constraint_schema', include_system_schemas)}
            ORDER BY
                constraint_schema,
                table_name,
                constraint_name;
        """

        constraints: list[dict[str, Any]] = []

        with engine.connect() as conn:
            rows = conn.execute(text(sql)).fetchall()

            for row in rows:
                constraints.append({
                    "schema": row[0],
                    "table_name": row[1],
                    "constraint_name": row[2],
                    "constraint_type": row[3],
                })

        return constraints

    # ── Summary calculation ──────────────────────────────────────

    @staticmethod
    def _calculate_summary(
        db_summary: dict[str, int],
        table_stats: list[dict[str, Any]],
        index_stats: list[dict[str, Any]],
        constraint_stats: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Derive aggregate summary metrics from raw statistics.

        Parameters
        ──────────
        db_summary        : dict[str, int]
            Output of ``_get_database_summary()``.
        table_stats       : list[dict[str, Any]]
            Output of ``_get_table_statistics()``.
        index_stats       : list[dict[str, Any]]
            Output of ``_get_index_statistics()``.
        constraint_stats  : list[dict[str, Any]]
            Output of ``_get_constraint_statistics()``.

        Returns
        ───────
        dict[str, Any]
            Combined summary including largest/smallest tables,
            averages, and total counts.
        """
        summary: dict[str, Any] = {**db_summary}
        summary["total_indexes"] = len(index_stats)
        summary["total_constraints"] = len(constraint_stats)

        if not table_stats:
            summary["total_estimated_rows"] = 0
            summary["average_columns_per_table"] = 0
            summary["largest_table"] = None
            summary["smallest_table"] = None
            return summary

        total_rows = sum(t["estimated_row_count"] for t in table_stats)
        total_cols = sum(t["total_columns"] for t in table_stats)
        table_count = len(table_stats)

        # Tables are already sorted DESC by row count from the query
        largest = table_stats[0]
        smallest = table_stats[-1]

        summary["total_estimated_rows"] = total_rows
        summary["average_columns_per_table"] = round(
            total_cols / table_count, 2
        )
        summary["largest_table"] = {
            "schema": largest["schema"],
            "table": largest["table_name"],
            "estimated_rows": largest["estimated_row_count"],
        }
        summary["smallest_table"] = {
            "schema": smallest["schema"],
            "table": smallest["table_name"],
            "estimated_rows": smallest["estimated_row_count"],
        }

        return summary
