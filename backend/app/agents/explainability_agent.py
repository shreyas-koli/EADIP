"""
Warehouse explainability agent.

Acts as an explanation coordinator. Consumes structured findings and recommendations
from the shared memory bus, invokes the ExplainabilityEngine, and stores the resulting
explanations in the shared memory bus.

No LLM calls, no database writes, no HTTP concerns.
"""

import logging
from typing import Any

from app.models.warehouse import Warehouse
from app.context.shared_context import SharedContext
from app.warehouse.explainability import ExplainabilityEngine

logger = logging.getLogger(__name__)


class ExplainabilityAgent:
    """
    Agent responsible for explaining warehouse recommendations using
    structured evidence from prior workflow steps.

    Usage::

        agent = ExplainabilityAgent()
        explanations = agent.generate_explanations(warehouse, context)
    """

    def __init__(self) -> None:
        """Initialise the agent with an ``ExplainabilityEngine`` instance."""
        self._engine = ExplainabilityEngine()

    # ── Generation ───────────────────────────────────────────────

    def generate_explanations(self, warehouse: Warehouse, context: SharedContext) -> dict[str, Any]:
        """
        Generate evidence-backed explanations for recommendations and store them in context.

        Parameters
        ──────────
        warehouse : Warehouse
            A registered ``Warehouse`` ORM instance.
        context : SharedContext
            The explicit shared memory bus.

        Returns
        ───────
        dict[str, Any]
            The generated explainability snapshot.
        """
        def _progress(msg: str, pct: int | None = None) -> None:
            context.emit_agent_progress("explainability", msg, pct)

        _progress("Starting explainability analysis...", 0)

        explanations = self._engine.analyse(warehouse, context, progress_callback=_progress)

        _progress("Explainability analysis completed.", 100)

        context.set_agent_result("explainability", explanations)

        return explanations
