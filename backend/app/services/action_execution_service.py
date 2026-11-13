"""
Action execution service layer — Phase 5 Controlled Execution Engine.

Handles authorization re-validation, approval verification, action integrity checks,
atomic status transitions (APPROVED -> EXECUTING -> COMPLETED/FAILED), DB record logging,
and SSE telemetry broadcasting.

CRITICAL SECURITY GUARANTEES:
- Approval is necessary BUT NOT SUFFICIENT.
- Re-validates user authorization, warehouse access, action approval state, and integrity.
- PROPOSED and REJECTED actions can NEVER be executed.
- Duplicate or concurrent executions are blocked atomically.
- Execution results leave ``verification_status = PENDING`` (Phase 6 boundary).
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.context.shared_context import SharedContext
from app.models.action_execution_record import ActionExecutionRecord
from app.models.approval import ActionApproval
from app.models.execution import DiscoverySession
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.automation import ExecutionResultResponse
from app.warehouse.execution_engine import ControlledExecutionEngine
from app.warehouse.service import get_warehouse_by_id

logger = logging.getLogger(__name__)


class ActionExecutionService:
    """
    Business logic service for executing approved warehouse action plans.
    """

    @classmethod
    def execute_action(
        cls,
        db: Session,
        warehouse_id: int,
        session_id: str,
        action_id: str,
        user: User,
    ) -> ExecutionResultResponse:
        """
        Re-validate and execute an approved action plan against the target warehouse.

        Parameters
        ──────────
        db : Session
            Active SQLAlchemy database session.
        warehouse_id : int
            ID of the target warehouse.
        session_id : str
            ID of the discovery session.
        action_id : str
            ID of the action plan to execute.
        user : User
            The authenticated user triggering execution.

        Returns
        ───────
        ExecutionResultResponse
            Structured execution result.
        """
        now = datetime.now(timezone.utc)

        # 1. Authorize user and retrieve warehouse
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

        # 4. Re-validate Approval Status in application DB
        stmt_appr = select(ActionApproval).where(
            ActionApproval.action_id == action_id,
            ActionApproval.session_id == session_obj.id,
        )
        approval_record = db.execute(stmt_appr).scalar_one_or_none()

        if approval_record is None or approval_record.status != "APPROVED":
            status_desc = approval_record.status if approval_record else "NO_APPROVAL_RECORD"
            raise ValueError(
                f"Action '{action_id}' cannot be executed because its status is '{status_desc}'. "
                f"Only APPROVED actions can be executed."
            )

        # 5. Check if action has already been executed or is currently executing (Idempotency Check)
        current_status = target_plan.get("status", "")
        if target_plan.get("executed") is True or current_status == "COMPLETED":
            # Return idempotent completed response
            return ExecutionResultResponse(
                execution_id=0,
                action_id=action_id,
                session_id=session_id,
                warehouse_id=warehouse_id,
                status="COMPLETED",
                action_type=target_plan.get("action_type", ""),
                started_at=now,
                completed_at=now,
                duration_ms=0.0,
                executed=True,
                message=f"Action '{action_id}' has already been executed successfully.",
                verification_status="PENDING",
            )

        if current_status == "EXECUTING":
            raise ValueError(f"Action '{action_id}' is currently executing in another process.")

        # 6. Action Integrity Check: Compare parameters against approved ActionApproval record
        approved_target = approval_record.target or {}
        current_target = target_plan.get("target") or {}
        if approved_target.get("table") != current_target.get("table") or \
           approved_target.get("column") != current_target.get("column"):
            raise ValueError(f"Action '{action_id}' integrity check failed: payload target parameters do not match approved record.")

        user_identity = user.email or user.full_name

        # 7. Atomic Transition to EXECUTING state
        target_plan["status"] = "EXECUTING"
        flag_modified(session_obj, "recommendations")

        exec_record = ActionExecutionRecord(
            action_id=action_id,
            approval_id=approval_record.id,
            session_id=session_obj.id,
            warehouse_id=warehouse.id,
            user_id=user.id,
            status="EXECUTING",
            action_type=target_plan.get("action_type"),
            target=target_plan.get("target"),
            created_at=now,
            updated_at=now,
        )
        db.add(exec_record)
        db.commit()
        db.refresh(exec_record)

        # Sync R1 Recommendation Outcome History (EXECUTING)
        from app.services.recommendation_outcome_service import RecommendationOutcomeService
        try:
            RecommendationOutcomeService.sync_action_outcome(
                db=db, warehouse_id=warehouse_id, session_id=session_id, action_id=action_id, user=user
            )
        except Exception as exc:
            logger.warning(f"Failed to sync recommendation outcome for action '{action_id}': {exc}")

        # Broadcast SSE telemetry event: action_execution_started
        SharedContext.broadcast_event({
            "event": "action_execution_started",
            "action_id": action_id,
            "execution_id": exec_record.id,
            "warehouse_id": warehouse_id,
            "session_id": session_id,
            "action_type": target_plan.get("action_type"),
            "status": "EXECUTING",
            "executed_by": user_identity,
            "timestamp": now.isoformat(),
        })
        SharedContext.broadcast_event({
            "event": "execution_state_changed",
            "action_id": action_id,
            "execution_id": exec_record.id,
            "status": "EXECUTING",
            "timestamp": now.isoformat(),
        })

        # 8. Execute controlled operation against target warehouse
        try:
            exec_result = ControlledExecutionEngine.execute(warehouse, target_plan)
        except Exception as exc:
            safe_err = str(exc)
            if warehouse.username and warehouse.username in safe_err:
                safe_err = safe_err.replace(warehouse.username, "***")
            logger.error(f"Uncaught exception during ControlledExecutionEngine.execute for action '{action_id}': {safe_err}")
            exec_result = {
                "success": False,
                "statement": None,
                "duration_ms": 0.0,
                "error": safe_err,
            }

        end_now = datetime.now(timezone.utc)
        duration_ms = exec_result.get("duration_ms", 0.0)

        # 9. Handle execution outcome
        if exec_result["success"]:
            new_status = "COMPLETED"
            target_plan["status"] = new_status
            target_plan["executed"] = True
            target_plan["verification_status"] = "PENDING"
            flag_modified(session_obj, "recommendations")

            exec_record.status = new_status
            exec_record.duration_ms = duration_ms
            exec_record.statement_fingerprint = exec_result.get("statement")
            exec_record.verification_status = "PENDING"
            exec_record.updated_at = end_now
            db.commit()

            # Sync R1 Recommendation Outcome History (COMPLETED)
            from app.services.recommendation_outcome_service import RecommendationOutcomeService
            try:
                RecommendationOutcomeService.sync_action_outcome(
                    db=db, warehouse_id=warehouse_id, session_id=session_id, action_id=action_id, user=user
                )
            except Exception as exc:
                logger.warning(f"Failed to sync recommendation outcome for action '{action_id}': {exc}")

            logger.info(f"Action '{action_id}' EXECUTED successfully on warehouse {warehouse_id} in {duration_ms}ms.")

            # Broadcast SSE telemetry event: action_execution_completed
            SharedContext.broadcast_event({
                "event": "action_execution_completed",
                "action_id": action_id,
                "execution_id": exec_record.id,
                "warehouse_id": warehouse_id,
                "session_id": session_id,
                "status": "COMPLETED",
                "duration_ms": duration_ms,
                "timestamp": end_now.isoformat(),
            })
            SharedContext.broadcast_event({
                "event": "execution_state_changed",
                "action_id": action_id,
                "execution_id": exec_record.id,
                "status": "COMPLETED",
                "timestamp": end_now.isoformat(),
            })

            return ExecutionResultResponse(
                execution_id=exec_record.id or 0,
                action_id=action_id,
                session_id=session_id,
                warehouse_id=warehouse_id,
                status="COMPLETED",
                action_type=target_plan.get("action_type", ""),
                started_at=now,
                completed_at=end_now,
                duration_ms=duration_ms,
                executed=True,
                message=f"Action '{action_id}' executed successfully against warehouse '{warehouse.name}'.",
                verification_status="PENDING",
            )
        else:
            new_status = "FAILED"
            safe_error = exec_result.get("error", "Execution failed")

            target_plan["status"] = new_status
            target_plan["executed"] = False
            target_plan["execution_error"] = safe_error
            flag_modified(session_obj, "recommendations")

            exec_record.status = new_status
            exec_record.duration_ms = duration_ms
            exec_record.statement_fingerprint = exec_result.get("statement")
            exec_record.error_message = safe_error
            exec_record.updated_at = end_now
            db.commit()

            # Sync R1 Recommendation Outcome History (FAILED)
            from app.services.recommendation_outcome_service import RecommendationOutcomeService
            try:
                RecommendationOutcomeService.sync_action_outcome(
                    db=db, warehouse_id=warehouse_id, session_id=session_id, action_id=action_id, user=user
                )
            except Exception as exc:
                logger.warning(f"Failed to sync recommendation outcome for action '{action_id}': {exc}")

            logger.error(f"Action '{action_id}' EXECUTION FAILED on warehouse {warehouse_id}: {safe_error}")

            # Broadcast SSE telemetry event: action_execution_failed
            SharedContext.broadcast_event({
                "event": "action_execution_failed",
                "action_id": action_id,
                "execution_id": exec_record.id or 0,
                "warehouse_id": warehouse_id,
                "session_id": session_id,
                "status": "FAILED",
                "error": safe_error,
                "duration_ms": duration_ms,
                "timestamp": end_now.isoformat(),
            })
            SharedContext.broadcast_event({
                "event": "execution_state_changed",
                "action_id": action_id,
                "execution_id": exec_record.id or 0,
                "status": "FAILED",
                "timestamp": end_now.isoformat(),
            })

            return ExecutionResultResponse(
                execution_id=exec_record.id or 0,
                action_id=action_id,
                session_id=session_id,
                warehouse_id=warehouse_id,
                status="FAILED",
                action_type=target_plan.get("action_type", ""),
                started_at=now,
                completed_at=end_now,
                duration_ms=duration_ms,
                executed=False,
                message=f"Action '{action_id}' execution failed.",
                verification_status="PENDING",
                error_message=safe_error,
            )
