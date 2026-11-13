"""
Recommendation Explanation Engine (R6).

Assembles deterministic, auditable, and structured explanations of recommendation decisions
by synthesizing evidence from:
- R1 Recommendation Outcome History
- R2 Deterministic SHA-256 Fingerprinting
- R3 Observational Current Condition Awareness
- R4 Recommendation Decision Engine
- R5 Recommendation Lifecycle & Suppression State

CRITICAL GUARANTEES (R6):
- Strictly DETERMINISTIC: Uses template-based reasoning from structured facts.
- ZERO LLM/AI dependency: No OpenAI, Gemini, Claude, Ollama, or generative model calls.
- ZERO hidden chain-of-thought: Only structured, auditable evidence and clear human summaries.
- ZERO warehouse mutations: Strictly observational and analytical.
- Preserves tenant isolation and credential redaction.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RecommendationExplanationEngine:
    """
    Pure deterministic engine for building structured audit explanations for recommendation candidates.
    """

    @classmethod
    def generate_explanation(
        cls,
        candidate: Dict[str, Any],
        fingerprint: Optional[str] = None,
        historical_match: Optional[Dict[str, Any]] = None,
        current_condition: Optional[Dict[str, Any]] = None,
        decision_result: Optional[Dict[str, Any]] = None,
        lifecycle_state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Synthesize structured evidence and produce a deterministic explanation payload.

        Parameters
        ----------
        candidate : Dict[str, Any]
            The recommendation candidate dictionary.
        fingerprint : Optional[str]
            SHA-256 structural fingerprint string (R2).
        historical_match : Optional[Dict[str, Any]]
            Historical outcome match summary or record (R1/R2).
        current_condition : Optional[Dict[str, Any]]
            Current condition evaluation result (R3).
        decision_result : Optional[Dict[str, Any]]
            Decision engine result dict (R4).
        lifecycle_state : Optional[str]
            Lifecycle state string (R5: ACTIVE, SUPPRESSED, REVIEW, REOPENED).

        Returns
        -------
        Dict[str, Any]
            Structured, JSON-serializable RecommendationExplanation payload.
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

        schema = str(candidate.get("schema") or target.get("schema") or params.get("schema") or "public").strip().lower()
        table = str(candidate.get("table") or target.get("table") or params.get("table") or "").strip().lower()
        column = candidate.get("column") or target.get("column") or target.get("columns") or params.get("column") or params.get("columns")

        norm_target = {"schema": schema, "table": table}
        if column:
            norm_target["column"] = column

        # Extract R4 Decision
        decision = decision_result.get("decision", "REVIEW") if decision_result else "REVIEW"
        reason_code = decision_result.get("reason_code", "CURRENT_CONDITION_UNAVAILABLE") if decision_result else "CURRENT_CONDITION_UNAVAILABLE"
        decision_reason = decision_result.get("reason", "Decision rationale unavailable.") if decision_result else "Decision rationale unavailable."

        # Extract R3 Current Condition
        cond_status = current_condition.get("condition_status", "UNCERTAIN") if current_condition else "UNCERTAIN"
        cond_type = current_condition.get("condition_type", "UNKNOWN") if current_condition else "UNKNOWN"
        cond_reason = current_condition.get("reason", "Condition unevaluated.") if current_condition else "Condition unevaluated."
        raw_evidence = current_condition.get("evidence", []) if current_condition else []

        # Extract R1/R2 Historical Outcome
        hist_outcome = None
        match_found = False
        if historical_match and isinstance(historical_match, dict):
            match_found = bool(historical_match.get("match_found", True))
            mro = historical_match.get("most_recent_outcome")
            if isinstance(mro, dict):
                hist_outcome = mro.get("final_outcome") or mro.get("verification_status") or mro.get("approval_status")
            if not hist_outcome:
                hist_outcome = (
                    historical_match.get("final_outcome")
                    or historical_match.get("verification_status")
                    or historical_match.get("approval_status")
                )
            if hist_outcome:
                hist_outcome = str(hist_outcome).strip().upper()

        # Derive lifecycle state if not provided
        derived_lifecycle = lifecycle_state
        if not derived_lifecycle:
            if decision == "PROPOSE":
                derived_lifecycle = "REOPENED" if hist_outcome in ("ACHIEVED", "VERIFIED") else "ACTIVE"
            elif decision == "SUPPRESS":
                derived_lifecycle = "SUPPRESSED"
            else:
                derived_lifecycle = "REVIEW"

        # 1. Deterministic Human Summary (NO LLM, Template-Based)
        summary = cls._build_deterministic_summary(
            action_type=action_type,
            schema=schema,
            table=table,
            decision=decision,
            reason_code=reason_code,
            cond_status=cond_status,
            hist_outcome=hist_outcome,
            lifecycle_state=derived_lifecycle,
        )

        # 2. Historical Context Evidence
        historical_context = {
            "match_found": match_found,
            "fingerprint": fingerprint,
            "historical_outcome": hist_outcome,
            "previous_final_outcome": hist_outcome,
            "previous_action_id": historical_match.get("action_id") if historical_match else None,
            "previous_session_id": historical_match.get("session_id") if historical_match else None,
            "summary": f"Historical match {'found with outcome ' + str(hist_outcome) if match_found else 'not found'}."
        }

        # 3. Current Condition Evidence
        condition_context = {
            "condition_status": cond_status,
            "condition_state": cond_status,
            "condition_type": cond_type,
            "observed_reason": cond_reason,
            "observed_facts": cond_reason,
            "measurement_available": current_condition.get("measurement_available", True) if current_condition else True,
            "evidence": raw_evidence,
        }

        # 4. Structured Evidence Items
        decision_evidence = [
            {
                "source": "R2_FINGERPRINT",
                "field": "fingerprint",
                "value": fingerprint,
                "interpretation": f"Cryptographic identity SHA-256 fingerprint: {fingerprint[:12] if fingerprint else 'None'}",
            },
            {
                "source": "R1_OUTCOME_HISTORY",
                "field": "final_outcome",
                "value": hist_outcome,
                "interpretation": f"Previous outcome for matching fingerprint: {hist_outcome or 'No previous history'}",
            },
            {
                "source": "R3_CURRENT_CONDITION",
                "field": "condition_status",
                "value": cond_status,
                "interpretation": f"Current warehouse observation status: {cond_status} ({cond_reason})",
            },
            {
                "source": "R4_DECISION_ENGINE",
                "field": "reason_code",
                "value": reason_code,
                "interpretation": f"R4 decision rule applied: {reason_code} -> {decision}",
            },
        ]

        lifecycle_evidence = [
            {
                "source": "R5_LIFECYCLE_MANAGER",
                "field": "lifecycle_state",
                "value": derived_lifecycle,
                "interpretation": f"State-aware lifecycle transition: {derived_lifecycle}",
            }
        ]

        # 5. Uncertainty Representation
        uncertainty: Optional[Dict[str, Any]] = None
        if cond_status in ("UNCERTAIN", "NOT_MEASURABLE") or decision == "REVIEW":
            desc_text = f"Candidate requires manual review. Current condition status is {cond_status} and decision reason code is {reason_code}."
            uncertainty = {
                "uncertainty_type": cond_status if cond_status in ("UNCERTAIN", "NOT_MEASURABLE") else "LIFECYCLE_REVIEW",
                "description": desc_text,
                "status": cond_status,
                "reason": desc_text,
            }

        return {
            "recommendation_id": str(rec_id),
            "fingerprint": fingerprint,
            "action_type": action_type,
            "target": norm_target,
            "decision": decision,
            "decision_reason_code": reason_code,
            "reason_code": reason_code,
            "decision_reason": decision_reason,
            "lifecycle_state": derived_lifecycle,
            "summary": summary,
            "historical_context": historical_context,
            "current_condition": condition_context,
            "decision_evidence": decision_evidence,
            "lifecycle_evidence": lifecycle_evidence,
            "uncertainty": uncertainty,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def _build_deterministic_summary(
        cls,
        action_type: str,
        schema: str,
        table: str,
        decision: str,
        reason_code: str,
        cond_status: str,
        hist_outcome: Optional[str],
        lifecycle_state: str,
    ) -> str:
        """
        Generate a deterministic, template-based human-readable explanation summary.
        NO LLM calls or free-form hallucination.
        """
        target_str = f"table '{schema}.{table}'" if table else f"schema '{schema}'"

        if decision == "PROPOSE":
            if reason_code == "CONDITION_REAPPEARED":
                return f"Recommendation {action_type} proposed for {target_str} because the associated condition has reappeared (PRESENT) after a matching recommendation previously achieved its objective."
            else:
                return f"Recommendation {action_type} proposed for {target_str} because no previous history exists and the associated condition is currently present in the warehouse."

        elif decision == "SUPPRESS":
            if hist_outcome in ("ACHIEVED", "VERIFIED"):
                return f"Recommendation {action_type} suppressed for {target_str} because the associated condition is currently resolved (RESOLVED) and a matching recommendation previously achieved its objective."
            else:
                return f"Recommendation {action_type} suppressed for {target_str} because the associated condition is currently resolved in the warehouse."

        else:  # REVIEW
            if reason_code == "HISTORICAL_ACTION_FAILED":
                return f"Recommendation {action_type} for {target_str} requires manual review because an equivalent previous action failed while the condition remains present in the warehouse."
            elif reason_code == "HISTORICAL_RECOMMENDATION_REJECTED":
                return f"Recommendation {action_type} for {target_str} requires manual review because an equivalent recommendation was previously rejected by a user while the condition remains present."
            elif reason_code == "CONDITION_UNCERTAIN":
                return f"Recommendation {action_type} for {target_str} requires manual review because the current warehouse condition could not be conclusively determined from available catalog statistics."
            elif reason_code == "CONDITION_NOT_MEASURABLE":
                return f"Recommendation {action_type} for {target_str} requires manual review because no authoritative warehouse condition evaluator exists for recommendation type '{action_type}'."
            else:
                return f"Recommendation {action_type} for {target_str} requires manual review due to reason '{reason_code}'."
