"""System Health Dashboard — aggregates toolbox system metrics."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import disk_ops as disk
import network_ops as net
import security_scan as sec
import startup_ops as startup


def get_dashboard() -> dict[str, Any]:
    overview = net.get_system_overview()
    intel = sec.get_intel_status()
    disks = disk.get_overview()
    boot = startup.get_overview()

    issues = []
    if overview["cpu"]["percent"] > 85:
        issues.append({"level": "warn", "message": f"High CPU: {overview['cpu']['percent']}%", "source": "system"})
    if overview["memory"]["percent"] > 90:
        issues.append({"level": "warn", "message": f"High memory: {overview['memory']['percent']}%", "source": "system"})
    for d in disks.get("drives", []):
        if d["percent"] > 90:
            issues.append({"level": "warn", "message": f"Low disk space on {d['mount']}: {d['percent']}% used", "source": "disk"})
    if intel.get("total_hashes", 0) == 0:
        issues.append({"level": "info", "message": "Threat database not updated — run Malware Defender scan", "source": "security"})
    if boot.get("auto_services", 0) > 80:
        issues.append({"level": "info", "message": f"{boot['auto_services']} auto-start services — review Startup Manager", "source": "startup"})

    quarantine = sec.list_quarantine()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "healthy": not any(i["level"] == "error" for i in issues),
        "issues": issues,
        "system": {
            "hostname": overview["hostname"],
            "cpu_percent": overview["cpu"]["percent"],
            "memory_percent": overview["memory"]["percent"],
            "memory_used_human": overview["memory"]["used_human"],
            "disk_percent": overview["disk"]["percent"],
            "process_count": overview["process_count"],
            "net_send_human": overview["network"]["send_rate_human"],
            "net_recv_human": overview["network"]["recv_rate_human"],
        },
        "security": {
            "threat_hashes": intel.get("total_hashes", 0),
            "last_intel_update": intel.get("last_update"),
            "quarantine_count": len(quarantine),
        },
        "disk": {
            "drives": disks.get("drives", []),
            "top_user_folders": disks.get("user_folders", [])[:5],
        },
        "startup": {
            "startup_items": boot.get("startup_count", 0),
            "scheduled_tasks": boot.get("task_count", 0),
            "services": boot.get("service_count", 0),
            "running_services": boot.get("running_services", 0),
            "auto_services": boot.get("auto_services", 0),
        },
    }