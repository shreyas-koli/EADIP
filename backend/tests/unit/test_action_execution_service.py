"""
Unit tests for ActionExecutionService (Phase 5 Controlled Execution Engine).

Verifies authorization re-validation, approval checking, action integrity checks,
PROPOSED/REJECTED execution blocks, idempotency, and SSE event broadcasting.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from app.models.user import User  # noqa: F401
from app.models.warehouse import Warehouse
from app.models.execution import DiscoverySession
from app.models.approval import ActionApproval
from app.models.action_execution_record import ActionExecutionRecord  # noqa: F401
from app.services.action_execution_service import ActionExecutionService
from app.context.shared_context import SharedContext


@pytest.fixture
def mock_user():
    return User(
        id=1,
        email="exec_user@example.com",
        full_name="Exec User",
        role="user",
        is_active=True,
    )


@pytest.fixture
def mock_warehouse(mock_user):
    return Warehouse(
        id=10,
        name="Exec WH",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="eadip_exec",
        username="postgres",
        encrypted_password=b"token",
        owner_id=mock_user.id,
    )


@pytest.fixture
def sample_action_plan():
    return {
        "action_id": "act_exec_001",
        "action_type": "CREATE_INDEX",
        "status": "APPROVED",
        "target": {"schema": "public", "table": "orders", "column": "created_at"},
        "statement": 'CREATE INDEX "idx_orders_created_at" ON "public"."orders" ("created_at")',
        "parameters": {"schema": "public", "table": "orders", "column": "created_at"},
        "executed": False,
    }


@pytest.fixture
def mock_session(mock_warehouse, sample_action_plan):
    return DiscoverySession(
        id=100,
        session_id="sess_exec_001",
        warehouse_id=mock_warehouse.id,
        started_at=datetime.now(timezone.utc),
        status="COMPLETED",
        recommendations={
            "automation": {
                "action_plans": [sample_action_plan]
            }
        },
    )


@pytest.fixture
def mock_approval(mock_warehouse, mock_session, mock_user):
    return ActionApproval(
        id=50,
        action_id="act_exec_001",
        session_id=mock_session.id,
        warehouse_id=mock_warehouse.id,
        user_id=mock_user.id,
        decision="APPROVE",
        status="APPROVED",
        action_type="CREATE_INDEX",
        target={"schema": "public", "table": "orders", "column": "created_at"},
        created_at=datetime.now(timezone.utc),
    )


def test_execute_proposed_action_fails(mock_user, mock_warehouse, mock_session):
    """Verify attempting to execute a PROPOSED (un-approved) action plan raises ValueError."""
    mock_session.recommendations["automation"]["action_plans"][0]["status"] = "PROPOSED"
    db = MagicMock()

    with patch("app.services.action_execution_service.get_warehouse_by_id", return_value=mock_warehouse):
        db.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: mock_session),
            MagicMock(scalar_one_or_none=lambda: None),  # No approval record in DB
        ]

        with pytest.raises(ValueError, match="Only APPROVED actions can be executed"):
            ActionExecutionService.execute_action(
                db=db,
                warehouse_id=mock_warehouse.id,
                session_id=mock_session.session_id,
                action_id="act_exec_001",
                user=mock_user,
            )


def test_execute_rejected_action_fails(mock_user, mock_warehouse, mock_session):
    """Verify attempting to execute a REJECTED action plan raises ValueError."""
    rejected_approval = ActionApproval(
        id=51,
        action_id="act_exec_001",
        session_id=mock_session.id,
        warehouse_id=mock_warehouse.id,
        user_id=mock_user.id,
        decision="REJECT",
        status="REJECTED",
    )
    db = MagicMock()

    with patch("app.services.action_execution_service.get_warehouse_by_id", return_value=mock_warehouse):
        db.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: mock_session),
            MagicMock(scalar_one_or_none=lambda: rejected_approval),
        ]

        with pytest.raises(ValueError, match="status is 'REJECTED'"):
            ActionExecutionService.execute_action(
                db=db,
                warehouse_id=mock_warehouse.id,
                session_id=mock_session.session_id,
                action_id="act_exec_001",
                user=mock_user,
            )


def test_execute_approved_action_success(mock_user, mock_warehouse, mock_session, mock_approval):
    """Verify executing an APPROVED action invokes execution engine and broadcasts SSE events."""
    db = MagicMock()
    emitted_events = []

    def capture_event(ev):
        emitted_events.append(dict(ev))

    SharedContext.register_listener(capture_event)

    exec_result = {
        "success": True,
        "statement": 'CREATE INDEX "idx_orders_created_at" ON "public"."orders" ("created_at")',
        "duration_ms": 45.2,
        "error": None,
    }

    try:
        with patch("app.services.action_execution_service.get_warehouse_by_id", return_value=mock_warehouse), \
             patch("app.warehouse.execution_engine.ControlledExecutionEngine.execute", return_value=exec_result):

            db.execute.side_effect = [
                MagicMock(scalar_one_or_none=lambda: mock_session),
                MagicMock(scalar_one_or_none=lambda: mock_approval),
            ]

            res = ActionExecutionService.execute_action(
                db=db,
                warehouse_id=mock_warehouse.id,
                session_id=mock_session.session_id,
                action_id="act_exec_001",
                user=mock_user,
            )

            assert res.status == "COMPLETED"
            assert res.executed is True
            assert res.verification_status == "PENDING"
            assert res.duration_ms == 45.2

            # Check SSE events emitted
            event_types = [e.get("event") for e in emitted_events]
            assert "action_execution_started" in event_types
            assert "action_execution_completed" in event_types
            assert "execution_state_changed" in event_types
    finally:
        SharedContext.unregister_listener(capture_event)


def test_execute_already_completed_action_is_idempotent(mock_user, mock_warehouse, mock_session, mock_approval):
    """Verify executing an already COMPLETED action plan returns idempotent response without re-executing."""
    mock_session.recommendations["automation"]["action_plans"][0]["executed"] = True
    mock_session.recommendations["automation"]["action_plans"][0]["status"] = "COMPLETED"
    db = MagicMock()

    with patch("app.services.action_execution_service.get_warehouse_by_id", return_value=mock_warehouse), \
         patch("app.warehouse.execution_engine.ControlledExecutionEngine.execute") as mock_engine:

        db.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: mock_session),
            MagicMock(scalar_one_or_none=lambda: mock_approval),
        ]

        res = ActionExecutionService.execute_action(
            db=db,
            warehouse_id=mock_warehouse.id,
            session_id=mock_session.session_id,
            action_id="act_exec_001",
            user=mock_user,
        )

        assert res.status == "COMPLETED"
        assert res.executed is True
        assert not mock_engine.called


def test_execute_analyze_table_success(mock_user, mock_warehouse, mock_session, mock_approval):
    """Verify successful ANALYZE_TABLE action execution marks state COMPLETED and verification_status PENDING."""
    analyze_plan = {
        "action_id": "act_exec_analyze_01",
        "action_type": "ANALYZE_TABLE",
        "status": "APPROVED",
        "target": {"schema": "public", "table": "votes"},
        "statement": 'ANALYZE "public"."votes"',
        "parameters": {"schema": "public", "table": "votes"},
        "executed": False,
    }
    mock_session.recommendations["automation"]["action_plans"] = [analyze_plan]
    mock_approval.action_id = "act_exec_analyze_01"
    mock_approval.action_type = "ANALYZE_TABLE"
    mock_approval.target = {"schema": "public", "table": "votes"}

    db = MagicMock()
    exec_result = {
        "success": True,
        "statement": 'ANALYZE "public"."votes"',
        "duration_ms": 12.5,
        "error": None,
    }

    with patch("app.services.action_execution_service.get_warehouse_by_id", return_value=mock_warehouse), \
         patch("app.warehouse.execution_engine.ControlledExecutionEngine.execute", return_value=exec_result):

        db.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: mock_session),
            MagicMock(scalar_one_or_none=lambda: mock_approval),
        ]

        res = ActionExecutionService.execute_action(
            db=db,
            warehouse_id=mock_warehouse.id,
            session_id=mock_session.session_id,
            action_id="act_exec_analyze_01",
            user=mock_user,
        )

        assert res.status == "COMPLETED"
        assert res.executed is True
        assert res.verification_status == "PENDING"
        assert res.duration_ms == 12.5


def test_execute_analyze_table_failure(mock_user, mock_warehouse, mock_session, mock_approval):
    """Verify failed ANALYZE_TABLE action execution preserves FAILED state and error message without raising unhandled exception."""
    analyze_plan = {
        "action_id": "act_exec_analyze_02",
        "action_type": "ANALYZE_TABLE",
        "status": "APPROVED",
        "target": {"schema": "public", "table": "votes"},
        "statement": 'ANALYZE "public"."votes"',
        "parameters": {"schema": "public", "table": "votes"},
        "executed": False,
    }
    mock_session.recommendations["automation"]["action_plans"] = [analyze_plan]
    mock_approval.action_id = "act_exec_analyze_02"
    mock_approval.action_type = "ANALYZE_TABLE"
    mock_approval.target = {"schema": "public", "table": "votes"}

    db = MagicMock()
    exec_result = {
        "success": False,
        "statement": 'ANALYZE "public"."votes"',
        "duration_ms": 5.0,
        "error": "Failed to decrypt warehouse credentials (WAREHOUSE_CREDENTIALS_INVALID_TOKEN)",
    }

    with patch("app.services.action_execution_service.get_warehouse_by_id", return_value=mock_warehouse), \
         patch("app.warehouse.execution_engine.ControlledExecutionEngine.execute", return_value=exec_result):

        db.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: mock_session),
            MagicMock(scalar_one_or_none=lambda: mock_approval),
        ]

        res = ActionExecutionService.execute_action(
            db=db,
            warehouse_id=mock_warehouse.id,
            session_id=mock_session.session_id,
            action_id="act_exec_analyze_02",
            user=mock_user,
        )

        assert res.status == "FAILED"
        assert res.executed is False
        assert "WAREHOUSE_CREDENTIALS_INVALID_TOKEN" in res.error_message
        assert res.verification_status == "PENDING"

