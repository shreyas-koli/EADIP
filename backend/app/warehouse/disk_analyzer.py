"""
Disk Monitoring Analyzer.

Evaluates raw disk telemetry collected by SystemMonitor against
configured thresholds to produce actionable findings for Disk Capacity
and Disk I/O.
"""

from typing import Any, Callable
from app.core.config import settings

def _format_bytes(size_bytes: float | None) -> str:
    """Helper to format bytes into readable GB string."""
    if size_bytes is None:
        return "Unknown"
    gb = size_bytes / (1024 ** 3)
    return f"{gb:.1f} GB"

def _format_mb(size_bytes: float | None) -> str:
    """Helper to format bytes into readable MB string."""
    if size_bytes is None:
        return "Unknown"
    mb = size_bytes / (1024 ** 2)
    return f"{mb:.1f} MB/s"

class DiskAnalyzer:
    """
    Analyzes host disk capacity and I/O metrics.
    """

    def analyze(
        self,
        disk_data: dict[str, Any],
        progress_callback: Callable[[str, int | None], None] | None = None
    ) -> list[dict[str, Any]]:
        """
        Evaluate disk telemetry against thresholds.
        
        Parameters
        ──────────
        disk_data : dict[str, Any]
            Raw disk metrics from SystemMonitor.
        progress_callback : Callable, optional
            Callback for SSE progress updates.
            
        Returns
        ───────
        list[dict[str, Any]]
            A list of findings (warnings or critical alerts).
        """
        findings = []
        if progress_callback:
            progress_callback("Analyzing disk capacity and I/O...", None)
            
        if not disk_data or "error" in disk_data:
            return findings

        # 1. Capacity Analysis
        constrained = disk_data.get("constrained_partition")
        if constrained:
            utilization = constrained.get("utilization_percent", 0)
            high_cap_pct = settings.MONITORING_DISK_CAPACITY_CRITICAL_PERCENT
            warn_cap_pct = settings.MONITORING_DISK_CAPACITY_WARNING_PERCENT
            
            used_gb = _format_bytes(constrained.get("used_bytes"))
            total_gb = _format_bytes(constrained.get("total_bytes"))
            mountpoint = constrained.get("mountpoint", "Unknown")

            if utilization >= high_cap_pct:
                findings.append({
                    "title": "Critical disk capacity",
                    "category": "System Disk",
                    "severity": "CRITICAL",
                    "description": (
                        f"Mount point '{mountpoint}' is at {utilization}% capacity "
                        f"({used_gb} / {total_gb}), "
                        f"exceeding the {high_cap_pct}% critical threshold."
                    ),
                    "evidence": {
                        "mountpoint": mountpoint,
                        "utilization_percent": utilization,
                        "used_bytes": constrained.get("used_bytes"),
                        "total_bytes": constrained.get("total_bytes"),
                    },
                    "threshold": high_cap_pct,
                })
            elif utilization >= warn_cap_pct:
                findings.append({
                    "title": "Elevated disk capacity",
                    "category": "System Disk",
                    "severity": "WARNING",
                    "description": (
                        f"Mount point '{mountpoint}' is at {utilization}% capacity "
                        f"({used_gb} / {total_gb}), "
                        f"exceeding the {warn_cap_pct}% warning threshold."
                    ),
                    "evidence": {
                        "mountpoint": mountpoint,
                        "utilization_percent": utilization,
                        "used_bytes": constrained.get("used_bytes"),
                        "total_bytes": constrained.get("total_bytes"),
                    },
                    "threshold": warn_cap_pct,
                })

        # 2. I/O Analysis
        io = disk_data.get("io")
        if io:
            read_bytes_sec = io.get("read_bytes_per_sec", 0)
            write_bytes_sec = io.get("write_bytes_per_sec", 0)
            
            read_mb_sec = read_bytes_sec / (1024 ** 2)
            write_mb_sec = write_bytes_sec / (1024 ** 2)
            
            read_warn_mb = settings.MONITORING_DISK_IO_READ_MB_S_WARNING
            write_warn_mb = settings.MONITORING_DISK_IO_WRITE_MB_S_WARNING

            if read_mb_sec >= read_warn_mb:
                findings.append({
                    "title": "High disk read I/O",
                    "category": "System Disk",
                    "severity": "WARNING",
                    "description": (
                        f"Disk read activity is at {_format_mb(read_bytes_sec)}, "
                        f"exceeding the {read_warn_mb} MB/s warning threshold."
                    ),
                    "evidence": {
                        "read_bytes_per_sec": read_bytes_sec,
                        "read_mb_per_sec": read_mb_sec,
                    },
                    "threshold": read_warn_mb,
                })
                
            if write_mb_sec >= write_warn_mb:
                findings.append({
                    "title": "High disk write I/O",
                    "category": "System Disk",
                    "severity": "WARNING",
                    "description": (
                        f"Disk write activity is at {_format_mb(write_bytes_sec)}, "
                        f"exceeding the {write_warn_mb} MB/s warning threshold."
                    ),
                    "evidence": {
                        "write_bytes_per_sec": write_bytes_sec,
                        "write_mb_per_sec": write_mb_sec,
                    },
                    "threshold": write_warn_mb,
                })

        return findings
