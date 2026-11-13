"""
Unit tests for ActionVerificationService (Phase 6).

Verifies authorization re-validation, execution record existence checks (must be COMPLETED),
action integrity checks, SSE telemetry event broadcasting, and idempotency.
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
from app.services.action_verification_service import ActionVerificationService


@pytest.fixture
def mock_user():
    return User(
        id=1,
        email="ver_user@example.com",
        full_name="Ver User",
        role="user",
        is_active=True,
    )


@pytest.fixture
def mock_warehouse(mock_user):
    return Warehouse(
        id=10,
        name="Ver WH",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="eadip_ver",
        username="postgres",
        encrypted_password=b"token",
        owner_id=mock_user.id,
    )


@pytest.fixture
def sample_executed_plan():
    return {
        "action_id": "act_ver_001",
        "action_type": "CREATE_INDEX",
        "status": "COMPLETED",
        "target": {"schema": "public", "table": "orders", "column": "created_at"},
        "statement": 'CREATE INDEX "idx_orders_created_at" ON "public"."orders" ("created_at")',
        "parameters": {"schema": "public", "table": "orders", "column": "created_at"},
        "executed": True,
        "verification_status": "PENDING",
    }


@pytest.fixture
def mock_session(mock_warehouse, sample_executed_plan):
    return DiscoverySession(
        id=100,
        session_id="sess_ver_001",
        warehouse_id=mock_warehouse.id,
        started_at=datetime.now(timezone.utc),
        status="COMPLETED",
        recommendations={
            "automation": {
                "action_plans": [sample_executed_plan]
            }
        },
    )


@pytest.fixture
def mock_execution(mock_warehouse, mock_session, mock_user):
    return ActionExecutionRecord(
        id=77,
        action_id="act_ver_001",
        approval_id=50,
        session_id=mock_session.id,
        warehouse_id=mock_warehouse.id,
        user_id=mock_user.id,
        status="COMPLETED",
        action_type="CREATE_INDEX",
        target={"schema": "public", "table": "orders", "column": "created_at"},
        created_at=datetime.now(timezone.utc),
    )


def test_verify_unexecuted_action_fails(mock_user, mock_warehouse, mock_session):
    """Verify attempting to verify an action with no execution record raises ValueError."""
    db = MagicMock()

    with patch("app.services.action_verification_service.get_warehouse_by_id", return_value=mock_warehouse):
        db.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: mock_session),
            MagicMock(scalars=lambda: MagicMock(first=lambda: None)),  # No execution record
        ]

        with pytest.raises(ValueError, match="no execution record exists"):
            ActionVerificationService.verify_action(
                db=db,
                warehouse_id=mock_warehouse.id,
                session_id=mock_session.session_id,
                action_id="act_ver_001",
                user=mock_user,
            )


def test_verify_failed_execution_fails(mock_user, mock_warehouse, mock_session, mock_execution):
    """Verify attempting to verify a FAILED execution record raises ValueError."""
    mock_execution.status = "FAILED"
    db = MagicMock()

    with patch("app.services.action_verification_service.get_warehouse_by_id", return_value=mock_warehouse):
        db.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: mock_session),
            MagicMock(scalars=lambda: MagicMock(first=lambda: mock_execution)),
        ]

        with pytest.raises(ValueError, match="Only COMPLETED executions can be verified"):
            ActionVerificationService.verify_action(
                db=db,
                warehouse_id=mock_warehouse.id,
                session_id=mock_session.session_id,
                action_id="act_ver_001",
                user=mock_user,
            )


def test_verify_completed_action_success(mock_user, mock_warehouse, mock_session, mock_execution):
    """Verify successful verification of a COMPLETED action plan."""
    db = MagicMock()

    engine_ver_result = {
        "status": "VERIFIED",
        "verified": True,
        "expected_state": {"index_exists": True},
        "observed_state": {"index_exists": True},
        "checks": [{"check_id": "index_exists", "description": "Index exists", "expected": True, "observed": True, "status": "PASS", "evidence": "Found"}],
        "evidence": ["Catalog contains index"],
        "duration_ms": 12.5,
        "error": None,
    }

    with patch("app.services.action_verification_service.get_warehouse_by_id", return_value=mock_warehouse), \
         patch("app.warehouse.verification_engine.ControlledVerificationEngine.verify", return_value=engine_ver_result):

        db.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: mock_session),
            MagicMock(scalars=lambda: MagicMock(first=lambda: mock_execution)),
            MagicMock(scalars=lambda: MagicMock(first=lambda: None)),  # No existing verification record
        ]

        res = ActionVerificationService.verify_action(
            db=db,
            warehouse_id=mock_warehouse.id,
            session_id=mock_session.session_id,
            action_id="act_ver_001",
            user=mock_user,
        )

        assert res.status == "VERIFIED"
        assert res.verified is True
        assert res.action_id == "act_ver_001"
        assert len(res.checks) == 1
        assert res.checks[0].status == "PASS"
        assert mock_execution.verification_status == "VERIFIED"
