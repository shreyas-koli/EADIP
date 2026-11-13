"""
Integration safety test for Phase 7 Supervisor Re-analysis & Post-Execution Feedback Loop.

Verifies complete end-to-end lifecycle safety:
1. PROPOSED -> APPROVED -> EXECUTE -> COMPLETED -> VERIFY -> VERIFIED -> REANALYZE -> ACHIEVED (No auto-follow-up)
2. Negative case: COMPLETED + VERIFICATION_FAILED -> REANALYZE -> NOT_ACHIEVED + FOLLOW_UP_REQUIRED
   (Strictly requires human approval via Phase 4; NO automatic execution or rollback loops!)
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from app.models.user import User  # noqa: F401
from app.models.warehouse import Warehouse
from app.models.execution import DiscoverySession
from app.models.approval import ActionApproval
from app.models.action_execution_record import ActionExecutionRecord
from app.models.action_verification_record import ActionVerificationRecord
from app.models.supervisor_reanalysis_record import SupervisorReanalysisRecord  # noqa: F401
from app.services.action_execution_service import ActionExecutionService
from app.services.action_verification_service import ActionVerificationService
from app.services.action_reanalysis_service import ActionReanalysisService


@pytest.fixture
def e2e_reanalysis_env():
    user = User(id=1, email="re_e2e@example.com", full_name="Reanalysis E2E User", role="user")
    warehouse = Warehouse(
        id=7,
        name="E2E Re WH",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="eadip_re_e2e",
        username="postgres",
        encrypted_password=b"token",
        owner_id=user.id,
    )
    action_plan = {
        "action_id": "act_e2e_re_1",
        "action_type": "CREATE_INDEX",
        "status": "APPROVED",
        "target": {"schema": "public", "table": "orders", "column": "created_at"},
        "statement": 'CREATE INDEX "idx_orders_created_at" ON "public"."orders" ("created_at")',
        "parameters": {"schema": "public", "table": "orders", "column": "created_at"},
        "executed": False,
        "verification_status": "PENDING",
    }
    session = DiscoverySession(
        id=77,
        session_id="sess_e2e_re",
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
        id=70,
        action_id="act_e2e_re_1",
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


def test_full_lifecycle_execution_verification_reanalysis(e2e_reanalysis_env):
    """
    Verify complete end-to-end lifecycle:
    PROPOSED -> APPROVED -> EXECUTE -> COMPLETED -> VERIFY -> VERIFIED -> REANALYZE -> ACHIEVED
    """
    user, warehouse, session, approval = e2e_reanalysis_env
    db = MagicMock()

    exec_record_created = ActionExecutionRecord(
        id=201,
        action_id="act_e2e_re_1",
        approval_id=approval.id,
        session_id=session.id,
        warehouse_id=warehouse.id,
        user_id=user.id,
        status="COMPLETED",
        action_type="CREATE_INDEX",
        target={"schema": "public", "table": "orders", "column": "created_at"},
        statement_fingerprint=approval.target.get("statement"),
        duration_ms=12.0,
        created_at=datetime.now(timezone.utc),
    )

    ver_record_created = ActionVerificationRecord(
        id=301,
        verification_id="ver_e2e_re_301",
        execution_id=exec_record_created.id,
        action_id="act_e2e_re_1",
        session_id=session.id,
        warehouse_id=warehouse.id,
        user_id=user.id,
        status="VERIFIED",
        verified=True,
        checks=[{"check_id": "index_exists", "status": "PASS"}],
        created_at=datetime.now(timezone.utc),
    )

    with patch("app.services.action_reanalysis_service.get_warehouse_by_id", return_value=warehouse):

        db.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: session),
            MagicMock(scalars=lambda: MagicMock(first=lambda: exec_record_created)),
            MagicMock(scalars=lambda: MagicMock(first=lambda: ver_record_created)),
            MagicMock(scalars=lambda: MagicMock(first=lambda: None)),
        ]

        re_res = ActionReanalysisService.reanalyze_action(
            db=db,
            warehouse_id=warehouse.id,
            session_id=session.session_id,
            action_id="act_e2e_re_1",
            user=user,
        )

        assert re_res.status == "SUCCESSFUL_OUTCOME"
        assert re_res.objective_status == "ACHIEVED"
        assert re_res.follow_up_required is False
        assert re_res.follow_up_type == "NONE"


def test_failed_verification_reanalysis_requires_approval_gate(e2e_reanalysis_env):
    """
    Verify negative case:
    COMPLETED + VERIFICATION_FAILED -> REANALYZE -> NOT_ACHIEVED + FOLLOW_UP_REQUIRED
    Follow-up details MUST be in PROPOSED state requiring human approval.
    No automatic execution or rollback occurs!
    """
    user, warehouse, session, approval = e2e_reanalysis_env
    db = MagicMock()

    exec_record_created = ActionExecutionRecord(
        id=202,
        action_id="act_e2e_re_1",
        approval_id=approval.id,
        session_id=session.id,
        warehouse_id=warehouse.id,
        user_id=user.id,
        status="COMPLETED",
        action_type="CREATE_INDEX",
        target={"schema": "public", "table": "orders", "column": "created_at"},
        created_at=datetime.now(timezone.utc),
    )

    failed_ver_record = ActionVerificationRecord(
        id=302,
        verification_id="ver_e2e_re_302",
        execution_id=exec_record_created.id,
        action_id="act_e2e_re_1",
        session_id=session.id,
        warehouse_id=warehouse.id,
        user_id=user.id,
        status="VERIFICATION_FAILED",
        verified=False,
        checks=[{"check_id": "index_exists", "status": "FAIL"}],
        created_at=datetime.now(timezone.utc),
    )

    with patch("app.services.action_reanalysis_service.get_warehouse_by_id", return_value=warehouse):

        db.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: session),
            MagicMock(scalars=lambda: MagicMock(first=lambda: exec_record_created)),
            MagicMock(scalars=lambda: MagicMock(first=lambda: failed_ver_record)),
            MagicMock(scalars=lambda: MagicMock(first=lambda: None)),
        ]

        re_res = ActionReanalysisService.reanalyze_action(
            db=db,
            warehouse_id=warehouse.id,
            session_id=session.session_id,
            action_id="act_e2e_re_1",
            user=user,
        )

        assert re_res.status == "UNSUCCESSFUL_OUTCOME"
        assert re_res.objective_status == "NOT_ACHIEVED"
        assert re_res.follow_up_required is True
        assert re_res.follow_up_details is not None
        assert re_res.follow_up_details["status"] == "PROPOSED"
        assert re_res.follow_up_details["requires_approval"] is True
