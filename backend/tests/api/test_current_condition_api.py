"""
API tests for Current Condition Awareness endpoint (R3).

GET /warehouses/{warehouse_id}/recommendation-history/conditions
"""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.warehouse.current_condition import ConditionStatus

client = TestClient(app)


def test_get_current_condition_unauthenticated():
    """API returns 401 when token is missing or invalid."""
    response = client.get("/warehouses/1/recommendation-history/conditions?action_type=ANALYZE_TABLE")
    assert response.status_code == 401


@patch("app.api.recommendation_history.get_current_user")
@patch("app.api.recommendation_history.CurrentConditionService.evaluate_candidate_condition")
def test_get_current_condition_authorized_success(mock_service_eval, mock_get_user):
    """API returns 200 OK with CurrentConditionResponse payload."""
    mock_user = MagicMock()
    mock_user.id = 1
    mock_get_user.return_value = mock_user

    mock_service_eval.return_value = {
        "recommendation_id": "rec_query",
        "fingerprint": "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "warehouse_id": 1,
        "action_type": "ANALYZE_TABLE",
        "target": {"schema": "public", "table": "votes"},
        "condition_status": ConditionStatus.PRESENT,
        "condition_type": "MODIFICATIONS_SINCE_ANALYZE",
        "evidence": [
            {
                "source": "pg_stat_user_tables",
                "field": "n_mod_since_analyze",
                "value": 250,
                "interpretation": "250 modifications have occurred since the last recorded analyze.",
            }
        ],
        "evaluated_at": "2026-09-26T20:00:00Z",
        "measurement_available": True,
        "reason": "250 modifications have occurred on table 'public.votes' since the last recorded analyze.",
        "historical_match": None,
    }

    headers = {"Authorization": "Bearer test-token"}
    response = client.get(
        "/warehouses/1/recommendation-history/conditions?action_type=ANALYZE_TABLE&schema=public&table=votes",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["warehouse_id"] == 1
    assert data["action_type"] == "ANALYZE_TABLE"
    assert data["condition_status"] == "PRESENT"
    assert len(data["evidence"]) == 1
    assert data["evidence"][0]["field"] == "n_mod_since_analyze"
    assert data["evidence"][0]["value"] == 250


@patch("app.api.recommendation_history.get_current_user")
@patch("app.api.recommendation_history.CurrentConditionService.evaluate_candidate_condition")
def test_get_current_condition_forbidden(mock_service_eval, mock_get_user):
    """API returns 403 Forbidden when user does not own warehouse."""
    mock_user = MagicMock()
    mock_user.id = 1
    mock_get_user.return_value = mock_user

    mock_service_eval.side_effect = PermissionError("Warehouse access denied.")

    headers = {"Authorization": "Bearer test-token"}
    response = client.get(
        "/warehouses/99/recommendation-history/conditions?action_type=ANALYZE_TABLE&table=votes",
        headers=headers,
    )

    assert response.status_code == 403
    assert "access denied" in response.json()["detail"]
