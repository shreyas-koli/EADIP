"""
Recommendation outcome service layer (R1: Recommendation Outcome History).

Provides historical outcome aggregation, lifecycle synchronization, idempotency,
and security controls for tracking recommendation execution & verification lifecycles.

CRITICAL SCOPE RESTRICTION (R1):
- History ONLY.
- Does NOT alter Recommendation Agent decision logic or suppress/block recommendations.
- Final outcomes are derived strictly from authoritative downstream records (Approval, Execution, Verification, Re-analysis).
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.context.shared_context import SharedContext
from app.models.action_execution_record import ActionExecutionRecord
from app.models.action_verification_record import ActionVerificationRecord
from app.models.approval import ActionApproval
from app.models.execution import DiscoverySession
from app.models.recommendation_outcome_record import RecommendationOutcomeRecord
from app.models.supervisor_reanalysis_record import SupervisorReanalysisRecord
from app.models.user import User
from app.models.warehouse import Warehouse
from app.warehouse.service import get_warehouse_by_id

logger = logging.getLogger(__name__)


class RecommendationOutcomeService:
    """
    Business logic service for reconstructing and querying historical outcomes
    of warehouse recommendations and action plans.
    """

    @staticmethod
    def derive_final_outcome(
        approval: Optional[ActionApproval] = None,
        execution: Optional[ActionExecutionRecord] = None,
        verification: Optional[ActionVerificationRecord] = None,
        reanalysis: Optional[SupervisorReanalysisRecord] = None,
        default_status: str = "PROPOSED",
    ) -> str:
        """
        Derive the final outcome state from authoritative downstream workflow records.

        Precedence (Highest to Lowest):
        1. Supervisor Re-analysis (ACHIEVED, NOT_ACHIEVED, UNCERTAIN)
        2. Action Verification (VERIFIED, VERIFICATION_FAILED, INCONCLUSIVE)
        3. Action Execution (FAILED, COMPLETED, EXECUTING)
        4. User Approval (REJECTED, APPROVED)
        5. Action Plan creation (PROPOSED)
        """
        if reanalysis is not None:
            if reanalysis.objective_status in ("ACHIEVED", "NOT_ACHIEVED", "UNCERTAIN"):
                return reanalysis.objective_status
            if reanalysis.status in ("SUCCESSFUL_OUTCOME", "UNSUCCESSFUL_OUTCOME", "UNCERTAIN_OUTCOME"):
                if reanalysis.status == "SUCCESSFUL_OUTCOME":
                    return "ACHIEVED"
                elif reanalysis.status == "UNSUCCESSFUL_OUTCOME":
                    return "NOT_ACHIEVED"
                else:
                    return "UNCERTAIN"

        if verification is not None:
            if verification.status in ("VERIFIED", "VERIFICATION_FAILED", "INCONCLUSIVE"):
                return verification.status

        if execution is not None:
            if execution.status == "FAILED":
                return "FAILED"
            elif execution.status == "COMPLETED":
                # If execution completed but verification is pending, report COMPLETED
                return "COMPLETED"
            elif execution.status == "EXECUTING":
                return "EXECUTING"

        if approval is not None:
            if approval.status in ("APPROVED", "REJECTED"):
                return approval.status

        return default_status

    @classmethod
    def sync_action_outcome(
        cls,
        db: Session,
        warehouse_id: int,
        session_id: str,
        action_id: str,
        user: Optional[User] = None,
    ) -> RecommendationOutcomeRecord:
        """
        Synchronize and persist the canonical historical outcome record for a specific action plan.

        Idempotent: updates existing record if present for (action_id, session_id), otherwise creates one.
        """
        now = datetime.now(timezone.utc)

        # 1. Retrieve DiscoverySession
        stmt_sess = select(DiscoverySession).where(
            DiscoverySession.session_id == session_id,
            DiscoverySession.warehouse_id == warehouse_id,
        )
        session_obj = db.execute(stmt_sess).scalar_one_or_none()
        if session_obj is None:
            raise ValueError(f"Discovery session '{session_id}' not found for warehouse {warehouse_id}.")

        # 2. Locate target action plan details from recommendations JSONB
        recs = session_obj.recommendations or {}
        automation_data = recs.get("automation") or {}
        action_plans = automation_data.get("action_plans", [])

        target_plan = None
        for plan in action_plans:
            if plan.get("action_id") == action_id:
                target_plan = plan
                break

        action_type = target_plan.get("action_type", "UNKNOWN") if target_plan else "UNKNOWN"
        target_info = target_plan.get("target") if target_plan else None
        rec_id = (target_plan.get("recommendation_id") if target_plan else None) or action_id

        # 3. Retrieve authoritative downstream records
        # Approval Record
        stmt_appr = select(ActionApproval).where(
            ActionApproval.action_id == action_id,
            ActionApproval.session_id == session_obj.id,
        )
        approval_obj = db.execute(stmt_appr).scalar_one_or_none()

        # Execution Record (latest execution attempt)
        stmt_exec = select(ActionExecutionRecord).where(
            ActionExecutionRecord.action_id == action_id,
            ActionExecutionRecord.session_id == session_obj.id,
        ).order_by(ActionExecutionRecord.created_at.desc())
        execution_obj = db.execute(stmt_exec).scalars().first()

        # Verification Record (latest verification run for execution)
        verification_obj = None
        if execution_obj is not None:
            stmt_ver = select(ActionVerificationRecord).where(
                ActionVerificationRecord.execution_id == execution_obj.id
            ).order_by(ActionVerificationRecord.created_at.desc())
            verification_obj = db.execute(stmt_ver).scalars().first()

        # Supervisor Re-analysis Record
        reanalysis_obj = None
        if execution_obj is not None:
            stmt_re = select(SupervisorReanalysisRecord).where(
                SupervisorReanalysisRecord.execution_id == execution_obj.id
            ).order_by(SupervisorReanalysisRecord.created_at.desc())
            reanalysis_obj = db.execute(stmt_re).scalars().first()

        # 4. Derive authoritative outcome status values
        approval_status = approval_obj.status if approval_obj else (target_plan.get("status") if target_plan else "PROPOSED")
        execution_status = execution_obj.status if execution_obj else "PENDING"
        verification_status = verification_obj.status if verification_obj else (execution_obj.verification_status if execution_obj else "PENDING")
        reanalysis_status = reanalysis_obj.status if reanalysis_obj else "PENDING"
        objective_status = reanalysis_obj.objective_status if reanalysis_obj else "PENDING"

        final_outcome = cls.derive_final_outcome(
            approval=approval_obj,
            execution=execution_obj,
            verification=verification_obj,
            reanalysis=reanalysis_obj,
            default_status=approval_status,
        )

        # 5. User ID resolution
        effective_user_id = None
        if user:
            effective_user_id = user.id
        elif approval_obj:
            effective_user_id = approval_obj.user_id
        elif execution_obj:
            effective_user_id = execution_obj.user_id
        elif reanalysis_obj:
            effective_user_id = reanalysis_obj.user_id

        # 6. Retrieve or create canonical RecommendationOutcomeRecord (Idempotency)
        stmt_rec = select(RecommendationOutcomeRecord).where(
            RecommendationOutcomeRecord.action_id == action_id,
            RecommendationOutcomeRecord.session_id == session_obj.id,
        )
        record = db.execute(stmt_rec).scalar_one_or_none()

        # Calculate R2 structural fingerprint
        from app.services.recommendation_fingerprint_service import RecommendationFingerprintService
        fp = RecommendationFingerprintService.generate_fingerprint(
            action_type=action_type,
            target=target_info,
        )

        if record is None:
            record = RecommendationOutcomeRecord(
                recommendation_id=rec_id,
                action_id=action_id,
                session_id=session_obj.id,
                warehouse_id=warehouse_id,
                user_id=effective_user_id,
                action_type=action_type,
                target=target_info,
                approval_id=approval_obj.id if approval_obj else None,
                execution_id=execution_obj.id if execution_obj else None,
                verification_id=verification_obj.id if verification_obj else None,
                reanalysis_id=reanalysis_obj.id if reanalysis_obj else None,
                approval_status=approval_status,
                execution_status=execution_status,
                verification_status=verification_status,
                reanalysis_status=reanalysis_status,
                objective_status=objective_status,
                final_outcome=final_outcome,
                fingerprint=fp,
                created_at=now,
                updated_at=now,
            )
            db.add(record)
        else:
            record.recommendation_id = rec_id
            record.action_type = action_type
            if target_info:
                record.target = target_info
            if effective_user_id:
                record.user_id = effective_user_id
            record.approval_id = approval_obj.id if approval_obj else record.approval_id
            record.execution_id = execution_obj.id if execution_obj else record.execution_id
            record.verification_id = verification_obj.id if verification_obj else record.verification_id
            record.reanalysis_id = reanalysis_obj.id if reanalysis_obj else record.reanalysis_id
            record.approval_status = approval_status
            record.execution_status = execution_status
            record.verification_status = verification_status
            record.reanalysis_status = reanalysis_status
            record.objective_status = objective_status
            record.final_outcome = final_outcome
            record.fingerprint = fp
            record.updated_at = now

        try:
            db.commit()
            db.refresh(record)
        except Exception as exc:
            db.rollback()
            logger.error(f"Failed to commit outcome record for action '{action_id}' (session '{session_id}'): {exc}")
            raise

        # 7. Broadcast SSE telemetry update
        SharedContext.broadcast_event({
            "event": "recommendation_outcome_updated",
            "action_id": action_id,
            "session_id": session_id,
            "warehouse_id": warehouse_id,
            "final_outcome": final_outcome,
            "approval_status": approval_status,
            "execution_status": execution_status,
            "verification_status": verification_status,
            "objective_status": objective_status,
            "timestamp": now.isoformat(),
        })

        logger.info(
            f"Synced outcome for action '{action_id}' (session '{session_id}'): "
            f"final_outcome='{final_outcome}'."
        )

        return record

    @classmethod
    def sync_all_session_outcomes(
        cls,
        db: Session,
        warehouse_id: int,
        session_id: str,
    ) -> List[RecommendationOutcomeRecord]:
        """
        Synchronize historical outcome records for all action plans in a discovery session.
        """
        stmt_sess = select(DiscoverySession).where(
            DiscoverySession.session_id == session_id,
            DiscoverySession.warehouse_id == warehouse_id,
        )
        session_obj = db.execute(stmt_sess).scalar_one_or_none()
        if session_obj is None:
            return []

        recs = session_obj.recommendations or {}
        automation_data = recs.get("automation") or {}
        action_plans = automation_data.get("action_plans", [])

        records = []
        for plan in action_plans:
            action_id = plan.get("action_id")
            if action_id:
                try:
                    rec = cls.sync_action_outcome(db, warehouse_id, session_id, action_id)
                    records.append(rec)
                except Exception as exc:
                    db.rollback()
                    logger.warning(f"Failed to sync outcome for action '{action_id}' in session '{session_id}': {exc}")

        return records

    @classmethod
    def get_warehouse_history(
        cls,
        db: Session,
        warehouse_id: int,
        user: User,
        session_id: Optional[str] = None,
        final_outcome: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[RecommendationOutcomeRecord]:
        """
        Retrieve historical recommendation outcome records for a warehouse with authorization.
        """
        warehouse = get_warehouse_by_id(db, warehouse_id, user)
        if warehouse is None:
            raise PermissionError(f"Warehouse {warehouse_id} not found or access denied for user.")

        stmt = select(RecommendationOutcomeRecord).where(
            RecommendationOutcomeRecord.warehouse_id == warehouse.id
        )

        if session_id:
            stmt_sess = select(DiscoverySession).where(
                DiscoverySession.session_id == session_id,
                DiscoverySession.warehouse_id == warehouse.id,
            )
            session_obj = db.execute(stmt_sess).scalar_one_or_none()
            if session_obj:
                stmt = stmt.where(RecommendationOutcomeRecord.session_id == session_obj.id)
            else:
                return []

        if final_outcome:
            stmt = stmt.where(RecommendationOutcomeRecord.final_outcome == final_outcome.upper())

        stmt = stmt.order_by(RecommendationOutcomeRecord.updated_at.desc()).limit(limit).offset(offset)
        return list(db.execute(stmt).scalars().all())

    @classmethod
    def get_action_outcome(
        cls,
        db: Session,
        warehouse_id: int,
        session_id: str,
        action_id: str,
        user: User,
    ) -> Optional[RecommendationOutcomeRecord]:
        """
        Retrieve the historical recommendation outcome record for a specific action plan.
        """
        warehouse = get_warehouse_by_id(db, warehouse_id, user)
        if warehouse is None:
            raise PermissionError(f"Warehouse {warehouse_id} not found or access denied for user.")

        stmt_sess = select(DiscoverySession).where(
            DiscoverySession.session_id == session_id,
            DiscoverySession.warehouse_id == warehouse.id,
        )
        session_obj = db.execute(stmt_sess).scalar_one_or_none()
        if session_obj is None:
            raise ValueError(f"Discovery session '{session_id}' not found for warehouse {warehouse_id}.")

        stmt = select(RecommendationOutcomeRecord).where(
            RecommendationOutcomeRecord.action_id == action_id,
            RecommendationOutcomeRecord.session_id == session_obj.id,
            RecommendationOutcomeRecord.warehouse_id == warehouse.id,
        )
        return db.execute(stmt).scalar_one_or_none()
