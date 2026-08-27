"""
PostgreSQL runtime monitoring analyzer.

Collects current-state metrics from a PostgreSQL database using
read-only system catalog queries.  Covers connections, running
queries, locks, transactions, database size, and basic performance
indicators.

All queries are **strictly read-only** — no INSERT, UPDATE, DELETE,
DROP, ALTER, or CREATE statements are used.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from sqlalchemy import text

from app.core.config import settings
from app.models.warehouse import Warehouse
from app.warehouse.connector import WarehouseConnector

logger = logging.getLogger(__name__)

_HIGH = "HIGH"
_MEDIUM = "MEDIUM"
_LOW = "LOW"


class MonitoringAnalyzer:
    """
    Collects PostgreSQL runtime state metrics via read-only queries.

    Each monitoring section is independently wrapped in try/except
    to support graceful degradation — if one query fails, the
    remaining sections still produce data.
    """

    def __init__(self) -> None:
        self._connector = WarehouseConnector()

    # ── Public API ───────────────────────────────────────────────

    def analyse(
        self,
        warehouse: Warehouse,
        progress_callback: Callable[[str, int | None], None] | None = None,
    ) -> dict[str, Any]:
        """
        Collect all monitoring metrics for the given warehouse.

        Parameters
        ──────────
        warehouse : Warehouse
            A registered ``Warehouse`` ORM instance.
        progress_callback : callable, optional
            ``(message, progress_pct)`` callback for SSE progress.

        Returns
        ───────
        dict[str, Any]
            Structured monitoring result with sections for
            connections, queries, locks, transactions, database,
            performance, findings, and summary.
        """
        engine = self._connector.connect(warehouse)
        errors: list[dict[str, str]] = []

        def _emit(msg: str, pct: int | None = None) -> None:
            if progress_callback:
                progress_callback(msg, pct)

        # ── 1. Connections ───────────────────────────────────────
        _emit("Collecting connection metrics...", 0)
        connections = self._collect_connections(engine, errors)

        # ── 2. Running queries ───────────────────────────────────
        _emit("Inspecting active sessions...", 15)
        queries = self._collect_running_queries(engine, errors)

        # ── 3. Long-running queries ──────────────────────────────
        _emit("Checking long-running queries...", 30)
        long_running = self._collect_long_running_queries(engine, errors)

        # ── 4. Waiting queries ───────────────────────────────────
        _emit("Checking waiting queries...", 45)
        waiting = self._collect_waiting_queries(engine, errors)

        # ── 5. Locks / blocking ──────────────────────────────────
        _emit("Checking locks...", 55)
        locks = self._collect_locks(engine, errors)

        # ── 6. Transactions ──────────────────────────────────────
        _emit("Inspecting transaction states...", 70)
        transactions = self._collect_transactions(engine, errors)

        # ── 7. Database size ─────────────────────────────────────
        _emit("Collecting database size...", 80)
        database = self._collect_database_size(engine, warehouse, errors)

        # ── 8. Performance indicators ────────────────────────────
        _emit("Collecting PostgreSQL performance indicators...", 90)
        performance = self._collect_performance(engine, errors)

        # ── Findings ─────────────────────────────────────────────
        _emit("Evaluating monitoring thresholds...", 95)
        findings = self._evaluate_findings(
            connections, queries, long_running, waiting, locks, transactions, performance
        )

        # ── Health status ────────────────────────────────────────
        high_count = sum(1 for f in findings if f["severity"] == _HIGH)
        medium_count = sum(1 for f in findings if f["severity"] == _MEDIUM)

        if high_count > 0:
            health_status = "CRITICAL"
        elif medium_count > 0:
            health_status = "WARNING"
        else:
            health_status = "HEALTHY"

        engine.dispose()

        return {
            "connections": connections,
            "queries": queries,
            "long_running_queries": long_running,
            "waiting_queries": waiting,
            "locks": locks,
            "transactions": transactions,
            "database": database,
            "performance": performance,
            "findings": findings,
            "errors": errors,
            "summary": {
                "health_status": health_status,
                "finding_count": len(findings),
                "high_findings": high_count,
                "medium_findings": medium_count,
                "low_findings": sum(1 for f in findings if f["severity"] == _LOW),
                "partial_failure": len(errors) > 0,
            },
        }

    # ── 1. Connections ───────────────────────────────────────────

    def _collect_connections(
        self, engine: Any, errors: list[dict[str, str]]
    ) -> dict[str, Any]:
        try:
            with engine.connect() as conn:
                # Max connections
                row = conn.execute(text("SHOW max_connections")).fetchone()
                max_connections = int(row[0]) if row else 0

                # Connection breakdown by state
                rows = conn.execute(text("""
                    SELECT
                        state,
                        COUNT(*) AS cnt
                    FROM pg_stat_activity
                    WHERE backend_type = 'client backend'
                    GROUP BY state
                """)).fetchall()

                state_counts: dict[str, int] = {}
                total = 0
                for r in rows:
                    state = r[0] or "unknown"
                    count = r[1]
                    state_counts[state] = count
                    total += count

                active = state_counts.get("active", 0)
                idle = state_counts.get("idle", 0)
                idle_in_tx = state_counts.get("idle in transaction", 0)
                idle_in_tx_aborted = state_counts.get("idle in transaction (aborted)", 0)

                # Waiting connections (wait_event IS NOT NULL and state = 'active')
                waiting_row = conn.execute(text("""
                    SELECT COUNT(*)
                    FROM pg_stat_activity
                    WHERE backend_type = 'client backend'
                      AND wait_event IS NOT NULL
                      AND state = 'active'
                """)).fetchone()
                waiting = waiting_row[0] if waiting_row else 0

                utilization = round((total / max_connections * 100), 1) if max_connections > 0 else 0.0

                return {
                    "current": total,
                    "maximum": max_connections,
                    "active": active,
                    "idle": idle,
                    "idle_in_transaction": idle_in_tx + idle_in_tx_aborted,
                    "waiting": waiting,
                    "utilization_percent": utilization,
                }
        except Exception as exc:
            logger.warning(f"Monitoring: connections query failed: {exc}")
            errors.append({"section": "connections", "error": str(exc)})
            return {
                "current": 0, "maximum": 0, "active": 0, "idle": 0,
                "idle_in_transaction": 0, "waiting": 0, "utilization_percent": 0.0,
            }

    # ── 2. Running queries ───────────────────────────────────────

    def _collect_running_queries(
        self, engine: Any, errors: list[dict[str, str]]
    ) -> dict[str, Any]:
        try:
            with engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT
                        pid,
                        state,
                        EXTRACT(EPOCH FROM (NOW() - query_start))::NUMERIC AS duration_seconds,
                        wait_event_type,
                        wait_event,
                        datname,
                        usename,
                        LEFT(query, 200) AS query_text
                    FROM pg_stat_activity
                    WHERE backend_type = 'client backend'
                      AND state = 'active'
                      AND pid != pg_backend_pid()
                    ORDER BY duration_seconds DESC NULLS LAST
                """)).fetchall()

                sessions = []
                for r in rows:
                    sessions.append({
                        "pid": r[0],
                        "state": r[1],
                        "duration_seconds": round(float(r[2]), 3) if r[2] is not None else None,
                        "wait_event_type": r[3],
                        "wait_event": r[4],
                        "database": r[5],
                        "user": r[6],
                        "query_text": r[7],
                    })

                return {
                    "running_count": len(sessions),
                    "sessions": sessions,
                }
        except Exception as exc:
            logger.warning(f"Monitoring: running queries failed: {exc}")
            errors.append({"section": "queries", "error": str(exc)})
            return {"running_count": 0, "sessions": []}

    # ── 3. Long-running queries ──────────────────────────────────

    def _collect_long_running_queries(
        self, engine: Any, errors: list[dict[str, str]]
    ) -> dict[str, Any]:
        threshold = settings.MONITORING_LONG_RUNNING_QUERY_SECONDS
        try:
            with engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT
                        pid,
                        state,
                        EXTRACT(EPOCH FROM (NOW() - query_start))::NUMERIC AS duration_seconds,
                        usename,
                        datname,
                        LEFT(query, 200) AS query_text
                    FROM pg_stat_activity
                    WHERE backend_type = 'client backend'
                      AND state = 'active'
                      AND pid != pg_backend_pid()
                      AND query_start IS NOT NULL
                      AND EXTRACT(EPOCH FROM (NOW() - query_start)) > :threshold
                    ORDER BY duration_seconds DESC
                """), {"threshold": threshold}).fetchall()

                longest_duration = None
                sessions = []
                for r in rows:
                    dur = round(float(r[2]), 3) if r[2] is not None else None
                    if longest_duration is None or (dur and dur > longest_duration):
                        longest_duration = dur
                    sessions.append({
                        "pid": r[0],
                        "state": r[1],
                        "duration_seconds": dur,
                        "user": r[3],
                        "database": r[4],
                        "query_text": r[5],
                    })

                return {
                    "count": len(sessions),
                    "threshold_seconds": threshold,
                    "longest_duration_seconds": longest_duration,
                    "sessions": sessions,
                }
        except Exception as exc:
            logger.warning(f"Monitoring: long-running queries failed: {exc}")
            errors.append({"section": "long_running_queries", "error": str(exc)})
            return {
                "count": 0, "threshold_seconds": threshold,
                "longest_duration_seconds": None, "sessions": [],
            }

    # ── 4. Waiting queries ───────────────────────────────────────

    def _collect_waiting_queries(
        self, engine: Any, errors: list[dict[str, str]]
    ) -> dict[str, Any]:
        try:
            with engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT
                        pid,
                        state,
                        wait_event_type,
                        wait_event,
                        EXTRACT(EPOCH FROM (NOW() - query_start))::NUMERIC AS duration_seconds,
                        usename,
                        LEFT(query, 200) AS query_text
                    FROM pg_stat_activity
                    WHERE backend_type = 'client backend'
                      AND wait_event IS NOT NULL
                      AND state = 'active'
                      AND pid != pg_backend_pid()
                    ORDER BY duration_seconds DESC NULLS LAST
                """)).fetchall()

                sessions = []
                for r in rows:
                    sessions.append({
                        "pid": r[0],
                        "state": r[1],
                        "wait_event_type": r[2],
                        "wait_event": r[3],
                        "duration_seconds": round(float(r[4]), 3) if r[4] is not None else None,
                        "user": r[5],
                        "query_text": r[6],
                    })

                return {
                    "waiting_count": len(sessions),
                    "sessions": sessions,
                }
        except Exception as exc:
            logger.warning(f"Monitoring: waiting queries failed: {exc}")
            errors.append({"section": "waiting_queries", "error": str(exc)})
            return {"waiting_count": 0, "sessions": []}

    # ── 5. Locks / blocking ──────────────────────────────────────

    def _collect_locks(
        self, engine: Any, errors: list[dict[str, str]]
    ) -> dict[str, Any]:
        try:
            with engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT
                        blocked.pid        AS blocked_pid,
                        blocked_activity.usename  AS blocked_user,
                        LEFT(blocked_activity.query, 200) AS blocked_query,
                        blocking.pid       AS blocking_pid,
                        blocking_activity.usename AS blocking_user,
                        LEFT(blocking_activity.query, 200) AS blocking_query,
                        EXTRACT(EPOCH FROM (NOW() - blocked_activity.query_start))::NUMERIC
                            AS blocked_duration_seconds
                    FROM pg_locks blocked
                    JOIN pg_stat_activity blocked_activity
                        ON blocked_activity.pid = blocked.pid
                    JOIN pg_locks blocking
                        ON blocking.locktype = blocked.locktype
                        AND blocking.database IS NOT DISTINCT FROM blocked.database
                        AND blocking.relation IS NOT DISTINCT FROM blocked.relation
                        AND blocking.page IS NOT DISTINCT FROM blocked.page
                        AND blocking.tuple IS NOT DISTINCT FROM blocked.tuple
                        AND blocking.virtualxid IS NOT DISTINCT FROM blocked.virtualxid
                        AND blocking.transactionid IS NOT DISTINCT FROM blocked.transactionid
                        AND blocking.classid IS NOT DISTINCT FROM blocked.classid
                        AND blocking.objid IS NOT DISTINCT FROM blocked.objid
                        AND blocking.objsubid IS NOT DISTINCT FROM blocked.objsubid
                        AND blocking.pid != blocked.pid
                    JOIN pg_stat_activity blocking_activity
                        ON blocking_activity.pid = blocking.pid
                    WHERE NOT blocked.granted
                      AND blocking.granted
                """)).fetchall()

                blocked_pids = set()
                blocking_pids = set()
                details = []
                for r in rows:
                    blocked_pids.add(r[0])
                    blocking_pids.add(r[3])
                    details.append({
                        "blocked_pid": r[0],
                        "blocked_user": r[1],
                        "blocked_query": r[2],
                        "blocking_pid": r[3],
                        "blocking_user": r[4],
                        "blocking_query": r[5],
                        "blocked_duration_seconds": round(float(r[6]), 3) if r[6] is not None else None,
                    })

                return {
                    "blocked_sessions": len(blocked_pids),
                    "blocking_sessions": len(blocking_pids),
                    "details": details,
                }
        except Exception as exc:
            logger.warning(f"Monitoring: locks query failed: {exc}")
            errors.append({"section": "locks", "error": str(exc)})
            return {"blocked_sessions": 0, "blocking_sessions": 0, "details": []}

    # ── 6. Transactions ──────────────────────────────────────────

    def _collect_transactions(
        self, engine: Any, errors: list[dict[str, str]]
    ) -> dict[str, Any]:
        idle_tx_threshold = settings.MONITORING_IDLE_IN_TRANSACTION_THRESHOLD
        long_tx_threshold = settings.MONITORING_LONG_RUNNING_TRANSACTION_SECONDS
        try:
            with engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT
                        state,
                        COUNT(*) AS cnt,
                        MAX(EXTRACT(EPOCH FROM (NOW() - xact_start))::NUMERIC)
                            AS max_duration_seconds
                    FROM pg_stat_activity
                    WHERE backend_type = 'client backend'
                      AND xact_start IS NOT NULL
                    GROUP BY state
                """)).fetchall()

                state_data: dict[str, dict[str, Any]] = {}
                for r in rows:
                    state = r[0] or "unknown"
                    state_data[state] = {
                        "count": r[1],
                        "max_duration_seconds": round(float(r[2]), 3) if r[2] is not None else None,
                    }

                active = state_data.get("active", {}).get("count", 0)
                idle = state_data.get("idle", {}).get("count", 0)
                idle_in_tx = state_data.get("idle in transaction", {}).get("count", 0)
                idle_in_tx_max = state_data.get("idle in transaction", {}).get("max_duration_seconds")

                # Long-running idle-in-transaction
                long_idle_tx_row = conn.execute(text("""
                    SELECT COUNT(*)
                    FROM pg_stat_activity
                    WHERE backend_type = 'client backend'
                      AND state = 'idle in transaction'
                      AND xact_start IS NOT NULL
                      AND EXTRACT(EPOCH FROM (NOW() - xact_start)) > :threshold
                """), {"threshold": idle_tx_threshold}).fetchone()
                long_idle_tx = int(long_idle_tx_row[0]) if long_idle_tx_row and long_idle_tx_row[0] is not None else 0

                # Long-running active transactions
                long_active_tx_row = conn.execute(text("""
                    SELECT COUNT(*)
                    FROM pg_stat_activity
                    WHERE backend_type = 'client backend'
                      AND state = 'active'
                      AND xact_start IS NOT NULL
                      AND EXTRACT(EPOCH FROM (NOW() - xact_start)) > :threshold
                """), {"threshold": long_tx_threshold}).fetchone()
                long_active_tx = int(long_active_tx_row[0]) if long_active_tx_row and long_active_tx_row[0] is not None else 0

                return {
                    "active": active,
                    "idle": idle,
                    "idle_in_transaction": idle_in_tx,
                    "idle_in_transaction_max_seconds": idle_in_tx_max,
                    "long_idle_in_transaction": long_idle_tx,
                    "long_idle_threshold_seconds": idle_tx_threshold,
                    "long_active_transactions": long_active_tx,
                    "long_active_threshold_seconds": long_tx_threshold,
                }
        except Exception as exc:
            logger.warning(f"Monitoring: transactions query failed: {exc}")
            errors.append({"section": "transactions", "error": str(exc)})
            return {
                "active": 0, "idle": 0, "idle_in_transaction": 0,
                "idle_in_transaction_max_seconds": None,
                "long_idle_in_transaction": 0,
                "long_idle_threshold_seconds": idle_tx_threshold,
                "long_active_transactions": 0,
                "long_active_threshold_seconds": long_tx_threshold,
            }

    # ── 7. Database size ─────────────────────────────────────────

    def _collect_database_size(
        self, engine: Any, warehouse: Warehouse, errors: list[dict[str, str]]
    ) -> dict[str, Any]:
        try:
            with engine.connect() as conn:
                row = conn.execute(text("""
                    SELECT
                        current_database() AS db_name,
                        pg_database_size(current_database()) AS size_bytes,
                        pg_size_pretty(pg_database_size(current_database())) AS size_pretty
                """)).fetchone()

                if row:
                    return {
                        "name": row[0],
                        "size_bytes": row[1],
                        "size_pretty": row[2],
                    }
                return {"name": warehouse.database_name, "size_bytes": 0, "size_pretty": "0 bytes"}
        except Exception as exc:
            logger.warning(f"Monitoring: database size query failed: {exc}")
            errors.append({"section": "database", "error": str(exc)})
            return {"name": warehouse.database_name, "size_bytes": 0, "size_pretty": "0 bytes"}

    # ── 8. Performance indicators ────────────────────────────────

    def _collect_performance(
        self, engine: Any, errors: list[dict[str, str]]
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}

        # Cache hit ratio
        try:
            with engine.connect() as conn:
                row = conn.execute(text("""
                    SELECT
                        SUM(heap_blks_hit) AS hit,
                        SUM(heap_blks_read) AS read
                    FROM pg_statio_user_tables
                """)).fetchone()

                if row and row[0] is not None and row[1] is not None:
                    total = row[0] + row[1]
                    ratio = round((row[0] / total * 100), 2) if total > 0 else 0.0
                    result["cache_hit_ratio"] = ratio
                else:
                    result["cache_hit_ratio"] = None
        except Exception as exc:
            logger.warning(f"Monitoring: cache hit ratio failed: {exc}")
            errors.append({"section": "performance.cache_hit_ratio", "error": str(exc)})
            result["cache_hit_ratio"] = None

        # Table scan statistics
        try:
            with engine.connect() as conn:
                row = conn.execute(text("""
                    SELECT
                        COALESCE(SUM(seq_scan), 0) AS seq_scans,
                        COALESCE(SUM(idx_scan), 0) AS idx_scans,
                        COALESCE(SUM(seq_tup_read), 0) AS tuples_read,
                        COALESCE(SUM(idx_tup_fetch), 0) AS tuples_returned,
                        COALESCE(SUM(n_dead_tup), 0) AS dead_tuples,
                        COALESCE(SUM(n_live_tup), 0) AS live_tuples
                    FROM pg_stat_user_tables
                """)).fetchone()

                if row:
                    result["seq_scans"] = int(row[0])
                    result["idx_scans"] = int(row[1])
                    result["tuples_read"] = int(row[2])
                    result["tuples_returned"] = int(row[3])
                    result["dead_tuples"] = int(row[4])
                    result["live_tuples"] = int(row[5])
                else:
                    result.update({
                        "seq_scans": 0, "idx_scans": 0,
                        "tuples_read": 0, "tuples_returned": 0,
                        "dead_tuples": 0, "live_tuples": 0,
                    })
        except Exception as exc:
            logger.warning(f"Monitoring: table scan stats failed: {exc}")
            errors.append({"section": "performance.table_scans", "error": str(exc)})
            result.update({
                "seq_scans": 0, "idx_scans": 0,
                "tuples_read": 0, "tuples_returned": 0,
                "dead_tuples": 0, "live_tuples": 0,
            })

        return result

    # ── Findings evaluation ──────────────────────────────────────

    def _evaluate_findings(
        self,
        connections: dict[str, Any],
        queries: dict[str, Any],
        long_running: dict[str, Any],
        waiting: dict[str, Any],
        locks: dict[str, Any],
        transactions: dict[str, Any],
        performance: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Evaluate monitoring thresholds and produce findings."""
        findings: list[dict[str, Any]] = []

        utilization = connections.get("utilization_percent", 0)
        high_pct = settings.MONITORING_CONNECTION_CRITICAL_PERCENT
        medium_pct = settings.MONITORING_CONNECTION_WARNING_PERCENT

        # Connection utilization
        if utilization >= high_pct:
            findings.append({
                "title": "Critical connection utilization",
                "category": "Connections",
                "severity": _HIGH,
                "description": (
                    f"Connection utilization is at {utilization}%, "
                    f"exceeding the {high_pct}% critical threshold."
                ),
                "evidence": {
                    "current": connections.get("current"),
                    "maximum": connections.get("maximum"),
                    "utilization_percent": utilization,
                },
                "threshold": high_pct,
            })
        elif utilization >= medium_pct:
            findings.append({
                "title": "Elevated connection utilization",
                "category": "Connections",
                "severity": _MEDIUM,
                "description": (
                    f"Connection utilization is at {utilization}%, "
                    f"exceeding the {medium_pct}% warning threshold."
                ),
                "evidence": {
                    "current": connections.get("current"),
                    "maximum": connections.get("maximum"),
                    "utilization_percent": utilization,
                },
                "threshold": medium_pct,
            })

        # Blocked sessions
        blocked = locks.get("blocked_sessions", 0)
        if blocked > 0:
            findings.append({
                "title": "Blocked sessions detected",
                "category": "Locks",
                "severity": _HIGH,
                "description": (
                    f"{blocked} session(s) are currently blocked by lock contention."
                ),
                "evidence": {
                    "blocked_sessions": blocked,
                    "blocking_sessions": locks.get("blocking_sessions", 0),
                },
                "threshold": 0,
            })

        # Long-running queries
        lr_count = long_running.get("count", 0)
        if lr_count > 0:
            findings.append({
                "title": "Long-running queries detected",
                "category": "Queries",
                "severity": _MEDIUM,
                "description": (
                    f"{lr_count} query(ies) running longer than "
                    f"{long_running.get('threshold_seconds')}s threshold. "
                    f"Longest: {long_running.get('longest_duration_seconds')}s."
                ),
                "evidence": {
                    "count": lr_count,
                    "threshold_seconds": long_running.get("threshold_seconds"),
                    "longest_duration_seconds": long_running.get("longest_duration_seconds"),
                },
                "threshold": long_running.get("threshold_seconds"),
            })

        # Waiting queries
        waiting_count = waiting.get("waiting_count", 0)
        if waiting_count > 0:
            findings.append({
                "title": "Waiting queries detected",
                "category": "Queries",
                "severity": _MEDIUM,
                "description": (
                    f"{waiting_count} query(ies) are currently waiting for resources."
                ),
                "evidence": {"waiting_count": waiting_count},
                "threshold": 0,
            })

        # Idle-in-transaction
        long_idle_tx = transactions.get("long_idle_in_transaction", 0)
        if long_idle_tx > 0:
            findings.append({
                "title": "Idle-in-transaction sessions detected",
                "category": "Transactions",
                "severity": _MEDIUM,
                "description": (
                    f"{long_idle_tx} session(s) are idle in an open transaction longer than threshold. "
                    f"This can hold locks and prevent vacuuming."
                ),
                "evidence": {
                    "long_idle_in_transaction": long_idle_tx,
                    "max_seconds": transactions.get("idle_in_transaction_max_seconds"),
                },
                "threshold": transactions.get("long_idle_threshold_seconds"),
            })

        # Long-running active transactions
        long_active_tx = transactions.get("long_active_transactions", 0)
        if long_active_tx > 0:
            findings.append({
                "title": "Long-running active transactions detected",
                "category": "Transactions",
                "severity": _MEDIUM,
                "description": (
                    f"{long_active_tx} transaction(s) running longer than the configured threshold."
                ),
                "evidence": {
                    "long_active_transactions": long_active_tx,
                },
                "threshold": transactions.get("long_active_threshold_seconds"),
            })
            
        # Cache Hit Ratio
        cache_hit_ratio = performance.get("cache_hit_ratio")
        if cache_hit_ratio is not None and cache_hit_ratio < settings.MONITORING_CACHE_HIT_WARNING_PERCENT:
            findings.append({
                "title": "Low cache hit ratio",
                "category": "Performance",
                "severity": _MEDIUM,
                "description": (
                    f"Cache hit ratio is {cache_hit_ratio}%, which is below the "
                    f"{settings.MONITORING_CACHE_HIT_WARNING_PERCENT}% warning threshold."
                ),
                "evidence": {
                    "cache_hit_ratio": cache_hit_ratio,
                },
                "threshold": settings.MONITORING_CACHE_HIT_WARNING_PERCENT,
            })

        return findings
