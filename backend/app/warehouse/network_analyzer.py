"""
Network Monitoring Analyzer.

Evaluates raw network telemetry collected by SystemMonitor against
configured thresholds to produce actionable findings for network errors and drops.
"""

from typing import Any, Callable
from app.core.config import settings


class NetworkAnalyzer:
    """
    Analyzes host network I/O, error rates, and packet drops.
    """

    def analyze(
        self,
        network_data: dict[str, Any],
        progress_callback: Callable[[str, int | None], None] | None = None
    ) -> list[dict[str, Any]]:
        """
        Evaluate network telemetry against thresholds.
        
        Parameters
        ──────────
        network_data : dict[str, Any]
            Raw network metrics from SystemMonitor.
        progress_callback : Callable, optional
            Callback for SSE progress updates.
            
        Returns
        ───────
        list[dict[str, Any]]
            A list of findings (warnings).
        """
        findings = []
        if progress_callback:
            progress_callback("Evaluating network errors...", None)
            
        if not network_data or "error" in network_data:
            return findings

        # Check Aggregate Errors/Drops Deltas
        deltas = network_data.get("deltas")
        if deltas:
            errors_delta = deltas.get("errors_delta", 0)
            drops_delta = deltas.get("drops_delta", 0)
            
            error_threshold = settings.MONITORING_NETWORK_ERRORS_WARNING
            drop_threshold = settings.MONITORING_NETWORK_DROPS_WARNING
            
            # Identify which interfaces contributed to the errors/drops
            interfaces = network_data.get("interfaces", {})
            error_interfaces = []
            drop_interfaces = []
            
            for nic_name, nic_data in interfaces.items():
                nic_deltas = nic_data.get("deltas", {})
                if nic_deltas.get("errors_delta", 0) > 0:
                    error_interfaces.append(f"{nic_name} ({nic_deltas['errors_delta']})")
                if nic_deltas.get("drops_delta", 0) > 0:
                    drop_interfaces.append(f"{nic_name} ({nic_deltas['drops_delta']})")

            # Error Finding
            if errors_delta >= error_threshold:
                findings.append({
                    "title": "Network errors detected",
                    "category": "System Network",
                    "severity": "WARNING",
                    "description": (
                        f"Network error count increased by {errors_delta} during the monitoring interval."
                    ),
                    "evidence": {
                        "errors_delta": errors_delta,
                        "contributing_interfaces": error_interfaces,
                    },
                    "threshold": error_threshold,
                })
                
            if progress_callback:
                progress_callback("Evaluating packet drops...", None)

            # Drop Finding
            if drops_delta >= drop_threshold:
                findings.append({
                    "title": "Network packet drops detected",
                    "category": "System Network",
                    "severity": "WARNING",
                    "description": (
                        f"Network packet drops increased by {drops_delta} during the monitoring interval."
                    ),
                    "evidence": {
                        "drops_delta": drops_delta,
                        "contributing_interfaces": drop_interfaces,
                    },
                    "threshold": drop_threshold,
                })

        return findings
