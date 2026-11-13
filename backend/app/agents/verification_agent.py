"""
Warehouse verification agent (Phase 6).

Acts as an observation and validation coordinator. Inspects target warehouse
catalog state to verify whether an executed action plan achieved its intended outcome.

Phase 6 agent:
- Strictly READ-ONLY against the target warehouse catalog.
- Does NOT create recommendations, does NOT execute SQL mutations, does NOT alter warehouse state.
- Does NOT trigger automatic rollbacks, retries, or Supervisor re-analysis.
- Does NOT invoke Phase 7.
"""

import logging
from typing import Any, Dict

from app.models.warehouse import Warehouse
from app.context.shared_context import SharedContext
from app.warehouse.verification_engine import ControlledVerificationEngine

logger = logging.getLogger(__name__)


class VerificationAgent:
    """
    Agent responsible for performing evidence-based read-only catalog verification
    on executed warehouse action plans.

    Usage::

        agent = VerificationAgent()
        result = agent.verify_action_plan(warehouse, action_plan, context)
    """

    def __init__(self) -> None:
        """Initialise the agent with a ``ControlledVerificationEngine`` instance."""
        self._engine = ControlledVerificationEngine()

    def verify_action_plan(
        self, warehouse: Warehouse, action_plan: Dict[str, Any], context: SharedContext
    ) -> Dict[str, Any]:
        """
        Perform evidence-based catalog verification for an executed action plan and store result in context.

        Parameters
        ──────────
        warehouse : Warehouse
            Target warehouse ORM instance.
        action_plan : Dict[str, Any]
            The executed action plan dictionary.
        context : SharedContext
            The explicit shared memory bus.

        Returns
        ───────
        Dict[str, Any]
            Verification result dictionary.
        """
        def _progress(msg: str, pct: int | None = None) -> None:
            context.emit_agent_progress("verification", msg, pct)

        _progress("Starting catalog verification analysis...", 0)

        result = self._engine.verify(warehouse, action_plan)

        _progress("Catalog verification analysis completed.", 100)

        # Store in verification namespace on context
        ver_map = context.get_agent_result("verification") or {}
        if isinstance(ver_map, dict):
            ver_map[action_plan.get("action_id", "default")] = result
            context.set_agent_result("verification", ver_map)

        return result
