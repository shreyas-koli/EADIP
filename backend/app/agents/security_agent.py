"""
Security analysis agent.

Orchestrates security analysis for a registered data warehouse.
This agent is a thin coordination layer — it delegates the actual
analysis work to :class:`SecurityAnalyzer` and returns the raw
security report dictionary for downstream consumers
(orchestrator, API, etc.).

No LLM calls, no database writes, no HTTP concerns.
"""

from typing import Any

from app.models.warehouse import Warehouse
from app.warehouse.security import SecurityAnalyzer
from app.context.shared_context import SharedContext


class SecurityAgent:
    """
    Agent responsible for producing a security analysis report
    for a registered data warehouse.

    This class is a lightweight coordination layer.  All analysis
    logic is encapsulated inside :class:`SecurityAnalyzer` — the
    agent only drives the workflow, publishes the result to the
    shared memory bus, and returns it to the caller.

    Usage::

        agent  = SecurityAgent()
        report = agent.generate_security_report(warehouse)
    """

    def __init__(self) -> None:
        """Initialise the agent with a ``SecurityAnalyzer`` instance."""
        self._analyzer = SecurityAnalyzer()

    # ── Security report generation ───────────────────────────────

    def generate_security_report(self, warehouse: Warehouse, context: SharedContext) -> dict[str, Any]:
        """
        Analyse the warehouse and return a security report snapshot.

        Delegates entirely to ``SecurityAnalyzer.analyse()`` which
        handles all inspection and result aggregation.  The result
        is then published to the shared memory bus so other agents
        and the orchestrator can access it.

        Parameters
        ──────────
        warehouse : Warehouse
            A registered, active ``Warehouse`` ORM instance whose
            connection details are stored in the platform database.

        Returns
        ───────
        dict[str, Any]
            A dictionary containing the security findings produced
            by ``SecurityAnalyzer.analyse()``.  The exact shape is
            defined by the analyser implementation; a representative
            example::

                {
                    "summary": {
                        "total_users":            12,
                        "superusers":              1,
                        "tables_without_rls":     4,
                        "public_schema_exposed":  True,
                    },
                    "users":       [ ... ],
                    "privileges":  [ ... ],
                    "findings":    [ ... ],
                }

        Side Effects
        ────────────
        Writes the returned report to the shared memory bus under
        the key ``"security"`` via::

            context.set_agent_result("security", security_report)

        This makes the report available to the orchestrator summary
        and any downstream agents that declare a ``"security"``
        dependency.
        """
        security_report = self._analyzer.analyse(warehouse, context)
        context.set_agent_result("security", security_report)
        return security_report
