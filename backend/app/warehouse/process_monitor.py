"""
PostgreSQL OS-Level Process Monitor.

Collects OS-level resource consumption metrics (CPU, Memory, status)
for active PostgreSQL backend processes using psutil, matching them
via PIDs obtained from pg_stat_activity.
"""

import logging
import psutil
from typing import Any
from sqlalchemy import text
from app.models.warehouse import Warehouse
from app.warehouse.connector import WarehouseConnector

logger = logging.getLogger(__name__)

class ProcessMonitor:
    """
    Collects OS telemetry for PostgreSQL backend processes.
    """

    def __init__(self) -> None:
        self._connector = WarehouseConnector()

    def collect_process_metrics(self, warehouse: Warehouse) -> dict[str, Any]:
        """
        Collect OS metrics for PostgreSQL PIDs.
        
        Returns
        ───────
        dict[str, Any]
            OS telemetry for the processes.
        """
        pids = []
        errors = []
        
        # 1. Fetch backend PIDs from PostgreSQL
        try:
            engine = self._connector.connect(warehouse)
            with engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT pid, state, datname, usename 
                    FROM pg_stat_activity 
                    WHERE backend_type = 'client backend'
                """)).fetchall()
                for r in rows:
                    pids.append({
                        "pid": r[0],
                        "state": r[1],
                        "database": r[2],
                        "user": r[3]
                    })
            engine.dispose()
        except Exception as exc:
            logger.warning(f"ProcessMonitor: Failed to fetch PIDs from pg_stat_activity: {exc}")
            errors.append({"step": "fetch_pids", "error": str(exc)})
            return {"pids_tracked": 0, "processes": [], "aggregate": {}, "errors": errors}

        # 2. Collect OS metrics via psutil
        process_data = []
        total_cpu_percent = 0.0
        total_memory_rss = 0
        total_memory_vms = 0
        
        for p_info in pids:
            pid = p_info["pid"]
            try:
                # In Windows, PID could be reused or not accessible if not running on the same host.
                # psutil.Process will raise NoSuchProcess if PID doesn't exist, 
                # or AccessDenied if lack of permissions.
                proc = psutil.Process(pid)
                
                # Retrieve metrics safely
                cpu_percent = proc.cpu_percent(interval=0.0) # non-blocking first call
                mem_info = proc.memory_info()
                status = proc.status()
                create_time = proc.create_time()
                
                process_data.append({
                    "pid": pid,
                    "db_state": p_info["state"],
                    "database": p_info["database"],
                    "user": p_info["user"],
                    "os_status": status,
                    "cpu_percent": cpu_percent,
                    "memory_rss_bytes": mem_info.rss,
                    "memory_vms_bytes": mem_info.vms,
                    "create_time": create_time
                })
                
                total_cpu_percent += cpu_percent
                total_memory_rss += mem_info.rss
                total_memory_vms += mem_info.vms
                
            except psutil.NoSuchProcess:
                # Process terminated between pg_stat_activity and psutil
                pass
            except psutil.AccessDenied:
                # We lack OS permissions to read this PID
                pass
            except Exception as e:
                logger.debug(f"ProcessMonitor: Unexpected error reading PID {pid}: {e}")
                
        aggregate = {
            "total_cpu_percent": total_cpu_percent,
            "total_memory_rss_bytes": total_memory_rss,
            "total_memory_vms_bytes": total_memory_vms,
        }
        
        return {
            "pids_tracked": len(process_data),
            "processes": process_data,
            "aggregate": aggregate,
            "errors": errors
        }
