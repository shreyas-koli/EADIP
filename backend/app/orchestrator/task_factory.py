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
from app.agents.security_agent import SecurityAgent
from app.agents.statistics_agent import StatisticsAgent
from app.agents.recommendation_agent import RecommendationAgent
from app.agents.data_quality_agent import DataQualityAgent
from app.models.warehouse import Warehouse
from app.context.shared_context import SharedContext
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
        """Initialise reusable agent instances."""
        self._metadata_agent   = MetadataAgent()
        self._statistics_agent = StatisticsAgent()
        self._security_agent   = SecurityAgent()
        self._recommendation_agent = RecommendationAgent()
        self._data_quality_agent = DataQualityAgent()

    # ── Metadata discovery plan ──────────────────────────────────

    def build_metadata_discovery(
        self,
        warehouse: Warehouse,
        context: SharedContext,
    ) -> list[AgentTask]:
        """
        Build an execution plan for warehouse metadata discovery.

        Constructs ``AgentTask`` descriptors for multiple agents and
        declares their dependency relationships so the orchestrator
        can schedule them in the correct order:

        * **Wave 1** — independent tasks run in parallel:

          1. ``metadata``   — structural schema discovery
          2. ``statistics`` — volumetric table/index analysis

        * **Wave 2** — dependent on Wave 1 completing:

          3. ``security`` — rule-based static security analysis;
             requires ``metadata`` to be present in
             :class:`~app.context.shared_context.SharedContext`
             before it can run.
          4. ``data_quality`` — deterministic data quality dimension scoring;
             requires ``metadata`` to be present in SharedContext.

        * **Wave 3** — dependent on Wave 1 and Wave 2 completing:

          5. ``recommendation`` — rule-based recommendations;
             requires ``metadata``, ``statistics``, ``security``,
             and ``data_quality`` to be present in the SharedContext.

        Parameters
        ──────────
        warehouse : Warehouse
            The target warehouse ORM instance.

        Returns
        ───────
        list[AgentTask]
            Five tasks — metadata, statistics, security, data_quality, and recommendation —
            ready for ``AgentOrchestrator.execute_parallel()``.
        """
        metadata_task = AgentTask(
            name="metadata",
            callable=self._metadata_agent.discover_metadata,
            args=(warehouse, context),
        )

        statistics_task = AgentTask(
            name="statistics",
            callable=self._statistics_agent.generate_statistics,
            args=(warehouse, context),
        )

        security_task = AgentTask(
            name="security",
            callable=self._security_agent.generate_security_report,
            args=(warehouse, context),
            dependencies=["metadata"],
        )

        data_quality_task = AgentTask(
            name="data_quality",
            callable=self._data_quality_agent.generate_quality_report,
            args=(warehouse, context),
            dependencies=["metadata"],
        )

        recommendation_task = AgentTask(
            name="recommendation",
            callable=self._recommendation_agent.generate_recommendations,
            args=(warehouse, context),
            dependencies=["metadata", "statistics", "security", "data_quality"],
        )

        return [
            metadata_task,
            statistics_task,
            security_task,
            data_quality_task,
            recommendation_task,
        ]

    # ── Future plan builders (stubs) ─────────────────────────────
    #
    # def build_analysis_tasks(self, warehouse) -> list[AgentTask]: ...
    # def build_query_tasks(self, warehouse, query) -> list[AgentTask]: ...
    # def build_prediction_tasks(self, warehouse) -> list[AgentTask]: ...
    # def build_explainability_tasks(self, warehouse) -> list[AgentTask]: ...
