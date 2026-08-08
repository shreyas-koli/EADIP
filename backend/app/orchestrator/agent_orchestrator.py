"""
Enterprise parallel orchestration engine.

Provides a **DAG-aware** workflow executor that schedules agent
tasks based on declared dependencies, runs independent tasks in
parallel via ``ThreadPoolExecutor``, and serialises dependent
chains automatically.

The orchestrator contains **zero business logic**.  It is solely
responsible for:

* Task decomposition and dependency resolution
* Parallel scheduling of independent tasks
* Sequential execution of dependent chains
* Lifecycle status management (WAITING → RUNNING → COMPLETED / FAILED)
* Execution timing and history recording
* Result collection from ``SharedContext``

Every agent writes its own output into the shared memory bus via
``context.set_agent_result(agent_name, result)``.  The orchestrator
never reads, transforms, or manipulates agent results.

No LLM calls, no database writes, no HTTP concerns.
"""

from __future__ import annotations

import threading
import time
import traceback
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.context.shared_context import AgentStatus, SharedContext


# ── Agent task descriptor ────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AgentTask:
    """
    Immutable descriptor for a single agent execution unit.

    Attributes
    ──────────
    name         Unique identifier used for status tracking, result
                 storage, and dependency resolution.
    callable     The agent function to invoke.
    args         Positional arguments forwarded to ``callable``.
    kwargs       Keyword arguments forwarded to ``callable``.
    dependencies Names of tasks that **must** complete successfully
                 before this task is eligible for scheduling.

    Example::

        AgentTask(
            name="metadata",
            callable=metadata_agent.discover,
            args=(warehouse,),
        )

        AgentTask(
            name="query",
            callable=query_agent.run,
            args=(warehouse,),
            dependencies=["metadata"],
        )
    """

    name: str
    callable: Callable[..., Any]
    args: tuple = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)


# ── Orchestration engine ─────────────────────────────────────────


class AgentOrchestrator:
    """
    DAG-aware parallel orchestration engine.

    Accepts a list of ``AgentTask`` descriptors, resolves their
    dependency graph, and executes them in waves:

    1. **Wave 0** — all tasks with no dependencies run in parallel.
    2. **Wave 1** — tasks whose dependencies were satisfied in
       wave 0 run in parallel.
    3. Repeat until every task has been executed or a dependency
       failure blocks further progress.

    The engine is **agent-agnostic** — it does not import, reference,
    or hardcode any specific agent class.

    Usage::

        orchestrator = AgentOrchestrator()

        summary = orchestrator.execute_parallel([
            AgentTask("metadata",   meta_fn,  (wh,)),
            AgentTask("statistics", stats_fn, (wh,)),
            AgentTask("security",   sec_fn,   (wh,)),
            AgentTask("query",      query_fn, (wh,), dependencies=["metadata"]),
            AgentTask("explain",    exp_fn,   (wh,), dependencies=["query"]),
        ])
    """

    def __init__(self, context: SharedContext | None = None, max_workers: int = 5) -> None:
        """
        Initialise the orchestration engine.

        Parameters
        ──────────
        context : SharedContext | None
            The explicit shared memory bus. If None, creates a new one.
        max_workers : int
            Maximum number of concurrent threads (default 5).
        """
        self._context = context if context is not None else SharedContext()
        self._max_workers = max_workers

    # ── Public API ───────────────────────────────────────────────

    def execute_parallel(
        self,
        tasks: list[AgentTask],
    ) -> dict[str, Any]:
        """
        Execute agent tasks respecting their dependency graph.

        Independent tasks run **simultaneously**; dependent tasks
        wait until all their prerequisites have completed
        successfully.

        Parameters
        ──────────
        tasks : list[AgentTask]
            The full set of agent tasks to orchestrate.

        Returns
        ───────
        dict[str, Any]
            Execution summary::

                {
                    "parallel":       True,
                    "session_id":     "a1b2c3…",
                    "total_execution_ms": 132,
                    "completed":      ["metadata", "statistics"],
                    "failed":         ["security"],
                    "skipped":        ["query"],
                    "agent_execution": [ ... ],
                    "agent_results":  { ... }
                }

        Raises
        ──────
        ValueError
            If a task declares a dependency on a name that does not
            appear in the task list (broken graph).
        """
        # ── Validate unique task names ───────────────────────────
        task_names = [t.name for t in tasks]
        if len(task_names) != len(set(task_names)):
            raise ValueError("Duplicate agent task names are not allowed.")

        # ── Validate the dependency graph ────────────────────────
        task_map: dict[str, AgentTask] = {t.name: t for t in tasks}
        self._validate_graph(task_map)

        # ── Initialise all tasks as WAITING ──────────────────────
        for task in tasks:
            self._context.set_agent_status(task.name, AgentStatus.WAITING)

        self._context.add_execution_log(
            f"Orchestrator received {len(tasks)} task(s) for execution."
        )

        completed: list[str] = []
        failed: list[str] = []
        skipped: list[str] = []
        agent_executions: list[dict[str, Any]] = []

        overall_start_ns = time.perf_counter_ns()

        # ── Execute in waves ─────────────────────────────────────
        remaining = set(task_map.keys())
        wave_id = 1

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            while remaining:
                ready = [
                    name for name in remaining
                    if all(dep in completed for dep in task_map[name].dependencies)
                ]
                # Find tasks whose dependencies are all satisfied

                # Tasks blocked by a failed dependency
                blocked = [
                    name for name in remaining
                    if name not in ready
                    and any(dep in failed or dep in skipped
                            for dep in task_map[name].dependencies)
                ]

                # Skip blocked tasks
                for name in blocked:
                    skipped.append(name)
                    remaining.discard(name)
                    self._context.set_agent_status(name, AgentStatus.SKIPPED)
                    self._context.add_execution_log(
                        f"Agent '{name}' skipped — dependency failed."
                    )
                    agent_executions.append({
                        "agent": name,
                        "wave": wave_id,
                        "thread": "orchestrator",
                        "started_at": datetime.now(timezone.utc).isoformat(),
                        "finished_at": datetime.now(timezone.utc).isoformat(),
                        "duration_ms": 0.0,
                    })

                if not ready:
                    # No tasks can proceed — break to avoid infinite loop
                    for name in remaining:
                        skipped.append(name)
                        self._context.set_agent_status(name, AgentStatus.SKIPPED)
                        self._context.add_execution_log(
                            f"Agent '{name}' skipped — unresolvable dependencies."
                        )
                        agent_executions.append({
                            "agent": name,
                            "wave": wave_id,
                            "thread": "orchestrator",
                            "started_at": datetime.now(timezone.utc).isoformat(),
                            "finished_at": datetime.now(timezone.utc).isoformat(),
                            "duration_ms": 0.0,
                        })
                    remaining.clear()
                    break

                # ── Execute this wave in parallel ────────────────────
                wave_completed, wave_failed, wave_metrics = self._execute_wave(
                    executor,
                    [task_map[name] for name in ready],
                    wave_id,
                )

                completed.extend(wave_completed)
                failed.extend(wave_failed)
                agent_executions.extend(wave_metrics)
                remaining -= set(ready)
                wave_id += 1

        overall_duration_ms = (time.perf_counter_ns() - overall_start_ns) / 1_000_000

        self._context.add_execution_log(
            f"Orchestrator finished. "
            f"{len(completed)} completed, {len(failed)} failed, "
            f"{len(skipped)} skipped in {overall_duration_ms}ms."
        )

        return {
            "parallel": True,
            "session_id": self._context.get_session_id(),
            "total_execution_ms": overall_duration_ms,
            "completed": completed,
            "failed": failed,
            "skipped": skipped,
            "agent_execution": agent_executions,
            "agent_results": self._context.get_all_agent_results(),
        }

    # ── Wave executor ────────────────────────────────────────────

    def _execute_wave(
        self,
        executor: ThreadPoolExecutor,
        tasks: list[AgentTask],
        wave_id: int,
    ) -> tuple[list[str], list[str], list[dict[str, Any]]]:
        """
        Execute a single wave of independent tasks in parallel.

        Parameters
        ──────────
        executor : ThreadPoolExecutor
            The shared executor pool.
        tasks : list[AgentTask]
            Tasks in this wave (all dependencies already met).
        wave_id : int
            The execution wave sequence number.

        Returns
        ───────
        tuple[list[str], list[str], list[dict[str, Any]]]
            ``(completed_names, failed_names, wave_metrics)``
        """
        completed: list[str] = []
        failed: list[str] = []
        wave_metrics: list[dict[str, Any]] = []

        self._context.add_execution_log(
            f"Executing Wave {wave_id}: {[t.name for t in tasks]}"
        )

        future_to_name: dict[Future[dict[str, Any]], str] = {}

        for task in tasks:
            future = executor.submit(
                self._run_agent, task, wave_id
            )
            future_to_name[future] = task.name

        for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    result = future.result()
                    if result["status"] == AgentStatus.COMPLETED:
                        completed.append(name)
                    else:
                        failed.append(name)
                    wave_metrics.append(result["metrics"])
                except Exception as exc:
                    # Fallback in case _run_agent itself raises
                    failed.append(name)
                    self._context.add_execution_log(
                        f"Agent '{name}' raised unexpected error: {exc}"
                    )
                    wave_metrics.append({
                        "agent": name,
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                    })

        return completed, failed, wave_metrics

    # ── Single agent runner ──────────────────────────────────────

    def _run_agent(self, task: AgentTask, wave_id: int) -> dict[str, Any]:
        """
        Execute a single agent task with full lifecycle tracking.

        Workflow
        ────────
        1. Set status → ``RUNNING``, record start time.
        2. Invoke ``task.callable(*task.args, **task.kwargs)``.
        3. On success → ``COMPLETED``.
        4. On failure → ``FAILED``, catch exception and format traceback.
        5. Record execution history regardless of outcome.
        6. Return detailed metrics dict for the orchestrator.

        Parameters
        ──────────
        task : AgentTask
            The task descriptor to execute.
        wave_id : int
            The execution wave sequence number.
            
        Returns
        ───────
        dict[str, Any]
            The execution metrics and final status of the task.
        """
        self._context.set_agent_status(task.name, AgentStatus.RUNNING)
        self._context.add_execution_log(f"Agent '{task.name}' started.")

        start_ns = time.perf_counter_ns()
        start_iso = datetime.now(timezone.utc).isoformat()
        status = AgentStatus.COMPLETED
        
        error_msg = None
        tb_str = None

        try:
            task.callable(*task.args, **task.kwargs)
        except Exception as exc:
            status = AgentStatus.FAILED
            error_msg = str(exc)
            tb_str = traceback.format_exc()
        finally:
            end_ns = time.perf_counter_ns()
            end_iso = datetime.now(timezone.utc).isoformat()
            duration_ms = (end_ns - start_ns) / 1_000_000

            self._context.set_agent_status(task.name, status)
            self._context.add_execution_history(
                agent=task.name,
                started_at=start_iso,
                finished_at=end_iso,
                duration_ms=duration_ms,
                status=status,
                thread=threading.current_thread().name,
                wave=wave_id,
            )
            self._context.add_execution_log(
                f"Agent '{task.name}' finished — "
                f"{status.value} in {duration_ms}ms."
            )
            
            metrics: dict[str, Any] = {
                "agent": task.name,
                "wave": wave_id,
                "thread": threading.current_thread().name,
                "started_at": start_iso,
                "finished_at": end_iso,
                "duration_ms": duration_ms,
            }
            if error_msg is not None:
                metrics["error"] = error_msg
                metrics["traceback"] = tb_str

            return {"status": status, "metrics": metrics}

    # ── Graph validation ─────────────────────────────────────────

    @staticmethod
    def _validate_graph(task_map: dict[str, AgentTask]) -> None:
        """
        Ensure every declared dependency references an existing task
        and that the dependency graph contains no cycles.

        Parameters
        ──────────
        task_map : dict[str, AgentTask]
            Mapping of task name → task descriptor.

        Raises
        ──────
        ValueError
            If any dependency points to a name not in the map,
            or if a circular dependency is detected.
        """
        # 1. Validate all dependencies exist
        all_names = set(task_map.keys())
        for task in task_map.values():
            missing = set(task.dependencies) - all_names
            if missing:
                raise ValueError(
                    f"Task '{task.name}' declares dependencies on "
                    f"unknown tasks: {missing}."
                )

        # 2. Detect circular dependencies (DFS)
        visited: set[str] = set()
        path: list[str] = []
        path_set: set[str] = set()

        def check_cycle(node: str) -> None:
            if node in path_set:
                cycle_start = path.index(node)
                cycle_nodes = path[cycle_start:] + [node]
                cycle_str = " -> ".join(cycle_nodes)
                raise ValueError(f"Circular dependency detected: {cycle_str}")
            
            if node in visited:
                return

            path.append(node)
            path_set.add(node)

            for dep in task_map[node].dependencies:
                check_cycle(dep)

            path.pop()
            path_set.remove(node)
            visited.add(node)

        for task_name in task_map:
            if task_name not in visited:
                check_cycle(task_name)
