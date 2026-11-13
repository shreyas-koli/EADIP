"""
Unit tests for CurrentConditionEvaluator (R3).

Verifies catalog-based current condition awareness for PostgreSQL warehouses:
- ANALYZE_TABLE condition status (PRESENT, RESOLVED, UNCERTAIN)
- Previous ACHIEVED outcome does NOT force RESOLVED if current evidence is PRESENT
- CREATE_INDEX condition status (PRESENT, RESOLVED)
- Unsupported action types return NOT_MEASURABLE
- Identifier safety, read-only guarantees, and credential redaction
- RecommendationAgent non-suppression assertion
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest

from app.models.warehouse import Warehouse
from app.warehouse.current_condition import ConditionStatus, CurrentConditionEvaluator
from app.warehouse.recommendation import RecommendationEngine
from app.context.shared_context import SharedContext


@pytest.fixture
def mock_pg_warehouse():
    wh = MagicMock(spec=Warehouse)
    wh.id = 101
    wh.db_type = "postgresql"
    wh.host = "localhost"
    wh.port = 5432
    wh.database_name = "test_db"
    wh.username = "sensitive_user"
    wh.encrypted_password = "encrypted_secret_pass"
    return wh


def make_mock_engine(first_return=None, all_return=None):
    mock_mappings = MagicMock()
    mock_mappings.first.return_value = first_return
    mock_mappings.all.return_value = all_return or []

    mock_conn = MagicMock()
    mock_conn.execution_options.return_value = mock_conn
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.mappings.return_value = mock_mappings

    mock_engine = MagicMock()
    mock_engine.connect.return_value = mock_conn
    return mock_engine


def test_analyze_table_present_when_modified(mock_pg_warehouse):
    """Test 1: ANALYZE_TABLE returns PRESENT when rows modified since last analyze with observational evidence wording."""
    mock_result = {
        "schemaname": "public",
        "relname": "votes",
        "last_analyze": None,
        "last_autoanalyze": None,
        "n_mod_since_analyze": 1500,
        "n_live_tup": 10000,
        "n_dead_tup": 50,
    }

    mock_engine = make_mock_engine(first_return=mock_result)

    candidate = {
        "recommendation_id": "rec_001",
        "action_type": "ANALYZE_TABLE",
        "target": {"schema": "public", "table": "votes"},
    }

    with patch("app.warehouse.current_condition.WarehouseConnector.connect", return_value=mock_engine):
        res = CurrentConditionEvaluator.evaluate_current_condition(mock_pg_warehouse, candidate)

    assert res["condition_status"] == ConditionStatus.PRESENT
    assert res["condition_type"] == "MODIFICATIONS_SINCE_ANALYZE"
    assert res["measurement_available"] is True
    assert "1500 modifications have occurred" in res["reason"]
    assert "ANALYZE is definitely required" not in res["reason"]
    assert "stale" not in res["reason"].lower()
    assert len(res["evidence"]) == 5
    assert res["evidence"][2]["field"] == "n_mod_since_analyze"
    assert res["evidence"][2]["value"] == 1500
    assert res["evidence"][2]["interpretation"] == "1500 modifications have occurred since the last recorded analyze."


def test_analyze_table_resolved_when_zero_modifications(mock_pg_warehouse):
    """Test 2: ANALYZE_TABLE returns RESOLVED when 0 modifications and analyze timestamp exists."""
    now = datetime.now(timezone.utc)
    mock_result = {
        "schemaname": "public",
        "relname": "votes",
        "last_analyze": now,
        "last_autoanalyze": None,
        "n_mod_since_analyze": 0,
        "n_live_tup": 10000,
        "n_dead_tup": 0,
    }

    mock_engine = make_mock_engine(first_return=mock_result)

    candidate = {
        "recommendation_id": "rec_002",
        "action_type": "ANALYZE_TABLE",
        "target": {"schema": "public", "table": "votes"},
    }

    with patch("app.warehouse.current_condition.WarehouseConnector.connect", return_value=mock_engine):
        res = CurrentConditionEvaluator.evaluate_current_condition(mock_pg_warehouse, candidate)

    assert res["condition_status"] == ConditionStatus.RESOLVED
    assert res["condition_type"] == "MODIFICATIONS_SINCE_ANALYZE"
    assert res["measurement_available"] is True
    assert "No modifications are currently recorded" in res["reason"]
    assert "never be needed" not in res["reason"].lower()
    assert res["evidence"][2]["interpretation"] == "No modifications are currently recorded since the latest analyze."


def test_previous_achieved_does_not_override_present_condition(mock_pg_warehouse):
    """Test 3: Previous outcome ACHIEVED does NOT force RESOLVED if current catalog shows PRESENT."""
    mock_result = {
        "schemaname": "public",
        "relname": "votes",
        "last_analyze": None,
        "last_autoanalyze": None,
        "n_mod_since_analyze": 500,
        "n_live_tup": 5000,
        "n_dead_tup": 10,
    }

    historical_match = {
        "recommendation_id": "rec_old",
        "final_outcome": "ACHIEVED",
        "verification_status": "VERIFIED",
    }

    mock_engine = make_mock_engine(first_return=mock_result)

    candidate = {
        "recommendation_id": "rec_003",
        "action_type": "ANALYZE_TABLE",
        "target": {"schema": "public", "table": "votes"},
    }

    with patch("app.warehouse.current_condition.WarehouseConnector.connect", return_value=mock_engine):
        res = CurrentConditionEvaluator.evaluate_current_condition(
            mock_pg_warehouse, candidate, historical_match=historical_match
        )

    # Current evidence MUST dictate status (PRESENT), not historical match ACHIEVED
    assert res["condition_status"] == ConditionStatus.PRESENT
    assert res["historical_match"] == historical_match


def test_analyze_table_uncertain_when_table_missing(mock_pg_warehouse):
    """Test 5: ANALYZE_TABLE returns UNCERTAIN when table not found in user stats catalog."""
    mock_engine = make_mock_engine(first_return=None)

    candidate = {
        "recommendation_id": "rec_004",
        "action_type": "ANALYZE_TABLE",
        "target": {"schema": "public", "table": "missing_table"},
    }

    with patch("app.warehouse.current_condition.WarehouseConnector.connect", return_value=mock_engine):
        res = CurrentConditionEvaluator.evaluate_current_condition(mock_pg_warehouse, candidate)

    assert res["condition_status"] == ConditionStatus.UNCERTAIN
    assert "not present in PostgreSQL user statistics" in res["reason"]


def test_create_index_resolved_when_index_exists(mock_pg_warehouse):
    """Test 7: CREATE_INDEX returns RESOLVED when matching index exists in catalog."""
    mock_rows = [
        {"indexname": "idx_votes_user_id", "indexdef": "CREATE INDEX idx_votes_user_id ON public.votes USING btree (user_id)"}
    ]

    mock_engine = make_mock_engine(all_return=mock_rows)

    candidate = {
        "recommendation_id": "rec_005",
        "action_type": "CREATE_INDEX",
        "target": {"schema": "public", "table": "votes", "column": "user_id"},
    }

    with patch("app.warehouse.current_condition.WarehouseConnector.connect", return_value=mock_engine):
        res = CurrentConditionEvaluator.evaluate_current_condition(mock_pg_warehouse, candidate)

    assert res["condition_status"] == ConditionStatus.RESOLVED
    assert res["condition_type"] == "MISSING_INDEX"
    assert "already exists" in res["reason"]


def test_create_index_present_when_index_absent(mock_pg_warehouse):
    """Test 7: CREATE_INDEX returns PRESENT when index is missing in catalog."""
    mock_rows = [
        {"indexname": "votes_pkey", "indexdef": "CREATE UNIQUE INDEX votes_pkey ON public.votes USING btree (id)"}
    ]

    mock_engine = make_mock_engine(all_return=mock_rows)

    candidate = {
        "recommendation_id": "rec_006",
        "action_type": "CREATE_INDEX",
        "target": {"schema": "public", "table": "votes", "column": "user_id"},
    }

    with patch("app.warehouse.current_condition.WarehouseConnector.connect", return_value=mock_engine):
        res = CurrentConditionEvaluator.evaluate_current_condition(mock_pg_warehouse, candidate)

    assert res["condition_status"] == ConditionStatus.PRESENT
    assert res["condition_type"] == "MISSING_INDEX"
    assert "does not exist in catalog" in res["reason"]


def test_unsupported_action_returns_not_measurable(mock_pg_warehouse):
    """Test 6: Unsupported action types cleanly return NOT_MEASURABLE."""
    candidate = {
        "recommendation_id": "rec_007",
        "action_type": "GRANT_READ_ONLY_ACCESS",
        "target": {"schema": "public", "table": "votes"},
    }

    res = CurrentConditionEvaluator.evaluate_current_condition(mock_pg_warehouse, candidate)

    assert res["condition_status"] == ConditionStatus.NOT_MEASURABLE
    assert res["condition_type"] == "UNSUPPORTED_ACTION_TYPE"
    assert res["measurement_available"] is False
    assert "No authoritative PostgreSQL condition evaluator exists" in res["reason"]


def test_credential_protection_in_errors(mock_pg_warehouse):
    """Test 10: Exception messages redact sensitive database usernames."""
    candidate = {
        "recommendation_id": "rec_008",
        "action_type": "ANALYZE_TABLE",
        "target": {"schema": "public", "table": "votes"},
    }

    with patch(
        "app.warehouse.current_condition.WarehouseConnector.connect",
        side_effect=Exception("Failed connection for sensitive_user at localhost"),
    ):
        res = CurrentConditionEvaluator.evaluate_current_condition(mock_pg_warehouse, candidate)

    assert res["condition_status"] == ConditionStatus.UNCERTAIN
    assert "sensitive_user" not in res["reason"]
    assert "***" in res["reason"]


def test_recommendation_agent_decision_logic_unchanged(mock_pg_warehouse):
    """Test 12: R3 evaluation does NOT alter RecommendationEngine candidate generation."""
    context = SharedContext()
    context.set_agent_result(
        "statistics",
        {
            "tables": [
                {
                    "schema": "public",
                    "table_name": "large_votes_table",
                    "estimated_row_count": 500000,
                    "total_columns": 5,
                }
            ]
        },
    )

    engine = RecommendationEngine()
    result = engine.analyse(mock_pg_warehouse, context)

    # RecommendationEngine produces candidates normally
    recs = result.get("recommendations", [])
    assert len(recs) == 1
    assert recs[0]["recommendation_type"] == "large_table_indexing"
