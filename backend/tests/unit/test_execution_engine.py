"""
Unit tests for ControlledExecutionEngine (Phase 5).

Verifies safe SQL statement generation, identifier sanitization, safety class enforcement,
and target warehouse query execution.
"""

import pytest
from unittest.mock import MagicMock, patch

from app.models.user import User  # noqa: F401
from app.models.warehouse import Warehouse
from app.warehouse.execution_engine import ControlledExecutionEngine


@pytest.fixture
def mock_warehouse():
    return Warehouse(
        id=99,
        name="Target WH",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="eadip_target",
        username="postgres",
        encrypted_password=b"token",
        owner_id=1,
    )


def test_generate_safe_sql_create_index():
    """Verify safe CREATE INDEX SQL statement generation."""
    sql = ControlledExecutionEngine._generate_safe_sql("CREATE_INDEX", "public", "orders", "created_at")
    assert sql == 'CREATE INDEX IF NOT EXISTS "idx_orders_created_at" ON "public"."orders" ("created_at")'


def test_generate_safe_sql_analyze_table():
    """Verify safe ANALYZE TABLE SQL statement generation."""
    sql = ControlledExecutionEngine._generate_safe_sql("ANALYZE_TABLE", "public", "orders", None)
    assert sql == 'ANALYZE "public"."orders"'


def test_execute_unsupported_action_type(mock_warehouse):
    """Verify execution of unsupported or unregistered action type returns failure."""
    plan = {
        "action_type": "DROP_TABLE_UNSAFE",
        "parameters": {"schema": "public", "table": "orders"},
    }
    res = ControlledExecutionEngine.execute(mock_warehouse, plan)
    assert res["success"] is False
    assert "Unsupported or unregistered action type" in res["error"]


def test_execute_unsafe_identifiers(mock_warehouse):
    """Verify execution with unsafe SQL identifiers returns failure."""
    plan = {
        "action_type": "CREATE_INDEX",
        "parameters": {"schema": "public", "table": "orders; DROP TABLE users;--", "column": "id"},
    }
    res = ControlledExecutionEngine.execute(mock_warehouse, plan)
    assert res["success"] is False
    assert "Invalid or missing target identifiers" in res["error"]


def test_execute_successful_statement(mock_warehouse):
    """Verify ControlledExecutionEngine executes valid SQL on target engine."""
    plan = {
        "action_type": "ANALYZE_TABLE",
        "parameters": {"schema": "public", "table": "orders"},
    }

    mock_conn = MagicMock()
    mock_conn.execution_options.return_value = mock_conn
    mock_conn.__enter__.return_value = mock_conn
    mock_engine = MagicMock()
    mock_engine.connect.return_value = mock_conn

    with patch("app.warehouse.connector.WarehouseConnector.connect", return_value=mock_engine):
        res = ControlledExecutionEngine.execute(mock_warehouse, plan)

        assert res["success"] is True
        assert res["statement"] == 'ANALYZE "public"."orders"'
        assert res["duration_ms"] >= 0.0
        assert res["error"] is None
        assert mock_conn.execute.called
