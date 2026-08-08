"""
Enterprise shared memory bus.

Provides a **thread-safe, singleton** context store designed for
concurrent access by multiple agents running inside a
``ThreadPoolExecutor``.  Every public method acquires an ``RLock``
so nested / re-entrant calls from the same thread are safe.

Agent results are stored in a **generic registry** — any current or
future agent can write its output via ``set_agent_result()`` without
requiring modifications to this class.

.. note::

   This is a **volatile, in-memory** store — all data is lost on
   process restart.  Persistent storage (Redis, database) can be
   introduced later by swapping the backing implementation.
"""

from __future__ import annotations

import copy
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ── Agent status enumeration ─────────────────────────────────────


class AgentStatus(str, Enum):
    """Possible lifecycle states of an agent."""

    WAITING = "WAITING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


# ── Shared context store ─────────────────────────────────────────


class SharedContext:
    """
    Thread-safe singleton shared memory bus for the multi-agent
    platform.

    Future Session Isolation:
    -------------------------
    The current implementation is process-wide and designed for
    development or single-tenant execution. For production, the
    platform should migrate to session-scoped storage (e.g., Redis
    or database-backed context) to isolate concurrent multi-user
    orchestrations. To migrate, replace the `_instance` singleton
    with a session-aware factory `get_context(session_id: str)`
    while preserving this public API.

    All mutable state is guarded by an ``RLock`` so the store is
    safe for use with ``ThreadPoolExecutor`` and other concurrency
    primitives.

    Agent results are stored in a **generic registry** keyed by
    agent name, so new agents (Lineage, Data Quality, Compliance,
    Cost, Forecast, Recommendation, Query, Explainability, …) can
    store and retrieve results without any code changes here.

    Usage::

        ctx = SharedContext()

        # Store agent outputs
        ctx.set_agent_result("metadata", metadata_result)
        ctx.set_agent_result("statistics", statistics_result)
        ctx.set_agent_result("security", security_result)

        # Retrieve later
        metadata   = ctx.get_agent_result("metadata")
        statistics = ctx.get_agent_result("statistics")
    """

    def __init__(self) -> None:
        """Initialise the shared context store (non-singleton)."""
        self._rlock = threading.RLock()

        self._session_id: str = str(uuid.uuid4())
        self._current_warehouse: dict[str, Any] | None = None
        self._agent_results: dict[str, Any] = {}
        self._execution_logs: list[dict[str, Any]] = []
        self._execution_history: list[dict[str, Any]] = []
        self._agent_status: dict[str, AgentStatus] = {}

    # ── Session ID ───────────────────────────────────────────────

    def get_session_id(self) -> str:
        """
        Return the unique session identifier.

        Returns
        ───────
        str
            A UUID-4 string generated when the context was created
            (or last cleared).
        """
        with self._rlock:
            return self._session_id

    # ── Current warehouse ────────────────────────────────────────

    def set_current_warehouse(self, warehouse: dict[str, Any]) -> None:
        """
        Store the currently active warehouse reference.

        Parameters
        ──────────
        warehouse : dict[str, Any]
            Serialised warehouse data (id, name, db_type, etc.).
        """
        with self._rlock:
            self._current_warehouse = warehouse

    def get_current_warehouse(self) -> dict[str, Any] | None:
        """
        Return the currently active warehouse, or ``None`` if unset.

        Returns
        ───────
        dict[str, Any] | None
        """
        with self._rlock:
            return copy.deepcopy(self._current_warehouse) if self._current_warehouse else None

    # ── Agent result registry ────────────────────────────────────

    def set_agent_result(self, agent_name: str, result: Any) -> None:
        """
        Store (or overwrite) the output of an agent.

        Parameters
        ──────────
        agent_name : str
            A unique key identifying the agent (e.g. ``"metadata"``,
            ``"statistics"``, ``"security"``, ``"lineage"``).
        result : Any
            The agent's output — can be any serialisable object
            (dict, list, primitive, etc.).

        Example::

            ctx.set_agent_result("metadata", metadata_dict)
            ctx.set_agent_result("statistics", stats_dict)
        """
        with self._rlock:
            self._agent_results[agent_name] = result

    def get_agent_result(self, agent_name: str) -> Any | None:
        """
        Retrieve the stored result for a specific agent.

        Returns a **deep copy** to prevent external mutation of
        the shared state.

        Parameters
        ──────────
        agent_name : str
            The key used when the result was stored.

        Returns
        ───────
        Any | None
            The agent's output, or ``None`` if no result has been
            stored under that key.
        """
        with self._rlock:
            value = self._agent_results.get(agent_name)
            if value is None:
                return None
            return copy.deepcopy(value)

    def has_agent_result(self, agent_name: str) -> bool:
        """
        Check whether a result exists for the given agent.

        Parameters
        ──────────
        agent_name : str
            The key to look up.

        Returns
        ───────
        bool
            ``True`` if a result is stored, ``False`` otherwise.
        """
        with self._rlock:
            return agent_name in self._agent_results

    def remove_agent_result(self, agent_name: str) -> None:
        """
        Remove the stored result for a specific agent.

        No-op if the key does not exist.

        Parameters
        ──────────
        agent_name : str
            The key to remove.
        """
        with self._rlock:
            self._agent_results.pop(agent_name, None)

    def clear_agent_results(self) -> None:
        """
        Remove **all** stored agent results.

        Other state (warehouse, logs, history, agent status, session)
        is preserved.
        """
        with self._rlock:
            self._agent_results.clear()

    def get_all_agent_results(self) -> dict[str, Any]:
        """
        Return a deep copy of the entire agent result registry.

        Returns
        ───────
        dict[str, Any]
            Mapping of agent name → result for every stored entry.
        """
        with self._rlock:
            return copy.deepcopy(self._agent_results)

    # ── Execution logs ───────────────────────────────────────────

    def add_execution_log(self, message: str) -> None:
        """
        Append a timestamped execution log entry.

        Parameters
        ──────────
        message : str
            A human-readable log message.
        """
        with self._rlock:
            self._execution_logs.append({
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    def get_execution_logs(self) -> list[dict[str, Any]]:
        """
        Return a copy of all execution log entries.

        Returns
        ───────
        list[dict[str, Any]]
            Each entry contains ``message`` and ``timestamp``.
        """
        with self._rlock:
            return copy.deepcopy(self._execution_logs)

    # ── Execution history ────────────────────────────────────────

    def add_execution_history(
        self,
        agent: str,
        started_at: str | None = None,
        finished_at: str | None = None,
        duration_ms: int | None = None,
        status: AgentStatus | None = None,
        thread: str | None = None,
        wave: int | None = None,
        # Legacy kwargs for backward compatibility
        start_time: str | None = None,
        end_time: str | None = None,
        duration: float | None = None,
    ) -> None:
        """
        Record a completed agent execution.

        Parameters
        ──────────
        agent      : str
            Name of the agent (e.g. ``"metadata_agent"``).
        started_at : str | None
            ISO-8601 UTC timestamp when the agent started.
        finished_at: str | None
            ISO-8601 UTC timestamp when the agent finished.
        duration_ms: int | None
            Execution duration in milliseconds.
        status     : AgentStatus | None
            Final outcome (``COMPLETED`` or ``FAILED``).
        thread     : str | None
            Name of the executing thread.
        wave       : int | None
            The execution wave ID.
        """
        # Resolve values (supporting legacy fields if new ones are omitted)
        final_started = started_at or start_time or ""
        final_finished = finished_at or end_time or ""
        if duration_ms is not None:
            final_duration = int(duration_ms)
        elif duration is not None:
            final_duration = int(duration * 1000)
        else:
            final_duration = 0

        with self._rlock:
            self._execution_history.append({
                "agent": agent,
                "started_at": final_started,
                "finished_at": final_finished,
                "duration_ms": final_duration,
                "status": status.value if status else "UNKNOWN",
                "thread": thread or "unknown",
                "wave": wave if wave is not None else 0,
            })

    def get_execution_history(self) -> list[dict[str, Any]]:
        """
        Return a copy of all execution history entries.

        Returns
        ───────
        list[dict[str, Any]]
        """
        with self._rlock:
            return copy.deepcopy(self._execution_history)

    # ── Agent status ─────────────────────────────────────────────

    def set_agent_status(self, agent: str, status: AgentStatus) -> None:
        """
        Update the lifecycle status of a specific agent.

        Parameters
        ──────────
        agent  : str
            Agent identifier (e.g. ``"metadata_agent"``).
        status : AgentStatus
            The new status (``WAITING``, ``RUNNING``, ``COMPLETED``,
            ``FAILED``).
        """
        with self._rlock:
            self._agent_status[agent] = status

    def get_agent_status(self, agent: str) -> AgentStatus | None:
        """
        Return the current status of a specific agent.

        Parameters
        ──────────
        agent : str
            Agent identifier.

        Returns
        ───────
        AgentStatus | None
            The current status, or ``None`` if the agent has not
            been registered yet.
        """
        with self._rlock:
            return self._agent_status.get(agent)

    def get_all_agent_statuses(self) -> dict[str, str]:
        """
        Return a snapshot of every agent's current status.

        Returns
        ───────
        dict[str, str]
            Mapping of agent name → status value string.
        """
        with self._rlock:
            return {
                agent: status.value
                for agent, status in self._agent_status.items()
            }

    # ── Reset ────────────────────────────────────────────────────

    def clear(self) -> None:
        """
        Reset all stored state to defaults and generate a new
        session id.

        Useful between sessions, warehouse switches, or during
        testing.
        """
        with self._rlock:
            self._session_id = str(uuid.uuid4())
            self._current_warehouse = None
            self._agent_results.clear()
            self._execution_logs.clear()
            self._execution_history.clear()
            self._agent_status.clear()
