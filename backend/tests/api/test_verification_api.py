"""
API endpoint tests for Phase 6 Verification API endpoints.

Tests POST /warehouses/{warehouse_id}/automation/sessions/{session_id}/actions/{action_id}/verify
and GET /warehouses/{warehouse_id}/automation/sessions/{session_id}/actions/{action_id}/verification.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User  # noqa: F401
from app.models.warehouse import Warehouse
from app.schemas.automation import VerificationResultResponse

client = TestClient(app)


@pytest.fixture
def mock_auth_user():
    user = MagicMock()
    user.id = 1
    user.email = "api_user@example.com"
    user.full_name = "API User"
    return user


def test_verify_action_unauthenticated():
    """Verify endpoint returns 401 when no token is supplied."""
    response = client.post("/warehouses/1/automation/sessions/sess_123/actions/act_001/verify")
    assert response.status_code == 401


def test_verify_action_success(mock_auth_user):
    """Verify POST verify endpoint returns 200 with structured VerificationResultResponse."""
    mock_resp = VerificationResultResponse(
        verification_id="ver_abc123",
        execution_id=99,
        action_id="act_001",
        session_id="sess_123",
        warehouse_id=1,
        status="VERIFIED",
        verified=True,
        action_type="CREATE_INDEX",
        expected_state={"index_exists": True},
        observed_state={"index_exists": True},
        evidence=["Index found in catalog"],
        checks=[{
            "check_id": "index_existence",
            "description": "Index exists",
            "expected": True,
            "observed": True,
            "status": "PASS",
            "evidence": "Found in pg_indexes",
        }],
        started_at="2026-09-20T18:00:00Z",
        completed_at="2026-09-20T18:00:01Z",
        duration_ms=10.0,
        message="Verification completed",
    )

    with patch("app.api.automation.get_current_user", return_value=mock_auth_user), \
         patch("app.api.automation.ActionVerificationService.verify_action", return_value=mock_resp):

        response = client.post(
            "/warehouses/1/automation/sessions/sess_123/actions/act_001/verify",
            headers={"Authorization": "Bearer fake-jwt-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["verification_id"] == "ver_abc123"
        assert data["status"] == "VERIFIED"
        assert data["verified"] is True
        assert len(data["checks"]) == 1


def test_verify_action_warehouse_not_found(mock_auth_user):
    """Verify endpoint returns 404 when warehouse does not exist or user lacks access."""
    with patch("app.api.automation.get_current_user", return_value=mock_auth_user), \
         patch("app.api.automation.ActionVerificationService.verify_action", side_effect=PermissionError("Warehouse not found")):

        response = client.post(
            "/warehouses/999/automation/sessions/sess_123/actions/act_001/verify",
            headers={"Authorization": "Bearer fake-jwt-token"},
        )

        assert response.status_code == 404
