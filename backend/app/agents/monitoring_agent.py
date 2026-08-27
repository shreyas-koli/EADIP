"""
Monitoring agent coordination layer.

Responsible for coordinating PostgreSQL runtime-state monitoring
and writing results to the shared context memory bus.

No LLM calls, no database writes, no HTTP concerns.
"""

from typing import Any

from app.models.warehouse import Warehouse
from app.context.shared_context import SharedContext
from app.core.config import settings
from app.warehouse.monitoring import MonitoringAnalyzer
from app.warehouse.system_monitor import SystemMonitor
from app.warehouse.cpu_analyzer import CPUAnalyzer
from app.warehouse.memory_analyzer import MemoryAnalyzer
from app.warehouse.disk_analyzer import DiskAnalyzer
from app.warehouse.network_analyzer import NetworkAnalyzer
from app.warehouse.process_monitor import ProcessMonitor
from app.warehouse.process_analyzer import ProcessAnalyzer


class MonitoringAgent:
    """
    A thin coordination layer for executing PostgreSQL runtime
    monitoring.

    Delegates all monitoring queries and threshold evaluation to
    the ``MonitoringAnalyzer`` and pushes the results into the
    ``SharedContext`` registry for downstream agents.
    """

    def __init__(self) -> None:
        """Initialize the agent with its underlying analyzer."""
        self._analyzer = MonitoringAnalyzer()
        self._system_monitor = SystemMonitor()
        self._cpu_analyzer = CPUAnalyzer()
        self._memory_analyzer = MemoryAnalyzer()
        self._disk_analyzer = DiskAnalyzer()
        self._network_analyzer = NetworkAnalyzer()
        self._process_monitor = ProcessMonitor()
        self._process_analyzer = ProcessAnalyzer()

    def collect_monitoring_data(self, warehouse: Warehouse, context: SharedContext) -> dict[str, Any]:
        """
        Collect current PostgreSQL runtime state metrics.

        Parameters
        ──────────
        warehouse : Warehouse
            A registered ``Warehouse`` ORM instance.
        context : SharedContext
            The shared memory bus for inter-agent communication.

        Returns
        ───────
        dict[str, Any]
            The monitoring result containing connections, queries,
            locks, transactions, database size, performance
            indicators, and findings.
        """
        context.emit_agent_progress("monitoring", "Connecting to PostgreSQL...", 0)

        def _progress(msg: str, pct: int | None = None) -> None:
            context.emit_agent_progress("monitoring", msg, pct)

        monitoring_result = self._analyzer.analyse(warehouse, progress_callback=_progress)

        _progress("Collecting host telemetry...", 90)
        sys_metrics = self._system_monitor.collect_system_metrics()
        
        cpu_findings = self._cpu_analyzer.analyze(sys_metrics["cpu"], progress_callback=_progress)
        mem_findings = self._memory_analyzer.analyze(sys_metrics["memory"], progress_callback=_progress)
        disk_findings = self._disk_analyzer.analyze(sys_metrics["disk"], progress_callback=_progress)
        net_findings = self._network_analyzer.analyze(sys_metrics["network"], progress_callback=_progress)
        
        _progress("Collecting PostgreSQL OS process telemetry...", 93)
        process_metrics = self._process_monitor.collect_process_metrics(warehouse)
        process_findings = self._process_analyzer.analyze(process_metrics, progress_callback=_progress)
        
        # Merge system metrics
        monitoring_result["system"] = sys_metrics
        monitoring_result["system"]["pg_processes"] = process_metrics
        
        # Combine host findings
        host_findings = []
        if cpu_findings:
            host_findings.extend(cpu_findings)
        if mem_findings:
            host_findings.extend(mem_findings)
        if disk_findings:
            host_findings.extend(disk_findings)
        if net_findings:
            host_findings.extend(net_findings)
        if process_findings:
            host_findings.extend(process_findings)
            
        # Combine host errors into global errors
        host_errors = sys_metrics.pop("errors", [])
        if process_metrics.get("errors"):
            host_errors.extend(process_metrics.get("errors", []))
            
        if host_errors:
            monitoring_result["errors"].extend(host_errors)
            
        # Remove redundant keys from system metrics
        sys_metrics.pop("findings", None)
        sys_metrics.pop("process", None) # Replaced by pg_processes
            
        # Correlations
        host_cpu = sys_metrics.get("cpu", {}).get("utilization_percent", 0)
        pg_cpu = process_metrics.get("aggregate", {}).get("total_cpu_percent", 0)
        
        if host_cpu >= settings.MONITORING_CPU_WARNING_PERCENT and pg_cpu >= settings.MONITORING_PROCESS_CPU_WARNING_PERCENT:
            correlation = {
                "title": "PostgreSQL contributes to high host CPU",
                "category": "Correlation",
                "severity": "WARNING",
                "description": "High PostgreSQL process CPU coincides with high host CPU usage.",
                "evidence": {
                    "host_cpu_percent": host_cpu,
                    "pg_processes_cpu_percent": pg_cpu
                },
                "threshold": settings.MONITORING_CPU_WARNING_PERCENT
            }
            host_findings.append(correlation)
            
        host_mem_util = sys_metrics.get("memory", {}).get("utilization_percent", 0)
        pg_mem_bytes = process_metrics.get("aggregate", {}).get("total_memory_rss_bytes", 0)
        pg_mem_mb = pg_mem_bytes / (1024 ** 2)
        
        if host_mem_util >= settings.MONITORING_MEMORY_WARNING_PERCENT and pg_mem_mb >= settings.MONITORING_PROCESS_MEMORY_WARNING_MB:
            correlation = {
                "title": "PostgreSQL contributes to elevated host memory",
                "category": "Correlation",
                "severity": "WARNING",
                "description": "Elevated PostgreSQL processes memory coincides with elevated host memory usage.",
                "evidence": {
                    "host_memory_percent": host_mem_util,
                    "pg_processes_memory_mb": pg_mem_mb
                },
                "threshold": settings.MONITORING_PROCESS_MEMORY_WARNING_MB
            }
            host_findings.append(correlation)
            
        # Merge combined findings
        if host_findings:
            monitoring_result["findings"].extend(host_findings)
            
            # Recalculate summary strictly across ALL findings
            high = 0
            medium = 0
            low = 0
            for finding in monitoring_result["findings"]:
                severity = finding["severity"]
                if severity == "CRITICAL":
                    high += 1
                elif severity == "WARNING":
                    medium += 1
                elif severity == "INFO":
                    low += 1
                    
            monitoring_result["summary"]["high_findings"] = high
            monitoring_result["summary"]["medium_findings"] = medium
            monitoring_result["summary"]["low_findings"] = low
            monitoring_result["summary"]["finding_count"] = len(monitoring_result["findings"])
            
            # Re-evaluate overall health
            if high > 0:
                monitoring_result["summary"]["health_status"] = "CRITICAL"
            elif medium > 0:
                monitoring_result["summary"]["health_status"] = "WARNING"
                
        # Partial failure handling
        if monitoring_result["errors"]:
            monitoring_result["summary"]["partial_failure"] = True

        context.emit_agent_progress("monitoring", "Monitoring analysis completed.", 100)

        context.set_agent_result(
            "monitoring",
            monitoring_result,
        )

        return monitoring_result
