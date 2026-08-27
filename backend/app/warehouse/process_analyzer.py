"""
PostgreSQL Process Monitoring Analyzer.

Evaluates OS-level telemetry collected by ProcessMonitor for PostgreSQL PIDs
against configured thresholds to produce actionable findings.
"""

from typing import Any, Callable
from app.core.config import settings

def _format_mb(size_bytes: float | None) -> str:
    """Helper to format bytes into readable MB string."""
    if size_bytes is None:
        return "Unknown"
    mb = size_bytes / (1024 ** 2)
    return f"{mb:.1f} MB"

class ProcessAnalyzer:
    """
    Analyzes PostgreSQL OS process metrics (CPU and Memory).
    """

    def analyze(
        self,
        process_data: dict[str, Any],
        progress_callback: Callable[[str, int | None], None] | None = None
    ) -> list[dict[str, Any]]:
        """
        Evaluate process telemetry against thresholds.
        
        Parameters
        ──────────
        process_data : dict[str, Any]
            OS process metrics from ProcessMonitor.
        progress_callback : Callable, optional
            Callback for SSE progress updates.
            
        Returns
        ───────
        list[dict[str, Any]]
            A list of findings (warnings).
        """
        findings = []
        if progress_callback:
            progress_callback("Analyzing PostgreSQL OS processes...", None)
            
        if not process_data or "error" in process_data or not process_data.get("pids_tracked"):
            return findings

        # Configured Thresholds
        cpu_warn_pct = settings.MONITORING_PROCESS_CPU_WARNING_PERCENT
        mem_warn_mb = settings.MONITORING_PROCESS_MEMORY_WARNING_MB
        
        # Analyze aggregate
        agg = process_data.get("aggregate", {})
        agg_cpu = agg.get("total_cpu_percent", 0.0)
        agg_mem = agg.get("total_memory_rss_bytes", 0)
        agg_mem_mb = agg_mem / (1024 ** 2)
        
        # We could generate a warning if the aggregate CPU is very high, 
        # but the prompt implies checking OS resources. We'll check individual PIDs
        # and generate warnings if ANY backend is consuming excessive CPU/Memory.
        # This keeps it consistent with checking specific process consumption.
        
        high_cpu_pids = []
        high_mem_pids = []
        
        processes = process_data.get("processes", [])
        for p in processes:
            pid = p.get("pid")
            cpu = p.get("cpu_percent", 0.0)
            mem_rss = p.get("memory_rss_bytes", 0)
            mem_mb = mem_rss / (1024 ** 2)
            
            if cpu >= cpu_warn_pct:
                high_cpu_pids.append(f"PID {pid} ({cpu:.1f}%)")
                
            if mem_mb >= mem_warn_mb:
                high_mem_pids.append(f"PID {pid} ({_format_mb(mem_rss)})")

        if high_cpu_pids:
            findings.append({
                "title": "High PostgreSQL process CPU",
                "category": "System Process",
                "severity": "WARNING",
                "description": (
                    f"{len(high_cpu_pids)} PostgreSQL backend(s) are exceeding the "
                    f"{cpu_warn_pct}% CPU warning threshold."
                ),
                "evidence": {
                    "high_cpu_processes": high_cpu_pids,
                    "aggregate_pg_cpu_percent": agg_cpu,
                },
                "threshold": cpu_warn_pct,
            })
            
        if high_mem_pids:
            findings.append({
                "title": "High PostgreSQL process Memory",
                "category": "System Process",
                "severity": "WARNING",
                "description": (
                    f"{len(high_mem_pids)} PostgreSQL backend(s) are exceeding the "
                    f"{mem_warn_mb} MB memory warning threshold."
                ),
                "evidence": {
                    "high_memory_processes": high_mem_pids,
                    "aggregate_pg_memory_rss_bytes": agg_mem,
                },
                "threshold": mem_warn_mb,
            })

        return findings
