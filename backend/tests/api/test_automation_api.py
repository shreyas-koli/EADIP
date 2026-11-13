"""
API tests for Automation & User Approval Gate endpoints (Phase 4).

Verifies OAuth2 authentication, warehouse ownership enforcement, 401/403/404 handling,
and structured approval/rejection HTTP responses.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.models.user import User  # noqa: F401
from app.models.warehouse import Warehouse
from app.models.execution import DiscoverySession
from app.schemas.automation import ApprovalResponse
from app.main import app

client = TestClient(app)


@pytest.fixture
def mock_user():
    return User(
        id=1,
        email="owner@example.com",
        full_name="Owner",
        role="user",
        is_active=True,
    )


@pytest.fixture
def mock_warehouse(mock_user):
    return Warehouse(
        id=42,
        name="Benchmark Warehouse",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="eadip_benchmark",
        username="postgres",
        encrypted_password=b"faketoken",
        owner_id=mock_user.id,
    )


def test_approve_action_unauthenticated():
    """Verify endpoint returns 401 when no token is provided."""
    response = client.post("/warehouses/42/automation/sessions/sess_123/actions/act_1/approve")
    assert response.status_code == 401


def test_approve_action_success(mock_user, mock_warehouse):
    """Verify endpoint successfully records approval for authorized user."""
    mock_resp = ApprovalResponse(
        action_id="act_1",
        session_id="sess_123",
        warehouse_id=42,
        status="APPROVED",
        decision="APPROVE",
        approved_by="owner@example.com",
        approved_at="2026-09-20T17:00:00Z",
        executed=False,
        reason=None,
        message="Action 'act_1' approved.",
    )

    with patch("app.api.automation.get_current_user", return_value=mock_user), \
         patch("app.services.automation_service.AutomationService.approve_action", return_value=mock_resp):
        
        headers = {"Authorization": "Bearer fake_valid_token"}
        response = client.post(
            "/warehouses/42/automation/sessions/sess_123/actions/act_1/approve",
            headers=headers,
            json={"reason": "Looks good"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["action_id"] == "act_1"
        assert data["status"] == "APPROVED"
        assert data["executed"] is False


def test_reject_action_success(mock_user, mock_warehouse):
    """Verify endpoint successfully records rejection for authorized user."""
    mock_resp = ApprovalResponse(
        action_id="act_1",
        session_id="sess_123",
        warehouse_id=42,
        status="REJECTED",
        decision="REJECT",
        approved_by="owner@example.com",
        approved_at="2026-09-20T17:00:00Z",
        executed=False,
        reason="Not desired right now",
        message="Action 'act_1' rejected.",
    )

    with patch("app.api.automation.get_current_user", return_value=mock_user), \
         patch("app.services.automation_service.AutomationService.reject_action", return_value=mock_resp):
        
        headers = {"Authorization": "Bearer fake_valid_token"}
        response = client.post(
            "/warehouses/42/automation/sessions/sess_123/actions/act_1/reject",
            headers=headers,
            json={"reason": "Not desired right now"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["action_id"] == "act_1"
        assert data["status"] == "REJECTED"
        assert data["executed"] is False
        assert data["reason"] == "Not desired right now"


def test_approve_action_warehouse_not_found(mock_user):
    """Verify 404 response when user attempts to approve action for an unauthorized/nonexistent warehouse."""
    with patch("app.api.automation.get_current_user", return_value=mock_user), \
         patch("app.services.automation_service.AutomationService.approve_action", side_effect=PermissionError("Warehouse 999 not found")):
        
        headers = {"Authorization": "Bearer fake_valid_token"}
        response = client.post(
            "/warehouses/999/automation/sessions/sess_123/actions/act_1/approve",
            headers=headers,
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
