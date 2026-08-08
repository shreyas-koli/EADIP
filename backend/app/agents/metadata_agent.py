"""
Metadata discovery agent.

Orchestrates schema introspection for a registered data warehouse.
This agent is a thin coordination layer — it delegates the actual
inspection work to :class:`MetadataInspector` and returns the raw
metadata dictionary for downstream consumers (orchestrator, API, etc.).

No LLM calls, no database writes, no HTTP concerns.
"""

from typing import Any

from app.models.warehouse import Warehouse
from app.warehouse.inspector import MetadataInspector
from app.context.shared_context import SharedContext


class MetadataAgent:
    """
    Agent responsible for discovering the structural metadata of
    a data warehouse.

    Usage::

        agent    = MetadataAgent()
        metadata = agent.discover_metadata(warehouse)
    """

    def __init__(self) -> None:
        """Initialise the agent with a ``MetadataInspector`` instance."""
        self._inspector = MetadataInspector()

    # ── Discovery ────────────────────────────────────────────────

    def discover_metadata(self, warehouse: Warehouse) -> dict[str, Any]:
        """
        Inspect the warehouse and return its full metadata snapshot.

        Workflow
        ────────
        1. Receive a ``Warehouse`` ORM instance.
        2. Delegate to ``MetadataInspector.inspect_database()``.
        3. Return the nested metadata dictionary.

        Parameters
        ──────────
        warehouse : Warehouse
            A registered, active warehouse whose connection details
            are already stored in the platform database.

        Returns
        ───────
        dict[str, Any]
            A nested dictionary containing every schema, table, and
            column discovered in the warehouse::

                {
                    "schemas": {
                        "public": {
                            "tables": {
                                "employees": {
                                    "columns": [
                                        {"name": "id", "type": "INTEGER", ...},
                                        ...
                                    ]
                                }
                            }
                        }
                    }
                }
        """
        result = self._inspector.inspect_database(warehouse)
        SharedContext().set_agent_result("metadata", result)
        return result
