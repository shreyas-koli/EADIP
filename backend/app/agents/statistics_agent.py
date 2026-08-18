"""
Statistics discovery agent.

Orchestrates statistical analysis for a registered data warehouse.
This agent is a thin coordination layer — it delegates the actual
computation to :class:`StatisticsAnalyzer` and returns the raw
statistics dictionary for downstream consumers (orchestrator, API, etc.).

No LLM calls, no database writes, no HTTP concerns.
"""

from typing import Any

from app.models.warehouse import Warehouse
from app.warehouse.statistics import StatisticsAnalyzer
from app.context.shared_context import SharedContext



class StatisticsAgent:
    """
    Agent responsible for computing structural and value-level
    statistics across a data warehouse.

    Usage::

        agent = StatisticsAgent()
        stats = agent.generate_statistics(warehouse)
    """

    def __init__(self) -> None:
        """Initialise the agent with a ``StatisticsAnalyzer`` instance."""
        self._analyzer = StatisticsAnalyzer()

    # ── Statistics generation ────────────────────────────────────

    def generate_statistics(self, warehouse: Warehouse, context: SharedContext) -> dict[str, Any]:
        """
        Analyse the warehouse and return a statistics snapshot.

        Delegates entirely to ``StatisticsAnalyzer.analyse()`` which
        handles the SQL execution and result aggregation.

        Parameters
        ──────────
        warehouse : Warehouse
            A registered, active ``Warehouse`` ORM instance whose
            connection details are stored in the platform database.

        Returns
        ───────
        dict[str, Any]
            A nested dictionary containing per-schema, per-table
            statistics such as row counts, column nullability ratios,
            distinct value counts, and data-type distributions::

                {
                    "schemas": {
                        "public": {
                            "tables": {
                                "employees": {
                                    "row_count": 1500,
                                    "columns": {
                                        "id":   {"distinct": 1500, "nulls": 0},
                                        "name": {"distinct": 1487, "nulls": 3},
                                        ...
                                    }
                                }
                            }
                        }
                    }
                }
        """
        context.emit_agent_progress("statistics", "Inspecting table statistics...")
        context.emit_agent_progress("statistics", "Counting rows...")
        context.emit_agent_progress("statistics", "Calculating table sizes...")
        context.emit_agent_progress("statistics", "Analyzing column distributions...")
        context.emit_agent_progress("statistics", "Detecting empty/small tables...")
        context.emit_agent_progress("statistics", "Computing statistics...")
        
        statistics = self._analyzer.analyse(warehouse)
        
        context.emit_agent_progress("statistics", "Statistics analysis completed.")
        context.set_agent_result("statistics", statistics)
        return statistics
