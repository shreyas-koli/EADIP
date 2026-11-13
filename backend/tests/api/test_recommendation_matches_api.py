"""
API tests for structural fingerprint matches endpoint GET /warehouses/{warehouse_id}/recommendation-history/matches (R2).

Verifies authentication requirements, warehouse access authorization,
pre-computed fingerprint and candidate query parameter lookups, and multi-match handling.
"""

from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from app.models.warehouse import Warehouse
from app.models.recommendation_outcome_record import RecommendationOutcomeRecord
from app.services.recommendation_fingerprint_service import RecommendationFingerprintService

client = TestClient(app)


@pytest.fixture
def mock_auth_user():
    return User(
        id=1,
        email="matches_user@example.com",
        full_name="Matches Test User",
        hashed_password="hashed_password",
        is_active=True,
    )


@pytest.fixture
def mock_warehouse(mock_auth_user):
    return Warehouse(
        id=20,
        name="Matches WH",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="matches_db",
        username="postgres",
        encrypted_password=b"token",
        owner_id=mock_auth_user.id,
        is_active=True,
    )


def test_recommendation_matches_unauthenticated():
    """Verify unauthenticated matches request is rejected with HTTP 401."""
    res = client.get("/warehouses/20/recommendation-history/matches?action_type=ANALYZE_TABLE&table=votes")
    assert res.status_code == 401


@patch("app.api.recommendation_history.get_current_user")
@patch("app.warehouse.service.get_warehouse_by_id")
def test_recommendation_matches_unauthorized_warehouse(mock_get_wh, mock_get_user, mock_auth_user):
    """Verify cross-warehouse access is rejected with HTTP 403."""
    mock_get_user.return_value = mock_auth_user
    mock_get_wh.return_value = None

    res = client.get(
        "/warehouses/20/recommendation-history/matches?action_type=ANALYZE_TABLE&table=votes",
        headers={"Authorization": "Bearer mock_token"},
    )
    assert res.status_code == 403


@patch("app.api.recommendation_history.get_current_user")
@patch("app.warehouse.service.get_warehouse_by_id")
@patch("app.services.recommendation_fingerprint_service.RecommendationFingerprintService.find_historical_matches")
def test_recommendation_matches_success(
    mock_find_matches, mock_get_wh, mock_get_user, mock_auth_user, mock_warehouse
):
    """Verify matching historical records are retrieved by candidate attributes."""
    mock_get_user.return_value = mock_auth_user
    mock_get_wh.return_value = mock_warehouse

    now = datetime.now(timezone.utc)
    fp = RecommendationFingerprintService.generate_fingerprint(
        action_type="ANALYZE_TABLE", schema="public", table="votes"
    )

    rec1 = RecommendationOutcomeRecord(
        id=1,
        recommendation_id="act_v1",
        action_id="act_v1",
        session_id=10,
        warehouse_id=mock_warehouse.id,
        action_type="ANALYZE_TABLE",
        target={"schema": "public", "table": "votes"},
        approval_status="APPROVED",
        execution_status="COMPLETED",
        verification_status="VERIFIED",
        objective_status="ACHIEVED",
        final_outcome="ACHIEVED",
        fingerprint=fp,
        created_at=now,
        updated_at=now,
    )
    rec2 = RecommendationOutcomeRecord(
        id=2,
        recommendation_id="act_v2",
        action_id="act_v2",
        session_id=20,
        warehouse_id=mock_warehouse.id,
        action_type="ANALYZE_TABLE",
        target={"schema": "public", "table": "votes"},
        approval_status="APPROVED",
        execution_status="COMPLETED",
        verification_status="VERIFICATION_FAILED",
        objective_status="NOT_ACHIEVED",
        final_outcome="NOT_ACHIEVED",
        fingerprint=fp,
        created_at=now,
        updated_at=now,
    )

    mock_find_matches.return_value = [rec2, rec1]

    res = client.get(
        f"/warehouses/{mock_warehouse.id}/recommendation-history/matches?action_type=ANALYZE_TABLE&schema=public&table=votes",
        headers={"Authorization": "Bearer mock_token"},
    )
    assert res.status_code == 200

    data = res.json()
    assert data["fingerprint"] == fp
    assert data["match_found"] is True
    assert data["match_count"] == 2
    assert len(data["matches"]) == 2
    assert data["matches"][0]["final_outcome"] == "NOT_ACHIEVED"
    assert data["matches"][1]["final_outcome"] == "ACHIEVED"
