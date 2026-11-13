"""
Recommendation Decision Service (R4).

Orchestrates recommendation lifecycle decision-making by synthesizing:
- R1 Historical Outcome History
- R2 Deterministic SHA-256 Fingerprinting
- R3 Observational Current Condition Awareness

Enforces warehouse tenant authorization, calculates deterministic decisions via RecommendationDecisionEngine,
and stores decision outputs in SharedContext / emits execution telemetry.

CRITICAL SAFETY & SCOPE GUARANTEES:
- Strict authorization: Enforces warehouse ownership via get_warehouse_by_id.
- Zero warehouse mutations: Operates entirely on catalog observations and historical outcome records.
- Zero automatic SQL execution or approval bypassing.
- Deterministic decision matrix (PROPOSE / SUPPRESS / REVIEW).
"""

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.context.shared_context import SharedContext
from app.models.user import User
from app.services.current_condition_service import CurrentConditionService
from app.services.recommendation_fingerprint_service import RecommendationFingerprintService
from app.warehouse.current_condition import CurrentConditionEvaluator
from app.warehouse.recommendation_decision import RecommendationDecisionEngine
from app.warehouse.service import get_warehouse_by_id

logger = logging.getLogger(__name__)


class RecommendationDecisionService:
    """
    Service layer orchestrating multi-layered R1-R4 recommendation decision evaluation.
    """

    @classmethod
    def evaluate_candidate_decision(
        cls,
        db: Session,
        warehouse_id: int,
        candidate: Dict[str, Any],
        user: User,
    ) -> Dict[str, Any]:
        """
        Evaluate recommendation lifecycle decision for a single recommendation candidate.

        Parameters
        ----------
        db : Session
            SQLAlchemy database session.
        warehouse_id : int
            Target warehouse identifier.
        candidate : Dict[str, Any]
            Candidate recommendation payload.
        user : User
            Authenticated user requesting evaluation.

        Returns
        -------
        Dict[str, Any]
            Structured R4 decision payload.
        """
        # 1. Authorize warehouse access
        warehouse = get_warehouse_by_id(db, warehouse_id, user)
        if not warehouse:
            raise PermissionError(f"Warehouse {warehouse_id} not found or access denied for user {user.id}.")

        # 2. Compute R2 Fingerprint and retrieve R1 historical outcome match
        match_summary = RecommendationFingerprintService.find_matches_for_candidate(
            db=db,
            warehouse_id=warehouse_id,
            candidate=candidate,
            limit=5,
        )
        fingerprint = match_summary.get("fingerprint")
        most_recent_match = match_summary["matches"][0] if match_summary.get("matches") else None

        # 3. Evaluate R3 Current Condition
        current_condition = CurrentConditionEvaluator.evaluate_current_condition(
            warehouse=warehouse,
            candidate=candidate,
            historical_match=most_recent_match,
            fingerprint=fingerprint,
        )

        # 4. Make deterministic R4 Decision
        decision_result = RecommendationDecisionEngine.make_decision(
            candidate=candidate,
            fingerprint=fingerprint,
            historical_match=most_recent_match,
            current_condition=current_condition,
        )

        return decision_result

    @classmethod
    def evaluate_candidates_batch(
        cls,
        db: Session,
        warehouse_id: int,
        candidates: List[Dict[str, Any]],
        user: User,
        context: Optional[SharedContext] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate R4 recommendation decisions for a list of candidate recommendations.

        Categorizes recommendations into:
        - active_recommendations (decision == PROPOSE)
        - suppressed_recommendations (decision == SUPPRESS)
        - review_recommendations (decision == REVIEW)

        Stores results in SharedContext if provided.
        """
        # 1. Authorize warehouse access
        warehouse = get_warehouse_by_id(db, warehouse_id, user)
        if not warehouse:
            raise PermissionError(f"Warehouse {warehouse_id} not found or access denied for user {user.id}.")

        decisions: List[Dict[str, Any]] = []
        propose_list: List[Dict[str, Any]] = []
        suppress_list: List[Dict[str, Any]] = []
        review_list: List[Dict[str, Any]] = []

        for candidate in candidates:
            try:
                dec = cls.evaluate_candidate_decision(
                    db=db,
                    warehouse_id=warehouse_id,
                    candidate=candidate,
                    user=user,
                )
                decisions.append(dec)

                rec_with_decision = {**candidate, "r4_decision": dec}

                if dec["decision"] == "PROPOSE":
                    propose_list.append(rec_with_decision)
                elif dec["decision"] == "SUPPRESS":
                    suppress_list.append(rec_with_decision)
                else:
                    review_list.append(rec_with_decision)

            except Exception as exc:
                logger.error(f"Error evaluating R4 decision for candidate {candidate}: {exc}")
                fallback_dec = {
                    "recommendation_id": candidate.get("recommendation_id") or candidate.get("id") or "rec_unknown",
                    "fingerprint": None,
                    "action_type": candidate.get("action_type") or candidate.get("recommendation_type") or "UNKNOWN",
                    "target": candidate.get("target") or {},
                    "decision": "REVIEW",
                    "reason_code": "EVALUATION_ERROR",
                    "reason": f"Decision evaluation encountered an error: {str(exc)}",
                    "historical_outcome": None,
                    "current_condition_status": None,
                    "evidence": [],
                    "evaluated_at": "",
                }
                decisions.append(fallback_dec)
                review_list.append({**candidate, "r4_decision": fallback_dec})

        summary = {
            "total_candidates": len(candidates),
            "propose_count": len(propose_list),
            "suppress_count": len(suppress_list),
            "review_count": len(review_list),
            "decisions": decisions,
            "propose_candidates": propose_list,
            "suppress_candidates": suppress_list,
            "review_candidates": review_list,
        }

        if context:
            context.set_agent_result("recommendation_decision", summary)
            # Emit telemetry event
            context.broadcast_event({
                "event": "recommendation_decision",
                "warehouse_id": warehouse_id,
                "summary": {
                    "total_candidates": len(candidates),
                    "propose_count": len(propose_list),
                    "suppress_count": len(suppress_list),
                    "review_count": len(review_list),
                },
            })

        return summary
