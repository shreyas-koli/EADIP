"""
Warehouse reporting agent.

Acts as a report coordinator. Consumes structured findings, recommendations,
and explainability outputs from the shared memory bus, invokes the ReportingEngine,
and stores the resulting consolidated report in the shared memory bus.

Read-only agent:
- No database writes, no SQL execution, no recommendation execution.
"""

import logging
from typing import Any

from app.models.warehouse import Warehouse
from app.context.shared_context import SharedContext
from app.warehouse.reporting import ReportingEngine

logger = logging.getLogger(__name__)


class ReportingAgent:
    """
    Agent responsible for consolidating warehouse intelligence findings
    into a structured overall report.

    Usage::

        agent = ReportingAgent()
        report = agent.generate_report(warehouse, context)
    """

    def __init__(self) -> None:
        """Initialise the agent with a ``ReportingEngine`` instance."""
        self._engine = ReportingEngine()

    # ── Generation ───────────────────────────────────────────────

    def generate_report(self, warehouse: Warehouse, context: SharedContext) -> dict[str, Any]:
        """
        Consolidate findings and recommendations into an overall report and store in context.

        Parameters
        ──────────
        warehouse : Warehouse
            A registered ``Warehouse`` ORM instance.
        context : SharedContext
            The explicit shared memory bus.

        Returns
        ───────
        dict[str, Any]
            The generated report snapshot.
        """
        def _progress(msg: str, pct: int | None = None) -> None:
            context.emit_agent_progress("reporting", msg, pct)

        _progress("Starting overall report consolidation...", 0)

        report = self._engine.generate_report(warehouse, context, progress_callback=_progress)

        _progress("Overall report consolidation completed.", 100)

        context.set_agent_result("reporting", report)

        return report
