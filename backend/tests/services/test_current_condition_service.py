"""
Unit tests for CurrentConditionService (R3).

Verifies authorization enforcement, candidate fingerprinting,
historical match integration, and evaluator delegation.
"""

from unittest.mock import MagicMock, patch
import pytest

from app.models.user import User
from app.models.warehouse import Warehouse
from app.services.current_condition_service import CurrentConditionService
from app.warehouse.current_condition import ConditionStatus


@pytest.fixture
def mock_db():
    db = MagicMock()
    return db


@pytest.fixture
def mock_user():
    u = MagicMock(spec=User)
    u.id = 42
    u.role = "user"
    return u


@pytest.fixture
def mock_warehouse():
    w = MagicMock(spec=Warehouse)
    w.id = 10
    w.owner_id = 42
    w.db_type = "postgresql"
    return w


def test_evaluate_candidate_condition_unauthorized_raises(mock_db, mock_user):
    """Test authorization check: accessing another user's warehouse raises PermissionError."""
    with patch("app.services.current_condition_service.get_warehouse_by_id", return_value=None):
        candidate = {"action_type": "ANALYZE_TABLE", "schema": "public", "table": "votes"}

        with pytest.raises(PermissionError) as exc_info:
            CurrentConditionService.evaluate_candidate_condition(
                db=mock_db,
                warehouse_id=999,
                candidate=candidate,
                user=mock_user,
            )

        assert "access denied" in str(exc_info.value)


def test_evaluate_candidate_condition_success(mock_db, mock_user, mock_warehouse):
    """Test authorized condition evaluation returns structured R3 payload with fingerprint."""
    candidate = {
        "recommendation_id": "rec_123",
        "action_type": "ANALYZE_TABLE",
        "schema": "public",
        "table": "votes",
    }

    mock_eval_result = {
        "recommendation_id": "rec_123",
        "fingerprint": "abc123sha",
        "warehouse_id": 10,
        "action_type": "ANALYZE_TABLE",
        "target": {"schema": "public", "table": "votes"},
        "condition_status": ConditionStatus.PRESENT,
        "condition_type": "MODIFICATIONS_SINCE_ANALYZE",
        "evidence": [],
        "evaluated_at": "2026-09-26T20:00:00Z",
        "measurement_available": True,
        "reason": "Table has 100 modifications",
        "historical_match": None,
    }

    with patch(
        "app.services.current_condition_service.get_warehouse_by_id",
        return_value=mock_warehouse,
    ), patch(
        "app.services.current_condition_service.RecommendationFingerprintService.find_matches_for_candidate",
        return_value={"fingerprint": "abc123sha", "match_found": False, "matches": []},
    ), patch(
        "app.services.current_condition_service.CurrentConditionEvaluator.evaluate_current_condition",
        return_value=mock_eval_result,
    ) as mock_eval:
        result = CurrentConditionService.evaluate_candidate_condition(
            db=mock_db,
            warehouse_id=10,
            candidate=candidate,
            user=mock_user,
        )

    assert result["condition_status"] == ConditionStatus.PRESENT
    assert result["fingerprint"] == "abc123sha"
    mock_eval.assert_called_once()
