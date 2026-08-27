"""
CPU Monitoring Analyzer.

Evaluates raw CPU telemetry collected by SystemMonitor against
configured thresholds to produce actionable findings.
"""

from typing import Any, Callable
from app.core.config import settings


class CPUAnalyzer:
    """
    Analyzes host CPU utilization and performance metrics.
    """

    def analyze(
        self,
        cpu_data: dict[str, Any],
        progress_callback: Callable[[str, int | None], None] | None = None
    ) -> list[dict[str, Any]]:
        """
        Evaluate CPU telemetry against thresholds.
        
        Parameters
        ──────────
        cpu_data : dict[str, Any]
            Raw CPU metrics from SystemMonitor (must contain 'utilization_percent').
        progress_callback : Callable, optional
            Callback for SSE progress updates.
            
        Returns
        ───────
        list[dict[str, Any]]
            A list of findings (warnings or critical alerts).
        """
        findings = []
        if progress_callback:
            progress_callback("Analyzing CPU utilization...", None)

        utilization = cpu_data.get("utilization_percent")
        if utilization is None:
            return findings

        high_pct = settings.MONITORING_CPU_CRITICAL_PERCENT
        warn_pct = settings.MONITORING_CPU_WARNING_PERCENT

        if utilization >= high_pct:
            findings.append({
                "title": "Critical CPU utilization",
                "category": "System CPU",
                "severity": "CRITICAL",
                "description": (
                    f"Host CPU utilization is at {utilization}%, "
                    f"exceeding the {high_pct}% critical threshold."
                ),
                "evidence": {
                    "utilization_percent": utilization,
                    "logical_cores": cpu_data.get("logical_cores"),
                },
                "threshold": high_pct,
            })
        elif utilization >= warn_pct:
            findings.append({
                "title": "Elevated CPU utilization",
                "category": "System CPU",
                "severity": "WARNING",
                "description": (
                    f"Host CPU utilization is at {utilization}%, "
                    f"exceeding the {warn_pct}% warning threshold."
                ),
                "evidence": {
                    "utilization_percent": utilization,
                    "logical_cores": cpu_data.get("logical_cores"),
                },
                "threshold": warn_pct,
            })

        return findings
