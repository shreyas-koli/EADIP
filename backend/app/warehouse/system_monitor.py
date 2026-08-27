"""
System monitoring foundation.

Provides platform-independent host telemetry (CPU, memory, disk, network)
using psutil. Future steps will expand this to deep-analyze these metrics
and integrate with PostgreSQL process metrics.
"""

from typing import Any
import psutil

class SystemMonitor:
    """
    Collects foundational host and system telemetry.
    
    This class is responsible ONLY for collecting data structures.
    Deep analysis, threshold evaluation, and finding generation will
    be implemented in subsequent steps.
    """

    def __init__(self) -> None:
        """Initialize the system monitor."""
        pass

    def collect_system_metrics(self) -> dict[str, Any]:
        """
        Collect foundational system metrics.
        
        Returns
        ───────
        dict[str, Any]
            A structured payload containing raw CPU, memory, disk, 
            network, and system information.
        """
        return {
            "system": self._get_system_info(),
            "cpu": self._get_cpu_info(),
            "memory": self._get_memory_info(),
            "disk": self._get_disk_info(),
            "network": self._get_network_info(),
            "process": self._get_process_info(),
            "findings": [],
            "errors": []
        }

    def _get_system_info(self) -> dict[str, Any]:
        """Return basic system and boot information."""
        try:
            return {
                "boot_time": psutil.boot_time()
            }
        except Exception as e:
            return {"error": str(e)}

    def _get_cpu_info(self) -> dict[str, Any]:
        """Return basic CPU hardware information and utilization metrics."""
        try:
            # We use a short interval for a quick snapshot.
            # In a real environment, you might use background threads or non-blocking calls.
            cpu_percent = psutil.cpu_percent(interval=0.1)
            freq = psutil.cpu_freq()
            return {
                "physical_cores": psutil.cpu_count(logical=False),
                "logical_cores": psutil.cpu_count(logical=True),
                "utilization_percent": cpu_percent,
                "frequency_mhz": freq.current if freq else None,
            }
        except Exception as e:
            return {"error": str(e)}

    def _get_memory_info(self) -> dict[str, Any]:
        """Return basic memory hardware information and utilization."""
        try:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            return {
                "total_bytes": mem.total,
                "available_bytes": mem.available,
                "used_bytes": mem.used,
                "utilization_percent": mem.percent,
                "swap_total_bytes": swap.total,
                "swap_used_bytes": swap.used,
                "swap_utilization_percent": swap.percent,
            }
        except Exception as e:
            return {"error": str(e)}

    def _get_disk_info(self) -> dict[str, Any]:
        """Return basic disk hardware information, capacity, and IO."""
        try:
            import time
            partitions = psutil.disk_partitions(all=False)
            
            # 1. Capacity Analysis
            # Track the most constrained partition (highest utilization)
            max_utilization = -1.0
            constrained_partition = None
            constrained_usage = None
            
            partition_data = []
            for p in partitions:
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    if usage.percent > max_utilization:
                        max_utilization = usage.percent
                        constrained_partition = p.mountpoint
                        constrained_usage = usage
                    
                    partition_data.append({
                        "device": p.device,
                        "mountpoint": p.mountpoint,
                        "total_bytes": usage.total,
                        "used_bytes": usage.used,
                        "free_bytes": usage.free,
                        "utilization_percent": usage.percent
                    })
                except Exception:
                    # Ignore partitions that might not be readable
                    pass

            # 2. Disk I/O Activity
            # Take a rapid snapshot to determine current MB/s
            io1 = psutil.disk_io_counters()
            time.sleep(0.1)
            io2 = psutil.disk_io_counters()
            
            read_bytes_sec = 0.0
            write_bytes_sec = 0.0
            
            if io1 and io2:
                read_bytes_sec = (io2.read_bytes - io1.read_bytes) / 0.1
                write_bytes_sec = (io2.write_bytes - io1.write_bytes) / 0.1

            return {
                "partitions": partition_data,
                "constrained_partition": {
                    "mountpoint": constrained_partition,
                    "utilization_percent": max_utilization,
                    "total_bytes": constrained_usage.total if constrained_usage else 0,
                    "used_bytes": constrained_usage.used if constrained_usage else 0,
                    "free_bytes": constrained_usage.free if constrained_usage else 0,
                } if constrained_partition else None,
                "io": {
                    "read_bytes_per_sec": read_bytes_sec,
                    "write_bytes_per_sec": write_bytes_sec,
                }
            }
        except Exception as e:
            return {"error": str(e)}

    def _get_network_info(self) -> dict[str, Any]:
        """Return aggregate and per-interface network information."""
        try:
            import time
            
            # Snapshot 1
            agg1 = psutil.net_io_counters(pernic=False)
            nic1 = psutil.net_io_counters(pernic=True)
            
            # Short sleep to get a differential (rate and error/drop delta)
            time.sleep(0.1)
            
            # Snapshot 2
            agg2 = psutil.net_io_counters(pernic=False)
            nic2 = psutil.net_io_counters(pernic=True)
            
            # Aggregate deltas/rates
            agg_recv_rate = None
            agg_sent_rate = None
            agg_errors_delta = 0
            agg_drops_delta = 0
            
            if agg1 and agg2:
                # If counters didn't reset
                if agg2.bytes_recv >= agg1.bytes_recv:
                    agg_recv_rate = (agg2.bytes_recv - agg1.bytes_recv) / 0.1
                if agg2.bytes_sent >= agg1.bytes_sent:
                    agg_sent_rate = (agg2.bytes_sent - agg1.bytes_sent) / 0.1
                    
                agg_errors_delta = max(0, (agg2.errin + agg2.errout) - (agg1.errin + agg1.errout))
                agg_drops_delta = max(0, (agg2.dropin + agg2.dropout) - (agg1.dropin + agg1.dropout))

            aggregate_data = {
                "bytes_sent": agg2.bytes_sent,
                "bytes_recv": agg2.bytes_recv,
                "packets_sent": agg2.packets_sent,
                "packets_recv": agg2.packets_recv,
                "errors_in": agg2.errin,
                "errors_out": agg2.errout,
                "drops_in": agg2.dropin,
                "drops_out": agg2.dropout,
            } if agg2 else None

            # Per-interface data
            interfaces_data = {}
            if nic2:
                for nic_name, stats2 in nic2.items():
                    stats1 = nic1.get(nic_name)
                    
                    recv_rate = None
                    sent_rate = None
                    errors_delta = 0
                    drops_delta = 0
                    
                    if stats1:
                        if stats2.bytes_recv >= stats1.bytes_recv:
                            recv_rate = (stats2.bytes_recv - stats1.bytes_recv) / 0.1
                        if stats2.bytes_sent >= stats1.bytes_sent:
                            sent_rate = (stats2.bytes_sent - stats1.bytes_sent) / 0.1
                            
                        errors_delta = max(0, (stats2.errin + stats2.errout) - (stats1.errin + stats1.errout))
                        drops_delta = max(0, (stats2.dropin + stats2.dropout) - (stats1.dropin + stats1.dropout))
                        
                    interfaces_data[nic_name] = {
                        "bytes_sent": stats2.bytes_sent,
                        "bytes_recv": stats2.bytes_recv,
                        "packets_sent": stats2.packets_sent,
                        "packets_recv": stats2.packets_recv,
                        "errors_in": stats2.errin,
                        "errors_out": stats2.errout,
                        "drops_in": stats2.dropin,
                        "drops_out": stats2.dropout,
                        "rates": {
                            "recv_bytes_per_sec": recv_rate,
                            "sent_bytes_per_sec": sent_rate,
                        },
                        "deltas": {
                            "errors_delta": errors_delta,
                            "drops_delta": drops_delta,
                        }
                    }

            return {
                "aggregate": aggregate_data,
                "interfaces": interfaces_data,
                "rates": {
                    "recv_bytes_per_sec": agg_recv_rate,
                    "sent_bytes_per_sec": agg_sent_rate,
                },
                "deltas": {
                    "errors_delta": agg_errors_delta,
                    "drops_delta": agg_drops_delta,
                }
            }
        except Exception as e:
            return {"error": str(e)}

    def _get_process_info(self) -> dict[str, Any]:
        """Return foundational PostgreSQL process structures."""
        # Future implementation will track specific PG process trees
        return {
            "pids_tracked": 0
        }
