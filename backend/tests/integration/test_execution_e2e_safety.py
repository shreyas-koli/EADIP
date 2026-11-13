"""
Integration safety test for Phase 5 Controlled Execution Engine.

Verifies complete lifecycle safety:
1. PROPOSED -> APPROVED -> EXECUTE -> COMPLETED
2. PROPOSED -> REJECTED -> EXECUTE -> DENIED (zero warehouse execution)
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from app.models.user import User  # noqa: F401
from app.models.warehouse import Warehouse
from app.models.execution import DiscoverySession
from app.models.approval import ActionApproval
from app.services.automation_service import AutomationService
from app.services.action_execution_service import ActionExecutionService


@pytest.fixture
def test_environment():
    user = User(id=1, email="safety@example.com", full_name="Safety Tester", role="user")
    warehouse = Warehouse(
        id=5,
        name="Safety WH",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="eadip_safety",
        username="postgres",
        encrypted_password=b"token",
        owner_id=user.id,
    )
    session = DiscoverySession(
        id=55,
        session_id="sess_e2e_safety",
        warehouse_id=warehouse.id,
        started_at=datetime.now(timezone.utc),
        status="COMPLETED",
        recommendations={
            "automation": {
                "action_plans": [
                    {
                        "action_id": "act_e2e_1",
                        "action_type": "ANALYZE_TABLE",
                        "status": "PROPOSED",
                        "target": {"schema": "public", "table": "orders"},
                        "statement": 'ANALYZE "public"."orders"',
                        "executed": False,
                    }
                ]
            }
        },
    )
    return user, warehouse, session


def test_rejected_action_execution_denied(test_environment):
    """Verify that a REJECTED action plan cannot be executed under any circumstances."""
    user, warehouse, session = test_environment
    rejected_approval = ActionApproval(
        id=10,
        action_id="act_e2e_1",
        session_id=session.id,
        warehouse_id=warehouse.id,
        user_id=user.id,
        decision="REJECT",
        status="REJECTED",
        target={"schema": "public", "table": "orders"},
    )
    session.recommendations["automation"]["action_plans"][0]["status"] = "REJECTED"

    db = MagicMock()
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: session),
        MagicMock(scalar_one_or_none=lambda: rejected_approval),
    ]

    with patch("app.services.action_execution_service.get_warehouse_by_id", return_value=warehouse), \
         patch("app.warehouse.connector.WarehouseConnector.connect") as mock_conn:

        with pytest.raises(ValueError, match="Only APPROVED actions can be executed"):
            ActionExecutionService.execute_action(
                db=db,
                warehouse_id=warehouse.id,
                session_id=session.session_id,
                action_id="act_e2e_1",
                user=user,
            )

        # Assert target warehouse connection was NEVER attempted
        assert not mock_conn.called


def test_approved_action_execution_lifecycle(test_environment):
    """Verify end-to-end flow: APPROVED action plan executes cleanly and records COMPLETED + PENDING verification."""
    user, warehouse, session = test_environment
    approved_approval = ActionApproval(
        id=12,
        action_id="act_e2e_1",
        session_id=session.id,
        warehouse_id=warehouse.id,
        user_id=user.id,
        decision="APPROVE",
        status="APPROVED",
        action_type="ANALYZE_TABLE",
        target={"schema": "public", "table": "orders"},
    )
    session.recommendations["automation"]["action_plans"][0]["status"] = "APPROVED"

    db = MagicMock()
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: session),
        MagicMock(scalar_one_or_none=lambda: approved_approval),
    ]

    exec_result = {
        "success": True,
        "statement": 'ANALYZE "public"."orders"',
        "duration_ms": 12.4,
        "error": None,
    }

    with patch("app.services.action_execution_service.get_warehouse_by_id", return_value=warehouse), \
         patch("app.warehouse.execution_engine.ControlledExecutionEngine.execute", return_value=exec_result):

        res = ActionExecutionService.execute_action(
            db=db,
            warehouse_id=warehouse.id,
            session_id=session.session_id,
            action_id="act_e2e_1",
            user=user,
        )

        assert res.status == "COMPLETED"
        assert res.executed is True
        assert res.verification_status == "PENDING"
        assert session.recommendations["automation"]["action_plans"][0]["status"] == "COMPLETED"
        assert session.recommendations["automation"]["action_plans"][0]["executed"] is True
