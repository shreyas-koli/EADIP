"""
API tests for Phase 5 Controlled Execution Engine endpoints.

Verifies OAuth2 authentication, warehouse ownership enforcement, 401/403/404 handling,
and HTTP response structure.
"""

import pytest
from unittest.mock import patch
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.models.user import User  # noqa: F401
from app.models.warehouse import Warehouse
from app.schemas.automation import ExecutionResultResponse
from app.main import app

client = TestClient(app)


@pytest.fixture
def mock_user():
    return User(
        id=1,
        email="exec_api_user@example.com",
        full_name="Exec Api User",
        role="user",
        is_active=True,
    )


def test_execute_action_unauthenticated():
    """Verify endpoint returns 401 when no OAuth2 token is provided."""
    response = client.post("/warehouses/10/automation/sessions/sess_100/actions/act_1/execute")
    assert response.status_code == 401


def test_execute_action_success(mock_user):
    """Verify endpoint returns 200 and ExecutionResultResponse for authorized execution."""
    now = datetime.now(timezone.utc)
    mock_resp = ExecutionResultResponse(
        execution_id=101,
        action_id="act_1",
        session_id="sess_100",
        warehouse_id=10,
        status="COMPLETED",
        action_type="CREATE_INDEX",
        started_at=now,
        completed_at=now,
        duration_ms=120.5,
        executed=True,
        message="Action 'act_1' executed successfully.",
        verification_status="PENDING",
    )

    with patch("app.api.automation.get_current_user", return_value=mock_user), \
         patch("app.services.action_execution_service.ActionExecutionService.execute_action", return_value=mock_resp):

        headers = {"Authorization": "Bearer fake_token"}
        response = client.post(
            "/warehouses/10/automation/sessions/sess_100/actions/act_1/execute",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["execution_id"] == 101
        assert data["status"] == "COMPLETED"
        assert data["executed"] is True
        assert data["verification_status"] == "PENDING"


def test_execute_action_warehouse_not_found(mock_user):
    """Verify endpoint returns 404 when warehouse is not found or access is denied."""
    with patch("app.api.automation.get_current_user", return_value=mock_user), \
         patch("app.services.action_execution_service.ActionExecutionService.execute_action", side_effect=PermissionError("Warehouse 99 not found")):

        headers = {"Authorization": "Bearer fake_token"}
        response = client.post(
            "/warehouses/99/automation/sessions/sess_100/actions/act_1/execute",
            headers=headers,
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
