"""
API tests for Recommendation Decision Engine endpoint (R4).

POST /warehouses/{warehouse_id}/recommendations/decide
"""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.warehouse.recommendation_decision import RecommendationDecisionState

client = TestClient(app)


def test_decide_endpoint_unauthenticated():
    """API returns 401 Unauthorized when Bearer token is missing."""
    response = client.post(
        "/warehouses/1/recommendations/decide",
        json={"action_type": "ANALYZE_TABLE", "schema": "public", "table": "votes"},
    )
    assert response.status_code == 401


@patch("app.api.recommendation_history.get_current_user")
@patch("app.api.recommendation_history.RecommendationDecisionService.evaluate_candidate_decision")
def test_decide_endpoint_authorized_success(mock_service_eval, mock_get_user):
    """API returns 200 OK with RecommendationDecisionResponse payload."""
    mock_user = MagicMock()
    mock_user.id = 1
    mock_get_user.return_value = mock_user

    mock_service_eval.return_value = {
        "recommendation_id": "rec_123",
        "fingerprint": "abc123sha256hash",
        "action_type": "ANALYZE_TABLE",
        "target": {"schema": "public", "table": "votes"},
        "decision": RecommendationDecisionState.PROPOSE,
        "reason_code": "CONDITION_REAPPEARED",
        "reason": "Equivalent recommendation previously achieved its objective, but modifications reappeared.",
        "historical_outcome": "ACHIEVED",
        "current_condition_status": "PRESENT",
        "evidence": [],
        "evaluated_at": "2026-09-26T20:30:00Z",
    }

    headers = {"Authorization": "Bearer test-token"}
    candidate = {"action_type": "ANALYZE_TABLE", "schema": "public", "table": "votes"}

    response = client.post(
        "/warehouses/1/recommendations/decide",
        json=candidate,
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "PROPOSE"
    assert data["reason_code"] == "CONDITION_REAPPEARED"
    assert data["fingerprint"] == "abc123sha256hash"


@patch("app.api.recommendation_history.get_current_user")
@patch("app.api.recommendation_history.RecommendationDecisionService.evaluate_candidate_decision")
def test_decide_endpoint_forbidden(mock_service_eval, mock_get_user):
    """API returns 403 Forbidden when user does not own target warehouse."""
    mock_user = MagicMock()
    mock_user.id = 1
    mock_get_user.return_value = mock_user

    mock_service_eval.side_effect = PermissionError("Warehouse access denied.")

    headers = {"Authorization": "Bearer test-token"}
    candidate = {"action_type": "ANALYZE_TABLE", "schema": "public", "table": "votes"}

    response = client.post(
        "/warehouses/99/recommendations/decide",
        json=candidate,
        headers=headers,
    )

    assert response.status_code == 403
    assert "access denied" in response.json()["detail"]
