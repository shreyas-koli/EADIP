"""
Automation service layer — User Approval / Human-in-the-Loop Gate.

Provides authorization, state validation, persistence, and audit recording
for action plan approvals and rejections.

CRITICAL SAFETY GUARANTEE:
- This service updates application-side approval state and database records ONLY.
- It NEVER executes SQL against the target warehouse.
- It NEVER mutates the warehouse in any way.
- All actions remain with ``executed = False``.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.approval import ActionApproval
from app.models.execution import DiscoverySession
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.automation import ApprovalRequest, ApprovalResponse
from app.warehouse.service import get_warehouse_by_id

logger = logging.getLogger(__name__)


class AutomationService:
    """
    Business logic service for managing the User Approval Gate (Phase 4).
    """

    @staticmethod
    def _get_session_and_warehouse(
        db: Session,
        warehouse_id: int,
        session_id: str,
        user: User,
    ) -> tuple[Warehouse, DiscoverySession]:
        """
        Validate warehouse ownership and retrieve discovery session.

        Raises ValueError or PermissionError on failure.
        """
        warehouse = get_warehouse_by_id(db, warehouse_id, user)
        if warehouse is None:
            raise PermissionError(f"Warehouse {warehouse_id} not found or access denied for user.")

        stmt = select(DiscoverySession).where(
            DiscoverySession.session_id == session_id,
            DiscoverySession.warehouse_id == warehouse.id,
        )
        session_obj = db.execute(stmt).scalar_one_or_none()
        if session_obj is None:
            raise ValueError(f"Discovery session '{session_id}' not found for warehouse {warehouse_id}.")

        return warehouse, session_obj

    @classmethod
    def get_action_plans(
        cls,
        db: Session,
        warehouse_id: int,
        session_id: str,
        user: User,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all action plans and their current approval status for a session.
        """
        _, session_obj = cls._get_session_and_warehouse(db, warehouse_id, session_id, user)

        recs = session_obj.recommendations or {}
        automation_data = recs.get("automation") or {}
        action_plans = automation_data.get("action_plans", [])

        # Fetch all approvals for this session to ensure frontend gets latest audit records
        stmt = select(ActionApproval).where(ActionApproval.session_id == session_obj.id)
        approvals = db.execute(stmt).scalars().all()
        approval_map = {appr.action_id: appr for appr in approvals}

        result = []
        for plan in action_plans:
            plan_copy = dict(plan)
            appr = approval_map.get(plan_copy.get("action_id"))
            if appr:
                plan_copy["status"] = appr.status
                plan_copy["approval"] = {
                    "approval_id": appr.id,
                    "decision": appr.decision,
                    "status": appr.status,
                    "approved_by": user.email if appr.user_id == user.id else str(appr.user_id),
                    "reason": appr.reason,
                    "created_at": appr.created_at.isoformat() if appr.created_at else None,
                }
            result.append(plan_copy)

        return result

    @classmethod
    def approve_action(
        cls,
        db: Session,
        warehouse_id: int,
        session_id: str,
        action_id: str,
        user: User,
        payload: Optional[ApprovalRequest] = None,
    ) -> ApprovalResponse:
        """
        Approve a proposed action plan.

        Transition: PROPOSED -> APPROVED
        """
        return cls._process_decision(
            db=db,
            warehouse_id=warehouse_id,
            session_id=session_id,
            action_id=action_id,
            user=user,
            decision="APPROVE",
            new_status="APPROVED",
            reason=payload.reason if payload else None,
        )

    @classmethod
    def reject_action(
        cls,
        db: Session,
        warehouse_id: int,
        session_id: str,
        action_id: str,
        user: User,
        payload: Optional[ApprovalRequest] = None,
    ) -> ApprovalResponse:
        """
        Reject a proposed action plan.

        Transition: PROPOSED -> REJECTED
        """
        return cls._process_decision(
            db=db,
            warehouse_id=warehouse_id,
            session_id=session_id,
            action_id=action_id,
            user=user,
            decision="REJECT",
            new_status="REJECTED",
            reason=payload.reason if payload else None,
        )

    @classmethod
    def _process_decision(
        cls,
        db: Session,
        warehouse_id: int,
        session_id: str,
        action_id: str,
        user: User,
        decision: str,
        new_status: str,
        reason: Optional[str] = None,
    ) -> ApprovalResponse:
        """
        Atomic decision processing for user approvals/rejections.

        Validates state transitions and updates DB & session recommendations JSONB.
        """
        warehouse, session_obj = cls._get_session_and_warehouse(db, warehouse_id, session_id, user)

        recs = session_obj.recommendations or {}
        automation_data = recs.get("automation") or {}
        action_plans = automation_data.get("action_plans", [])

        # Find target action plan
        target_plan = None
        for plan in action_plans:
            if plan.get("action_id") == action_id:
                target_plan = plan
                break

        if target_plan is None:
            raise ValueError(f"Action plan '{action_id}' not found in discovery session '{session_id}'.")

        current_status = target_plan.get("status", "PROPOSED")

        # Check existing approval record in DB
        stmt = select(ActionApproval).where(
            ActionApproval.action_id == action_id,
            ActionApproval.session_id == session_obj.id,
        )
        existing_approval = db.execute(stmt).scalar_one_or_none()

        if existing_approval:
            # Duplicate / conflict prevention
            if existing_approval.status == new_status:
                # Idempotent response for duplicate request
                return ApprovalResponse(
                    action_id=action_id,
                    session_id=session_id,
                    warehouse_id=warehouse_id,
                    status=existing_approval.status,
                    decision=existing_approval.decision,
                    approved_by=user.email or user.full_name,
                    approved_at=existing_approval.created_at,
                    executed=False,
                    reason=existing_approval.reason,
                    message=f"Action '{action_id}' is already {existing_approval.status}.",
                )
            else:
                raise ValueError(
                    f"Cannot change action '{action_id}' status from '{existing_approval.status}' to '{new_status}'."
                )

        if current_status != "PROPOSED":
            raise ValueError(f"Cannot process decision for action '{action_id}' with current status '{current_status}'.")

        now = datetime.now(timezone.utc)

        # 1. Update action status inside session JSONB structure
        target_plan["status"] = new_status
        target_plan["executed"] = False  # Explicit safety assertion!
        flag_modified(session_obj, "recommendations")

        # 2. Insert ActionApproval audit record
        approval_record = ActionApproval(
            action_id=action_id,
            session_id=session_obj.id,
            warehouse_id=warehouse.id,
            user_id=user.id,
            decision=decision,
            status=new_status,
            reason=reason,
            action_type=target_plan.get("action_type"),
            target=target_plan.get("target"),
            risk_level=target_plan.get("risk_level"),
            created_at=now,
            updated_at=now,
        )
        db.add(approval_record)

        # 3. Commit transaction atomically
        db.commit()
        db.refresh(approval_record)

        # Sync R1 Recommendation Outcome History
        from app.services.recommendation_outcome_service import RecommendationOutcomeService
        try:
            RecommendationOutcomeService.sync_action_outcome(
                db=db,
                warehouse_id=warehouse_id,
                session_id=session_id,
                action_id=action_id,
                user=user,
            )
        except Exception as exc:
            logger.warning(f"Failed to sync recommendation outcome for action '{action_id}': {exc}")

        # 4. Broadcast SSE telemetry events over existing telemetry infrastructure
        from app.context.shared_context import SharedContext

        user_identity = user.email or user.full_name
        if decision == "APPROVE":
            SharedContext.broadcast_event({
                "event": "action_approved",
                "action_id": action_id,
                "warehouse_id": warehouse_id,
                "session_id": session_id,
                "approved_by": user_identity,
                "status": "APPROVED",
                "timestamp": now.isoformat(),
            })
        else:
            SharedContext.broadcast_event({
                "event": "action_rejected",
                "action_id": action_id,
                "warehouse_id": warehouse_id,
                "session_id": session_id,
                "rejected_by": user_identity,
                "status": "REJECTED",
                "reason": reason,
                "timestamp": now.isoformat(),
            })

        SharedContext.broadcast_event({
            "event": "approval_state_changed",
            "action_id": action_id,
            "warehouse_id": warehouse_id,
            "session_id": session_id,
            "status": new_status,
            "decision": decision,
            "user_id": user.id,
            "timestamp": now.isoformat(),
        })

        logger.info(
            f"User {user.id} ({user.email}) recorded decision '{decision}' ({new_status}) for action '{action_id}' "
            f"in warehouse {warehouse_id} (session '{session_id}')."
        )

        message = (
            f"Action '{action_id}' approved and awaiting future execution phase."
            if new_status == "APPROVED"
            else f"Action '{action_id}' rejected."
        )

        return ApprovalResponse(
            action_id=action_id,
            session_id=session_id,
            warehouse_id=warehouse_id,
            status=new_status,
            decision=decision,
            approved_by=user.email or user.full_name,
            approved_at=now,
            executed=False,
            reason=reason,
            message=message,
        )
