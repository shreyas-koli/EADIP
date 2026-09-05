"""
Warehouse Explorer Service.

Handles metadata introspection of PostgreSQL warehouses securely without
exposing passwords or data rows.
"""

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.inspection import inspect
import sqlalchemy.exc

# Filter out common system schemas to keep the explorer clean.
SYSTEM_SCHEMAS = {"pg_catalog", "information_schema", "pg_toast"}

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
