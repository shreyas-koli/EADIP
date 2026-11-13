"""
Focused unit tests for Phase 4 SSE approval telemetry integration.

Verifies that action_approved, action_rejected, and approval_state_changed events
are emitted through the telemetry architecture when user decisions are recorded.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from app.models.user import User  # noqa: F401
from app.models.warehouse import Warehouse
from app.models.execution import DiscoverySession
from app.context.shared_context import SharedContext
from app.services.automation_service import AutomationService
from app.schemas.automation import ApprovalRequest


@pytest.fixture
def mock_user():
    return User(
        id=5,
        email="sse_user@example.com",
        full_name="SSE Tester",
        role="user",
        is_active=True,
    )


@pytest.fixture
def mock_warehouse(mock_user):
    return Warehouse(
        id=77,
        name="Telemetry WH",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="eadip_telemetry",
        username="postgres",
        encrypted_password=b"token",
        owner_id=mock_user.id,
    )


@pytest.fixture
def mock_session(mock_warehouse):
    return DiscoverySession(
        id=770,
        session_id="sess_telemetry_1",
        warehouse_id=mock_warehouse.id,
        started_at=datetime.now(timezone.utc),
        status="COMPLETED",
        recommendations={
            "automation": {
                "action_plans": [
                    {
                        "action_id": "act_sse_99",
                        "action_type": "CREATE_INDEX",
                        "status": "PROPOSED",
                        "statement": 'CREATE INDEX "idx_sse" ON "public"."test" ("col")',
                        "executed": False,
                    }
                ]
            }
        },
    )


def test_approve_emits_action_approved_and_approval_state_changed_events(mock_user, mock_warehouse, mock_session):
    """Verify approving an action plan broadcasts 'action_approved' and 'approval_state_changed' SSE events."""
    db = MagicMock()
    emitted_events = []

    def capture_event(ev_data):
        emitted_events.append(dict(ev_data))

    SharedContext.register_listener(capture_event)

    try:
        with patch("app.services.automation_service.get_warehouse_by_id", return_value=mock_warehouse):
            db.execute.side_effect = [
                MagicMock(scalar_one_or_none=lambda: mock_session),
                MagicMock(scalar_one_or_none=lambda: None),
            ]

            response = AutomationService.approve_action(
                db=db,
                warehouse_id=mock_warehouse.id,
                session_id=mock_session.session_id,
                action_id="act_sse_99",
                user=mock_user,
            )

            assert response.status == "APPROVED"

            # Check emitted SSE events
            event_types = [e.get("event") for e in emitted_events]
            assert "action_approved" in event_types
            assert "approval_state_changed" in event_types

            approved_ev = next(e for e in emitted_events if e["event"] == "action_approved")
            assert approved_ev["action_id"] == "act_sse_99"
            assert approved_ev["warehouse_id"] == 77
            assert approved_ev["session_id"] == "sess_telemetry_1"
            assert approved_ev["approved_by"] == "sse_user@example.com"
            assert approved_ev["status"] == "APPROVED"

            state_ev = next(e for e in emitted_events if e["event"] == "approval_state_changed")
            assert state_ev["action_id"] == "act_sse_99"
            assert state_ev["status"] == "APPROVED"
            assert state_ev["decision"] == "APPROVE"
            assert state_ev["user_id"] == 5
    finally:
        SharedContext.unregister_listener(capture_event)


def test_reject_emits_action_rejected_and_approval_state_changed_events(mock_user, mock_warehouse, mock_session):
    """Verify rejecting an action plan broadcasts 'action_rejected' and 'approval_state_changed' SSE events."""
    db = MagicMock()
    emitted_events = []

    def capture_event(ev_data):
        emitted_events.append(dict(ev_data))

    SharedContext.register_listener(capture_event)

    try:
        with patch("app.services.automation_service.get_warehouse_by_id", return_value=mock_warehouse):
            db.execute.side_effect = [
                MagicMock(scalar_one_or_none=lambda: mock_session),
                MagicMock(scalar_one_or_none=lambda: None),
            ]

            payload = ApprovalRequest(reason="Performance impact too high")
            response = AutomationService.reject_action(
                db=db,
                warehouse_id=mock_warehouse.id,
                session_id=mock_session.session_id,
                action_id="act_sse_99",
                user=mock_user,
                payload=payload,
            )

            assert response.status == "REJECTED"

            event_types = [e.get("event") for e in emitted_events]
            assert "action_rejected" in event_types
            assert "approval_state_changed" in event_types

            rejected_ev = next(e for e in emitted_events if e["event"] == "action_rejected")
            assert rejected_ev["action_id"] == "act_sse_99"
            assert rejected_ev["warehouse_id"] == 77
            assert rejected_ev["rejected_by"] == "sse_user@example.com"
            assert rejected_ev["status"] == "REJECTED"
            assert rejected_ev["reason"] == "Performance impact too high"

            state_ev = next(e for e in emitted_events if e["event"] == "approval_state_changed")
            assert state_ev["action_id"] == "act_sse_99"
            assert state_ev["status"] == "REJECTED"
            assert state_ev["decision"] == "REJECT"
    finally:
        SharedContext.unregister_listener(capture_event)
