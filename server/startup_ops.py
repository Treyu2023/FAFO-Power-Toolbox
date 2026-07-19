"""Startup & Service Manager — boot items, services, scheduled tasks."""
from __future__ import annotations

import json
import os
import platform
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil

IS_WINDOWS = platform.system() == "Windows"
_CREATE_FLAGS = subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(cmd: list[str], timeout: float = 20) -> tuple[str, str, int]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=_CREATE_FLAGS, errors="replace")
        return p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired:
        return "", "timeout", 124


def list_startup_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    if IS_WINDOWS:
        startup_dirs = [
            ("User Startup", Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"),
            ("All Users Startup", Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"),
        ]
        for label, sdir in startup_dirs:
            if not sdir.is_dir():
                continue
            for f in sdir.iterdir():
                items.append({
                    "id": f"startup:{f}",
                    "category": "startup_folder",
                    "name": f.name,
                    "path": str(f),
                    "command": str(f),
                    "location": label,
                    "enabled": True,
                    "impact": "medium",
                })

        run_keys = [
            ("HKCU Run", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run"),
            ("HKLM Run", r"HKLM\Software\Microsoft\Windows\CurrentVersion\Run"),
            ("HKCU RunOnce", r"HKCU\Software\Microsoft\Windows\CurrentVersion\RunOnce"),
            ("HKLM RunOnce", r"HKLM\Software\Microsoft\Windows\CurrentVersion\RunOnce"),
        ]
        for label, key in run_keys:
            out, _, code = _run(["reg", "query", key])
            if code != 0:
                continue
            for line in out.splitlines():
                m = re.match(r"\s+(\S+)\s+REG_\w+\s+(.+)", line)
                if m:
                    name, val = m.group(1), m.group(2).strip()
                    items.append({
                        "id": f"reg:{key}\\{name}",
                        "category": "registry_run",
                        "name": name,
                        "path": f"{key}\\{name}",
                        "command": val,
                        "location": label,
                        "enabled": True,
                        "impact": "high",
                    })
    else:
        autostart = Path.home() / ".config" / "autostart"
        if autostart.is_dir():
            for f in autostart.glob("*.desktop"):
                items.append({
                    "id": f"startup:{f}",
                    "category": "autostart",
                    "name": f.stem,
                    "path": str(f),
                    "command": f.read_text(encoding="utf-8", errors="replace")[:200],
                    "location": "XDG autostart",
                    "enabled": True,
                    "impact": "medium",
                })

    return items


def list_scheduled_tasks() -> list[dict[str, Any]]:
    if not IS_WINDOWS:
        return []
    out, _, code = _run(["schtasks", "/Query", "/FO", "LIST", "/V"], timeout=60)
    if code != 0:
        return []

    tasks = []
    current: dict[str, str] = {}
    for line in out.splitlines():
        if not line.strip():
            if current.get("TaskName"):
                name = current["TaskName"]
                tasks.append({
                    "id": f"task:{name}",
                    "category": "scheduled_task",
                    "name": name,
                    "path": name,
                    "command": current.get("Task To Run", ""),
                    "location": current.get("Author", "Windows"),
                    "enabled": current.get("Status", "").lower() != "disabled",
                    "schedule": current.get("Schedule Type", ""),
                    "last_run": current.get("Last Run Time", ""),
                    "next_run": current.get("Next Run Time", ""),
                    "impact": "medium",
                })
            current = {}
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            current[k.strip()] = v.strip()
    return tasks


def list_services() -> list[dict[str, Any]]:
    services: list[dict[str, Any]] = []
    if IS_WINDOWS:
        out, _, code = _run([
            "powershell", "-NoProfile", "-Command",
            "Get-Service | Select-Object Name,DisplayName,Status,StartType | ConvertTo-Json -Compress",
        ], timeout=45)
        if code == 0 and out.strip():
            try:
                data = json.loads(out)
                if isinstance(data, dict):
                    data = [data]
                for svc in data:
                    name = svc.get("Name", "")
                    start = str(svc.get("StartType", "Manual"))
                    status = str(svc.get("Status", "Stopped"))
                    services.append({
                        "id": f"svc:{name}",
                        "category": "service",
                        "name": name,
                        "display_name": svc.get("DisplayName", name),
                        "path": name,
                        "state": status.upper(),
                        "start_type": start.upper().replace(" ", "_"),
                        "enabled": start.lower() != "disabled",
                        "running": status.lower() == "running",
                        "impact": "high" if start.lower() == "automatic" else "medium",
                    })
            except json.JSONDecodeError:
                pass
        if not services:
            out, _, _ = _run(["sc", "query", "type=", "service", "state=", "all"], timeout=30)
            blocks = re.split(r"\r?\n\r?\n", out)
            for block in blocks:
                name_m = re.search(r"SERVICE_NAME:\s+(.+)", block)
                if not name_m:
                    continue
                name = name_m.group(1).strip()
                state_m = re.search(r"STATE\s+:\s+\d+\s+(\w+)", block)
                disp_m = re.search(r"DISPLAY_NAME:\s+(.+)", block)
                state = state_m.group(1) if state_m else "UNKNOWN"
                services.append({
                    "id": f"svc:{name}",
                    "category": "service",
                    "name": name,
                    "display_name": disp_m.group(1).strip() if disp_m else name,
                    "path": name,
                    "state": state,
                    "start_type": "UNKNOWN",
                    "enabled": True,
                    "running": state == "RUNNING",
                    "impact": "medium",
                })
    services.sort(key=lambda s: (not s.get("running"), s["name"].lower()))
    return services


def get_overview() -> dict[str, Any]:
    startup = list_startup_items()
    tasks = list_scheduled_tasks()
    services = list_services()
    return {
        "timestamp": _utc_now(),
        "startup_count": len(startup),
        "task_count": len(tasks),
        "service_count": len(services),
        "running_services": sum(1 for s in services if s.get("running")),
        "auto_services": sum(1 for s in services if s.get("start_type") in ("AUTO_START", "AUTOMATIC")),
        "startup": startup,
        "tasks": tasks[:200],
        "services": services,
    }


def disable_item(item_id: str) -> dict[str, Any]:
    if item_id.startswith("reg:"):
        path = item_id[4:]
        out, err, code = _run(["reg", "delete", path, "/f"])
        return {"ok": code == 0, "action": "delete_registry", "detail": out or err}
    if item_id.startswith("task:"):
        name = item_id[5:]
        out, err, code = _run(["schtasks", "/Change", "/TN", name, "/DISABLE"])
        return {"ok": code == 0, "action": "disable_task", "detail": out or err}
    if item_id.startswith("svc:"):
        name = item_id[4:]
        _run(["sc", "stop", name], timeout=15)
        out, err, code = _run(["sc", "config", name, "start=", "disabled"])
        return {"ok": code == 0, "action": "disable_service", "detail": out or err}
    if item_id.startswith("startup:"):
        path = Path(item_id[8:])
        if path.exists():
            backup = path.with_suffix(path.suffix + ".disabled")
            path.rename(backup)
            return {"ok": True, "action": "rename_disabled", "backup": str(backup)}
    return {"ok": False, "error": "Unknown item or unsupported action"}


def enable_item(item_id: str) -> dict[str, Any]:
    if item_id.startswith("task:"):
        name = item_id[5:]
        out, err, code = _run(["schtasks", "/Change", "/TN", name, "/ENABLE"])
        return {"ok": code == 0, "action": "enable_task", "detail": out or err}
    if item_id.startswith("svc:"):
        name = item_id[4:]
        out, err, code = _run(["sc", "config", name, "start=", "auto"])
        return {"ok": code == 0, "action": "enable_service", "detail": out or err}
    return {"ok": False, "error": "Enable not supported for this item type"}