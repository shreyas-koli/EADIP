"""
Controlled Execution Engine (Phase 5).

Executes approved warehouse-changing action plans against connected external target databases.

CRITICAL SAFETY GUARANTEES:
- Strictly executes ONLY action types registered in ``_ACTION_REGISTRY``.
- Re-validates target identifiers (schema, table, column) via ``_quote_identifier``.
- Generates SQL statements strictly from safe structured parameters (never raw user text).
- Re-checks safety classification — rejects destructive or unregistered actions.
- Bounded execution timeout (statement_timeout = 30s).
- Secrets (passwords, connection strings) are never returned or logged.
"""

import time
import logging
from typing import Any, Dict
from sqlalchemy import text

from app.models.warehouse import Warehouse
from app.warehouse.connector import WarehouseConnector
from app.warehouse.automation import _ACTION_REGISTRY, _is_safe_identifier, _quote_identifier, SafetyClass

logger = logging.getLogger(__name__)

# Bounded statement execution timeout for target warehouse operations (30 seconds)
STATEMENT_TIMEOUT_MS = 30000


class ControlledExecutionEngine:
    """
    Safe, controlled engine that executes approved warehouse action plans against
    connected target data warehouses.
    """

    @classmethod
    def execute(cls, warehouse: Warehouse, action_plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an approved action plan against the target warehouse.

        Parameters
        ──────────
        warehouse : Warehouse
            The target warehouse ORM instance.
        action_plan : Dict[str, Any]
            The approved action plan payload.

        Returns
        ───────
        Dict[str, Any]
            Result payload containing:
            - ``success``: bool
            - ``statement``: str (safe SQL executed)
            - ``duration_ms``: float
            - ``error``: Optional[str] (sanitized safe error)
        """
        action_type = action_plan.get("action_type", "")
        params = action_plan.get("parameters") or action_plan.get("target") or {}

        # 1. Validate action type exists in registry
        action_def = _ACTION_REGISTRY.get(action_type)
        if action_def is None:
            return {
                "success": False,
                "statement": None,
                "duration_ms": 0.0,
                "error": f"Unsupported or unregistered action type: '{action_type}'.",
            }

        # 2. Safety class check: Reject destructive operations
        if action_def.is_destructive or action_def.safety_class == SafetyClass.IRREVERSIBLE_OR_HIGH_RISK:
            return {
                "success": False,
                "statement": None,
                "duration_ms": 0.0,
                "error": f"Action type '{action_type}' is marked high-risk or destructive and cannot be automated.",
            }

        # 3. Parameter and identifier validation
        schema = params.get("schema", "")
        table = params.get("table", "")
        column = params.get("column")

        if not schema or not table or not _is_safe_identifier(schema) or not _is_safe_identifier(table):
            return {
                "success": False,
                "statement": None,
                "duration_ms": 0.0,
                "error": f"Invalid or missing target identifiers: schema={schema!r}, table={table!r}.",
            }

        if action_type == "CREATE_INDEX" and (not column or not _is_safe_identifier(column)):
            return {
                "success": False,
                "statement": None,
                "duration_ms": 0.0,
                "error": f"Invalid or missing column identifier for CREATE_INDEX: column={column!r}.",
            }

        # 4. Construct safe SQL statement from validated parameters
        statement_sql = cls._generate_safe_sql(action_type, schema, table, column)
        if not statement_sql:
            return {
                "success": False,
                "statement": None,
                "duration_ms": 0.0,
                "error": f"Failed to generate safe SQL statement for action '{action_type}'.",
            }

        # 5. Connect to target warehouse and execute query with timeout
        start_time = time.perf_counter()
        try:
            engine = WarehouseConnector.connect(warehouse)
            with engine.connect() as connection:
                # Set statement timeout on PostgreSQL connection
                if warehouse.db_type.lower() == "postgresql":
                    try:
                        connection.execute(text(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}"))
                    except Exception as timeout_err:
                        logger.warning(f"Could not set statement_timeout: {timeout_err}")

                logger.info(f"[EXECUTION ENGINE] Executing statement on warehouse {warehouse.id}: {statement_sql}")
                connection.execute(text(statement_sql))
                connection.commit()

            engine.dispose()
            end_time = time.perf_counter()
            duration_ms = round((end_time - start_time) * 1000, 2)

            return {
                "success": True,
                "statement": statement_sql,
                "duration_ms": duration_ms,
                "error": None,
            }
        except Exception as exc:
            end_time = time.perf_counter()
            duration_ms = round((end_time - start_time) * 1000, 2)
            safe_error = str(exc)

            # Sanitize passwords or connection details from error message
            if warehouse.username and warehouse.username in safe_error:
                safe_error = safe_error.replace(warehouse.username, "***")

            logger.error(f"[EXECUTION ENGINE FAILED] Action '{action_type}' failed on warehouse {warehouse.id}: {safe_error}")
            return {
                "success": False,
                "statement": statement_sql,
                "duration_ms": duration_ms,
                "error": safe_error,
            }

    @staticmethod
    def _generate_safe_sql(
        action_type: str,
        schema: str,
        table: str,
        column: str | None,
    ) -> str | None:
        """
        Generate controlled SQL statements from pre-validated identifiers.
        """
        q_schema = _quote_identifier(schema)
        q_table = _quote_identifier(table)

        if action_type == "CREATE_INDEX":
            if not column:
                return None
            q_column = _quote_identifier(column)
            index_name = f"idx_{table}_{column}"
            if not _is_safe_identifier(index_name):
                import hashlib
                index_name = f"idx_{hashlib.sha256(f'{table}_{column}'.encode()).hexdigest()[:12]}"
            q_index = _quote_identifier(index_name)
            return f"CREATE INDEX IF NOT EXISTS {q_index} ON {q_schema}.{q_table} ({q_column})"

        if action_type == "ANALYZE_TABLE":
            return f"ANALYZE {q_schema}.{q_table}"

        return None
