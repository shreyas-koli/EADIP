"""
Unit tests for ControlledVerificationEngine (Phase 6).

Verifies evidence-based read-only catalog verification for CREATE_INDEX and ANALYZE_TABLE,
identifier sanitization, statement timeout, and unsupported action INCONCLUSIVE handling.
"""

import pytest
from unittest.mock import MagicMock, patch

from app.models.user import User  # noqa: F401
from app.models.warehouse import Warehouse
from app.warehouse.verification_engine import ControlledVerificationEngine


@pytest.fixture
def mock_warehouse():
    return Warehouse(
        id=88,
        name="Ver Target WH",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="eadip_ver",
        username="postgres",
        encrypted_password=b"token",
        owner_id=1,
    )


def test_verify_unsupported_action_type(mock_warehouse):
    """Verify unsupported action type returns INCONCLUSIVE status."""
    plan = {
        "action_type": "UNSUPPORTED_ACTION_TYPE",
        "parameters": {"schema": "public", "table": "orders"},
    }
    res = ControlledVerificationEngine.verify(mock_warehouse, plan)
    assert res["status"] == "INCONCLUSIVE"
    assert res["verified"] is None
    assert len(res["checks"]) > 0
    assert res["checks"][0]["status"] == "INCONCLUSIVE"


def test_verify_unsafe_identifiers(mock_warehouse):
    """Verify unsafe SQL identifiers return INCONCLUSIVE status."""
    plan = {
        "action_type": "CREATE_INDEX",
        "parameters": {"schema": "public", "table": "orders; DROP TABLE users;--", "column": "id"},
    }
    res = ControlledVerificationEngine.verify(mock_warehouse, plan)
    assert res["status"] == "INCONCLUSIVE"
    assert res["verified"] is None
    assert res["error"] == "Invalid target identifiers"


def test_verify_create_index_success(mock_warehouse):
    """Verify successful CREATE_INDEX verification when index exists in pg_indexes."""
    plan = {
        "action_type": "CREATE_INDEX",
        "parameters": {"schema": "public", "table": "orders", "column": "created_at"},
    }

    mock_row = {"indexname": "idx_orders_created_at", "indexdef": 'CREATE INDEX idx_orders_created_at ON public.orders USING btree (created_at)'}
    mock_mappings = MagicMock()
    mock_mappings.first.return_value = mock_row

    mock_conn = MagicMock()
    mock_conn.execution_options.return_value = mock_conn
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.mappings.return_value = mock_mappings

    mock_engine = MagicMock()
    mock_engine.connect.return_value = mock_conn

    with patch("app.warehouse.connector.WarehouseConnector.connect", return_value=mock_engine):
        res = ControlledVerificationEngine.verify(mock_warehouse, plan)

        assert res["status"] == "VERIFIED"
        assert res["verified"] is True
        assert res["expected_state"]["index_exists"] is True
        assert res["observed_state"]["index_exists"] is True
        assert len(res["checks"]) == 2
        assert res["checks"][0]["status"] == "PASS"


def test_verify_create_index_missing_fails(mock_warehouse):
    """Verify CREATE_INDEX verification returns VERIFICATION_FAILED when index is absent."""
    plan = {
        "action_type": "CREATE_INDEX",
        "parameters": {"schema": "public", "table": "orders", "column": "created_at"},
    }

    mock_mappings = MagicMock()
    mock_mappings.first.return_value = None  # Index not found in catalog

    mock_conn = MagicMock()
    mock_conn.execution_options.return_value = mock_conn
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.mappings.return_value = mock_mappings

    mock_engine = MagicMock()
    mock_engine.connect.return_value = mock_conn

    with patch("app.warehouse.connector.WarehouseConnector.connect", return_value=mock_engine):
        res = ControlledVerificationEngine.verify(mock_warehouse, plan)

        assert res["status"] == "VERIFICATION_FAILED"
        assert res["verified"] is False
        assert res["observed_state"]["index_exists"] is False
        assert res["checks"][0]["status"] == "FAIL"


def test_verify_analyze_table_success(mock_warehouse):
    """Verify ANALYZE_TABLE verification returns VERIFIED when table is found in stat catalog."""
    plan = {
        "action_type": "ANALYZE_TABLE",
        "parameters": {"schema": "public", "table": "orders"},
    }

    mock_row = {"schemaname": "public", "relname": "orders", "last_analyze": "2026-09-20 18:00:00"}
    mock_mappings = MagicMock()
    mock_mappings.first.return_value = mock_row

    mock_conn = MagicMock()
    mock_conn.execution_options.return_value = mock_conn
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.mappings.return_value = mock_mappings

    mock_engine = MagicMock()
    mock_engine.connect.return_value = mock_conn

    with patch("app.warehouse.connector.WarehouseConnector.connect", return_value=mock_engine):
        res = ControlledVerificationEngine.verify(mock_warehouse, plan)

        assert res["status"] == "VERIFIED"
        assert res["verified"] is True
        assert res["observed_state"]["table_exists"] is True
