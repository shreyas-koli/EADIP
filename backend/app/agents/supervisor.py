"""
Supervisor agent — top-level orchestrator for the multi-agent system.

Coordinates sub-agents (currently ``MetadataAgent``) and manages
shared state via ``SharedContext``.  The supervisor is the single
entry point that the API layer calls; it decides whether to invoke
an agent or serve cached results.

No LLM calls, no database writes, no HTTP concerns.
"""

from typing import Any

from app.agents.metadata_agent import MetadataAgent
from app.context.shared_context import SharedContext
from app.models.warehouse import Warehouse


class SupervisorAgent:
    """
    Central orchestrator that delegates tasks to specialised agents
    and keeps the shared context up to date.

    Usage::

        supervisor = SupervisorAgent()
        metadata   = supervisor.discover_metadata(warehouse)
    """

    def __init__(self) -> None:
        """Initialise sub-agents and the shared context store."""
        self._metadata_agent = MetadataAgent()
        self._context = SharedContext()

    # ── Metadata discovery ───────────────────────────────────────

    def discover_metadata(self, warehouse: Warehouse) -> dict[str, Any]:
        """
        Return the structural metadata of a warehouse, using the
        shared context as a cache layer.

        Workflow
        ────────
        1. Check ``SharedContext`` for existing metadata.
        2. **Cache hit** — log and return immediately.
        3. **Cache miss** — delegate to ``MetadataAgent``, store
           the result and the current warehouse in the context,
           then return.

        Parameters
        ──────────
        warehouse : Warehouse
            A registered, active ``Warehouse`` ORM instance.

        Returns
        ───────
        dict[str, Any]
            Nested schema → tables → columns dictionary.
        """
        # ── Check cache ──────────────────────────────────────────
        cached_metadata = self._context.get_metadata()

        if cached_metadata is not None:
            self._context.add_log("Metadata loaded from Shared Context.")
            return cached_metadata

        # ── Cache miss — run discovery ───────────────────────────
        self._context.add_log("Metadata not found in Shared Context.")

        metadata = self._metadata_agent.discover_metadata(warehouse)

        # ── Persist into shared context ──────────────────────────
        self._context.set_metadata(metadata)
        self._context.set_current_warehouse({
            "id": warehouse.id,
            "name": warehouse.name,
            "db_type": warehouse.db_type,
            "host": warehouse.host,
            "port": warehouse.port,
            "database_name": warehouse.database_name,
        })

        self._context.add_log("Metadata discovery completed.")

        return metadata
