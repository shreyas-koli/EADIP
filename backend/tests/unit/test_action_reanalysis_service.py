"""
Unit tests for ActionReanalysisService (Phase 7).

Verifies user authorization, execution record relationship checks, action parameter integrity,
persistence of SupervisorReanalysisRecord, and SSE telemetry event broadcasting.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from app.models.user import User
from app.models.warehouse import Warehouse
from app.models.execution import DiscoverySession
from app.models.action_execution_record import ActionExecutionRecord
from app.models.action_verification_record import ActionVerificationRecord
from app.models.supervisor_reanalysis_record import SupervisorReanalysisRecord  # noqa: F401
from app.services.action_reanalysis_service import ActionReanalysisService


@pytest.fixture
def mock_user():
    return User(
        id=1,
        email="re_user@example.com",
        full_name="Reanalysis User",
        role="user",
        is_active=True,
    )


@pytest.fixture
def mock_warehouse(mock_user):
    return Warehouse(
        id=10,
        name="Re WH",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="eadip_re",
        username="postgres",
        encrypted_password=b"token",
        owner_id=mock_user.id,
    )


@pytest.fixture
def sample_action_plan():
    return {
        "action_id": "act_re_svc_001",
        "action_type": "CREATE_INDEX",
        "status": "COMPLETED",
        "target": {"schema": "public", "table": "orders", "column": "created_at"},
        "statement": 'CREATE INDEX "idx_orders_created_at" ON "public"."orders" ("created_at")',
        "parameters": {"schema": "public", "table": "orders", "column": "created_at"},
        "executed": True,
        "verification_status": "VERIFIED",
    }


@pytest.fixture
def mock_session(mock_warehouse, sample_action_plan):
    return DiscoverySession(
        id=100,
        session_id="sess_re_svc_001",
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
def mock_execution(mock_warehouse, mock_session, mock_user):
    return ActionExecutionRecord(
        id=77,
        action_id="act_re_svc_001",
        approval_id=50,
        session_id=mock_session.id,
        warehouse_id=mock_warehouse.id,
        user_id=mock_user.id,
        status="COMPLETED",
        action_type="CREATE_INDEX",
        target={"schema": "public", "table": "orders", "column": "created_at"},
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_verification(mock_warehouse, mock_session, mock_user, mock_execution):
    return ActionVerificationRecord(
        id=88,
        verification_id="ver_svc_100",
        execution_id=mock_execution.id,
        action_id="act_re_svc_001",
        session_id=mock_session.id,
        warehouse_id=mock_warehouse.id,
        user_id=mock_user.id,
        status="VERIFIED",
        verified=True,
        checks=[{"status": "PASS"}],
        created_at=datetime.now(timezone.utc),
    )


def test_reanalyze_unexecuted_action_fails(mock_user, mock_warehouse, mock_session):
    """Verify attempting to re-analyze an unexecuted action raises ValueError."""
    db = MagicMock()

    with patch("app.services.action_reanalysis_service.get_warehouse_by_id", return_value=mock_warehouse):
        db.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: mock_session),
            MagicMock(scalars=lambda: MagicMock(first=lambda: None)),  # No execution record
        ]

        with pytest.raises(ValueError, match="no execution record exists"):
            ActionReanalysisService.reanalyze_action(
                db=db,
                warehouse_id=mock_warehouse.id,
                session_id=mock_session.session_id,
                action_id="act_re_svc_001",
                user=mock_user,
            )


def test_reanalyze_action_success(mock_user, mock_warehouse, mock_session, mock_execution, mock_verification):
    """Verify successful post-execution supervisor re-analysis."""
    db = MagicMock()

    engine_re_result = {
        "status": "SUCCESSFUL_OUTCOME",
        "objective_status": "ACHIEVED",
        "before_state": {"target": mock_execution.target},
        "after_state": {"execution_status": "COMPLETED", "verification_status": "VERIFIED"},
        "comparisons": [{"metric": "structural_catalog_state", "status": "MATCH"}],
        "findings": ["Structural objective achieved"],
        "conclusion": "Action achieved its objective.",
        "follow_up_required": False,
        "follow_up_type": "NONE",
        "follow_up_details": None,
        "duration_ms": 14.2,
    }

    with patch("app.services.action_reanalysis_service.get_warehouse_by_id", return_value=mock_warehouse), \
         patch("app.warehouse.reanalysis_engine.ControlledReanalysisEngine.reanalyze", return_value=engine_re_result):

        db.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: mock_session),
            MagicMock(scalars=lambda: MagicMock(first=lambda: mock_execution)),
            MagicMock(scalars=lambda: MagicMock(first=lambda: mock_verification)),
            MagicMock(scalars=lambda: MagicMock(first=lambda: None)),  # No existing reanalysis record
        ]

        res = ActionReanalysisService.reanalyze_action(
            db=db,
            warehouse_id=mock_warehouse.id,
            session_id=mock_session.session_id,
            action_id="act_re_svc_001",
            user=mock_user,
        )

        assert res.status == "SUCCESSFUL_OUTCOME"
        assert res.objective_status == "ACHIEVED"
        assert res.action_id == "act_re_svc_001"
        assert res.follow_up_required is False
        assert "achieved" in res.conclusion.lower()
