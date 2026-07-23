"""
Comprehensive PC diagnostics for the AI HTML Toolbox HUD.

Collects hardware/software identity in plain English, flags bottlenecks,
compatibility notes, and actionable suggestions. Results are device-local
under %LOCALAPPDATA%\\FAFO\\Devices\\<hostname>\\Reports\\PC\\.
"""
from __future__ import annotations

import json
import os
import platform
import re
import socket
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import psutil

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "VERSION"

# Default scan modules (UI checkboxes map to these keys)
DEFAULT_OPTIONS: dict[str, bool] = {
    "identity": True,
    "cpu": True,
    "memory": True,
    "gpu": True,
    "storage": True,
    "network": True,
    "power": True,
    "problem_devices": True,
    "event_log": True,
    "startup": True,
    "security_overview": True,
    "compatibility": True,
    "bottlenecks": True,
    "friendly_summaries": True,
}

OPTION_META = [
    {"id": "identity", "label": "PC identity & OS", "desc": "Name, brand, Windows version, uptime"},
    {"id": "cpu", "label": "Processor", "desc": "CPU model, cores, current load"},
    {"id": "memory", "label": "Memory (RAM)", "desc": "Capacity, free space, stick summary"},
    {"id": "gpu", "label": "Graphics", "desc": "GPU name(s), drivers, status"},
    {"id": "storage", "label": "Storage & drives", "desc": "Disks, free space, health signals"},
    {"id": "network", "label": "Network adapters", "desc": "Wi‑Fi / Ethernet links in plain English"},
    {"id": "power", "label": "Power plan", "desc": "Active power scheme (Balanced / High performance)"},
    {"id": "problem_devices", "label": "Problem devices", "desc": "Hardware Windows flags as unhealthy"},
    {"id": "event_log", "label": "Recent stability log", "desc": "Unexpected restarts & error volume (slower)"},
    {"id": "startup", "label": "Startup load", "desc": "How many programs start with Windows"},
    {"id": "security_overview", "label": "Security overview", "desc": "Threat DB / quarantine (toolbox)"},
    {"id": "compatibility", "label": "Compatibility notes", "desc": "Whether major parts play well together"},
    {"id": "bottlenecks", "label": "Bottleneck analysis", "desc": "Likely speed / capacity limits"},
    {"id": "friendly_summaries", "label": "Simple language", "desc": "Extra plain-English explanations"},
]


def _device_id() -> str:
    name = os.environ.get("COMPUTERNAME") or platform.node() or "UNKNOWN-PC"
    safe = re.sub(r"[^\w.\-]+", "-", name).strip("-").upper() or "UNKNOWN-PC"
    return safe


def _device_store() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    return base / "FAFO" / "Devices" / _device_id()


def _pc_reports_dir() -> Path:
    d = _device_store() / "Reports" / "PC"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read_version() -> str:
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip() or "0.00.00"
    except OSError:
        return "0.00.00"


def _wmic_or_cim(ps_snippet: str, timeout: int = 25) -> Any:
    """Run a small PowerShell snippet; return parsed JSON or None."""
    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        ps_snippet,
    ]
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        out = (r.stdout or "").strip()
        if not out:
            return None
        return json.loads(out)
    except Exception:
        return None


def _sev_rank(s: str) -> int:
    return {"ok": 0, "info": 1, "warn": 2, "bad": 3}.get(s, 1)


def _merge_sev(a: str, b: str) -> str:
    return a if _sev_rank(a) >= _sev_rank(b) else b


def _bytes_gb(n: float | int | None) -> float | None:
    if n is None:
        return None
    return round(float(n) / (1024**3), 2)


def _human_device_class(class_name: str | None, name: str | None) -> str:
    c = (class_name or "").lower()
    n = (name or "").lower()
    if "display" in c or "gpu" in n or "geforce" in n or "radeon" in n:
        return "Graphics card"
    if "net" in c or "wifi" in n or "ethernet" in n or "wireless" in n:
        return "Network adapter"
    if "mouse" in c or "hid" in c:
        return "Mouse / input device"
    if "keyboard" in c:
        return "Keyboard"
    if "media" in c or "audio" in c or "sound" in n:
        return "Audio device"
    if "bluetooth" in c or "bluetooth" in n:
        return "Bluetooth"
    if "usb" in c:
        return "USB device"
    if "disk" in c or "volume" in c or "storage" in c:
        return "Storage"
    if "processor" in c:
        return "Processor"
    if "monitor" in c:
        return "Monitor"
    if "camera" in n or "imaging" in c:
        return "Camera"
    if not class_name:
        return "Device"
    return class_name


def get_options_schema() -> dict[str, Any]:
    return {
        "defaults": dict(DEFAULT_OPTIONS),
        "options": OPTION_META,
        "eventLogDaysDefault": 7,
        "eventLogDaysMax": 30,
    }


def _collect_identity(components: list, findings: list) -> dict:
    uname = platform.uname()
    boot = datetime.fromtimestamp(psutil.boot_time())
    uptime_h = round((datetime.now() - boot).total_seconds() / 3600, 1)
    mem = psutil.virtual_memory()
    data = {
        "computerName": os.environ.get("COMPUTERNAME") or uname.node,
        "os": f"{uname.system} {uname.release}",
        "osVersion": uname.version,
        "architecture": uname.machine,
        "uptimeHours": uptime_h,
        "bootTime": boot.isoformat(timespec="seconds"),
        "totalRamGb": _bytes_gb(mem.total),
    }
    # Enrich via WMI when possible
    wmi = _wmic_or_cim(
        r"""
$cs = Get-CimInstance Win32_ComputerSystem
$os = Get-CimInstance Win32_OperatingSystem
$bb = Get-CimInstance Win32_BaseBoard
$bios = Get-CimInstance Win32_BIOS
@{
  manufacturer = $cs.Manufacturer
  model = $cs.Model
  caption = $os.Caption
  build = $os.BuildNumber
  board = $bb.Product
  boardMfr = $bb.Manufacturer
  bios = $bios.SMBIOSBIOSVersion
} | ConvertTo-Json -Compress
"""
    )
    if isinstance(wmi, dict):
        data.update(
            {
                "manufacturer": wmi.get("manufacturer"),
                "model": wmi.get("model"),
                "osCaption": wmi.get("caption"),
                "osBuild": wmi.get("build"),
                "motherboard": wmi.get("board"),
                "motherboardMfr": wmi.get("boardMfr"),
                "biosVersion": wmi.get("bios"),
            }
        )

    brand = data.get("manufacturer") or "PC"
    model = data.get("model") or "unknown model"
    os_name = data.get("osCaption") or data["os"]
    friendly = f"{brand} {model}".strip()
    summary = (
        f"This computer is a {friendly} running {os_name}. "
        f"It has been on for about {uptime_h} hours since the last boot."
    )
    components.append(
        {
            "id": "identity",
            "name": "This PC",
            "friendlyName": friendly,
            "category": "Overview",
            "status": "ok",
            "summary": summary,
            "simple": f"You're on a {friendly} with Windows.",
            "details": data,
            "links": ["cpu", "memory", "storage", "gpu", "network"],
            "suggestions": [],
        }
    )
    findings.append(
        {"severity": "info", "area": "Identity", "message": f"{friendly} · {os_name} · up {uptime_h}h"}
    )
    return data


def _collect_cpu(components: list, findings: list) -> dict:
    freq = psutil.cpu_freq()
    pct = psutil.cpu_percent(interval=0.6)
    logical = psutil.cpu_count(logical=True) or 0
    physical = psutil.cpu_count(logical=False) or logical
    name = platform.processor() or "CPU"
    wmi = _wmic_or_cim(
        r"(Get-CimInstance Win32_Processor | Select-Object -First 1 Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed | ConvertTo-Json -Compress)"
    )
    max_mhz = None
    if isinstance(wmi, dict):
        name = (wmi.get("Name") or name or "").strip()
        physical = wmi.get("NumberOfCores") or physical
        logical = wmi.get("NumberOfLogicalProcessors") or logical
        max_mhz = wmi.get("MaxClockSpeed")

    data = {
        "name": name,
        "physicalCores": physical,
        "logicalProcessors": logical,
        "loadPercent": pct,
        "maxMhz": max_mhz,
        "currentMhz": round(freq.current) if freq else None,
    }
    status = "ok"
    suggestions = []
    simple = f"Your brain chip is a {name} with {physical} cores ({logical} threads)."
    summary = (
        f"{name}: {physical} cores / {logical} threads, currently about {pct:.0f}% busy."
    )
    if pct >= 90:
        status = "bad"
        summary += " The processor is very busy right now."
        suggestions.append(
            {
                "priority": "high",
                "title": "CPU is near max",
                "why": f"Load is {pct:.0f}%. Heavy apps or background tasks may be fighting for the processor.",
                "how": "Open Task Manager (Ctrl+Shift+Esc) → Processes, sort by CPU, and close unused heavy apps. Scan for malware if this is constant.",
            }
        )
        findings.append({"severity": "bad", "area": "CPU", "message": f"High load {pct:.0f}%"})
    elif pct >= 75:
        status = "warn"
        findings.append({"severity": "warn", "area": "CPU", "message": f"Elevated load {pct:.0f}%"})
    else:
        findings.append({"severity": "ok", "area": "CPU", "message": f"{name} · {pct:.0f}% load"})

    components.append(
        {
            "id": "cpu",
            "name": "Processor",
            "friendlyName": name,
            "category": "Compute",
            "status": status,
            "summary": summary,
            "simple": simple,
            "details": data,
            "links": ["memory", "gpu", "bottlenecks"],
            "suggestions": suggestions,
        }
    )
    return data


def _collect_memory(components: list, findings: list) -> dict:
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    total = _bytes_gb(vm.total) or 0
    free = _bytes_gb(vm.available) or 0
    used_pct = vm.percent
    sticks = _wmic_or_cim(
        r"""
Get-CimInstance Win32_PhysicalMemory | ForEach-Object {
  @{ capacityGb = [math]::Round($_.Capacity/1GB,1); speed = $_.ConfiguredClockSpeed; mfr = $_.Manufacturer; part = ($_.PartNumber -replace '\s+$','') }
} | ConvertTo-Json -Compress
"""
    )
    if isinstance(sticks, dict):
        sticks = [sticks]
    if not isinstance(sticks, list):
        sticks = []

    data = {
        "totalGb": total,
        "freeGb": free,
        "usedPercent": used_pct,
        "swapPercent": swap.percent,
        "modules": sticks,
        "moduleCount": len(sticks),
    }
    status = "ok"
    suggestions = []
    simple = f"You have about {total:.0f} GB of memory (RAM); roughly {free:.1f} GB is free right now."
    summary = f"{total:.1f} GB RAM total · {free:.1f} GB free ({used_pct:.0f}% in use)."
    if sticks:
        speeds = sorted({s.get("speed") for s in sticks if s.get("speed")})
        if speeds:
            summary += f" {len(sticks)} module(s) reported"
            if len(speeds) == 1:
                summary += f" at {speeds[0]} MHz."
            else:
                summary += f" at mixed speeds {speeds} MHz."
                status = _merge_sev(status, "warn")
                suggestions.append(
                    {
                        "priority": "medium",
                        "title": "RAM sticks at different speeds",
                        "why": "Mixed memory speeds often force all sticks to run at the slower rate.",
                        "how": "Match capacity and speed when upgrading. In BIOS/UEFI, enable XMP/DOCP only if stable.",
                    }
                )

    if used_pct >= 92:
        status = "bad"
        suggestions.append(
            {
                "priority": "high",
                "title": "Memory almost full",
                "why": f"RAM is {used_pct:.0f}% used ({free:.1f} GB free). Windows will slow down and use disk as emergency memory.",
                "how": "Close heavy browsers/tabs and apps. If this is normal for your work, consider adding RAM (match existing modules).",
            }
        )
        findings.append({"severity": "bad", "area": "Memory", "message": f"{used_pct:.0f}% used · {free:.1f} GB free"})
    elif used_pct >= 80:
        status = _merge_sev(status, "warn")
        findings.append({"severity": "warn", "area": "Memory", "message": f"{used_pct:.0f}% used · {free:.1f} GB free"})
    else:
        findings.append({"severity": "ok", "area": "Memory", "message": f"{total:.0f} GB · {free:.1f} GB free"})

    if total < 8:
        status = _merge_sev(status, "warn")
        suggestions.append(
            {
                "priority": "medium",
                "title": "Low total RAM for modern Windows",
                "why": f"Only {total:.0f} GB is installed. Windows 11 and browsers often want 16 GB for comfort.",
                "how": "Upgrade toward 16 GB if the laptop/desktop supports dual-channel matching sticks.",
            }
        )

    components.append(
        {
            "id": "memory",
            "name": "Memory (RAM)",
            "friendlyName": f"{total:.0f} GB RAM",
            "category": "Compute",
            "status": status,
            "summary": summary,
            "simple": simple,
            "details": data,
            "links": ["cpu", "storage", "bottlenecks"],
            "suggestions": suggestions,
        }
    )
    return data


def _collect_gpu(components: list, findings: list) -> dict:
    gpus = _wmic_or_cim(
        r"""
Get-CimInstance Win32_VideoController | ForEach-Object {
  @{ name = $_.Name; driver = $_.DriverVersion; status = $_.Status; ram = $_.AdapterRAM }
} | ConvertTo-Json -Compress
"""
    )
    if isinstance(gpus, dict):
        gpus = [gpus]
    if not isinstance(gpus, list):
        gpus = []

    items = []
    status = "ok"
    suggestions = []
    for g in gpus:
        name = (g.get("name") or "Display adapter").strip()
        st = (g.get("status") or "OK").strip()
        items.append(
            {
                "name": name,
                "driver": g.get("driver"),
                "status": st,
                "kind": _human_device_class("Display", name),
            }
        )
        if st and st.upper() not in ("OK",):
            status = "warn"
            findings.append({"severity": "warn", "area": "GPU", "message": f"{name} status={st}"})
        else:
            findings.append({"severity": "ok", "area": "GPU", "message": name})

    names = ", ".join(i["name"] for i in items) if items else "No GPU reported"
    simple = (
        f"Graphics: {names}."
        if items
        else "Windows did not report a graphics card (unusual)."
    )
    if len(items) > 1:
        simple += " You have more than one graphics device (common on laptops: power-saving + high-performance)."
        suggestions.append(
            {
                "priority": "low",
                "title": "Laptop dual-GPU tip",
                "why": "Games and creative apps should use the stronger GPU when plugged in.",
                "how": "Windows Settings → System → Display → Graphics — set heavy apps to High performance.",
            }
        )

    components.append(
        {
            "id": "gpu",
            "name": "Graphics",
            "friendlyName": names if items else "Graphics",
            "category": "Compute",
            "status": status if items else "info",
            "summary": simple,
            "simple": simple,
            "details": {"adapters": items},
            "links": ["cpu", "power", "bottlenecks"],
            "suggestions": suggestions,
        }
    )
    return {"adapters": items}


def _collect_storage(components: list, findings: list) -> dict:
    disks_wmi = _wmic_or_cim(
        r"""
try {
  Get-PhysicalDisk | ForEach-Object {
    @{ name = $_.FriendlyName; media = "$($_.MediaType)"; bus = "$($_.BusType)"; sizeGb = [math]::Round($_.Size/1GB,0); health = "$($_.HealthStatus)"; op = "$($_.OperationalStatus)" }
  } | ConvertTo-Json -Compress
} catch {
  Get-CimInstance Win32_DiskDrive | ForEach-Object {
    @{ name = $_.Model; media = $_.MediaType; bus = $_.InterfaceType; sizeGb = [math]::Round($_.Size/1GB,0); health = $_.Status; op = $_.Status }
  } | ConvertTo-Json -Compress
}
"""
    )
    if isinstance(disks_wmi, dict):
        disks_wmi = [disks_wmi]
    if not isinstance(disks_wmi, list):
        disks_wmi = []

    volumes = []
    status = "ok"
    suggestions = []
    for part in psutil.disk_partitions(all=False):
        if "cdrom" in part.opts.lower() or not part.fstype:
            continue
        try:
            u = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        free_pct = round(100 * u.free / u.total, 0) if u.total else 0
        entry = {
            "mount": part.mountpoint,
            "fstype": part.fstype,
            "totalGb": _bytes_gb(u.total),
            "freeGb": _bytes_gb(u.free),
            "freePercent": free_pct,
            "usedPercent": u.percent,
        }
        volumes.append(entry)
        label = part.mountpoint
        if free_pct < 10:
            status = "bad"
            findings.append(
                {"severity": "bad", "area": "Storage", "message": f"{label} only {free_pct:.0f}% free"}
            )
            suggestions.append(
                {
                    "priority": "high",
                    "title": f"Drive {label} is almost full",
                    "why": f"Only about {entry['freeGb']} GB free ({free_pct:.0f}%). Windows and apps need free space for updates and temp files.",
                    "how": "Use Disk Space Analyzer in this toolbox, empty Recycle Bin, move videos to another drive, or uninstall large unused apps.",
                }
            )
        elif free_pct < 15:
            status = _merge_sev(status, "warn")
            findings.append(
                {"severity": "warn", "area": "Storage", "message": f"{label} {free_pct:.0f}% free"}
            )
        else:
            findings.append(
                {"severity": "ok", "area": "Storage", "message": f"{label} {free_pct:.0f}% free"}
            )

    for d in disks_wmi:
        h = str(d.get("health") or "")
        if re.search(r"Unhealthy|Warning|Predictive", h, re.I):
            status = "bad"
            findings.append(
                {"severity": "bad", "area": "Storage", "message": f"{d.get('name')}: {h}"}
            )
            suggestions.append(
                {
                    "priority": "high",
                    "title": f"Disk health warning: {d.get('name')}",
                    "why": f"Windows reported health '{h}'. Data loss risk if ignored.",
                    "how": "Back up important files now. Check manufacturer tools (Samsung Magician, Crucial Storage, etc.) and plan replacement.",
                }
            )

    disk_names = ", ".join(
        f"{d.get('name')} ({d.get('sizeGb')} GB)" for d in disks_wmi[:4]
    ) or "internal storage"
    simple = f"Storage: {disk_names}."
    if volumes:
        c = next((v for v in volumes if v["mount"].upper().startswith("C")), volumes[0])
        simple += f" System drive {c['mount']} has about {c['freeGb']} GB free."

    components.append(
        {
            "id": "storage",
            "name": "Storage",
            "friendlyName": "Drives & free space",
            "category": "Storage",
            "status": status,
            "summary": simple,
            "simple": simple,
            "details": {"disks": disks_wmi, "volumes": volumes},
            "links": ["memory", "bottlenecks", "identity"],
            "suggestions": suggestions,
        }
    )
    return {"disks": disks_wmi, "volumes": volumes}


def _collect_network(components: list, findings: list) -> dict:
    adapters = []
    status = "ok"
    for name, addrs in psutil.net_if_addrs().items():
        stats = psutil.net_if_stats().get(name)
        if not stats or not stats.isup:
            continue
        # skip virtual loopbacks
        if name.lower().startswith("loopback") or name == "lo":
            continue
        ipv4 = next((a.address for a in addrs if a.family.name == "AF_INET"), None)
        adapters.append(
            {
                "name": name,
                "speedMbps": stats.speed if stats.speed and stats.speed > 0 else None,
                "ipv4": ipv4,
                "kind": _human_device_class("Net", name),
            }
        )

    if not adapters:
        status = "warn"
        findings.append({"severity": "warn", "area": "Network", "message": "No active adapters"})
        simple = "No active network connection was found."
        suggestions = [
            {
                "priority": "high",
                "title": "No network link",
                "why": "Windows shows no active Ethernet/Wi‑Fi adapter up.",
                "how": "Check Wi‑Fi is on, cable is seated, and airplane mode is off. Try Settings → Network.",
            }
        ]
    else:
        findings.append(
            {
                "severity": "ok",
                "area": "Network",
                "message": ", ".join(a["name"] for a in adapters[:3]),
            }
        )
        parts = []
        for a in adapters[:3]:
            spd = f" ~{a['speedMbps']} Mbps" if a.get("speedMbps") else ""
            parts.append(f"{a['name']}{spd}")
        simple = "Online via " + "; ".join(parts) + "."
        suggestions = []

    components.append(
        {
            "id": "network",
            "name": "Network",
            "friendlyName": "Internet & links",
            "category": "Network",
            "status": status,
            "summary": simple,
            "simple": simple,
            "details": {"adapters": adapters, "hostname": socket.gethostname()},
            "links": ["identity", "security"],
            "suggestions": suggestions,
        }
    )
    return {"adapters": adapters}


def _collect_power(components: list, findings: list) -> dict:
    scheme = None
    try:
        r = subprocess.run(
            ["powercfg", "/getactivescheme"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        scheme = (r.stdout or "").strip()
    except Exception:
        scheme = None

    label = "Unknown power plan"
    status = "info"
    suggestions = []
    if scheme:
        m = re.search(r"\(([^)]+)\)\s*$", scheme)
        label = m.group(1) if m else scheme
        status = "ok"
        findings.append({"severity": "info", "area": "Power", "message": label})
        if re.search(r"power.?saver", label, re.I):
            status = "warn"
            suggestions.append(
                {
                    "priority": "medium",
                    "title": "Power Saver may slow the PC",
                    "why": "Power Saver reduces CPU speed and can make games/creative apps feel laggy.",
                    "how": "Settings → System → Power — use Balanced on battery, Best performance when plugged in for heavy work.",
                }
            )
    simple = f"Windows power plan: {label}."

    components.append(
        {
            "id": "power",
            "name": "Power plan",
            "friendlyName": label,
            "category": "System",
            "status": status,
            "summary": simple,
            "simple": simple,
            "details": {"activeScheme": scheme, "label": label},
            "links": ["cpu", "gpu"],
            "suggestions": suggestions,
        }
    )
    return {"label": label, "raw": scheme}


def _collect_problem_devices(components: list, findings: list) -> dict:
    raw = _wmic_or_cim(
        r"""
Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
  Where-Object { $_.Status -ne 'OK' } |
  Select-Object -First 40 Status, Class, FriendlyName, InstanceId |
  ForEach-Object {
    @{ status = "$($_.Status)"; class = "$($_.Class)"; name = $_.FriendlyName; id = $_.InstanceId }
  } | ConvertTo-Json -Compress
""",
        timeout=40,
    )
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        raw = []

    devices = []
    for d in raw:
        name = d.get("name") or "Unknown device"
        devices.append(
            {
                "name": name,
                "status": d.get("status"),
                "class": d.get("class"),
                "kind": _human_device_class(d.get("class"), name),
                "id": d.get("id"),
                "simple": f"{_human_device_class(d.get('class'), name)}: {name} — Windows says “{d.get('status')}”.",
            }
        )

    status = "ok"
    suggestions = []
    if devices:
        # Filter noise: many "Unknown" are harmless; Error/Degraded matter more
        serious = [
            d
            for d in devices
            if re.search(r"Error|Degraded|Failed", str(d.get("status") or ""), re.I)
        ]
        if serious:
            status = "warn"
            findings.append(
                {
                    "severity": "warn",
                    "area": "Devices",
                    "message": f"{len(serious)} device(s) with errors",
                }
            )
            suggestions.append(
                {
                    "priority": "medium",
                    "title": "Some hardware needs attention",
                    "why": f"{len(serious)} devices report Error/Degraded (examples: {', '.join(s['name'] for s in serious[:3])}).",
                    "how": "Open Device Manager → look for yellow marks. Update or reinstall the driver, or disable unused ghost devices with Ghost Device Cleaner.",
                }
            )
        else:
            findings.append(
                {
                    "severity": "info",
                    "area": "Devices",
                    "message": f"{len(devices)} non-OK present devices (may be benign)",
                }
            )
        simple = f"Windows listed {len(devices)} device(s) that are not fully OK. Important ones are highlighted in details."
    else:
        findings.append({"severity": "ok", "area": "Devices", "message": "No problem devices"})
        simple = "No problem devices found — hardware looks clean from Windows’ point of view."

    components.append(
        {
            "id": "problem_devices",
            "name": "Problem devices",
            "friendlyName": "Hardware health flags",
            "category": "Devices",
            "status": status,
            "summary": simple,
            "simple": simple,
            "details": {"devices": devices, "count": len(devices)},
            "links": ["gpu", "network", "storage"],
            "suggestions": suggestions,
        }
    )
    return {"devices": devices}


def _collect_event_log(components: list, findings: list, days: int = 7) -> dict:
    days = max(1, min(int(days or 7), 30))
    ps = rf"""
$start = (Get-Date).AddDays(-{days})
$sys = @(Get-WinEvent -FilterHashtable @{{ LogName='System'; Level=1,2,3; StartTime=$start }} -MaxEvents 400 -ErrorAction SilentlyContinue)
$app = @(Get-WinEvent -FilterHashtable @{{ LogName='Application'; Level=1,2,3; StartTime=$start }} -MaxEvents 400 -ErrorAction SilentlyContinue)
$k41 = @($sys | Where-Object {{ $_.Id -eq 41 -and $_.ProviderName -match 'Kernel-Power' }})
$u6008 = @($sys | Where-Object {{ $_.Id -eq 6008 }})
$topSys = $sys | Group-Object ProviderName | Sort-Object Count -Descending | Select-Object -First 6 | ForEach-Object {{ @{{ name=$_.Name; count=$_.Count }} }}
$topApp = $app | Group-Object ProviderName | Sort-Object Count -Descending | Select-Object -First 6 | ForEach-Object {{ @{{ name=$_.Name; count=$_.Count }} }}
@{{
  days = {days}
  systemCount = $sys.Count
  applicationCount = $app.Count
  kernelPower41 = $k41.Count
  unexpected6008 = $u6008.Count
  topSystem = @($topSys)
  topApplication = @($topApp)
}} | ConvertTo-Json -Depth 4 -Compress
"""
    data = _wmic_or_cim(ps, timeout=60) or {}
    if not isinstance(data, dict):
        data = {"error": "event log scan failed", "days": days}

    k41 = int(data.get("kernelPower41") or 0)
    u6 = int(data.get("unexpected6008") or 0)
    status = "ok"
    suggestions = []
    if k41 or u6:
        status = "bad"
        findings.append(
            {
                "severity": "bad",
                "area": "Stability",
                "message": f"Unexpected shutdowns (41={k41}, 6008={u6}) in {days}d",
            }
        )
        suggestions.append(
            {
                "priority": "high",
                "title": "Unexpected restarts detected",
                "why": "Windows recorded hard restarts or unclean shutdowns. Causes include power loss, crashes, overheating, or holding the power button.",
                "how": "Note when it happens (gaming, sleep, idle). Check power cable/battery, GPU temps, and recent driver updates. Review Reliability Monitor.",
            }
        )
        simple = f"Stability concern: {k41 + u6} unexpected restart signal(s) in the last {days} days."
    else:
        findings.append(
            {"severity": "ok", "area": "Stability", "message": f"No 41/6008 in {days}d sample"}
        )
        simple = f"No unexpected restart signatures in the last {days} days (sampled)."

    sys_c = int(data.get("systemCount") or 0)
    if sys_c > 250:
        status = _merge_sev(status, "warn")
        simple += f" System error/warning volume is elevated ({sys_c} sampled)."

    components.append(
        {
            "id": "event_log",
            "name": "Stability log",
            "friendlyName": f"Last {days} days",
            "category": "System",
            "status": status,
            "summary": simple,
            "simple": simple,
            "details": data,
            "links": ["power", "storage", "gpu"],
            "suggestions": suggestions,
        }
    )
    return data


def _collect_startup(components: list, findings: list) -> dict:
    data: dict[str, Any] = {"startupCount": None, "note": None}
    try:
        import startup_ops as startup

        ov = startup.get_overview()
        data = {
            "startupCount": ov.get("startup_count"),
            "taskCount": ov.get("task_count"),
            "serviceCount": ov.get("service_count"),
            "runningServices": ov.get("running_services"),
            "autoServices": ov.get("auto_services"),
        }
    except Exception as e:
        data["note"] = str(e)

    count = data.get("startupCount")
    auto = data.get("autoServices") or 0
    status = "ok"
    suggestions = []
    if count is None:
        simple = "Startup inventory unavailable right now."
        status = "info"
    else:
        simple = f"About {count} items try to start with Windows; {auto} services set to automatic."
        if count and count > 40:
            status = "warn"
            suggestions.append(
                {
                    "priority": "medium",
                    "title": "Heavy startup list",
                    "why": f"{count} startup entries can slow boot and steal RAM.",
                    "how": "Open Startup & Service Manager in this toolbox and disable apps you rarely use (keep security/GPU helpers).",
                }
            )
            findings.append({"severity": "warn", "area": "Startup", "message": f"{count} startup items"})
        else:
            findings.append({"severity": "ok", "area": "Startup", "message": f"{count} startup items"})

    components.append(
        {
            "id": "startup",
            "name": "Startup load",
            "friendlyName": "What runs at boot",
            "category": "System",
            "status": status,
            "summary": simple,
            "simple": simple,
            "details": data,
            "links": ["memory", "security"],
            "suggestions": suggestions,
        }
    )
    return data


def _collect_security(components: list, findings: list) -> dict:
    data: dict[str, Any] = {}
    try:
        import security_scan as sec

        intel = sec.get_intel_status()
        q = sec.list_quarantine()
        data = {
            "threatHashes": intel.get("total_hashes", 0),
            "lastIntelUpdate": intel.get("last_update"),
            "quarantineCount": len(q),
        }
    except Exception as e:
        data = {"note": str(e)}

    status = "info"
    suggestions = []
    hashes = int(data.get("threatHashes") or 0)
    if hashes == 0:
        simple = "Toolbox threat database is empty — Malware Defender has not pulled intel yet."
        suggestions.append(
            {
                "priority": "low",
                "title": "Optional: update threat intel",
                "why": "Malware Defender can use open threat feeds for extra scanning.",
                "how": "Open Malware Defender and run an update/scan when convenient.",
            }
        )
        findings.append({"severity": "info", "area": "Security", "message": "Threat DB empty"})
    else:
        status = "ok"
        simple = f"Threat intel database holds about {hashes:,} hashes."
        findings.append({"severity": "ok", "area": "Security", "message": f"{hashes:,} threat hashes"})

    components.append(
        {
            "id": "security",
            "name": "Security overview",
            "friendlyName": "Toolbox security",
            "category": "Security",
            "status": status,
            "summary": simple,
            "simple": simple,
            "details": data,
            "links": ["startup", "network"],
            "suggestions": suggestions,
        }
    )
    return data


def _analyze_compatibility(cpu: dict | None, memory: dict | None, gpu: dict | None, storage: dict | None) -> list[dict]:
    notes = []
    if memory and (memory.get("totalGb") or 0) < 16 and gpu:
        adapters = (gpu.get("adapters") or [])
        heavy = any(
            re.search(r"rtx|gtx|radeon|arc", a.get("name") or "", re.I) for a in adapters
        )
        if heavy:
            notes.append(
                {
                    "id": "ram-vs-gpu",
                    "status": "warn",
                    "title": "Strong GPU, modest RAM",
                    "message": (
                        f"A capable graphics card is paired with only ~{memory.get('totalGb')} GB RAM. "
                        "Games and creative apps may hitch when RAM fills before the GPU is maxed."
                    ),
                    "components": ["memory", "gpu", "bottlenecks"],
                    "suggestion": "16 GB is a comfortable minimum for gaming + browser multitasking; 32 GB for heavy creators.",
                }
            )

    if storage and memory:
        vols = storage.get("volumes") or []
        c = next((v for v in vols if str(v.get("mount", "")).upper().startswith("C")), None)
        if c and (c.get("freePercent") or 100) < 15 and (memory.get("usedPercent") or 0) > 75:
            notes.append(
                {
                    "id": "ram-disk-pressure",
                    "status": "warn",
                    "title": "Low free disk + busy RAM",
                    "message": "When RAM is tight, Windows uses disk as overflow. A nearly full system drive makes that overflow very slow.",
                    "components": ["memory", "storage", "bottlenecks"],
                    "suggestion": "Free space on C: first, then reduce open apps or add RAM.",
                }
            )

    if cpu and memory:
        # Dual channel: 1 stick often bottlenecks CPU
        mods = memory.get("moduleCount") or 0
        if mods == 1 and (memory.get("totalGb") or 0) >= 8:
            notes.append(
                {
                    "id": "single-channel-ram",
                    "status": "info",
                    "title": "Single RAM module",
                    "message": "Only one memory stick was detected. Many systems run faster with two matched sticks (dual-channel).",
                    "components": ["memory", "cpu"],
                    "suggestion": "If the board has a free slot, add a matching stick for a free performance boost.",
                }
            )

    if not notes:
        notes.append(
            {
                "id": "compat-ok",
                "status": "ok",
                "title": "No major mismatches flagged",
                "message": "Based on this scan, major parts look reasonably matched. Minor tips may still appear under suggestions.",
                "components": ["identity", "cpu", "memory", "gpu"],
                "suggestion": None,
            }
        )
    return notes


def _analyze_bottlenecks(
    cpu: dict | None,
    memory: dict | None,
    storage: dict | None,
    findings: list,
) -> list[dict]:
    bottlenecks = []
    if cpu and (cpu.get("loadPercent") or 0) >= 85:
        bottlenecks.append(
            {
                "id": "cpu-bound",
                "severity": "warn",
                "title": "Processor under heavy load",
                "message": f"CPU around {cpu.get('loadPercent'):.0f}% — tasks may feel laggy until load drops.",
                "components": ["cpu"],
            }
        )
    if memory and (memory.get("usedPercent") or 0) >= 85:
        bottlenecks.append(
            {
                "id": "ram-bound",
                "severity": "warn",
                "title": "Memory pressure",
                "message": f"RAM is {memory.get('usedPercent'):.0f}% full ({memory.get('freeGb')} GB free). Expect slowdowns and disk thrashing.",
                "components": ["memory", "storage"],
            }
        )
    if storage:
        for v in storage.get("volumes") or []:
            if (v.get("freePercent") or 100) < 12:
                bottlenecks.append(
                    {
                        "id": f"disk-{v.get('mount')}",
                        "severity": "bad" if (v.get("freePercent") or 0) < 8 else "warn",
                        "title": f"Low free space on {v.get('mount')}",
                        "message": f"Only {v.get('freePercent'):.0f}% free ({v.get('freeGb')} GB). Installs, updates, and virtual memory suffer.",
                        "components": ["storage"],
                    }
                )

    if not bottlenecks:
        bottlenecks.append(
            {
                "id": "none",
                "severity": "ok",
                "title": "No active bottleneck spotted",
                "message": "At scan time, CPU, RAM, and disk free space look workable. Re-run during a freeze for better clues.",
                "components": ["cpu", "memory", "storage"],
            }
        )
    return bottlenecks


def run_diagnostics(
    options: dict[str, bool] | None = None,
    event_log_days: int = 7,
    persist: bool = True,
) -> dict[str, Any]:
    """Run selected diagnostics modules and return a HUD-ready report."""
    t0 = time.time()
    opts = dict(DEFAULT_OPTIONS)
    if options:
        for k, v in options.items():
            if k in opts:
                opts[k] = bool(v)

    device = _device_id()
    components: list[dict] = []
    findings: list[dict] = []
    raw: dict[str, Any] = {}

    identity = cpu = memory = gpu = storage = network = power = None
    problem = events = startup = security = None

    if opts.get("identity"):
        identity = _collect_identity(components, findings)
        raw["identity"] = identity
    if opts.get("cpu"):
        cpu = _collect_cpu(components, findings)
        raw["cpu"] = cpu
    if opts.get("memory"):
        memory = _collect_memory(components, findings)
        raw["memory"] = memory
    if opts.get("gpu"):
        gpu = _collect_gpu(components, findings)
        raw["gpu"] = gpu
    if opts.get("storage"):
        storage = _collect_storage(components, findings)
        raw["storage"] = storage
    if opts.get("network"):
        network = _collect_network(components, findings)
        raw["network"] = network
    if opts.get("power"):
        power = _collect_power(components, findings)
        raw["power"] = power
    if opts.get("problem_devices"):
        problem = _collect_problem_devices(components, findings)
        raw["problem_devices"] = problem
    if opts.get("event_log"):
        events = _collect_event_log(components, findings, days=event_log_days)
        raw["event_log"] = events
    if opts.get("startup"):
        startup = _collect_startup(components, findings)
        raw["startup"] = startup
    if opts.get("security_overview"):
        security = _collect_security(components, findings)
        raw["security"] = security

    compatibility = []
    bottlenecks = []
    if opts.get("compatibility"):
        compatibility = _analyze_compatibility(cpu, memory, gpu, storage)
        components.append(
            {
                "id": "compatibility",
                "name": "Compatibility",
                "friendlyName": "Do parts work well together?",
                "category": "Analysis",
                "status": max((n.get("status") or "ok" for n in compatibility), key=_sev_rank),
                "summary": compatibility[0]["message"] if compatibility else "",
                "simple": compatibility[0]["message"] if compatibility else "",
                "details": {"notes": compatibility},
                "links": list({c for n in compatibility for c in (n.get("components") or [])}),
                "suggestions": [
                    {
                        "priority": "medium",
                        "title": n["title"],
                        "why": n["message"],
                        "how": n.get("suggestion") or "See related components.",
                    }
                    for n in compatibility
                    if n.get("status") not in ("ok",) and n.get("suggestion")
                ],
            }
        )
    if opts.get("bottlenecks"):
        bottlenecks = _analyze_bottlenecks(cpu, memory, storage, findings)
        components.append(
            {
                "id": "bottlenecks",
                "name": "Bottlenecks",
                "friendlyName": "What might be slowing you down",
                "category": "Analysis",
                "status": max((b.get("severity") or "ok" for b in bottlenecks), key=_sev_rank),
                "summary": bottlenecks[0]["message"] if bottlenecks else "",
                "simple": bottlenecks[0]["message"] if bottlenecks else "",
                "details": {"items": bottlenecks},
                "links": list({c for b in bottlenecks for c in (b.get("components") or [])}),
                "suggestions": [],
            }
        )

    # Aggregate suggestions from components
    suggestions: list[dict] = []
    for c in components:
        for s in c.get("suggestions") or []:
            suggestions.append({**s, "componentId": c["id"], "componentName": c["name"]})
    for n in compatibility:
        if n.get("suggestion") and n.get("status") != "ok":
            suggestions.append(
                {
                    "priority": "medium" if n.get("status") == "warn" else "low",
                    "title": n["title"],
                    "why": n["message"],
                    "how": n["suggestion"],
                    "componentId": "compatibility",
                    "componentName": "Compatibility",
                }
            )

    bad = sum(1 for f in findings if f.get("severity") == "bad")
    warn = sum(1 for f in findings if f.get("severity") == "warn")
    if bad:
        overall_sev, overall_label = "bad", "Attention needed"
        score = max(25, 70 - bad * 15 - warn * 5)
    elif warn:
        overall_sev, overall_label = "warn", "Mostly OK - review warnings"
        score = max(55, 88 - warn * 6)
    else:
        overall_sev, overall_label = "ok", "Healthy"
        score = 95

    # Plain-English executive summary
    bullets = []
    if identity:
        bullets.append(
            f"PC: {identity.get('manufacturer') or ''} {identity.get('model') or identity.get('computerName')}".strip()
        )
    if cpu:
        bullets.append(f"Processor load ~{cpu.get('loadPercent'):.0f}% · {cpu.get('name')}")
    if memory:
        bullets.append(
            f"Memory {memory.get('totalGb'):.0f} GB total, {memory.get('freeGb'):.1f} GB free"
        )
    if storage and storage.get("volumes"):
        c = next(
            (v for v in storage["volumes"] if str(v.get("mount", "")).upper().startswith("C")),
            storage["volumes"][0],
        )
        bullets.append(f"Drive {c.get('mount')} has {c.get('freePercent'):.0f}% free")
    if bottlenecks and bottlenecks[0].get("id") != "none":
        bullets.append(f"Watch: {bottlenecks[0].get('title')}")
    else:
        bullets.append("No severe bottleneck flagged at scan time")

    report = {
        "meta": {
            "deviceId": device,
            "collectedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
            "durationMs": int((time.time() - t0) * 1000),
            "options": opts,
            "eventLogDays": event_log_days,
            "toolboxVersion": _read_version(),
            "schema": 1,
        },
        "overall": {
            "severity": overall_sev,
            "label": overall_label,
            "score": score,
            "bad": bad,
            "warn": warn,
            "ok": sum(1 for f in findings if f.get("severity") == "ok"),
        },
        "summary": {
            "headline": overall_label,
            "bullets": bullets,
            "friendly": (
                f"{overall_label}. "
                + " ".join(bullets[:3])
                + (" Click any component tile to explore details and fixes." if opts.get("friendly_summaries") else "")
            ),
        },
        "components": components,
        "findings": findings,
        "suggestions": suggestions,
        "compatibility": compatibility,
        "bottlenecks": bottlenecks,
        "nav": [
            {"id": c["id"], "name": c["name"], "category": c["category"], "status": c["status"]}
            for c in components
        ],
        "raw": raw,
    }

    if persist:
        out_dir = _pc_reports_dir()
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        latest_json = out_dir / "hud_report_latest.json"
        stamped_json = out_dir / f"hud_report_{stamp}.json"
        latest_json.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        stamped_json.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

        # Simple markdown for Report Library / non-technical sharing
        md_lines = [
            f"# System health — {device}",
            "",
            f"**{overall_label}** (score {score}/100)  ",
            f"Collected: {report['meta']['collectedAt']}  ",
            "",
            "## In plain English",
            "",
        ]
        for b in bullets:
            md_lines.append(f"- {b}")
        md_lines += ["", "## Components", ""]
        for c in components:
            md_lines.append(f"### {c['name']} ({c['status']})")
            md_lines.append("")
            md_lines.append(c.get("simple") or c.get("summary") or "")
            md_lines.append("")
        if suggestions:
            md_lines += ["## Suggested actions", ""]
            for s in suggestions[:12]:
                md_lines.append(f"### {s.get('title')}")
                md_lines.append(f"- **Why:** {s.get('why')}")
                md_lines.append(f"- **What to try:** {s.get('how')}")
                md_lines.append("")
        md_path = out_dir / "hud_report_latest.md"
        md_path.write_text("\n".join(md_lines), encoding="utf-8")

        # Minimal friendly HTML snapshot (also used offline)
        html = _render_simple_html(report)
        (out_dir / "hud_report_latest.html").write_text(html, encoding="utf-8")
        report["meta"]["paths"] = {
            "json": str(latest_json),
            "markdown": str(md_path),
            "html": str(out_dir / "hud_report_latest.html"),
            "deviceRoot": str(_device_store()),
        }

    return report


def _render_simple_html(report: dict) -> str:
    o = report["overall"]
    sev = o.get("severity") or "info"
    colors = {"ok": "#34d399", "warn": "#fbbf24", "bad": "#f43f5e", "info": "#60a5fa"}
    color = colors.get(sev, "#60a5fa")
    bullets = "".join(f"<li>{_esc(b)}</li>" for b in report.get("summary", {}).get("bullets") or [])
    cards = []
    for c in report.get("components") or []:
        cards.append(
            f"""<section class="card sev-{_esc(c.get('status'))}" id="{_esc(c.get('id'))}">
  <h2>{_esc(c.get('name'))} <small>{_esc(c.get('friendlyName'))}</small></h2>
  <p class="simple">{_esc(c.get('simple') or c.get('summary'))}</p>
</section>"""
        )
    sugg = []
    for s in (report.get("suggestions") or [])[:10]:
        sugg.append(
            f"<li><strong>{_esc(s.get('title'))}</strong><br><em>Why:</em> {_esc(s.get('why'))}<br><em>Try:</em> {_esc(s.get('how'))}</li>"
        )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>System health — {_esc(report.get('meta',{}).get('deviceId'))}</title>
<style>
body{{font-family:Segoe UI,system-ui,sans-serif;background:#0a0f18;color:#eef3fb;margin:0;padding:24px;line-height:1.5}}
h1{{margin:0 0 8px}} .banner{{display:inline-block;padding:8px 14px;border-radius:999px;font-weight:800;background:rgba(0,0,0,.35);border:1px solid {color};color:{color};margin:12px 0}}
.card{{background:#121a2b;border:1px solid #243049;border-radius:14px;padding:14px 16px;margin:12px 0}}
.card h2{{margin:0 0 8px;font-size:1.05rem}} .card small{{color:#8b9bb4;font-weight:500}}
.simple{{color:#c7d2e5;margin:0}} ul{{padding-left:1.2rem}} a{{color:#67e8f9}}
</style></head><body>
<h1>System health — {_esc(report.get('meta',{}).get('deviceId'))}</h1>
<div class="banner">{_esc(o.get('label'))} · score {o.get('score')}/100</div>
<p>{_esc(report.get('summary',{}).get('friendly'))}</p>
<ul>{bullets}</ul>
{''.join(cards)}
<h2>Suggested actions</h2>
<ul>{''.join(sugg) if sugg else '<li>No urgent actions — re-run if something feels wrong.</li>'}</ul>
<p style="color:#8b9bb4;font-size:.85rem">Generated by AI HTML Toolbox · device-local report</p>
</body></html>"""


def _esc(s: Any) -> str:
    t = "" if s is None else str(s)
    return (
        t.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def load_latest() -> dict[str, Any] | None:
    path = _pc_reports_dir() / "hud_report_latest.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
