"""
Unit tests for the MonitoringAnalyzer.

All PostgreSQL queries are mocked — no live database required.
"""

import re
import textwrap
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.warehouse.monitoring import MonitoringAnalyzer


# ── Helpers ──────────────────────────────────────────────────────

def _make_mock_warehouse():
    """Create a mock Warehouse ORM instance."""
    wh = MagicMock()
    wh.database_name = "test_db"
    wh.db_type = "postgresql"
    wh.host = "localhost"
    wh.port = 5432
    wh.username = "test_user"
    wh.encrypted_password = "enc_pass"
    wh.name = "test_warehouse"
    return wh


def _build_mock_connection(query_results: dict):
    """
    Build a mock engine whose .connect() returns a context manager
    that responds to execute(text(...)) calls by matching SQL fragments.
    """
    mock_engine = MagicMock()
    mock_conn = MagicMock()

    def mock_execute(sql_text, params=None):
        sql = str(sql_text.text) if hasattr(sql_text, "text") else str(sql_text)
        for fragment, result in query_results.items():
            if fragment.lower() in sql.lower():
                mock_result = MagicMock()
                if isinstance(result, list):
                    mock_result.fetchall.return_value = result
                    mock_result.fetchone.return_value = result[0] if result else None
                else:
                    mock_result.fetchone.return_value = result
                    mock_result.fetchall.return_value = [result] if result else []
                return mock_result
        # Default empty result
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_result.fetchall.return_value = []
        return mock_result

    mock_conn.execute = mock_execute
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_engine.connect.return_value = mock_conn
    mock_engine.dispose = MagicMock()
    return mock_engine


# ── Test: Connection metrics ─────────────────────────────────────

class TestConnectionMetrics:
    def test_connection_breakdown(self):
        engine = _build_mock_connection({
            "show max_connections": ("100",),
            "group by state": [
                ("active", 3),
                ("idle", 8),
                ("idle in transaction", 1),
            ],
            "wait_event is not null": (0,),
        })
        analyzer = MonitoringAnalyzer()
        errors: list = []
        result = analyzer._collect_connections(engine, errors)

        assert result["maximum"] == 100
        assert result["current"] == 12  # 3 + 8 + 1
        assert result["active"] == 3
        assert result["idle"] == 8
        assert result["idle_in_transaction"] == 1
        assert result["waiting"] == 0
        assert result["utilization_percent"] == 12.0
        assert len(errors) == 0

    def test_connection_utilization_zero_max(self):
        engine = _build_mock_connection({
            "show max_connections": ("0",),
            "group by state": [],
            "wait_event is not null": (0,),
        })
        analyzer = MonitoringAnalyzer()
        errors: list = []
        result = analyzer._collect_connections(engine, errors)
        assert result["utilization_percent"] == 0.0

    def test_connection_query_failure(self):
        engine = MagicMock()
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("Connection refused")
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        engine.connect.return_value = mock_conn

        analyzer = MonitoringAnalyzer()
        errors: list = []
        result = analyzer._collect_connections(engine, errors)
        assert result["current"] == 0
        assert len(errors) == 1
        assert errors[0]["section"] == "connections"


# ── Test: Active/Idle classification ─────────────────────────────

class TestActiveIdleClassification:
    def test_classifies_correctly(self):
        engine = _build_mock_connection({
            "show max_connections": ("200",),
            "group by state": [
                ("active", 5),
                ("idle", 10),
                ("idle in transaction", 2),
                ("idle in transaction (aborted)", 1),
            ],
            "wait_event is not null": (1,),
        })
        analyzer = MonitoringAnalyzer()
        errors: list = []
        result = analyzer._collect_connections(engine, errors)

        assert result["active"] == 5
        assert result["idle"] == 10
        assert result["idle_in_transaction"] == 3  # 2 + 1 (aborted)
        assert result["waiting"] == 1
        assert result["current"] == 18


# ── Test: Running queries ────────────────────────────────────────

class TestRunningQueries:
    def test_running_query_collection(self):
        engine = _build_mock_connection({
            "state = 'active'": [
                (123, "active", 1.5, None, None, "mydb", "user1", "SELECT 1"),
                (456, "active", 0.3, "Lock", "relation", "mydb", "user2", "UPDATE t SET"),
            ],
        })
        analyzer = MonitoringAnalyzer()
        errors: list = []
        result = analyzer._collect_running_queries(engine, errors)

        assert result["running_count"] == 2
        assert len(result["sessions"]) == 2
        assert result["sessions"][0]["pid"] == 123
        assert result["sessions"][0]["duration_seconds"] == 1.5
        assert len(errors) == 0


# ── Test: Long-running queries ───────────────────────────────────

class TestLongRunningQueries:
    @patch("app.warehouse.monitoring.settings")
    def test_detects_long_running(self, mock_settings):
        mock_settings.MONITORING_LONG_RUNNING_QUERY_SECONDS = 5
        engine = _build_mock_connection({
            "extract(epoch": [
                (100, "active", 14.7, "admin", "mydb", "SELECT * FROM big_table"),
                (200, "active", 8.2, "admin", "mydb", "UPDATE inventory SET"),
            ],
        })
        analyzer = MonitoringAnalyzer()
        errors: list = []
        result = analyzer._collect_long_running_queries(engine, errors)

        assert result["count"] == 2
        assert result["threshold_seconds"] == 5
        assert result["longest_duration_seconds"] == 14.7

    @patch("app.warehouse.monitoring.settings")
    def test_no_long_running(self, mock_settings):
        mock_settings.MONITORING_LONG_RUNNING_QUERY_SECONDS = 5
        engine = _build_mock_connection({
            "extract(epoch": [],
        })
        analyzer = MonitoringAnalyzer()
        errors: list = []
        result = analyzer._collect_long_running_queries(engine, errors)

        assert result["count"] == 0
        assert result["longest_duration_seconds"] is None


# ── Test: Waiting queries ────────────────────────────────────────

class TestWaitingQueries:
    def test_detects_waiting(self):
        engine = _build_mock_connection({
            "wait_event is not null": [
                (300, "active", "Lock", "relation", 2.1, "user1", "SELECT FOR UPDATE"),
            ],
        })
        analyzer = MonitoringAnalyzer()
        errors: list = []
        result = analyzer._collect_waiting_queries(engine, errors)

        assert result["waiting_count"] == 1
        assert result["sessions"][0]["wait_event_type"] == "Lock"


# ── Test: Lock detection ─────────────────────────────────────────

class TestLockDetection:
    def test_detects_blocking(self):
        engine = _build_mock_connection({
            "not blocked.granted": [
                (10, "user1", "SELECT ...", 20, "user2", "UPDATE ...", 3.5),
            ],
        })
        analyzer = MonitoringAnalyzer()
        errors: list = []
        result = analyzer._collect_locks(engine, errors)

        assert result["blocked_sessions"] == 1
        assert result["blocking_sessions"] == 1
        assert len(result["details"]) == 1

    def test_no_blocking(self):
        engine = _build_mock_connection({
            "not blocked.granted": [],
        })
        analyzer = MonitoringAnalyzer()
        errors: list = []
        result = analyzer._collect_locks(engine, errors)

        assert result["blocked_sessions"] == 0
        assert result["blocking_sessions"] == 0


# ── Test: Transaction detection ──────────────────────────────────

class TestTransactionDetection:
    @patch("app.warehouse.monitoring.settings")
    def test_transaction_states(self, mock_settings):
        mock_settings.MONITORING_IDLE_IN_TRANSACTION_THRESHOLD = 30
        engine = _build_mock_connection({
            "group by state": [
                ("active", 2, 5.0),
                ("idle", 3, None),
                ("idle in transaction", 1, 45.0),
            ],
            "idle in transaction": (1,),
        })
        analyzer = MonitoringAnalyzer()
        errors: list = []
        result = analyzer._collect_transactions(engine, errors)

        assert result["active"] == 2
        assert result["idle_in_transaction"] == 1


# ── Test: Database size ──────────────────────────────────────────

class TestDatabaseSize:
    def test_collects_size(self):
        engine = _build_mock_connection({
            "pg_database_size": ("stackoverflow", 4123456789, "3.84 GB"),
        })
        warehouse = _make_mock_warehouse()
        analyzer = MonitoringAnalyzer()
        errors: list = []
        result = analyzer._collect_database_size(engine, warehouse, errors)

        assert result["name"] == "stackoverflow"
        assert result["size_bytes"] == 4123456789
        assert result["size_pretty"] == "3.84 GB"


# ── Test: Cache hit ratio ────────────────────────────────────────

class TestCacheHitRatio:
    def test_calculates_ratio(self):
        engine = _build_mock_connection({
            "pg_statio_user_tables": (9800, 200),  # 98% hit ratio
            "pg_stat_user_tables": (100, 50, 5000, 4000, 10, 10000),
        })
        analyzer = MonitoringAnalyzer()
        errors: list = []
        result = analyzer._collect_performance(engine, errors)

        assert result["cache_hit_ratio"] == 98.0

    def test_zero_total(self):
        engine = _build_mock_connection({
            "pg_statio_user_tables": (0, 0),
            "pg_stat_user_tables": (0, 0, 0, 0, 0, 0),
        })
        analyzer = MonitoringAnalyzer()
        errors: list = []
        result = analyzer._collect_performance(engine, errors)

        assert result["cache_hit_ratio"] == 0.0


# ── Test: Threshold evaluation ───────────────────────────────────

class TestThresholdEvaluation:
    @patch("app.warehouse.monitoring.settings")
    def test_high_connection_utilization(self, mock_settings):
        mock_settings.MONITORING_CONNECTION_CRITICAL_PERCENT = 90.0
        mock_settings.MONITORING_CONNECTION_WARNING_PERCENT = 75.0
        analyzer = MonitoringAnalyzer()

        connections = {"utilization_percent": 95.0, "current": 95, "maximum": 100}
        findings = analyzer._evaluate_findings(
            connections, {"running_count": 0}, {"count": 0}, {"waiting_count": 0},
            {"blocked_sessions": 0}, {"idle_in_transaction": 0},
            {}
        )

        assert any(f["severity"] == "HIGH" and "connection" in f["title"].lower() for f in findings)

    @patch("app.warehouse.monitoring.settings")
    def test_medium_connection_utilization(self, mock_settings):
        mock_settings.MONITORING_CONNECTION_CRITICAL_PERCENT = 90.0
        mock_settings.MONITORING_CONNECTION_WARNING_PERCENT = 75.0
        analyzer = MonitoringAnalyzer()

        connections = {"utilization_percent": 80.0, "current": 80, "maximum": 100}
        findings = analyzer._evaluate_findings(
            connections, {"running_count": 0}, {"count": 0}, {"waiting_count": 0},
            {"blocked_sessions": 0}, {"idle_in_transaction": 0},
            {}
        )

        assert any(f["severity"] == "MEDIUM" and "connection" in f["title"].lower() for f in findings)

    @patch("app.warehouse.monitoring.settings")
    def test_blocked_sessions_finding(self, mock_settings):
        mock_settings.MONITORING_CONNECTION_CRITICAL_PERCENT = 90.0
        mock_settings.MONITORING_CONNECTION_WARNING_PERCENT = 75.0
        analyzer = MonitoringAnalyzer()

        findings = analyzer._evaluate_findings(
            {"utilization_percent": 10.0}, {"running_count": 0}, {"count": 0},
            {"waiting_count": 0},
            {"blocked_sessions": 2, "blocking_sessions": 1},
            {"idle_in_transaction": 0},
            {}
        )

        assert any(f["severity"] == "HIGH" and "blocked" in f["title"].lower() for f in findings)

    @patch("app.warehouse.monitoring.settings")
    def test_long_running_finding(self, mock_settings):
        mock_settings.MONITORING_CONNECTION_CRITICAL_PERCENT = 90.0
        mock_settings.MONITORING_CONNECTION_WARNING_PERCENT = 75.0
        analyzer = MonitoringAnalyzer()

        findings = analyzer._evaluate_findings(
            {"utilization_percent": 10.0}, {"running_count": 1},
            {"count": 1, "threshold_seconds": 5, "longest_duration_seconds": 14.7},
            {"waiting_count": 0},
            {"blocked_sessions": 0}, {"idle_in_transaction": 0},
            {}
        )

        assert any(f["severity"] == "MEDIUM" and "long-running" in f["title"].lower() for f in findings)

    @patch("app.warehouse.monitoring.settings")
    def test_idle_in_transaction_finding(self, mock_settings):
        mock_settings.MONITORING_CONNECTION_CRITICAL_PERCENT = 90.0
        mock_settings.MONITORING_CONNECTION_WARNING_PERCENT = 75.0
        analyzer = MonitoringAnalyzer()

        findings = analyzer._evaluate_findings(
            {"utilization_percent": 10.0}, {"running_count": 0},
            {"count": 0},
            {"waiting_count": 0},
            {"blocked_sessions": 0},
            {"long_idle_in_transaction": 2, "idle_in_transaction_max_seconds": 60.0, "long_idle_threshold_seconds": 30},
            {}
        )

        assert any(f["severity"] == "MEDIUM" and "idle-in-transaction" in f["title"].lower() for f in findings)

    @patch("app.warehouse.monitoring.settings")
    def test_healthy_no_findings(self, mock_settings):
        mock_settings.MONITORING_CONNECTION_CRITICAL_PERCENT = 90.0
        mock_settings.MONITORING_CONNECTION_WARNING_PERCENT = 75.0
        analyzer = MonitoringAnalyzer()

        findings = analyzer._evaluate_findings(
            {"utilization_percent": 10.0}, {"running_count": 0},
            {"count": 0}, {"waiting_count": 0},
            {"blocked_sessions": 0}, {"idle_in_transaction": 0},
            {}
        )

        assert len(findings) == 0


# ── Test: Graceful degradation ───────────────────────────────────

class TestGracefulDegradation:
    @patch("app.warehouse.monitoring.WarehouseConnector")
    def test_partial_failure_still_produces_result(self, mock_connector_cls):
        """If one query fails, the rest still collect data."""
        mock_connector = MagicMock()

        call_count = {"n": 0}

        mock_conn = MagicMock()
        def fail_on_second(sql_text, params=None):
            call_count["n"] += 1
            if call_count["n"] == 3:
                raise Exception("pg_stat_activity unavailable")
            mock_result = MagicMock()
            mock_result.fetchone.return_value = ("100",)
            mock_result.fetchall.return_value = []
            return mock_result

        mock_conn.execute = fail_on_second
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        mock_engine.dispose = MagicMock()

        mock_connector.connect.return_value = mock_engine
        mock_connector_cls.return_value = mock_connector

        analyzer = MonitoringAnalyzer()
        analyzer._connector = mock_connector
        result = analyzer.analyse(_make_mock_warehouse())

        # The result should still contain all sections, just some with defaults
        assert "connections" in result
        assert "queries" in result
        assert "locks" in result
        assert "database" in result
        assert "summary" in result
        assert result["summary"]["partial_failure"] is True


# ── Test: Read-only safety ───────────────────────────────────────

class TestReadOnlySafety:
    def test_no_mutating_sql_in_source(self):
        """Verify the monitoring module contains no mutating SQL."""
        import inspect
        source = inspect.getsource(MonitoringAnalyzer)

        # These patterns should NOT appear in monitoring queries
        forbidden = [
            r'\bINSERT\b', r'\bUPDATE\b', r'\bDELETE\b',
            r'\bDROP\b', r'\bALTER\b', r'\bCREATE\b',
            r'\bTRUNCATE\b', r'\bpg_terminate_backend\b',
            r'\bpg_cancel_backend\b',
        ]

        for pattern in forbidden:
            # Only match in SQL strings, not in Python comments or variable names
            # Check that the pattern doesn't appear in text("...") blocks
            sql_blocks = re.findall(r'text\("""(.*?)"""\)', source, re.DOTALL)
            sql_blocks += re.findall(r"text\('(.*?)'\)", source, re.DOTALL)
            for sql in sql_blocks:
                assert not re.search(pattern, sql, re.IGNORECASE), \
                    f"Forbidden SQL pattern '{pattern}' found in monitoring query: {sql[:80]}..."


# ── Test: Progress events ────────────────────────────────────────

class TestProgressEvents:
    @patch("app.warehouse.monitoring.WarehouseConnector")
    def test_emits_progress(self, mock_connector_cls):
        mock_connector = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("100",)
        mock_result.fetchall.return_value = []
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        mock_engine.dispose = MagicMock()
        mock_connector.connect.return_value = mock_engine
        mock_connector_cls.return_value = mock_connector

        progress_calls: list = []
        def callback(msg, pct):
            progress_calls.append((msg, pct))

        analyzer = MonitoringAnalyzer()
        analyzer._connector = mock_connector
        analyzer.analyse(_make_mock_warehouse(), progress_callback=callback)

        # Should have at least 8 progress calls (one per section + findings)
        assert len(progress_calls) >= 8

        # First call should be 0%
        assert progress_calls[0][1] == 0

        # Last call should be 95%
        assert progress_calls[-1][1] == 95

        # Percentages should be non-decreasing
        pcts = [p[1] for p in progress_calls if p[1] is not None]
        assert pcts == sorted(pcts)
