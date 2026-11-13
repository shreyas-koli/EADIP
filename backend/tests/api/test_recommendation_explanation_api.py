"""
API tests for Recommendation Explanation Engine endpoints (R6).

POST /warehouses/{warehouse_id}/recommendations/explain
GET /warehouses/{warehouse_id}/recommendations/{recommendation_id}/explanation
"""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_explain_endpoint_unauthenticated():
    """API returns 401 Unauthorized when Bearer token is missing."""
    response = client.post(
        "/warehouses/1/recommendations/explain",
        json={"action_type": "ANALYZE_TABLE", "schema": "public", "table": "votes"},
    )
    assert response.status_code == 401


@patch("app.api.recommendation_history.get_current_user")
@patch("app.api.recommendation_history.RecommendationExplanationService.get_candidate_explanation")
def test_explain_endpoint_authorized_success(mock_service_explain, mock_get_user):
    """API returns 200 OK with RecommendationExplanationResponse payload."""
    mock_user = MagicMock()
    mock_user.id = 1
    mock_get_user.return_value = mock_user

    mock_service_explain.return_value = {
        "recommendation_id": "rec_123",
        "warehouse_id": 1,
        "session_id": "session-10",
        "fingerprint": "abc123sha256hash",
        "action_type": "ANALYZE_TABLE",
        "target": {"schema": "public", "table": "votes"},
        "decision": "PROPOSE",
        "reason_code": "CONDITION_REAPPEARED",
        "decision_reason": "Matching historical recommendation reached ACHIEVED, but condition PRESENT again.",
        "lifecycle_state": "REOPENED",
        "summary": "Recommendation proposed because the current condition is present again.",
        "historical_context": {
            "match_found": True,
            "match_count": 1,
            "previous_final_outcome": "ACHIEVED",
        },
        "current_condition": {
            "condition_state": "PRESENT",
            "condition_type": "MODIFICATIONS_SINCE_ANALYZE",
            "observed_facts": "150 modifications",
        },
        "decision_evidence": [],
        "lifecycle_evidence": [],
        "uncertainty": None,
        "generated_at": "2026-09-26T20:30:00Z",
    }

    headers = {"Authorization": "Bearer test-token"}
    candidate = {"action_type": "ANALYZE_TABLE", "schema": "public", "table": "votes"}

    response = client.post(
        "/warehouses/1/recommendations/explain",
        json=candidate,
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "PROPOSE"
    assert data["lifecycle_state"] == "REOPENED"
    assert data["reason_code"] == "CONDITION_REAPPEARED"
    assert data["fingerprint"] == "abc123sha256hash"
    assert data["summary"] is not None


@patch("app.api.recommendation_history.get_current_user")
@patch("app.api.recommendation_history.RecommendationExplanationService.get_candidate_explanation")
def test_explain_endpoint_forbidden(mock_service_explain, mock_get_user):
    """API returns 403 Forbidden when user does not own target warehouse."""
    mock_user = MagicMock()
    mock_user.id = 1
    mock_get_user.return_value = mock_user

    mock_service_explain.side_effect = PermissionError("Warehouse access denied.")

    headers = {"Authorization": "Bearer test-token"}
    candidate = {"action_type": "ANALYZE_TABLE", "schema": "public", "table": "votes"}

    response = client.post(
        "/warehouses/99/recommendations/explain",
        json=candidate,
        headers=headers,
    )

    assert response.status_code == 403
    assert "access denied" in response.json()["detail"]


@patch("app.api.recommendation_history.get_current_user")
@patch("app.api.recommendation_history.RecommendationExplanationService.get_historical_explanation")
def test_get_explanation_by_id_endpoint(mock_get_historical, mock_get_user):
    """GET /warehouses/{warehouse_id}/recommendations/{recommendation_id}/explanation returns 200 OK."""
    mock_user = MagicMock()
    mock_user.id = 1
    mock_get_user.return_value = mock_user

    mock_get_historical.return_value = {
        "recommendation_id": "rec_999",
        "warehouse_id": 1,
        "fingerprint": "fp_999",
        "action_type": "VACUUM_TABLE",
        "target": {"schema": "public", "table": "orders"},
        "decision": "SUPPRESS",
        "reason_code": "CONDITION_RESOLVED",
        "decision_reason": "Current condition is RESOLVED.",
        "lifecycle_state": "SUPPRESSED",
        "summary": "Recommendation suppressed because condition is resolved.",
        "historical_context": {"match_found": True},
        "current_condition": {"condition_state": "RESOLVED"},
        "decision_evidence": [],
        "lifecycle_evidence": [],
        "uncertainty": None,
        "generated_at": "2026-09-26T20:30:00Z",
    }

    headers = {"Authorization": "Bearer test-token"}

    response = client.get(
        "/warehouses/1/recommendations/rec_999/explanation",
        headers=headers,
        params={"action_type": "VACUUM_TABLE"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["recommendation_id"] == "rec_999"
    assert data["decision"] == "SUPPRESS"
    assert data["lifecycle_state"] == "SUPPRESSED"
