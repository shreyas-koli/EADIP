"""
Warehouse automation agent.

Acts as an automation coordinator. Consumes recommendations from the shared
memory bus, invokes the AutomationEngine, and stores the resulting structured
action plans in the shared memory bus.

Phase 3 agent:
- No SQL execution, no database writes, no warehouse mutation.
- All generated actions remain in status ``PROPOSED``.
- No approval is automatically granted.
"""

import logging
from typing import Any

from app.models.warehouse import Warehouse
from app.context.shared_context import SharedContext
from app.warehouse.automation import AutomationEngine

logger = logging.getLogger(__name__)


class AutomationAgent:
    """
    Agent responsible for transforming warehouse recommendations into
    safe, structured, executable action plans.

    The agent does NOT execute any actions. It produces data structures
    that a future approval/execution pipeline will consume.

    Usage::

        agent = AutomationAgent()
        result = agent.generate_action_plans(warehouse, context)
    """

    def __init__(self) -> None:
        """Initialise the agent with an ``AutomationEngine`` instance."""
        self._engine = AutomationEngine()

    # ── Generation ───────────────────────────────────────────────

    def generate_action_plans(self, warehouse: Warehouse, context: SharedContext) -> dict[str, Any]:
        """
        Generate structured action plans from recommendations and store them in context.

        Parameters
        ──────────
        warehouse : Warehouse
            A registered ``Warehouse`` ORM instance.
        context : SharedContext
            The explicit shared memory bus.

        Returns
        ───────
        dict[str, Any]
            The generated automation result containing action plans.
        """
        def _progress(msg: str, pct: int | None = None) -> None:
            context.emit_agent_progress("automation", msg, pct)

        _progress("Starting automation analysis...", 0)

        automation_result = self._engine.analyse(warehouse, context, progress_callback=_progress)

        _progress("Automation analysis completed.", 100)

        context.set_agent_result("automation", automation_result)

        return automation_result
