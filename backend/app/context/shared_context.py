"""
Shared in-memory context store for the multi-agent system.

Provides a thread-safe, singleton container that every agent and
service can read from / write to during a session.  The store holds
the current warehouse reference, discovered metadata, query history,
and execution logs.

.. note::

   This is a **volatile, in-memory** store — all data is lost on
   process restart.  Persistent storage (Redis, database) can be
   introduced later by swapping the backing implementation.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any


class SharedContext:
    """
    Singleton context store shared across agents, services, and
    API layers.

    Usage::

        ctx = SharedContext()          # always returns the same instance
        ctx.set_metadata(metadata)
        ctx.add_query("SELECT * FROM users")
        ctx.add_log("Metadata discovery completed.")
    """

    _instance: SharedContext | None = None
    _lock: threading.Lock = threading.Lock()

    # ── Singleton ────────────────────────────────────────────────

    def __new__(cls) -> SharedContext:
        """Return the single shared instance (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialise()
                    cls._instance = instance
        return cls._instance

    def _initialise(self) -> None:
        """Set up default internal state (called once)."""
        self._current_warehouse: dict[str, Any] | None = None
        self._metadata: dict[str, Any] | None = None
        self._recommendations: list[str] = []
        self._queries: list[dict[str, Any]] = []
        self._logs: list[dict[str, Any]] = []

    # ── Warehouse ────────────────────────────────────────────────

    def set_current_warehouse(self, warehouse: dict[str, Any]) -> None:
        """
        Store the currently active warehouse reference.

        Parameters
        ──────────
        warehouse : dict[str, Any]
            Serialised warehouse data (id, name, db_type, etc.).
        """
        self._current_warehouse = warehouse

    def get_current_warehouse(self) -> dict[str, Any] | None:
        """
        Return the currently active warehouse, or ``None`` if unset.

        Returns
        ───────
        dict[str, Any] | None
        """
        return self._current_warehouse

    # ── Metadata ─────────────────────────────────────────────────

    def set_metadata(self, metadata: dict[str, Any]) -> None:
        """
        Store the discovered metadata snapshot.

        Parameters
        ──────────
        metadata : dict[str, Any]
            Nested schema → tables → columns dictionary as returned
            by ``MetadataAgent.discover_metadata()``.
        """
        self._metadata = metadata

    def get_metadata(self) -> dict[str, Any] | None:
        """
        Return the stored metadata snapshot, or ``None`` if no
        discovery has run yet.

        Returns
        ───────
        dict[str, Any] | None
        """
        return self._metadata

    # ── Recommendations ──────────────────────────────────────────

    def set_recommendations(self, recommendations: list[str]) -> None:
        """
        Replace the current recommendation list.

        Parameters
        ──────────
        recommendations : list[str]
        """
        self._recommendations = list(recommendations)

    def get_recommendations(self) -> list[str]:
        """
        Return the current recommendations.

        Returns
        ───────
        list[str]
        """
        return list(self._recommendations)

    # ── Query history ────────────────────────────────────────────

    def add_query(self, query: str) -> None:
        """
        Append a query to the history with a UTC timestamp.

        Parameters
        ──────────
        query : str
            The SQL query string that was executed.
        """
        self._queries.append({
            "query": query,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_queries(self) -> list[dict[str, Any]]:
        """
        Return the full query history.

        Returns
        ───────
        list[dict[str, Any]]
            Each entry contains ``query`` and ``timestamp``.
        """
        return list(self._queries)

    # ── Execution logs ───────────────────────────────────────────

    def add_log(self, message: str) -> None:
        """
        Append an execution log entry with a UTC timestamp.

        Parameters
        ──────────
        message : str
            A human-readable log message.
        """
        self._logs.append({
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_logs(self) -> list[dict[str, Any]]:
        """
        Return the full execution log.

        Returns
        ───────
        list[dict[str, Any]]
            Each entry contains ``message`` and ``timestamp``.
        """
        return list(self._logs)

    # ── Reset ────────────────────────────────────────────────────

    def clear(self) -> None:
        """
        Reset all stored state to defaults.

        Useful between sessions or during testing.
        """
        self._current_warehouse = None
        self._metadata = None
        self._recommendations = []
        self._queries = []
        self._logs = []
