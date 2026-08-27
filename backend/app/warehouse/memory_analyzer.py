"""
Memory Monitoring Analyzer.

Evaluates raw memory telemetry collected by SystemMonitor against
configured thresholds to produce actionable findings for RAM and swap.
"""

from typing import Any, Callable
from app.core.config import settings

def _format_bytes(size_bytes: int | None) -> str:
    """Helper to format bytes into readable GB string."""
    if size_bytes is None:
        return "Unknown"
    gb = size_bytes / (1024 ** 3)
    return f"{gb:.1f} GB"

class MemoryAnalyzer:
    """
    Analyzes host memory and swap utilization metrics.
    """

    def analyze(
        self,
        memory_data: dict[str, Any],
        progress_callback: Callable[[str, int | None], None] | None = None
    ) -> list[dict[str, Any]]:
        """
        Evaluate memory and swap telemetry against thresholds.
        
        Parameters
        ──────────
        memory_data : dict[str, Any]
            Raw memory metrics from SystemMonitor.
        progress_callback : Callable, optional
            Callback for SSE progress updates.
            
        Returns
        ───────
        list[dict[str, Any]]
            A list of findings (warnings or critical alerts).
        """
        findings = []
        if progress_callback:
            progress_callback("Analyzing memory and swap utilization...", None)

        mem_utilization = memory_data.get("utilization_percent")
        swap_utilization = memory_data.get("swap_utilization_percent")
        
        mem_used_gb = _format_bytes(memory_data.get("used_bytes"))
        mem_total_gb = _format_bytes(memory_data.get("total_bytes"))
        swap_used_gb = _format_bytes(memory_data.get("swap_used_bytes"))
        swap_total_gb = _format_bytes(memory_data.get("swap_total_bytes"))

        # RAM Analysis
        if mem_utilization is not None:
            high_mem_pct = settings.MONITORING_MEMORY_CRITICAL_PERCENT
            warn_mem_pct = settings.MONITORING_MEMORY_WARNING_PERCENT

            if mem_utilization >= high_mem_pct:
                findings.append({
                    "title": "Critical memory utilization",
                    "category": "System Memory",
                    "severity": "CRITICAL",
                    "description": (
                        f"Host memory utilization is at {mem_utilization}% "
                        f"({mem_used_gb} / {mem_total_gb}), "
                        f"exceeding the {high_mem_pct}% critical threshold."
                    ),
                    "evidence": {
                        "utilization_percent": mem_utilization,
                        "used_bytes": memory_data.get("used_bytes"),
                        "total_bytes": memory_data.get("total_bytes"),
                    },
                    "threshold": high_mem_pct,
                })
            elif mem_utilization >= warn_mem_pct:
                findings.append({
                    "title": "Elevated memory utilization",
                    "category": "System Memory",
                    "severity": "WARNING",
                    "description": (
                        f"Host memory utilization is at {mem_utilization}% "
                        f"({mem_used_gb} / {mem_total_gb}), "
                        f"exceeding the {warn_mem_pct}% warning threshold."
                    ),
                    "evidence": {
                        "utilization_percent": mem_utilization,
                        "used_bytes": memory_data.get("used_bytes"),
                        "total_bytes": memory_data.get("total_bytes"),
                    },
                    "threshold": warn_mem_pct,
                })

        # Swap Analysis
        if swap_utilization is not None and memory_data.get("swap_total_bytes", 0) > 0:
            high_swap_pct = settings.MONITORING_SWAP_CRITICAL_PERCENT
            warn_swap_pct = settings.MONITORING_SWAP_WARNING_PERCENT

            if swap_utilization >= high_swap_pct:
                findings.append({
                    "title": "Critical swap utilization",
                    "category": "System Memory",
                    "severity": "CRITICAL",
                    "description": (
                        f"Host swap utilization is at {swap_utilization}% "
                        f"({swap_used_gb} / {swap_total_gb}), "
                        f"exceeding the {high_swap_pct}% critical threshold. "
                        f"This may indicate severe memory pressure and disk thrashing."
                    ),
                    "evidence": {
                        "swap_utilization_percent": swap_utilization,
                        "swap_used_bytes": memory_data.get("swap_used_bytes"),
                        "swap_total_bytes": memory_data.get("swap_total_bytes"),
                    },
                    "threshold": high_swap_pct,
                })
            elif swap_utilization >= warn_swap_pct:
                findings.append({
                    "title": "Elevated swap utilization",
                    "category": "System Memory",
                    "severity": "WARNING",
                    "description": (
                        f"Host swap utilization is at {swap_utilization}% "
                        f"({swap_used_gb} / {swap_total_gb}), "
                        f"exceeding the {warn_swap_pct}% warning threshold."
                    ),
                    "evidence": {
                        "swap_utilization_percent": swap_utilization,
                        "swap_used_bytes": memory_data.get("swap_used_bytes"),
                        "swap_total_bytes": memory_data.get("swap_total_bytes"),
                    },
                    "threshold": warn_swap_pct,
                })

        return findings
