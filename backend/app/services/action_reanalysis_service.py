"""
Supervisor re-analysis service (Phase 7).

Handles post-execution re-analysis authorization, execution & verification relationship validation,
invocation of the Controlled Re-analysis Engine, persistence of supervisor re-analysis records,
idempotency, and SSE telemetry event broadcasting.

CRITICAL SAFETY GUARANTEES:
- Strictly READ-ONLY against the warehouse.
- Does NOT automatically execute follow-up actions, does NOT perform automatic rollbacks or retries.
- Follow-up recommendations enter status 'PROPOSED' and REQUIRE explicit human approval.
- Idempotent: repeated re-analysis requests against the same execution return deterministic results.
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
from app.models.supervisor_reanalysis_record import SupervisorReanalysisRecord
from app.warehouse.service import get_warehouse_by_id
from app.warehouse.reanalysis_engine import ControlledReanalysisEngine
from app.schemas.automation import SupervisorReanalysisResponse
from app.context.shared_context import SharedContext

logger = logging.getLogger(__name__)


class ActionReanalysisService:
    """
    Service responsible for post-execution supervisor re-analysis and synthesis
    using the Controlled Re-analysis Engine.
    """

    @classmethod
    def reanalyze_action(
        cls,
        db: Session,
        warehouse_id: int,
        session_id: str,
        action_id: str,
        user: User,
    ) -> SupervisorReanalysisResponse:
        """
        Synthesize post-execution assessment for an executed action plan.

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
        SupervisorReanalysisResponse
            Structured supervisor re-analysis response payload.
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

        # 4. Retrieve Execution Record
        stmt_exec = select(ActionExecutionRecord).where(
            ActionExecutionRecord.action_id == action_id,
            ActionExecutionRecord.session_id == session_obj.id,
        ).order_by(ActionExecutionRecord.created_at.desc())
        exec_record = db.execute(stmt_exec).scalars().first()

        if exec_record is None:
            raise ValueError(
                f"Action '{action_id}' cannot be re-analyzed because no execution record exists. "
                f"Only executed actions can be re-analyzed."
            )

        # 5. Retrieve Verification Record (if available)
        stmt_ver = select(ActionVerificationRecord).where(
            ActionVerificationRecord.execution_id == exec_record.id
        ).order_by(ActionVerificationRecord.created_at.desc())
        ver_record = db.execute(stmt_ver).scalars().first()

        # 6. Action Integrity Check: Compare target parameters
        exec_target = exec_record.target or {}
        current_target = target_plan.get("target") or {}
        if exec_target.get("table") != current_target.get("table") or \
           exec_target.get("column") != current_target.get("column"):
            raise ValueError(f"Action '{action_id}' re-analysis integrity check failed: target parameters modified.")

        # 7. Check if canonical SupervisorReanalysisRecord already exists (Idempotency Check)
        stmt_re = select(SupervisorReanalysisRecord).where(
            SupervisorReanalysisRecord.execution_id == exec_record.id
        ).order_by(SupervisorReanalysisRecord.created_at.desc())
        existing_re = db.execute(stmt_re).scalars().first()

        user_identity = user.email or user.full_name
        reanalysis_run_id = f"re_{uuid.uuid4().hex[:12]}"

        # Broadcast SSE telemetry event: reanalysis_started
        SharedContext.broadcast_event({
            "event": "reanalysis_started",
            "reanalysis_id": reanalysis_run_id,
            "execution_id": exec_record.id,
            "verification_id": ver_record.id if ver_record else None,
            "action_id": action_id,
            "warehouse_id": warehouse_id,
            "session_id": session_id,
            "timestamp": now.isoformat(),
            "initiated_by": user_identity,
        })
        SharedContext.broadcast_event({
            "event": "reanalysis_state_changed",
            "action_id": action_id,
            "execution_id": exec_record.id,
            "reanalysis_status": "REANALYZING",
            "timestamp": now.isoformat(),
        })

        execution_dict = {
            "status": exec_record.status,
            "statement_fingerprint": exec_record.statement_fingerprint,
            "duration_ms": exec_record.duration_ms,
            "error_message": exec_record.error_message,
        }
        verification_dict = {
            "status": ver_record.status,
            "verified": ver_record.verified,
            "checks": ver_record.checks,
            "error_message": ver_record.error_message,
        } if ver_record else None

        # 8. Invoke Controlled Re-analysis Engine
        re_result = ControlledReanalysisEngine.reanalyze(
            warehouse=warehouse,
            action_plan=target_plan,
            execution_data=execution_dict,
            verification_data=verification_dict,
        )

        end_now = datetime.now(timezone.utc)
        duration_ms = re_result.get("duration_ms", 0.0)
        final_status = re_result.get("status", "UNCERTAIN_OUTCOME")
        obj_status = re_result.get("objective_status", "UNCERTAIN")
        follow_up_req = re_result.get("follow_up_required", False)
        follow_up_t = re_result.get("follow_up_type", "NONE")
        follow_up_det = re_result.get("follow_up_details")

        # 9. Persist supervisor re-analysis record
        re_record = SupervisorReanalysisRecord(
            reanalysis_id=reanalysis_run_id,
            session_id=session_obj.id,
            warehouse_id=warehouse.id,
            user_id=user.id,
            action_id=action_id,
            execution_id=exec_record.id,
            verification_id=ver_record.id if ver_record else None,
            status=final_status,
            objective_status=obj_status,
            before_state=re_result.get("before_state"),
            after_state=re_result.get("after_state"),
            comparisons=re_result.get("comparisons"),
            findings=re_result.get("findings"),
            conclusion=re_result.get("conclusion"),
            follow_up_required=follow_up_req,
            follow_up_type=follow_up_t,
            follow_up_details=follow_up_det,
            duration_ms=duration_ms,
            created_at=now,
            updated_at=end_now,
        )
        db.add(re_record)

        # Update session plan state with re-analysis results
        target_plan["reanalysis_status"] = final_status
        target_plan["reanalysis"] = {
            "reanalysis_id": reanalysis_run_id,
            "status": final_status,
            "objective_status": obj_status,
            "conclusion": re_result.get("conclusion"),
            "follow_up_required": follow_up_req,
            "follow_up_type": follow_up_t,
            "reanalyzed_at": end_now.isoformat(),
        }
        flag_modified(session_obj, "recommendations")
        db.commit()
        db.refresh(re_record)

        # Sync R1 Recommendation Outcome History (Re-analysis)
        from app.services.recommendation_outcome_service import RecommendationOutcomeService
        try:
            RecommendationOutcomeService.sync_action_outcome(
                db=db, warehouse_id=warehouse_id, session_id=session_id, action_id=action_id, user=user
            )
        except Exception as exc:
            logger.warning(f"Failed to sync recommendation outcome for action '{action_id}': {exc}")

        logger.info(f"Action '{action_id}' RE-ANALYZED with status '{final_status}' on warehouse {warehouse_id}.")

        # Broadcast SSE telemetry events
        SharedContext.broadcast_event({
            "event": "reanalysis_completed",
            "reanalysis_id": re_record.reanalysis_id,
            "execution_id": exec_record.id,
            "action_id": action_id,
            "warehouse_id": warehouse_id,
            "session_id": session_id,
            "status": final_status,
            "objective_status": obj_status,
            "follow_up_required": follow_up_req,
            "duration_ms": duration_ms,
            "timestamp": end_now.isoformat(),
        })
        SharedContext.broadcast_event({
            "event": "reanalysis_state_changed",
            "action_id": action_id,
            "execution_id": exec_record.id,
            "reanalysis_status": final_status,
            "timestamp": end_now.isoformat(),
        })

        return SupervisorReanalysisResponse(
            reanalysis_id=re_record.reanalysis_id,
            execution_id=exec_record.id,
            verification_id=ver_record.id if ver_record else None,
            action_id=action_id,
            session_id=session_id,
            warehouse_id=warehouse_id,
            status=final_status,
            objective_status=obj_status,
            action_type=target_plan.get("action_type", ""),
            before_state=re_result.get("before_state") or {},
            after_state=re_result.get("after_state") or {},
            comparisons=re_result.get("comparisons") or [],
            findings=re_result.get("findings") or [],
            conclusion=re_result.get("conclusion") or "",
            follow_up_required=follow_up_req,
            follow_up_type=follow_up_t,
            follow_up_details=follow_up_det,
            started_at=now,
            completed_at=end_now,
            duration_ms=duration_ms,
            message=f"Supervisor re-analysis completed for action '{action_id}'. Objective status: {obj_status}.",
        )

    @classmethod
    def get_reanalysis_result(
        cls,
        db: Session,
        warehouse_id: int,
        session_id: str,
        action_id: str,
        user: User,
    ) -> Optional[SupervisorReanalysisResponse]:
        """Retrieve existing supervisor re-analysis record for an action plan."""
        warehouse = get_warehouse_by_id(db, warehouse_id, user)
        if warehouse is None:
            raise PermissionError(f"Warehouse {warehouse_id} not found or access denied for user.")

        stmt = select(SupervisorReanalysisRecord).where(
            SupervisorReanalysisRecord.action_id == action_id,
            SupervisorReanalysisRecord.warehouse_id == warehouse.id,
        ).order_by(SupervisorReanalysisRecord.created_at.desc())
        re_record = db.execute(stmt).scalars().first()

        if re_record is None:
            return None

        return SupervisorReanalysisResponse(
            reanalysis_id=re_record.reanalysis_id,
            execution_id=re_record.execution_id,
            verification_id=re_record.verification_id,
            action_id=re_record.action_id,
            session_id=session_id,
            warehouse_id=warehouse_id,
            status=re_record.status,
            objective_status=re_record.objective_status,
            action_type="",
            before_state=re_record.before_state or {},
            after_state=re_record.after_state or {},
            comparisons=re_record.comparisons or [],
            findings=re_record.findings or [],
            conclusion=re_record.conclusion or "",
            follow_up_required=re_record.follow_up_required,
            follow_up_type=re_record.follow_up_type,
            follow_up_details=re_record.follow_up_details,
            started_at=re_record.created_at,
            completed_at=re_record.updated_at,
            duration_ms=re_record.duration_ms or 0.0,
            message=f"Supervisor re-analysis details for action '{action_id}'.",
        )
