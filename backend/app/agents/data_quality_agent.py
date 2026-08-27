"""
Data quality agent coordination layer.

Responsible for coordinating data quality analysis tasks and writing
results to the shared context memory bus.
"""

from typing import Any

from app.models.warehouse import Warehouse
from app.context.shared_context import SharedContext
from app.warehouse.data_quality import DataQualityAnalyzer


class DataQualityAgent:
    """
    A thin coordination layer for executing data quality analysis.

    Delegates all business logic and rule evaluation to the
    ``DataQualityAnalyzer`` and pushes the results into the
    ``SharedContext`` registry for downstream agents.
    """

    def __init__(self) -> None:
        """Initialize the agent with its underlying analyzer."""
        self._analyzer = DataQualityAnalyzer()

    def generate_quality_report(self, warehouse: Warehouse, context: SharedContext) -> dict[str, Any]:
        """
        Generate a data quality report for the target warehouse.

        Parameters
        ──────────
        warehouse : Warehouse
            A registered ``Warehouse`` ORM instance.

        Returns
        ───────
        dict[str, Any]
            The generated quality result containing scores and issues.
        """
        context.emit_agent_progress("data_quality", "Inspecting nullable columns...", 0)
        
        def _progress(msg: str, pct: int | None = None) -> None:
            context.emit_agent_progress("data_quality", msg, pct)
            
        quality_result = self._analyzer.analyse(warehouse, context, progress_callback=_progress)
        
        context.emit_agent_progress("data_quality", "Data-quality analysis completed.", 100)

        context.set_agent_result(
            "data_quality",
            quality_result,
        )

        return quality_result
