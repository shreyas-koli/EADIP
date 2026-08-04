"""
Execution plan factory.

Responsible for constructing lists of ``AgentTask`` descriptors
that the ``AgentOrchestrator`` can execute.  The factory **never**
runs agents — it only assembles execution plans with the correct
dependencies, callables, and arguments.

Separating plan construction from execution allows the orchestrator
to remain fully generic while domain-specific task wiring lives
here.

No LLM calls, no database writes, no HTTP concerns, no execution.
"""

from __future__ import annotations

from typing import Any

from app.agents.metadata_agent import MetadataAgent
from app.agents.statistics_agent import StatisticsAgent
from app.context.shared_context import SharedContext
from app.models.warehouse import Warehouse
from app.orchestrator.agent_orchestrator import AgentTask


class TaskFactory:
    """
    Constructs execution plans for the ``AgentOrchestrator``.

    Each ``build_*`` method returns a ``list[AgentTask]`` that can
    be passed directly to ``AgentOrchestrator.execute_parallel()``.

    The factory is designed to grow over time — new ``build_*``
    methods can be added for analysis, security, prediction,
    explainability, etc. without modifying the orchestrator.

    Usage::

        factory = TaskFactory()
        tasks   = factory.build_metadata_discovery(warehouse)

        orchestrator = AgentOrchestrator()
        summary      = orchestrator.execute_parallel(tasks)
    """

    def __init__(self) -> None:
        """Initialise reusable agent instances and shared context."""
        self._metadata_agent = MetadataAgent()
        self._statistics_agent = StatisticsAgent()
        # self._context = SharedContext()

    # ── Metadata discovery plan ──────────────────────────────────

    def build_metadata_discovery(
        self,
        warehouse: Warehouse,
    ) -> list[AgentTask]:
        """
        Build an execution plan for warehouse metadata discovery.

        Creates independent ``AgentTask`` objects for:

        1. Metadata discovery
        2. Statistics generation

        Both tasks have no dependencies and will be scheduled in the
        same execution wave.

        Parameters
        ──────────
        warehouse : Warehouse
            The target warehouse ORM instance.

        Returns
        ───────
        list[AgentTask]
            A list containing the metadata and statistics tasks.
            Ready for ``AgentOrchestrator.execute_parallel()``.
        """
        metadata_task = AgentTask(
            name="metadata",
            callable=self._metadata_agent.discover_metadata,
            args=(warehouse,),
            # dependencies=["metadata"],
        )

        statistics_task = AgentTask(
            name="statistics",
            callable=self._statistics_agent.generate_statistics,
            args=(warehouse,),
            # dependencies=["statistics"],
        )

        return [
            metadata_task,
            statistics_task,
        ]

    # ── Future plan builders (stubs) ─────────────────────────────
    #
    # def build_analysis_tasks(self, warehouse) -> list[AgentTask]: ...
    # def build_query_tasks(self, warehouse, query) -> list[AgentTask]: ...
    # def build_security_tasks(self, warehouse) -> list[AgentTask]: ...
    # def build_prediction_tasks(self, warehouse) -> list[AgentTask]: ...
    # def build_explainability_tasks(self, warehouse) -> list[AgentTask]: ...
