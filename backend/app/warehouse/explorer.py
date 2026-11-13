"""
Warehouse Explorer Service.

Handles metadata introspection of PostgreSQL warehouses securely without
exposing passwords or data rows.
"""

import datetime
import decimal
import time
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.inspection import inspect
import sqlalchemy.exc

# Filter out common system schemas to keep the explorer clean.
SYSTEM_SCHEMAS = {"pg_catalog", "information_schema", "pg_toast"}

# Hard limits for row pagination
DEFAULT_ROW_LIMIT = 50
MAX_ROW_LIMIT = 100

# Maximum bytes for a single cell value before it is truncated
_MAX_CELL_BYTES = 4096

# Statement timeout for row queries (milliseconds)
_QUERY_TIMEOUT_MS = 30_000


def _safe_identifier(name: str) -> str:
    """
    PostgreSQL-safe quoting for schema/table/column identifiers.

    Replaces any double-quote characters (the only dangerous char in a
    quoted identifier) and wraps the name in double-quotes, making it
    safe to embed in a query string.

    We use this instead of sqlalchemy.sql.expression.quoted_name to avoid
    any ORM complexity while still being injection-proof.
    """
    return '"' + name.replace('"', '""') + '"'


def _serialize_value(val: Any) -> Any:
    """
    Convert a Python/PostgreSQL value to a JSON-serialisable type.

    Handles:
    - None  → None
    - bool  → bool
    - int/float → native
    - Decimal → float
    - datetime / date / time → ISO string
    - uuid.UUID → str
    - bytes → hex string
    - lists/dicts (e.g. JSONB already decoded by psycopg2) → pass-through
    - very large strings → truncated with indicator
    """
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, decimal.Decimal):
        return float(val)
    if isinstance(val, (datetime.datetime, datetime.date, datetime.time)):
        return val.isoformat()
    if isinstance(val, uuid.UUID):
        return str(val)
    if isinstance(val, (dict, list)):
        # Already decoded JSON/JSONB — pass through (Pydantic will serialise)
        return val
    if isinstance(val, (bytes, bytearray, memoryview)):
        raw = bytes(val)
        if len(raw) > _MAX_CELL_BYTES:
            return f"<binary {len(raw)} bytes>"
        return raw.hex()
    # Fallback: stringify
    s = str(val)
    if len(s.encode()) > _MAX_CELL_BYTES:
        return s[:_MAX_CELL_BYTES] + "… [truncated]"
    return s


class ExplorerService:
    @staticmethod
    def get_schemas(engine: Engine) -> list[dict]:
        """
        Get all non-system schemas in the database.
        """
        inspector = inspect(engine)
        all_schemas = inspector.get_schema_names()
        
        user_schemas = []
        for s in all_schemas:
            if s not in SYSTEM_SCHEMAS and not s.startswith("pg_temp_") and not s.startswith("pg_toast_"):
                user_schemas.append({"name": s})
                
        # Sort alphabetically for better UX
        return sorted(user_schemas, key=lambda x: x["name"])

    @staticmethod
    def get_tables(engine: Engine, schema_name: str) -> list[dict]:
        """
        Get all tables in a specific schema with estimated row counts.
        Uses pg_class.reltuples for fast estimates instead of slow COUNT(*).
        """
        # We parameterize :schema_name to prevent SQL injection.
        # c.relkind 'r' = ordinary table, 'p' = partitioned table, 'v' = view
        query = text("""
            SELECT
                c.relname AS name,
                c.reltuples::bigint AS estimated_row_count
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = :schema_name
              AND c.relkind IN ('r', 'p', 'v', 'm')
            ORDER BY c.relname;
        """)
        
        with engine.connect() as conn:
            result = conn.execute(query, {"schema_name": schema_name})
            tables = []
            for row in result:
                tables.append({
                    "name": row.name,
                    "schema_name": schema_name,
                    "estimated_row_count": max(0, row.estimated_row_count or 0)
                })
            return tables

    @staticmethod
    def get_columns(engine: Engine, schema_name: str, table_name: str) -> list[dict]:
        """
        Get all columns for a specific table using SQLAlchemy inspector.
        """
        inspector = inspect(engine)
        try:
            columns_info = inspector.get_columns(table_name, schema=schema_name)
            pk_constraint = inspector.get_pk_constraint(table_name, schema=schema_name)
            fk_constraints = inspector.get_foreign_keys(table_name, schema=schema_name)
        except sqlalchemy.exc.NoSuchTableError:
            return []
            
        pk_cols = set(pk_constraint.get("constrained_columns", [])) if pk_constraint else set()
        
        fk_cols = {}
        for fk in fk_constraints:
            for col in fk.get("constrained_columns", []):
                fk_cols[col] = {
                    "referred_table": fk.get("referred_table"),
                    "referred_schema": fk.get("referred_schema")
                }
                
        result = []
        for i, col in enumerate(columns_info):
            result.append({
                "name": col["name"],
                "data_type": str(col["type"]),
                "nullable": col.get("nullable", True),
                "position": i + 1,
                "is_primary_key": col["name"] in pk_cols,
                "foreign_key": fk_cols.get(col["name"])
            })
            
        return result

    @staticmethod
    def get_rows(
        engine: Engine,
        schema_name: str,
        table_name: str,
        limit: int = DEFAULT_ROW_LIMIT,
        offset: int = 0,
    ) -> dict:
        """
        Fetch paginated rows from a table using safe identifier quoting.

        - Identifiers (schema, table) are double-quoted to prevent injection.
        - A statement_timeout is set per connection to guard against slow queries.
        - Total row count is estimated from pg_class.reltuples (no COUNT(*)).
        - All values are serialised to JSON-safe Python types.
        """
        # Clamp limit to allowed range
        limit = max(1, min(limit, MAX_ROW_LIMIT))
        offset = max(0, offset)

        safe_schema = _safe_identifier(schema_name)
        safe_table = _safe_identifier(table_name)
        full_ref = f"{safe_schema}.{safe_table}"

        # Fast estimated count — does NOT scan the table
        count_query = text("""
            SELECT GREATEST(c.reltuples::bigint, 0) AS estimated
            FROM   pg_class c
            JOIN   pg_namespace n ON n.oid = c.relnamespace
            WHERE  n.nspname = :schema_name
              AND  c.relname  = :table_name
        """)

        # Row data query — identifiers are double-quoted above, values are
        # bound via parameterised LIMIT/OFFSET so there is no injection risk.
        # The query string itself contains only safe quoted identifiers.
        row_query = text(
            f"SELECT * FROM {full_ref} LIMIT :limit OFFSET :offset"  # noqa: S608
        )

        with engine.connect() as conn:
            # Apply per-statement timeout to prevent runaway queries
            conn.execute(text(f"SET LOCAL statement_timeout = {_QUERY_TIMEOUT_MS}"))

            # Estimated total
            count_row = conn.execute(
                count_query, {"schema_name": schema_name, "table_name": table_name}
            ).fetchone()
            total_rows = int(count_row.estimated) if count_row else 0

            # Fetch rows
            result = conn.execute(row_query, {"limit": limit, "offset": offset})
            columns = list(result.keys())
            rows = [
                [_serialize_value(cell) for cell in row]
                for row in result.fetchall()
            ]

        return {
            "columns": columns,
            "rows": rows,
            "limit": limit,
            "offset": offset,
            "returned_rows": len(rows),
            "total_rows": total_rows,
            "is_estimated_total": True,
        }

    # ── SQL Console ───────────────────────────────────────────────────────────

    @staticmethod
    def execute_query(engine: Engine, validated_sql: str) -> dict:
        """
        Execute a pre-validated, read-only SQL statement against the warehouse.

        Security layers applied here:
        1. Runs inside a READ ONLY transaction — PostgreSQL will reject any
           mutation even if validation missed something.
        2. statement_timeout (_QUERY_TIMEOUT_MS) hard-cancels slow queries.
        3. Results are capped at MAX_QUERY_ROWS; `truncated` is set if so.
        4. All cell values pass through _serialize_value for JSON safety.

        Parameters
        ----------
        engine : Engine
            SQLAlchemy engine for the target warehouse.
        validated_sql : str
            SQL already cleared by sql_validator.validate_sql().

        Returns
        -------
        dict matching QueryResponse schema.
        """
        max_rows = 1_000

        with engine.connect() as conn:
            # Layer 1: read-only transaction + statement timeout
            conn.execute(text("SET LOCAL statement_timeout = :ms"), {"ms": _QUERY_TIMEOUT_MS})
            conn.execute(text("SET TRANSACTION READ ONLY"))

            t_start = time.monotonic()
            result = conn.execute(text(validated_sql))
            columns = list(result.keys())

            # Layer 3: cap at max_rows + 1 so we can detect truncation cheaply
            raw_rows = result.fetchmany(max_rows + 1)
            t_end = time.monotonic()

            truncated = len(raw_rows) > max_rows
            rows_to_return = raw_rows[:max_rows]

            rows = [
                [_serialize_value(cell) for cell in row]
                for row in rows_to_return
            ]

        execution_time_ms = (t_end - t_start) * 1000

        return {
            "columns": columns,
            "rows": rows,
            "returned_rows": len(rows),
            "execution_time_ms": round(execution_time_ms, 2),
            "truncated": truncated,
        }
