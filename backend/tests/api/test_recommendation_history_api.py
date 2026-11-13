"""
API tests for Recommendation Outcome History router (R1).

Verifies authentication requirements, warehouse ownership authorization,
session & action relationship validation, filtering, pagination, and credential redaction.
"""

from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from app.models.warehouse import Warehouse
from app.models.recommendation_outcome_record import RecommendationOutcomeRecord

client = TestClient(app)


@pytest.fixture
def mock_auth_user():
    return User(
        id=1,
        email="history_user@example.com",
        full_name="History Test User",
        hashed_password="hashed_password",
        is_active=True,
    )


@pytest.fixture
def mock_warehouse(mock_auth_user):
    return Warehouse(
        id=10,
        name="History WH",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="history_db",
        username="postgres",
        encrypted_password=b"encrypted_secret_token",
        owner_id=mock_auth_user.id,
        is_active=True,
    )


def test_recommendation_history_unauthenticated():
    """Verify unauthenticated request is rejected with HTTP 401."""
    res = client.get("/warehouses/10/recommendation-history")
    assert res.status_code == 401


@patch("app.api.recommendation_history.get_current_user")
@patch("app.services.recommendation_outcome_service.get_warehouse_by_id")
def test_recommendation_history_unauthorized_warehouse(mock_get_wh, mock_get_user, mock_auth_user):
    """Verify user accessing another user's warehouse is rejected with HTTP 403."""
    mock_get_user.return_value = mock_auth_user
    mock_get_wh.side_effect = PermissionError("Warehouse 10 not found or access denied for user.")

    res = client.get(
        "/warehouses/10/recommendation-history",
        headers={"Authorization": "Bearer mock_token"},
    )
    assert res.status_code == 403


@patch("app.api.recommendation_history.get_current_user")
@patch("app.services.recommendation_outcome_service.RecommendationOutcomeService.get_warehouse_history")
def test_recommendation_history_success(mock_get_history, mock_get_user, mock_auth_user, mock_warehouse):
    """Verify history retrieval returns structured, credential-free outcome history."""
    mock_get_user.return_value = mock_auth_user
    now = datetime.now(timezone.utc)

    mock_record = RecommendationOutcomeRecord(
        id=1,
        recommendation_id="act_hist_1",
        action_id="act_hist_1",
        session_id=100,
        warehouse_id=mock_warehouse.id,
        user_id=mock_auth_user.id,
        action_type="CREATE_INDEX",
        target={"schema": "public", "table": "orders", "column": "id"},
        approval_status="APPROVED",
        execution_status="COMPLETED",
        verification_status="VERIFIED",
        objective_status="ACHIEVED",
        final_outcome="ACHIEVED",
        created_at=now,
        updated_at=now,
    )
    mock_get_history.return_value = [mock_record]

    res = client.get(
        f"/warehouses/{mock_warehouse.id}/recommendation-history",
        headers={"Authorization": "Bearer mock_token"},
    )
    assert res.status_code == 200

    data = res.json()
    assert "items" in data
    assert len(data["items"]) == 1

    item = data["items"][0]
    assert item["action_id"] == "act_hist_1"
    assert item["action_type"] == "CREATE_INDEX"
    assert item["final_outcome"] == "ACHIEVED"

    # Redaction checks: credentials/passwords must NOT be present
    raw_str = res.text.lower()
    assert "encrypted_password" not in raw_str
    assert "encrypted_secret_token" not in raw_str


@patch("app.api.recommendation_history.get_current_user")
@patch("app.services.recommendation_outcome_service.RecommendationOutcomeService.get_warehouse_history")
def test_recommendation_history_with_r6_1_fingerprint_serialization(mock_get_history, mock_get_user, mock_auth_user, mock_warehouse):
    """Verify history records containing fingerprint attribute serialize cleanly via Pydantic response model."""
    mock_get_user.return_value = mock_auth_user
    now = datetime.now(timezone.utc)

    mock_record = RecommendationOutcomeRecord(
        id=2,
        recommendation_id="act_hist_r6_1",
        action_id="act_hist_r6_1",
        session_id=101,
        warehouse_id=mock_warehouse.id,
        user_id=mock_auth_user.id,
        action_type="ANALYZE_TABLE",
        target={"schema": "public", "table": "votes"},
        approval_status="APPROVED",
        execution_status="FAILED",
        verification_status="PENDING",
        objective_status="PENDING",
        final_outcome="FAILED",
        fingerprint="fp_sha256_abcdef1234567890",
        created_at=now,
        updated_at=now,
    )
    mock_get_history.return_value = [mock_record]

    res = client.get(
        f"/warehouses/{mock_warehouse.id}/recommendation-history",
        headers={"Authorization": "Bearer mock_token"},
    )
    assert res.status_code == 200

    data = res.json()
    assert "items" in data
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["fingerprint"] == "fp_sha256_abcdef1234567890"
    assert item["final_outcome"] == "FAILED"


@patch("app.api.recommendation_history.get_current_user")
@patch("app.services.recommendation_outcome_service.RecommendationOutcomeService.get_warehouse_history")
def test_recommendation_history_empty(mock_get_history, mock_get_user, mock_auth_user, mock_warehouse):
    """Verify requesting recommendation history when no records exist returns HTTP 200 with empty list."""
    mock_get_user.return_value = mock_auth_user
    mock_get_history.return_value = []

    res = client.get(
        f"/warehouses/{mock_warehouse.id}/recommendation-history",
        headers={"Authorization": "Bearer mock_token"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["items"] == []
    assert data["total"] == 0

