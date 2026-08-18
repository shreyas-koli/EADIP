"""
Warehouse recommendation agent.

This agent acts as a thin coordination layer. It delegates the actual
recommendation logic to the :class:`RecommendationEngine` and stores
the generated recommendations in the shared memory bus.

No LLM calls, no database writes, no HTTP concerns.
"""

from typing import Any

from app.models.warehouse import Warehouse
from app.warehouse.recommendation import RecommendationEngine
from app.context.shared_context import SharedContext


class RecommendationAgent:
    """
    Agent responsible for orchestrating the generation of recommendations
    for a data warehouse.

    Usage::

        agent = RecommendationAgent()
        recommendations = agent.generate_recommendations(warehouse)
    """

    def __init__(self) -> None:
        """Initialise the agent with a ``RecommendationEngine`` instance."""
        self._engine = RecommendationEngine()

    # ── Generation ───────────────────────────────────────────────

    def generate_recommendations(self, warehouse: Warehouse, context: SharedContext) -> dict[str, Any]:
        """
        Generate recommendations for the warehouse and store them in context.

        Parameters
        ──────────
        warehouse : Warehouse
            A registered ``Warehouse`` ORM instance.

        Returns
        ───────
        dict[str, Any]
            The generated recommendations snapshot.
        """
        context.emit_agent_progress("recommendation", "Collecting findings from upstream agents...")
        context.emit_agent_progress("recommendation", "Grouping related findings...")
        context.emit_agent_progress("recommendation", "Prioritizing recommendations...")
        context.emit_agent_progress("recommendation", "Calculating impact/effort/confidence...")
        context.emit_agent_progress("recommendation", "Building final recommendations...")
        
        recommendations = self._engine.analyse(warehouse, context)
        
        context.emit_agent_progress("recommendation", "Recommendation analysis completed.")
        
        context.set_agent_result(
            "recommendation",
            recommendations,
        )

        return recommendations
