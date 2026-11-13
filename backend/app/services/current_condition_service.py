"""
Current Condition Service (R3).

Orchestrates current-condition evaluation by validating warehouse authorization,
generating candidate fingerprints (R2), retrieving historical outcome context (R1/R2),
and executing read-only PostgreSQL catalog checks via CurrentConditionEvaluator.

CRITICAL SECURITY & SCOPE GUARANTEES:
- Enforces user authentication and warehouse ownership.
- Never mutates database or warehouse state.
- Never alters Recommendation Agent decision logic or generates recommendation suppressions.
- Redacts database credentials from log and exception outputs.
"""

import logging
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.models.user import User
from app.warehouse.service import get_warehouse_by_id
from app.services.recommendation_fingerprint_service import RecommendationFingerprintService
from app.warehouse.current_condition import CurrentConditionEvaluator

logger = logging.getLogger(__name__)


class CurrentConditionService:
    """
    Service layer for authorized R3 current condition evaluation.
    """

    @classmethod
    def evaluate_candidate_condition(
        cls,
        db: Session,
        warehouse_id: int,
        candidate: Dict[str, Any],
        user: User,
    ) -> Dict[str, Any]:
        """
        Evaluate the current warehouse condition for a given recommendation candidate.

        Parameters
        ----------
        db : Session
            SQLAlchemy database session.
        warehouse_id : int
            Target warehouse identifier.
        candidate : Dict[str, Any]
            Recommendation candidate dictionary.
        user : User
            Authenticated user performing the evaluation request.

        Returns
        -------
        Dict[str, Any]
            Structured R3 current condition evaluation payload.
        """
        # 1. Authorize warehouse ownership via existing service helper
        warehouse = get_warehouse_by_id(db, warehouse_id, user)
        if not warehouse:
            raise PermissionError(f"Warehouse {warehouse_id} not found or access denied for user {user.id}.")

        # 2. Generate R2 fingerprint and retrieve historical matches
        match_summary = RecommendationFingerprintService.find_matches_for_candidate(
            db=db,
            warehouse_id=warehouse_id,
            candidate=candidate,
            limit=5,
        )
        fingerprint = match_summary.get("fingerprint")
        most_recent_match = match_summary["matches"][0] if match_summary.get("matches") else None

        # 3. Evaluate current warehouse condition
        result = CurrentConditionEvaluator.evaluate_current_condition(
            warehouse=warehouse,
            candidate=candidate,
            historical_match=most_recent_match,
            fingerprint=fingerprint,
        )

        return result
