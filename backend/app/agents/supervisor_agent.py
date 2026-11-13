"""
Warehouse supervisor agent (Phase 7 extension).

Acts as the post-execution re-analysis and feedback coordinator.
Synthesizes pre-execution state, execution results, verification catalog evidence,
and current warehouse observations into structured post-execution assessments.

Phase 7 agent:
- Strictly READ-ONLY against the target warehouse.
- Does NOT execute database mutations, does NOT trigger automatic rollbacks or retries.
- Does NOT automatically approve follow-up recommendations.
"""

import logging
from typing import Any, Dict

from app.models.warehouse import Warehouse
from app.context.shared_context import SharedContext
from app.warehouse.reanalysis_engine import ControlledReanalysisEngine

logger = logging.getLogger(__name__)


class SupervisorAgent:
    """
    Supervisor Agent extension responsible for post-execution re-analysis.

    Usage::

        agent = SupervisorAgent()
        result = agent.reanalyze_outcome(warehouse, action_plan, execution_data, verification_data, context)
    """

    def __init__(self) -> None:
        """Initialise the agent with a ``ControlledReanalysisEngine`` instance."""
        self._engine = ControlledReanalysisEngine()

    def reanalyze_outcome(
        self,
        warehouse: Warehouse,
        action_plan: Dict[str, Any],
        execution_data: Dict[str, Any],
        verification_data: Dict[str, Any] | None,
        context: SharedContext,
    ) -> Dict[str, Any]:
        """
        Synthesize post-execution assessment and store result in shared memory bus.

        Parameters
        ──────────
        warehouse : Warehouse
            Target warehouse ORM instance.
        action_plan : Dict[str, Any]
            Action plan payload.
        execution_data : Dict[str, Any]
            Execution record data dict.
        verification_data : Dict[str, Any] | None
            Verification record data dict.
        context : SharedContext
            Explicit shared memory bus.

        Returns
        ───────
        Dict[str, Any]
            Re-analysis assessment dictionary.
        """
        def _progress(msg: str, pct: int | None = None) -> None:
            context.emit_agent_progress("supervisor_reanalysis", msg, pct)

        _progress("Starting post-execution supervisor re-analysis...", 0)

        result = self._engine.reanalyze(
            warehouse=warehouse,
            action_plan=action_plan,
            execution_data=execution_data,
            verification_data=verification_data,
        )

        _progress("Post-execution supervisor re-analysis completed.", 100)

        # Store in reanalysis namespace on context
        re_map = context.get_agent_result("supervisor_reanalysis") or {}
        if isinstance(re_map, dict):
            re_map[action_plan.get("action_id", "default")] = result
            context.set_agent_result("supervisor_reanalysis", re_map)

        return result
