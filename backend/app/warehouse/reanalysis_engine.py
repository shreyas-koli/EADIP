"""
Controlled Re-analysis Engine (Phase 7).

Synthesizes pre-execution warehouse state, intended action plan, target execution results,
and Phase 6 verification evidence into a structured post-execution assessment.

CRITICAL SAFETY GUARANTEES:
- Strictly READ-ONLY analysis against the warehouse.
- Does NOT execute database mutations (INSERT, UPDATE, DELETE, DROP, ALTER, etc.).
- Does NOT automatically execute follow-up actions or retries.
- Does NOT automatically approve recommendations.
- Prevents fabricated causal claims: explicitly marks unmeasured latency/performance metrics as NOT_MEASURED.
"""

import time
import logging
from typing import Any, Dict, List, Optional

from app.models.warehouse import Warehouse

logger = logging.getLogger(__name__)


class ControlledReanalysisEngine:
    """
    Safe, controlled engine that evaluates post-execution outcomes and objective attainment
    by comparing pre-execution target state, execution metrics, and verification catalog evidence.
    """

    @classmethod
    def reanalyze(
        cls,
        warehouse: Warehouse,
        action_plan: Dict[str, Any],
        execution_data: Dict[str, Any],
        verification_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Synthesize post-execution assessment for an executed action plan.

        Parameters
        ──────────
        warehouse : Warehouse
            Target warehouse ORM instance.
        action_plan : Dict[str, Any]
            The action plan payload.
        execution_data : Dict[str, Any]
            The execution record data dict.
        verification_data : Optional[Dict[str, Any]]
            The verification record data dict (if available).

        Returns
        ───────
        Dict[str, Any]
            Re-analysis assessment payload containing:
            - ``status``: 'SUCCESSFUL_OUTCOME' | 'UNSUCCESSFUL_OUTCOME' | 'UNCERTAIN_OUTCOME'
            - ``objective_status``: 'ACHIEVED' | 'NOT_ACHIEVED' | 'UNCERTAIN'
            - ``before_state``: Dict[str, Any]
            - ``after_state``: Dict[str, Any]
            - ``comparisons``: List[Dict[str, Any]]
            - ``findings``: List[str]
            - ``conclusion``: str
            - ``follow_up_required``: bool
            - ``follow_up_type``: 'NONE' | 'OBSERVATION' | 'ANALYSIS' | 'RECOMMENDATION'
            - ``follow_up_details``: Optional[Dict[str, Any]]
            - ``duration_ms``: float
        """
        start_time = time.perf_counter()

        action_id = action_plan.get("action_id", "")
        action_type = action_plan.get("action_type", "")
        target = action_plan.get("target") or {}

        exec_status = execution_data.get("status", "FAILED")
        ver_status = verification_data.get("status", "INCONCLUSIVE") if verification_data else "INCONCLUSIVE"
        ver_verified = verification_data.get("verified") if verification_data else None

        # Build Before State snapshot from action plan & target
        before_state = {
            "target": target,
            "action_type": action_type,
            "statement": action_plan.get("statement"),
            "risk_level": action_plan.get("risk_level"),
            "safety_class": action_plan.get("safety_class"),
        }

        # Build After State snapshot from execution and verification outcomes
        after_state = {
            "execution_status": exec_status,
            "execution_duration_ms": execution_data.get("duration_ms"),
            "executed_statement": execution_data.get("statement_fingerprint"),
            "verification_status": ver_status,
            "verification_verified": ver_verified,
            "verification_checks": verification_data.get("checks", []) if verification_data else [],
            "error_message": execution_data.get("error_message") or (verification_data.get("error_message") if verification_data else None),
        }

        # Comparisons list: Structural check + Explicitly unmeasured performance metric
        comparisons: List[Dict[str, Any]] = [
            {
                "metric": "structural_catalog_state",
                "before": "UNVERIFIED",
                "after": ver_status,
                "status": "MATCH" if ver_status == "VERIFIED" else "MISMATCH",
                "evidence": f"Phase 6 catalog verification status is '{ver_status}'.",
            },
            {
                "metric": "query_latency_impact",
                "before": None,
                "after": None,
                "status": "NOT_MEASURED",
                "reason": "No comparable post-execution latency benchmark was captured.",
            }
        ]

        findings: List[str] = []
        follow_up_required = False
        follow_up_type = "NONE"
        follow_up_details: Optional[Dict[str, Any]] = None

        # Decision Logic Matrix
        if exec_status == "COMPLETED" and ver_status == "VERIFIED":
            status = "SUCCESSFUL_OUTCOME"
            objective_status = "ACHIEVED"
            findings.append(f"Action '{action_id}' executed successfully and target catalog state was verified by Phase 6.")
            findings.append("Structural objective achieved. Performance benchmark remains unmeasured.")
            conclusion = (
                f"Action '{action_id}' ({action_type}) achieved its structural objective on target table "
                f"'{target.get('table')}'. No further automated action required."
            )
        elif exec_status == "COMPLETED" and ver_status == "VERIFICATION_FAILED":
            status = "UNSUCCESSFUL_OUTCOME"
            objective_status = "NOT_ACHIEVED"
            follow_up_required = True
            follow_up_type = "ANALYSIS"
            findings.append(f"Action '{action_id}' execution completed, but Phase 6 catalog verification failed.")
            findings.append("The expected catalog modification was not observed in target metadata.")
            conclusion = (
                f"Action '{action_id}' executed but target state verification failed. "
                f"Follow-up analysis is recommended to investigate warehouse metadata."
            )
            follow_up_details = cls._build_proposed_follow_up(action_plan, "Verification failed; investigate catalog schema.")
        elif exec_status == "COMPLETED" and ver_status in ("INCONCLUSIVE", "PENDING"):
            status = "UNCERTAIN_OUTCOME"
            objective_status = "UNCERTAIN"
            follow_up_required = True
            follow_up_type = "OBSERVATION"
            findings.append(f"Action '{action_id}' execution completed, but catalog verification is '{ver_status}'.")
            conclusion = (
                f"Action '{action_id}' executed successfully, but verification outcome is inconclusive. "
                f"Additional observation is required."
            )
            follow_up_details = cls._build_proposed_follow_up(action_plan, "Verification outcome inconclusive; observe catalog state.")
        else:
            status = "UNSUCCESSFUL_OUTCOME"
            objective_status = "NOT_ACHIEVED"
            follow_up_required = True
            follow_up_type = "ANALYSIS"
            err_msg = execution_data.get("error_message") or "Target warehouse execution failed."
            findings.append(f"Action '{action_id}' execution failed: {err_msg}")
            conclusion = f"Action '{action_id}' failed during target execution: {err_msg}. Follow-up analysis required."
            follow_up_details = cls._build_proposed_follow_up(action_plan, f"Execution failed: {err_msg}")

        end_time = time.perf_counter()
        duration_ms = round((end_time - start_time) * 1000, 2)

        return {
            "status": status,
            "objective_status": objective_status,
            "before_state": before_state,
            "after_state": after_state,
            "comparisons": comparisons,
            "findings": findings,
            "conclusion": conclusion,
            "follow_up_required": follow_up_required,
            "follow_up_type": follow_up_type,
            "follow_up_details": follow_up_details,
            "duration_ms": duration_ms,
        }

    @staticmethod
    def _build_proposed_follow_up(action_plan: Dict[str, Any], reason: str) -> Dict[str, Any]:
        """
        Construct a safe follow-up action plan dictionary in PROPOSED state.

        MUST NEVER automatically execute or approve follow-up actions.
        Requires explicit user approval via Phase 4 gate.
        """
        action_id = action_plan.get("action_id", "act_followup")
        return {
            "follow_up_action_id": f"followup_{action_id}",
            "original_action_id": action_id,
            "action_type": action_plan.get("action_type", ""),
            "target": action_plan.get("target", {}),
            "status": "PROPOSED",
            "requires_approval": True,
            "reason": reason,
            "message": "Follow-up action proposed for post-execution investigation. Requires user approval.",
        }
