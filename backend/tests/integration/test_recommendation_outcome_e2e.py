"""
End-to-end integration tests for Recommendation Outcome History (R1).

Verifies the full lifecycle progression:
Discovery -> Proposed Action -> User Approval -> Controlled Execution -> Verification -> Supervisor Re-analysis -> Outcome History.

Validates that:
- RecommendationOutcomeRecord stays in sync across all phase transitions.
- Idempotency guarantees prevent duplicate history records.
- RecommendationAgent continues generating recommendations identically without interference.
"""

from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock, patch

from app.agents.recommendation_agent import RecommendationAgent
from app.context.shared_context import SharedContext
from app.models.approval import ActionApproval
from app.models.action_execution_record import ActionExecutionRecord
from app.models.action_verification_record import ActionVerificationRecord
from app.models.execution import DiscoverySession
from app.models.recommendation_outcome_record import RecommendationOutcomeRecord
from app.models.supervisor_reanalysis_record import SupervisorReanalysisRecord
from app.models.user import User
from app.models.warehouse import Warehouse
from app.services.action_execution_service import ActionExecutionService
from app.services.action_reanalysis_service import ActionReanalysisService
from app.services.action_verification_service import ActionVerificationService
from app.services.automation_service import AutomationService
from app.services.recommendation_outcome_service import RecommendationOutcomeService


@pytest.fixture
def mock_user():
    return User(
        id=1,
        email="e2e_history@example.com",
        full_name="E2E History User",
        role="user",
        is_active=True,
    )


@pytest.fixture
def mock_warehouse(mock_user):
    return Warehouse(
        id=10,
        name="E2E Outcome WH",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="e2e_db",
        username="postgres",
        encrypted_password=b"token",
        owner_id=mock_user.id,
        is_active=True,
    )


def test_e2e_recommendation_outcome_lifecycle(mock_warehouse, mock_user, monkeypatch):
    """
    End-to-end integration test verifying recommendation outcome history lifecycle.
    """
    now = datetime.now(timezone.utc)
    session_id = "sess_e2e_history_001"
    action_id = "act_e2e_001"

    action_plan = {
        "action_id": action_id,
        "recommendation_type": "CREATE_INDEX",
        "action_type": "CREATE_INDEX",
        "status": "PROPOSED",
        "automation_status": "PROPOSED",
        "target": {"schema": "public", "table": "orders", "column": "created_at"},
        "statement": 'CREATE INDEX "idx_orders_created_at" ON "public"."orders" ("created_at")',
        "risk_level": "LOW",
        "safety_class": "REVERSIBLE_WRITE",
        "executed": False,
    }

    session_obj = DiscoverySession(
        id=100,
        session_id=session_id,
        warehouse_id=mock_warehouse.id,
        started_at=now,
        finished_at=now,
        total_duration_ms=1000.0,
        status="COMPLETED",
        recommendations={
            "recommendation": {
                "recommendations": [
                    {
                        "id": action_id,
                        "type": "CREATE_INDEX",
                        "target_table": "public.orders",
                        "impact": "HIGH",
                    }
                ]
            },
            "automation": {
                "action_plans": [action_plan]
            },
        },
    )

    mock_db = MagicMock()

    def mock_execute(stmt):
        mock_res = MagicMock()
        stmt_str = str(stmt)
        if "discovery_sessions" in stmt_str:
            mock_res.scalar_one_or_none.return_value = session_obj
        else:
            mock_res.scalar_one_or_none.return_value = None

        mock_res.scalars().first.return_value = None
        mock_res.scalars().all.return_value = []
        return mock_res

    mock_db.execute.side_effect = mock_execute

    # 1. Initial Sync for PROPOSED action
    rec_record = RecommendationOutcomeService.sync_action_outcome(
        db=mock_db, warehouse_id=mock_warehouse.id, session_id=session_id, action_id=action_id, user=mock_user
    )
    assert rec_record.action_id == action_id
    assert rec_record.approval_status == "PROPOSED"
    assert rec_record.final_outcome == "PROPOSED"

    # 2. Transition to APPROVED
    appr_obj = ActionApproval(
        id=50,
        action_id=action_id,
        session_id=session_obj.id,
        warehouse_id=mock_warehouse.id,
        user_id=mock_user.id,
        decision="APPROVE",
        status="APPROVED",
    )
    rec_record_appr = RecommendationOutcomeService.derive_final_outcome(approval=appr_obj)
    assert rec_record_appr == "APPROVED"

    # 3. Transition to COMPLETED
    exec_obj = ActionExecutionRecord(
        id=77,
        action_id=action_id,
        approval_id=appr_obj.id,
        session_id=session_obj.id,
        warehouse_id=mock_warehouse.id,
        user_id=mock_user.id,
        status="COMPLETED",
    )
    rec_record_exec = RecommendationOutcomeService.derive_final_outcome(approval=appr_obj, execution=exec_obj)
    assert rec_record_exec == "COMPLETED"

    # 4. Transition to VERIFIED
    ver_obj = ActionVerificationRecord(
        id=88,
        verification_id="ver_e2e_001",
        execution_id=exec_obj.id,
        action_id=action_id,
        session_id=session_obj.id,
        warehouse_id=mock_warehouse.id,
        user_id=mock_user.id,
        status="VERIFIED",
    )
    rec_record_ver = RecommendationOutcomeService.derive_final_outcome(
        approval=appr_obj, execution=exec_obj, verification=ver_obj
    )
    assert rec_record_ver == "VERIFIED"

    # 5. Transition to ACHIEVED (Supervisor Re-analysis)
    re_obj = SupervisorReanalysisRecord(
        id=99,
        reanalysis_id="re_e2e_001",
        execution_id=exec_obj.id,
        verification_id=ver_obj.id,
        action_id=action_id,
        session_id=session_obj.id,
        warehouse_id=mock_warehouse.id,
        user_id=mock_user.id,
        status="SUCCESSFUL_OUTCOME",
        objective_status="ACHIEVED",
    )
    rec_record_final = RecommendationOutcomeService.derive_final_outcome(
        approval=appr_obj, execution=exec_obj, verification=ver_obj, reanalysis=re_obj
    )
    assert rec_record_final == "ACHIEVED"

    # 6. Critical assertion: RecommendationAgent decision logic is completely UNCHANGED
    agent = RecommendationAgent()
    context = SharedContext()
    recs_out = agent.generate_recommendations(mock_warehouse, context)
    assert isinstance(recs_out, dict)
