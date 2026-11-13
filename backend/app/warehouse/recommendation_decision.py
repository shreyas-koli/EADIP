"""
Recommendation Decision Engine (R4).

Combines:
1. R1 Historical Outcome ("What happened to this recommendation before?")
2. R2 Fingerprint ("Is this candidate structurally identical?")
3. R3 Current Condition ("What measurable condition exists in the warehouse right now?")

Produces a structured, deterministic recommendation lifecycle decision:
- PROPOSE: Candidate condition is observed (PRESENT) and should be proposed.
- SUPPRESS: Candidate condition is resolved (RESOLVED) and should not be proposed in active set right now.
- REVIEW: Unsafe or ambiguous (historical FAILED/REJECTED/UNCERTAIN or condition UNCERTAIN/NOT_MEASURABLE).

CRITICAL BOUNDARY GUARANTEES (R4):
- NO warehouse mutations.
- NO automatic execution or SQL statements.
- NO AI/LLM non-determinism.
- NO permanent suppression (state-aware per evaluation).
- NO alteration of RecommendationAgent candidate generation.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RecommendationDecisionState:
    PROPOSE = "PROPOSE"
    SUPPRESS = "SUPPRESS"
    REVIEW = "REVIEW"


class DecisionReasonCode:
    NO_HISTORY_CONDITION_PRESENT = "NO_HISTORY_CONDITION_PRESENT"
    NO_HISTORY_CONDITION_RESOLVED = "NO_HISTORY_CONDITION_RESOLVED"
    CONDITION_REAPPEARED = "CONDITION_REAPPEARED"
    CONDITION_RESOLVED = "CONDITION_RESOLVED"
    HISTORICAL_ACTION_FAILED = "HISTORICAL_ACTION_FAILED"
    HISTORICAL_FAILED_CONDITION_RESOLVED = "HISTORICAL_FAILED_CONDITION_RESOLVED"
    HISTORICAL_RECOMMENDATION_REJECTED = "HISTORICAL_RECOMMENDATION_REJECTED"
    HISTORICAL_OUTCOME_UNCERTAIN = "HISTORICAL_OUTCOME_UNCERTAIN"
    CONDITION_UNCERTAIN = "CONDITION_UNCERTAIN"
    CONDITION_NOT_MEASURABLE = "CONDITION_NOT_MEASURABLE"
    CURRENT_CONDITION_UNAVAILABLE = "CURRENT_CONDITION_UNAVAILABLE"


class RecommendationDecisionEngine:
    """
    Pure deterministic policy engine for evaluating recommendation candidates against
    historical matches (R1/R2) and current warehouse catalog evidence (R3).
    """

    @classmethod
    def make_decision(
        cls,
        candidate: Dict[str, Any],
        fingerprint: Optional[str] = None,
        historical_match: Optional[Dict[str, Any]] = None,
        current_condition: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate inputs and return a structured R4 decision payload.

        Parameters
        ----------
        candidate : Dict[str, Any]
            The recommendation candidate dictionary.
        fingerprint : Optional[str]
            SHA-256 structural fingerprint string.
        historical_match : Optional[Dict[str, Any]]
            Most recent historical match dictionary (from R1/R2).
        current_condition : Optional[Dict[str, Any]]
            Current condition evaluation dictionary (from R3).

        Returns
        -------
        Dict[str, Any]
            Structured decision payload containing decision, reason_code, reason, and evidence.
        """
        rec_id = candidate.get("recommendation_id") or candidate.get("id") or "rec_unknown"
        action_type = (
            candidate.get("action_type")
            or candidate.get("recommendation_type")
            or candidate.get("type")
            or candidate.get("category")
            or "UNKNOWN"
        ).strip().upper()

        target = candidate.get("target") if isinstance(candidate.get("target"), dict) else {}
        params = candidate.get("parameters") if isinstance(candidate.get("parameters"), dict) else {}

        schema = (
            candidate.get("schema")
            or target.get("schema")
            or params.get("schema")
            or "public"
        )
        table = (
            candidate.get("table")
            or target.get("table")
            or params.get("table")
            or ""
        )
        column = (
            candidate.get("column")
            or target.get("column")
            or target.get("columns")
            or params.get("column")
            or params.get("columns")
        )

        norm_target = {
            "schema": str(schema).strip().lower(),
            "table": str(table).strip().lower(),
        }
        if column:
            norm_target["column"] = column

        # Extract current condition status
        cond_status = current_condition.get("condition_status") if current_condition else None
        evidence = current_condition.get("evidence", []) if current_condition else []

        # Extract historical outcome status
        hist_outcome = None
        if historical_match and isinstance(historical_match, dict):
            hist_outcome = (
                historical_match.get("final_outcome")
                or historical_match.get("verification_status")
                or historical_match.get("approval_status")
            )
            if hist_outcome:
                hist_outcome = str(hist_outcome).strip().upper()

        # Deterministic Decision Matrix
        decision: str
        reason_code: str
        reason: str

        if not current_condition:
            decision = RecommendationDecisionState.REVIEW
            reason_code = DecisionReasonCode.CURRENT_CONDITION_UNAVAILABLE
            reason = "Current condition evaluation is missing or unavailable for this candidate."

        elif cond_status == "UNCERTAIN":
            decision = RecommendationDecisionState.REVIEW
            reason_code = DecisionReasonCode.CONDITION_UNCERTAIN
            reason = f"Current warehouse condition for '{norm_target['schema']}.{norm_target['table']}' is ambiguous or insufficient to make an automated decision."

        elif cond_status == "NOT_MEASURABLE":
            decision = RecommendationDecisionState.REVIEW
            reason_code = DecisionReasonCode.CONDITION_NOT_MEASURABLE
            reason = f"No authoritative warehouse condition evaluator exists to measure recommendation type '{action_type}'."

        elif not hist_outcome:
            # Case A & B: No historical match
            if cond_status == "PRESENT":
                decision = RecommendationDecisionState.PROPOSE
                reason_code = DecisionReasonCode.NO_HISTORY_CONDITION_PRESENT
                reason = f"No previous equivalent recommendation exists and the associated condition is currently observable on '{norm_target['schema']}.{norm_target['table']}'."
            elif cond_status == "RESOLVED":
                decision = RecommendationDecisionState.SUPPRESS
                reason_code = DecisionReasonCode.NO_HISTORY_CONDITION_RESOLVED
                reason = f"No previous recommendation exists and the associated condition is currently resolved on '{norm_target['schema']}.{norm_target['table']}'."
            else:
                decision = RecommendationDecisionState.REVIEW
                reason_code = DecisionReasonCode.CONDITION_UNCERTAIN
                reason = "Current condition status is unrecognized."

        elif hist_outcome in ("ACHIEVED", "VERIFIED"):
            # Case C & D: Historical ACHIEVED
            if cond_status == "PRESENT":
                decision = RecommendationDecisionState.PROPOSE
                reason_code = DecisionReasonCode.CONDITION_REAPPEARED
                reason = f"Equivalent recommendation previously achieved its objective, but the associated condition has reappeared in current warehouse state on '{norm_target['schema']}.{norm_target['table']}'."
            elif cond_status == "RESOLVED":
                decision = RecommendationDecisionState.SUPPRESS
                reason_code = DecisionReasonCode.CONDITION_RESOLVED
                reason = f"The equivalent recommendation previously achieved its objective and the associated condition remains resolved on '{norm_target['schema']}.{norm_target['table']}'."
            else:
                decision = RecommendationDecisionState.REVIEW
                reason_code = DecisionReasonCode.CONDITION_UNCERTAIN
                reason = "Current condition status is unrecognized."

        elif hist_outcome in ("FAILED", "NOT_ACHIEVED", "VERIFICATION_FAILED"):
            # Historical FAILED
            if cond_status == "PRESENT":
                decision = RecommendationDecisionState.REVIEW
                reason_code = DecisionReasonCode.HISTORICAL_ACTION_FAILED
                reason = f"An equivalent previous action failed on '{norm_target['schema']}.{norm_target['table']}' while the associated condition is currently present."
            elif cond_status == "RESOLVED":
                decision = RecommendationDecisionState.SUPPRESS
                reason_code = DecisionReasonCode.HISTORICAL_FAILED_CONDITION_RESOLVED
                reason = f"Equivalent recommendation previously failed, but the associated condition is currently resolved on '{norm_target['schema']}.{norm_target['table']}'."
            else:
                decision = RecommendationDecisionState.REVIEW
                reason_code = DecisionReasonCode.CONDITION_UNCERTAIN
                reason = "Current condition status is unrecognized."

        elif hist_outcome == "REJECTED":
            # Historical REJECTED
            if cond_status == "PRESENT":
                decision = RecommendationDecisionState.REVIEW
                reason_code = DecisionReasonCode.HISTORICAL_RECOMMENDATION_REJECTED
                reason = f"An equivalent recommendation was previously rejected by a user while the associated condition is currently present on '{norm_target['schema']}.{norm_target['table']}'."
            elif cond_status == "RESOLVED":
                decision = RecommendationDecisionState.SUPPRESS
                reason_code = DecisionReasonCode.CONDITION_RESOLVED
                reason = f"An equivalent recommendation was previously rejected and the associated condition is currently resolved on '{norm_target['schema']}.{norm_target['table']}'."
            else:
                decision = RecommendationDecisionState.REVIEW
                reason_code = DecisionReasonCode.CONDITION_UNCERTAIN
                reason = "Current condition status is unrecognized."

        else:
            # Historical UNCERTAIN / INCONCLUSIVE / PENDING / PROPOSED
            if cond_status == "PRESENT":
                decision = RecommendationDecisionState.REVIEW
                reason_code = DecisionReasonCode.HISTORICAL_OUTCOME_UNCERTAIN
                reason = f"Historical outcome for equivalent recommendation is inconclusive while the condition is present on '{norm_target['schema']}.{norm_target['table']}'."
            elif cond_status == "RESOLVED":
                decision = RecommendationDecisionState.SUPPRESS
                reason_code = DecisionReasonCode.CONDITION_RESOLVED
                reason = f"The associated current condition is resolved on '{norm_target['schema']}.{norm_target['table']}'."
            else:
                decision = RecommendationDecisionState.REVIEW
                reason_code = DecisionReasonCode.CONDITION_UNCERTAIN
                reason = "Current condition status is unrecognized."

        return {
            "recommendation_id": str(rec_id),
            "fingerprint": fingerprint,
            "action_type": action_type,
            "target": norm_target,
            "decision": decision,
            "reason_code": reason_code,
            "reason": reason,
            "historical_outcome": hist_outcome,
            "current_condition_status": cond_status,
            "evidence": evidence,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }
