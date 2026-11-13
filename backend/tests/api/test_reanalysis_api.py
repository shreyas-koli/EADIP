"""
API endpoint tests for Phase 7 Supervisor Re-analysis API endpoints.

Tests POST /warehouses/{warehouse_id}/automation/sessions/{session_id}/actions/{action_id}/reanalyze
and GET /warehouses/{warehouse_id}/automation/sessions/{session_id}/actions/{action_id}/reanalysis.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User  # noqa: F401
from app.schemas.automation import SupervisorReanalysisResponse

client = TestClient(app)


@pytest.fixture
def mock_auth_user():
    user = MagicMock()
    user.id = 1
    user.email = "api_re_user@example.com"
    user.full_name = "API Reanalysis User"
    return user


def test_reanalyze_action_unauthenticated():
    """Verify reanalyze endpoint returns 401 when no token is supplied."""
    response = client.post("/warehouses/1/automation/sessions/sess_123/actions/act_001/reanalyze")
    assert response.status_code == 401


def test_reanalyze_action_success(mock_auth_user):
    """Verify POST reanalyze endpoint returns 200 with structured SupervisorReanalysisResponse."""
    mock_resp = SupervisorReanalysisResponse(
        reanalysis_id="re_abc123",
        execution_id=99,
        verification_id=88,
        action_id="act_001",
        session_id="sess_123",
        warehouse_id=1,
        status="SUCCESSFUL_OUTCOME",
        objective_status="ACHIEVED",
        action_type="CREATE_INDEX",
        before_state={"table": "orders"},
        after_state={"execution_status": "COMPLETED", "verification_status": "VERIFIED"},
        comparisons=[{
            "metric": "structural_catalog_state",
            "before": "UNVERIFIED",
            "after": "VERIFIED",
            "status": "MATCH",
            "evidence": "Confirmed",
        }],
        findings=["Structural objective achieved"],
        conclusion="Action executed and verified successfully.",
        follow_up_required=False,
        follow_up_type="NONE",
        started_at="2026-09-20T18:00:00Z",
        completed_at="2026-09-20T18:00:01Z",
        duration_ms=12.0,
        message="Supervisor re-analysis completed",
    )

    with patch("app.api.automation.get_current_user", return_value=mock_auth_user), \
         patch("app.api.automation.ActionReanalysisService.reanalyze_action", return_value=mock_resp):

        response = client.post(
            "/warehouses/1/automation/sessions/sess_123/actions/act_001/reanalyze",
            headers={"Authorization": "Bearer fake-jwt-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["reanalysis_id"] == "re_abc123"
        assert data["status"] == "SUCCESSFUL_OUTCOME"
        assert data["objective_status"] == "ACHIEVED"
        assert data["follow_up_required"] is False
