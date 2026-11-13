"""
Integration safety test for Phase 6 Verification Agent & Controlled Verification Engine.

Verifies complete end-to-end lifecycle safety:
1. PROPOSED -> APPROVED -> EXECUTE -> COMPLETED -> VERIFY -> VERIFIED
2. PROPOSED -> APPROVED -> EXECUTE -> FAILED -> VERIFY -> DENIED (ValueError)
3. Unsupported action verification -> INCONCLUSIVE
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from app.models.user import User  # noqa: F401
from app.models.warehouse import Warehouse
from app.models.execution import DiscoverySession
from app.models.approval import ActionApproval
from app.models.action_execution_record import ActionExecutionRecord
from app.models.action_verification_record import ActionVerificationRecord  # noqa: F401
from app.services.action_execution_service import ActionExecutionService
from app.services.action_verification_service import ActionVerificationService


@pytest.fixture
def e2e_environment():
    user = User(id=1, email="ver_e2e@example.com", full_name="E2E Verifier", role="user")
    warehouse = Warehouse(
        id=6,
        name="E2E Ver WH",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="eadip_ver_e2e",
        username="postgres",
        encrypted_password=b"token",
        owner_id=user.id,
    )
    action_plan = {
        "action_id": "act_e2e_ver_1",
        "action_type": "CREATE_INDEX",
        "status": "APPROVED",
        "target": {"schema": "public", "table": "orders", "column": "created_at"},
        "statement": 'CREATE INDEX "idx_orders_created_at" ON "public"."orders" ("created_at")',
        "parameters": {"schema": "public", "table": "orders", "column": "created_at"},
        "executed": False,
        "verification_status": "PENDING",
    }
    session = DiscoverySession(
        id=66,
        session_id="sess_e2e_ver",
        warehouse_id=warehouse.id,
        started_at=datetime.now(timezone.utc),
        status="COMPLETED",
        recommendations={
            "automation": {
                "action_plans": [action_plan]
            }
        },
    )
    approval = ActionApproval(
        id=60,
        action_id="act_e2e_ver_1",
        session_id=session.id,
        warehouse_id=warehouse.id,
        user_id=user.id,
        decision="APPROVE",
        status="APPROVED",
        action_type="CREATE_INDEX",
        target={"schema": "public", "table": "orders", "column": "created_at"},
        created_at=datetime.now(timezone.utc),
    )
    return user, warehouse, session, approval


def test_full_lifecycle_execution_and_verification(e2e_environment):
    """
    Verify complete lifecycle:
    PROPOSED -> APPROVED -> EXECUTE -> COMPLETED -> VERIFY -> VERIFIED
    """
    user, warehouse, session, approval = e2e_environment
    db = MagicMock()

    # Phase 5 Execution Engine result
    exec_engine_res = {
        "success": True,
        "statement": 'CREATE INDEX "idx_orders_created_at" ON "public"."orders" ("created_at")',
        "duration_ms": 15.0,
        "error": None,
    }

    # Phase 6 Verification Engine result
    ver_engine_res = {
        "status": "VERIFIED",
        "verified": True,
        "expected_state": {"index_exists": True},
        "observed_state": {"index_exists": True},
        "checks": [{"check_id": "index_exists", "description": "Index exists", "expected": True, "observed": True, "status": "PASS", "evidence": "Catalog confirmed"}],
        "evidence": ["Catalog confirmed index"],
        "duration_ms": 8.0,
        "error": None,
    }

    exec_record_created = ActionExecutionRecord(
        id=101,
        action_id="act_e2e_ver_1",
        approval_id=approval.id,
        session_id=session.id,
        warehouse_id=warehouse.id,
        user_id=user.id,
        status="COMPLETED",
        action_type="CREATE_INDEX",
        target={"schema": "public", "table": "orders", "column": "created_at"},
        created_at=datetime.now(timezone.utc),
    )

    with patch("app.services.action_execution_service.get_warehouse_by_id", return_value=warehouse), \
         patch("app.warehouse.execution_engine.ControlledExecutionEngine.execute", return_value=exec_engine_res), \
         patch("app.services.action_verification_service.get_warehouse_by_id", return_value=warehouse), \
         patch("app.warehouse.verification_engine.ControlledVerificationEngine.verify", return_value=ver_engine_res):

        # 1. Step 1: Execute Approved Action
        db.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: session),
            MagicMock(scalar_one_or_none=lambda: approval),
        ]

        exec_res = ActionExecutionService.execute_action(
            db=db,
            warehouse_id=warehouse.id,
            session_id=session.session_id,
            action_id="act_e2e_ver_1",
            user=user,
        )

        assert exec_res.status == "COMPLETED"
        assert exec_res.executed is True
        assert exec_res.verification_status == "PENDING"

        # 2. Step 2: Verify Completed Action
        db.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: session),
            MagicMock(scalars=lambda: MagicMock(first=lambda: exec_record_created)),
            MagicMock(scalars=lambda: MagicMock(first=lambda: None)),
        ]

        ver_res = ActionVerificationService.verify_action(
            db=db,
            warehouse_id=warehouse.id,
            session_id=session.session_id,
            action_id="act_e2e_ver_1",
            user=user,
        )

        assert ver_res.status == "VERIFIED"
        assert ver_res.verified is True
        assert ver_res.action_id == "act_e2e_ver_1"
        assert len(ver_res.checks) == 1
        assert ver_res.checks[0].status == "PASS"
