"""
Recommendation Explanation Service (R6).

Orchestrates structured audit explanation generation by consolidating:
- R1 Recommendation Outcome History
- R2 Deterministic SHA-256 Fingerprinting
- R3 Current Condition Awareness
- R4 Decision Engine Policy Rationale
- R5 Lifecycle & Suppression Transitions

CRITICAL SECURITY & AUDIT GUARANTEES:
- Enforces user authentication and warehouse ownership.
- Zero warehouse mutations: Performs strictly read-only audit synthesis.
- Zero AI/LLM dependency: Uses deterministic evidence templates.
- Redacts database credentials and sensitive row contents.
"""

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.context.shared_context import SharedContext
from app.models.user import User
from app.models.recommendation_explanation_record import RecommendationExplanationRecord
from app.services.recommendation_fingerprint_service import RecommendationFingerprintService
from app.warehouse.current_condition import CurrentConditionEvaluator
from app.warehouse.recommendation_decision import RecommendationDecisionEngine
from app.warehouse.recommendation_explanation import RecommendationExplanationEngine
from app.warehouse.service import get_warehouse_by_id

logger = logging.getLogger(__name__)


class RecommendationExplanationService:
    """
    Service layer for authorized R6 recommendation explanation & auditability.
    Supports durable DB persistence and historical explanation retrievability.
    """

    @classmethod
    def get_candidate_explanation(
        cls,
        db: Session,
        warehouse_id: int,
        candidate: Dict[str, Any],
        user: User,
        lifecycle_state: Optional[str] = None,
        session_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate a structured, auditable explanation payload for a single candidate.
        If session_id is provided and a persisted record exists, returns the persisted record.
        Otherwise synthesizes the explanation and persists it if session_id is available.
        """
        # 1. Authorize warehouse ownership
        warehouse = get_warehouse_by_id(db, warehouse_id, user)
        if not warehouse:
            raise PermissionError(f"Warehouse {warehouse_id} not found or access denied for user {user.id}.")

        effective_session_id = session_id or candidate.get("session_id")
        rec_id = str(candidate.get("recommendation_id") or candidate.get("id") or "rec_unknown")

        # Check for existing persisted record if session_id is provided
        if effective_session_id and db is not None:
            existing_record = db.query(RecommendationExplanationRecord).filter(
                RecommendationExplanationRecord.session_id == int(effective_session_id),
                RecommendationExplanationRecord.recommendation_id == rec_id,
            ).first()
            if existing_record:
                return cls._record_to_dict(existing_record)

        # 2. Retrieve R2 fingerprint and R1 historical matches
        match_summary = RecommendationFingerprintService.find_matches_for_candidate(
            db=db,
            warehouse_id=warehouse_id,
            candidate=candidate,
            limit=5,
        )
        fingerprint = match_summary.get("fingerprint")
        most_recent_match = match_summary["matches"][0] if match_summary.get("matches") else None

        # 3. Evaluate R3 current condition
        current_condition = CurrentConditionEvaluator.evaluate_current_condition(
            warehouse=warehouse,
            candidate=candidate,
            historical_match=most_recent_match,
            fingerprint=fingerprint,
        )

        # 4. Evaluate R4 recommendation decision
        decision_result = RecommendationDecisionEngine.make_decision(
            candidate=candidate,
            fingerprint=fingerprint,
            historical_match=most_recent_match,
            current_condition=current_condition,
        )

        # 5. Synthesize R6 structured explanation
        explanation = RecommendationExplanationEngine.generate_explanation(
            candidate=candidate,
            fingerprint=fingerprint,
            historical_match=most_recent_match,
            current_condition=current_condition,
            decision_result=decision_result,
            lifecycle_state=lifecycle_state,
        )

        if effective_session_id and db is not None:
            explanation["session_id"] = int(effective_session_id)
            record = cls.persist_explanation_record(db, warehouse_id, int(effective_session_id), explanation)
            return cls._record_to_dict(record)

        return explanation

    @classmethod
    def get_historical_explanation(
        cls,
        db: Session,
        warehouse_id: int,
        recommendation_id: str,
        user: User,
        session_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a persisted historical explanation record from DB WITHOUT re-evaluating live catalog state.
        """
        warehouse = get_warehouse_by_id(db, warehouse_id, user)
        if not warehouse:
            raise PermissionError(f"Warehouse {warehouse_id} not found or access denied for user {user.id}.")

        query = db.query(RecommendationExplanationRecord).filter(
            RecommendationExplanationRecord.warehouse_id == warehouse_id,
            RecommendationExplanationRecord.recommendation_id == recommendation_id,
        )
        if session_id is not None:
            query = query.filter(RecommendationExplanationRecord.session_id == session_id)

        record = query.order_by(RecommendationExplanationRecord.created_at.desc()).first()
        if not record:
            return None

        return cls._record_to_dict(record)

    @classmethod
    def persist_explanation_record(
        cls,
        db: Session,
        warehouse_id: int,
        session_id: int,
        explanation: Dict[str, Any],
    ) -> RecommendationExplanationRecord:
        """
        Persist an immutable RecommendationExplanationRecord for a discovery session.
        Idempotent: returns existing record if present.
        """
        rec_id = str(explanation.get("recommendation_id") or "rec_unknown")

        existing = db.query(RecommendationExplanationRecord).filter(
            RecommendationExplanationRecord.session_id == session_id,
            RecommendationExplanationRecord.recommendation_id == rec_id,
        ).first()

        if existing:
            return existing

        record = RecommendationExplanationRecord(
            recommendation_id=rec_id,
            action_id=str(explanation.get("action_id")) if explanation.get("action_id") else None,
            session_id=session_id,
            warehouse_id=warehouse_id,
            action_type=str(explanation.get("action_type") or "UNKNOWN"),
            fingerprint=explanation.get("fingerprint"),
            target=explanation.get("target"),
            decision=str(explanation.get("decision") or "REVIEW"),
            decision_reason_code=str(explanation.get("decision_reason_code") or explanation.get("reason_code") or "CURRENT_CONDITION_UNAVAILABLE"),
            decision_reason=str(explanation.get("decision_reason") or ""),
            lifecycle_state=str(explanation.get("lifecycle_state") or "REVIEW"),
            summary=str(explanation.get("summary") or ""),
            historical_context=explanation.get("historical_context"),
            current_condition=explanation.get("current_condition"),
            decision_evidence=explanation.get("decision_evidence"),
            lifecycle_evidence=explanation.get("lifecycle_evidence"),
            uncertainty=explanation.get("uncertainty"),
        )
        db.add(record)
        try:
            db.commit()
            db.refresh(record)
        except Exception as exc:
            db.rollback()
            logger.warning(f"Error persisting RecommendationExplanationRecord: {exc}")
            existing = db.query(RecommendationExplanationRecord).filter(
                RecommendationExplanationRecord.session_id == session_id,
                RecommendationExplanationRecord.recommendation_id == rec_id,
            ).first()
            if existing:
                return existing
        return record

    @classmethod
    def generate_explanations_batch(
        cls,
        db: Session,
        warehouse_id: int,
        candidates: List[Dict[str, Any]],
        user: User,
        session_id: Optional[int] = None,
        context: Optional[SharedContext] = None,
    ) -> Dict[str, Any]:
        """
        Generate structured explanations for candidate recommendations in a discovery session and persist them.
        """
        warehouse = get_warehouse_by_id(db, warehouse_id, user)
        if not warehouse:
            raise PermissionError(f"Warehouse {warehouse_id} not found or access denied for user {user.id}.")

        explanations: List[Dict[str, Any]] = []
        for candidate in candidates:
            try:
                exp = cls.get_candidate_explanation(
                    db=db,
                    warehouse_id=warehouse_id,
                    candidate=candidate,
                    user=user,
                    session_id=session_id,
                )
                explanations.append(exp)
            except Exception as exc:
                logger.error(f"Error generating R6 explanation for candidate {candidate}: {exc}")
                fallback = {
                    "recommendation_id": candidate.get("recommendation_id") or candidate.get("id") or "rec_unknown",
                    "fingerprint": None,
                    "action_type": candidate.get("action_type") or candidate.get("recommendation_type") or "UNKNOWN",
                    "target": candidate.get("target") or {},
                    "decision": "REVIEW",
                    "decision_reason_code": "EXPLANATION_ERROR",
                    "decision_reason": f"Explanation generation encountered error: {str(exc)}",
                    "lifecycle_state": "REVIEW",
                    "summary": f"Explanation generation failed with error: {str(exc)}",
                    "historical_context": {"match_found": False},
                    "current_condition": {"condition_status": "UNCERTAIN"},
                    "decision_evidence": [],
                    "lifecycle_evidence": [],
                    "uncertainty": {"uncertainty_type": "ERROR", "description": str(exc)},
                    "generated_at": "",
                }
                explanations.append(fallback)

        batch_summary = {
            "total_explanations": len(explanations),
            "explanations": explanations,
        }

        if context:
            context.set_agent_result("recommendation_explanation", batch_summary)
            context.broadcast_event({
                "event": "recommendation_explanation_generated",
                "warehouse_id": warehouse_id,
                "total_explanations": len(explanations),
            })

        return batch_summary

    @staticmethod
    def _record_to_dict(rec: RecommendationExplanationRecord) -> Dict[str, Any]:
        """Convert a RecommendationExplanationRecord ORM object into a dictionary payload."""
        return {
            "recommendation_id": rec.recommendation_id,
            "action_id": rec.action_id,
            "session_id": rec.session_id,
            "warehouse_id": rec.warehouse_id,
            "fingerprint": rec.fingerprint,
            "action_type": rec.action_type,
            "target": rec.target or {},
            "decision": rec.decision,
            "decision_reason_code": rec.decision_reason_code,
            "reason_code": rec.decision_reason_code,
            "decision_reason": rec.decision_reason,
            "lifecycle_state": rec.lifecycle_state,
            "summary": rec.summary,
            "historical_context": rec.historical_context or {"match_found": False},
            "current_condition": rec.current_condition or {"condition_status": "UNCERTAIN"},
            "decision_evidence": rec.decision_evidence or [],
            "lifecycle_evidence": rec.lifecycle_evidence or [],
            "uncertainty": rec.uncertainty,
            "generated_at": rec.created_at.isoformat() if rec.created_at else "",
        }

