"""
Unit tests for AutomationService (User Approval Gate - Phase 4).

Verifies approval and rejection workflows, state transition safety, atomicity,
duplicate request handling, and audit record creation.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from app.models.user import User  # noqa: F401
from app.models.warehouse import Warehouse
from app.models.execution import DiscoverySession
from app.models.approval import ActionApproval
from app.services.automation_service import AutomationService
from app.schemas.automation import ApprovalRequest


@pytest.fixture
def mock_user():
    user = User(
        id=10,
        email="testowner@example.com",
        full_name="Test Owner",
        role="user",
        is_active=True,
    )
    return user


@pytest.fixture
def mock_warehouse(mock_user):
    return Warehouse(
        id=100,
        name="Test WH",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="eadip_test",
        username="postgres",
        encrypted_password=b"token",
        owner_id=mock_user.id,
    )


@pytest.fixture
def sample_action_plan():
    return {
        "action_id": "act_123456",
        "recommendation_type": "large_table_indexing",
        "action_type": "CREATE_INDEX",
        "status": "PROPOSED",
        "automation_status": "AUTOMATABLE",
        "target": {"schema": "public", "table": "orders", "column": "created_at"},
        "description": "Create B-tree index on public.orders(created_at)",
        "statement": 'CREATE INDEX "idx_orders_created_at" ON "public"."orders" ("created_at")',
        "parameters": {"schema": "public", "table": "orders", "column": "created_at"},
        "risk_level": "MEDIUM",
        "impact_level": "HIGH",
        "safety_class": "REVERSIBLE_WRITE",
        "preconditions": ["Target table public.orders must exist."],
        "safety_checks": ["Target table public.orders must exist."],
        "rollback_plan": {"rollback_available": True, "statement": 'DROP INDEX "public"."idx_orders_created_at"'},
        "verification_plan": {"verification_type": "INDEX_EXISTS", "description": "Check index exists"},
        "requires_approval": True,
        "requires_verification": True,
        "is_destructive": False,
        "is_reversible": True,
        "is_executable": True,
        "executed": False,
        "created_at": "2026-09-20T17:00:00+00:00",
        "source_agent": "automation",
        "evidence": [],
    }


@pytest.fixture
def mock_session(mock_warehouse, sample_action_plan):
    session = DiscoverySession(
        id=500,
        session_id="sess_abc123",
        warehouse_id=mock_warehouse.id,
        started_at=datetime.now(timezone.utc),
        status="COMPLETED",
        recommendations={
            "automation": {
                "action_plans": [sample_action_plan]
            }
        },
    )
    return session


def test_approve_proposed_action(mock_user, mock_warehouse, mock_session):
    """Verify that a PROPOSED action plan can be successfully APPROVED."""
    db = MagicMock()
    
    with patch("app.services.automation_service.get_warehouse_by_id", return_value=mock_warehouse):
        db.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: mock_session),  # DiscoverySession query
            MagicMock(scalar_one_or_none=lambda: None),         # ActionApproval existing check
        ]
        
        response = AutomationService.approve_action(
            db=db,
            warehouse_id=mock_warehouse.id,
            session_id=mock_session.session_id,
            action_id="act_123456",
            user=mock_user,
        )
        
        assert response.action_id == "act_123456"
        assert response.status == "APPROVED"
        assert response.decision == "APPROVE"
        assert response.executed is False
        assert "approved" in response.message.lower()
        
        # Verify DB add and commit were invoked
        assert db.add.called
        assert db.commit.called
        
        # Verify internal action plan status was updated in JSONB
        updated_plan = mock_session.recommendations["automation"]["action_plans"][0]
        assert updated_plan["status"] == "APPROVED"
        assert updated_plan["executed"] is False


def test_reject_proposed_action_with_reason(mock_user, mock_warehouse, mock_session):
    """Verify that a PROPOSED action plan can be REJECTED with a reason."""
    db = MagicMock()
    
    with patch("app.services.automation_service.get_warehouse_by_id", return_value=mock_warehouse):
        db.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: mock_session),
            MagicMock(scalar_one_or_none=lambda: None),
        ]
        
        payload = ApprovalRequest(reason="Not needed at this time.")
        response = AutomationService.reject_action(
            db=db,
            warehouse_id=mock_warehouse.id,
            session_id=mock_session.session_id,
            action_id="act_123456",
            user=mock_user,
            payload=payload,
        )
        
        assert response.action_id == "act_123456"
        assert response.status == "REJECTED"
        assert response.decision == "REJECT"
        assert response.executed is False
        assert response.reason == "Not needed at this time."
        
        updated_plan = mock_session.recommendations["automation"]["action_plans"][0]
        assert updated_plan["status"] == "REJECTED"
        assert updated_plan["executed"] is False


def test_duplicate_approval_is_idempotent(mock_user, mock_warehouse, mock_session):
    """Verify duplicate approval request for an already APPROVED action returns idempotent response."""
    db = MagicMock()
    existing = ActionApproval(
        action_id="act_123456",
        session_id=mock_session.id,
        warehouse_id=mock_warehouse.id,
        user_id=mock_user.id,
        decision="APPROVE",
        status="APPROVED",
        created_at=datetime.now(timezone.utc),
    )
    
    with patch("app.services.automation_service.get_warehouse_by_id", return_value=mock_warehouse):
        db.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: mock_session),
            MagicMock(scalar_one_or_none=lambda: existing),
        ]
        
        response = AutomationService.approve_action(
            db=db,
            warehouse_id=mock_warehouse.id,
            session_id=mock_session.session_id,
            action_id="act_123456",
            user=mock_user,
        )
        
        assert response.status == "APPROVED"
        assert response.executed is False
        assert "already APPROVED" in response.message


def test_conflict_rejected_to_approved_fails(mock_user, mock_warehouse, mock_session):
    """Verify an action already REJECTED cannot be APPROVED."""
    db = MagicMock()
    existing = ActionApproval(
        action_id="act_123456",
        session_id=mock_session.id,
        warehouse_id=mock_warehouse.id,
        user_id=mock_user.id,
        decision="REJECT",
        status="REJECTED",
        created_at=datetime.now(timezone.utc),
    )
    
    with patch("app.services.automation_service.get_warehouse_by_id", return_value=mock_warehouse):
        db.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: mock_session),
            MagicMock(scalar_one_or_none=lambda: existing),
        ]
        
        with pytest.raises(ValueError, match="Cannot change action 'act_123456' status from 'REJECTED' to 'APPROVED'"):
            AutomationService.approve_action(
                db=db,
                warehouse_id=mock_warehouse.id,
                session_id=mock_session.session_id,
                action_id="act_123456",
                user=mock_user,
            )


def test_invalid_action_id_raises_value_error(mock_user, mock_warehouse, mock_session):
    """Verify attempting to approve a non-existent action ID raises ValueError."""
    db = MagicMock()
    
    with patch("app.services.automation_service.get_warehouse_by_id", return_value=mock_warehouse):
        db.execute.return_value = MagicMock(scalar_one_or_none=lambda: mock_session)
        
        with pytest.raises(ValueError, match="Action plan 'act_nonexistent' not found"):
            AutomationService.approve_action(
                db=db,
                warehouse_id=mock_warehouse.id,
                session_id=mock_session.session_id,
                action_id="act_nonexistent",
                user=mock_user,
            )
