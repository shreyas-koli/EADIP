"""
Action verification service (Phase 6).

Handles pre-verification validation, authorization checks, execution completion checks,
action integrity re-validation, invocation of the Controlled Verification Engine,
database persistence of verification records, idempotency, and SSE telemetry emission.

CRITICAL SAFETY GUARANTEES:
- Verification can ONLY be performed on actions with a valid ActionExecutionRecord
  where status == 'COMPLETED' and executed == True.
- Failed, Executing, Proposed, or Rejected actions CANNOT be verified.
- Does NOT execute SQL mutations, does NOT trigger automatic rollbacks, does NOT invoke Phase 7.
- Idempotent: repeated verification requests against the same execution return deterministic results.
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.user import User
from app.models.execution import DiscoverySession
from app.models.approval import ActionApproval
from app.models.action_execution_record import ActionExecutionRecord
from app.models.action_verification_record import ActionVerificationRecord
from app.warehouse.service import get_warehouse_by_id
from app.warehouse.verification_engine import ControlledVerificationEngine
from app.schemas.automation import VerificationResultResponse
from app.context.shared_context import SharedContext

logger = logging.getLogger(__name__)


class ActionVerificationService:
    """
    Service responsible for verifying executed warehouse actions against target warehouse
    state using the Controlled Verification Engine.
    """

    @classmethod
    def verify_action(
        cls,
        db: Session,
        warehouse_id: int,
        session_id: str,
        action_id: str,
        user: User,
    ) -> VerificationResultResponse:
        """
        Verify an executed action plan against the target data warehouse.

        Parameters
        ──────────
        db : Session
            System database session.
        warehouse_id : int
            ID of the target warehouse.
        session_id : str
            String session ID of the discovery session.
        action_id : str
            String ID of the target action plan.
        user : User
            Authenticated requesting user.

        Returns
        ───────
        VerificationResultResponse
            Structured verification result payload.
        """
        now = datetime.now(timezone.utc)

        # 1. Retrieve warehouse and authorize user
        warehouse = get_warehouse_by_id(db, warehouse_id, user)
        if warehouse is None:
            raise PermissionError(f"Warehouse {warehouse_id} not found or access denied for user.")

        # 2. Retrieve discovery session
        stmt_sess = select(DiscoverySession).where(
            DiscoverySession.session_id == session_id,
            DiscoverySession.warehouse_id == warehouse.id,
        )
        session_obj = db.execute(stmt_sess).scalar_one_or_none()
        if session_obj is None:
            raise ValueError(f"Discovery session '{session_id}' not found for warehouse {warehouse_id}.")

        # 3. Locate target action plan in recommendations JSONB
        recs = session_obj.recommendations or {}
        automation_data = recs.get("automation") or {}
        action_plans = automation_data.get("action_plans", [])

        target_plan = None
        for plan in action_plans:
            if plan.get("action_id") == action_id:
                target_plan = plan
                break

        if target_plan is None:
            raise ValueError(f"Action plan '{action_id}' not found in discovery session '{session_id}'.")

        # 4. Re-validate Execution Record (MUST exist and be COMPLETED)
        stmt_exec = select(ActionExecutionRecord).where(
            ActionExecutionRecord.action_id == action_id,
            ActionExecutionRecord.session_id == session_obj.id,
        ).order_by(ActionExecutionRecord.created_at.desc())
        exec_record = db.execute(stmt_exec).scalars().first()

        if exec_record is None:
            raise ValueError(
                f"Action '{action_id}' cannot be verified because no execution record exists. "
                f"Only COMPLETED executions can be verified."
            )

        if exec_record.status != "COMPLETED":
            raise ValueError(
                f"Action '{action_id}' cannot be verified because its execution status is '{exec_record.status}'. "
                f"Only COMPLETED executions can be verified."
            )

        # 5. Check if canonical ActionVerificationRecord already exists (Idempotency Check)
        stmt_ver = select(ActionVerificationRecord).where(
            ActionVerificationRecord.execution_id == exec_record.id
        ).order_by(ActionVerificationRecord.created_at.desc())
        existing_ver = db.execute(stmt_ver).scalars().first()

        # 6. Action Integrity Check: Compare parameters against execution record
        exec_target = exec_record.target or {}
        current_target = target_plan.get("target") or {}
        if exec_target.get("table") != current_target.get("table") or \
           exec_target.get("column") != current_target.get("column"):
            raise ValueError(f"Action '{action_id}' verification integrity check failed: target parameters modified.")

        user_identity = user.email or user.full_name

        verification_run_id = f"ver_{uuid.uuid4().hex[:12]}"

        # Broadcast SSE telemetry event: verification_started
        SharedContext.broadcast_event({
            "event": "verification_started",
            "verification_id": verification_run_id,
            "execution_id": exec_record.id,
            "action_id": action_id,
            "warehouse_id": warehouse_id,
            "session_id": session_id,
            "timestamp": now.isoformat(),
            "initiated_by": user_identity,
        })
        SharedContext.broadcast_event({
            "event": "verification_state_changed",
            "action_id": action_id,
            "execution_id": exec_record.id,
            "verification_status": "VERIFYING",
            "timestamp": now.isoformat(),
        })

        # 7. Invoke Controlled Verification Engine
        ver_result = ControlledVerificationEngine.verify(warehouse, target_plan)

        end_now = datetime.now(timezone.utc)
        duration_ms = ver_result.get("duration_ms", 0.0)
        final_status = ver_result.get("status", "INCONCLUSIVE")
        verified_bool = ver_result.get("verified")
        safe_error = ver_result.get("error")

        # 8. Persist verification record
        ver_record = ActionVerificationRecord(
            verification_id=verification_run_id,
            execution_id=exec_record.id,
            action_id=action_id,
            session_id=session_obj.id,
            warehouse_id=warehouse.id,
            user_id=user.id,
            status=final_status,
            verified=verified_bool,
            action_type=target_plan.get("action_type"),
            target=current_target,
            expected_state=ver_result.get("expected_state"),
            observed_state=ver_result.get("observed_state"),
            evidence=ver_result.get("evidence"),
            checks=ver_result.get("checks"),
            duration_ms=duration_ms,
            error_message=safe_error,
            created_at=now,
            updated_at=end_now,
        )
        db.add(ver_record)

        # Update ExecutionRecord and session plan state
        exec_record.verification_status = final_status
        target_plan["verification_status"] = final_status
        target_plan["verification"] = {
            "verification_id": verification_run_id,
            "status": final_status,
            "verified": verified_bool,
            "checks": ver_result.get("checks"),
            "evidence": ver_result.get("evidence"),
            "verified_at": end_now.isoformat(),
        }
        flag_modified(session_obj, "recommendations")
        db.commit()
        db.refresh(ver_record)

        # Sync R1 Recommendation Outcome History (Verification)
        from app.services.recommendation_outcome_service import RecommendationOutcomeService
        try:
            RecommendationOutcomeService.sync_action_outcome(
                db=db, warehouse_id=warehouse_id, session_id=session_id, action_id=action_id, user=user
            )
        except Exception as exc:
            logger.warning(f"Failed to sync recommendation outcome for action '{action_id}': {exc}")

        logger.info(f"Action '{action_id}' VERIFIED with status '{final_status}' on warehouse {warehouse_id}.")

        # Broadcast SSE telemetry events
        event_name = "verification_completed" if final_status == "VERIFIED" else "verification_failed"
        SharedContext.broadcast_event({
            "event": event_name,
            "verification_id": ver_record.verification_id,
            "execution_id": exec_record.id,
            "action_id": action_id,
            "warehouse_id": warehouse_id,
            "session_id": session_id,
            "status": final_status,
            "verified": verified_bool,
            "duration_ms": duration_ms,
            "timestamp": end_now.isoformat(),
        })
        SharedContext.broadcast_event({
            "event": "verification_state_changed",
            "action_id": action_id,
            "execution_id": exec_record.id,
            "verification_status": final_status,
            "timestamp": end_now.isoformat(),
        })

        return VerificationResultResponse(
            verification_id=ver_record.verification_id,
            execution_id=exec_record.id,
            action_id=action_id,
            session_id=session_id,
            warehouse_id=warehouse_id,
            status=final_status,
            verified=verified_bool,
            action_type=target_plan.get("action_type", ""),
            expected_state=ver_result.get("expected_state") or {},
            observed_state=ver_result.get("observed_state") or {},
            evidence=ver_result.get("evidence") or [],
            checks=ver_result.get("checks") or [],
            started_at=now,
            completed_at=end_now,
            duration_ms=duration_ms,
            message=f"Verification completed for action '{action_id}' with status '{final_status}'.",
            error_message=safe_error,
        )

    @classmethod
    def get_verification_result(
        cls,
        db: Session,
        warehouse_id: int,
        session_id: str,
        action_id: str,
        user: User,
    ) -> Optional[VerificationResultResponse]:
        """Retrieve existing verification record for an action plan."""
        warehouse = get_warehouse_by_id(db, warehouse_id, user)
        if warehouse is None:
            raise PermissionError(f"Warehouse {warehouse_id} not found or access denied for user.")

        stmt = select(ActionVerificationRecord).where(
            ActionVerificationRecord.action_id == action_id,
            ActionVerificationRecord.warehouse_id == warehouse.id,
        ).order_by(ActionVerificationRecord.created_at.desc())
        ver_record = db.execute(stmt).scalars().first()

        if ver_record is None:
            return None

        return VerificationResultResponse(
            verification_id=ver_record.verification_id,
            execution_id=ver_record.execution_id,
            action_id=ver_record.action_id,
            session_id=session_id,
            warehouse_id=warehouse_id,
            status=ver_record.status,
            verified=ver_record.verified,
            action_type=ver_record.action_type or "",
            expected_state=ver_record.expected_state or {},
            observed_state=ver_record.observed_state or {},
            evidence=ver_record.evidence or [],
            checks=ver_record.checks or [],
            started_at=ver_record.created_at,
            completed_at=ver_record.updated_at,
            duration_ms=ver_record.duration_ms or 0.0,
            message=f"Verification details for action '{action_id}'.",
            error_message=ver_record.error_message,
        )
