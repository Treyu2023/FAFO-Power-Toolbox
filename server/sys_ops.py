"""
Admin ops: system health snapshot + secrets presence (loopback only).

SECURITY:
- Never return client_secret, access_token, refresh_token, or DPAPI payload bytes.
- Secrets presence lists names + has/mtime only — never decrypts.
- Process rows: name/pid/mem/cpu only — no cmdline/exe paths (may contain secrets).
"""
from __future__ import annotations

import os
import platform
import socket
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Short TTL so refresh is useful but not abusive
_CACHE_TTL_SEC = 10.0
_lock = threading.Lock()
_health_cache: dict[str, Any] = {"at": 0.0, "data": None}
_presence_cache: dict[str, Any] = {"at": 0.0, "data": None}

# Expected FAFO secret *names* (no values). Missing → has:false still returned.
KNOWN_SECRET_NAMES = (
    "xero.client_secret",
    "xero.refresh_token",
    "ABUSE_CH_AUTH_KEY",
    "XAI_API_KEY",
    "VERCEL_TOKEN",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bytes_human(n: int | float) -> str:
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"


def _fafo_secrets_dir() -> Path:
    try:
        from security_scan import FAFO_SECRETS_DIR
        return Path(FAFO_SECRETS_DIR)
    except Exception:
        return Path(os.environ.get("LOCALAPPDATA", "")) / "FAFO" / "Secrets"


def _bind_hint() -> dict[str, Any]:
    host = "127.0.0.87"
    port = 18765
    try:
        root = Path(__file__).resolve().parent.parent
        bind_file = root / "shared" / "aitoolbox-bind.json"
        if bind_file.is_file():
            import json
            data = json.loads(bind_file.read_text(encoding="utf-8"))
            host = str(data.get("host") or host)
            port = int(data.get("port") or port)
    except Exception:
        pass
    return {"host": host, "port": port, "endpoint": f"http://{host}:{port}"}


def _port_listening(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.4)
            return s.connect_ex((host, int(port))) == 0
    except OSError:
        return False


def _uptime_seconds() -> float | None:
    try:
        import psutil
        return max(0.0, time.time() - float(psutil.boot_time()))
    except Exception:
        return None


def _disk_for_path(path: str | Path) -> dict[str, Any]:
    try:
        import psutil
        p = Path(path)
        # On Windows use drive root of path
        root = p.anchor or str(p)
        if os.name == "nt":
            root = os.path.splitdrive(str(p.resolve()))[0] + "\\"
        usage = psutil.disk_usage(root)
        return {
            "ok": True,
            "path": str(root),
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "percent": usage.percent,
            "totalHuman": _bytes_human(usage.total),
            "usedHuman": _bytes_human(usage.used),
            "freeHuman": _bytes_human(usage.free),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def _top_processes(limit: int = 12) -> dict[str, Any]:
    """Top processes by CPU/memory — name/pid/metrics only (no cmdline/exe)."""
    try:
        import network_ops as net
        data = net.list_processes(sort_by="cpu", limit=400, include_network=False)
        rows = data.get("processes") or []
        skip = {"system idle process", "idle", "system"}
        rows = [p for p in rows if (p.get("name") or "").lower() not in skip]

        def slim(items: list[dict], key: str) -> list[dict]:
            sorted_items = sorted(items, key=lambda x: x.get(key) or 0, reverse=True)
            out = []
            for p in sorted_items[:limit]:
                out.append({
                    "pid": p.get("pid"),
                    "name": (p.get("name") or "")[:120],
                    "cpuPercent": p.get("cpu_percent") or 0,
                    "memoryPercent": p.get("memory_percent") or 0,
                    "memoryHuman": p.get("memory_human") or "",
                    # intentionally omit cmdline / exe
                })
            return out

        return {
            "ok": True,
            "topCpu": slim(rows, "cpu_percent"),
            "topMemory": slim(rows, "memory_bytes"),
            "total": data.get("total") or len(rows),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:160], "topCpu": [], "topMemory": [], "total": 0}


def _xero_presence() -> dict[str, Any]:
    """Reuse xero.status() — already presence-only."""
    try:
        import xero_ops as xero
        st = xero.status()
        # Strip any unexpected keys if future code adds them
        safe = {
            "ok": bool(st.get("ok")),
            "connected": bool(st.get("connected")),
            "hasClientSecret": bool(st.get("hasClientSecret")),
            "hasRefreshToken": bool(st.get("hasRefreshToken")),
            "hasAccessToken": bool(st.get("hasAccessToken")),
            "tenantId": st.get("tenantId"),
            "tenantCount": st.get("tenantCount") or 0,
            "expiresAt": st.get("expiresAt"),
            "lastError": (str(st.get("lastError"))[:200] if st.get("lastError") else None),
            "bindHint": st.get("bindHint") or "presence only — no tokens",
        }
        return safe
    except Exception as e:
        return {
            "ok": False,
            "connected": False,
            "hasClientSecret": False,
            "hasRefreshToken": False,
            "hasAccessToken": False,
            "error": str(e)[:160],
        }


def get_sys_health(*, force: bool = False) -> dict[str, Any]:
    """
    System Health Desk payload. Cached ~10s.
    Browser-safe: metrics + presence flags only.
    """
    now = time.time()
    with _lock:
        if not force and _health_cache["data"] and (now - float(_health_cache["at"] or 0)) < _CACHE_TTL_SEC:
            return _health_cache["data"]

    errors: list[str] = []
    bind = _bind_hint()
    overview: dict[str, Any] = {}
    try:
        import network_ops as net
        overview = net.get_system_overview()
    except Exception as e:
        errors.append("overview: " + str(e)[:120])
        overview = {}

    uptime = _uptime_seconds()
    fafo_local = Path(os.environ.get("LOCALAPPDATA", "")) / "FAFO"
    toolbox_root = Path(__file__).resolve().parent.parent

    try:
        procs = _top_processes(12)
    except Exception as e:
        procs = {"ok": False, "error": str(e)[:120], "topCpu": [], "topMemory": [], "total": 0}
        errors.append("processes")

    system_disk = _disk_for_path("C:\\" if os.name == "nt" else "/")
    fafo_disk = _disk_for_path(fafo_local if fafo_local.exists() else toolbox_root)

    # Toolbox is this process — if we answer, server is up
    toolbox_listening = _port_listening(bind["host"], bind["port"])

    cpu = (overview.get("cpu") or {}) if overview else {}
    mem = (overview.get("memory") or {}) if overview else {}

    payload = {
        "ok": True,
        "generatedAt": _utc_now(),
        "cacheTtlSec": _CACHE_TTL_SEC,
        "host": {
            "hostname": overview.get("hostname") or socket.gethostname(),
            "platform": overview.get("platform") or platform.platform(),
            "os": platform.system(),
            "osRelease": platform.release(),
            "python": platform.python_version(),
        },
        "uptime": {
            "seconds": uptime,
            "human": _format_uptime(uptime) if uptime is not None else None,
            "bootTime": overview.get("boot_time") if overview else None,
        },
        "cpu": {
            "percent": cpu.get("percent"),
            "coresLogical": cpu.get("cores_logical"),
            "coresPhysical": cpu.get("cores_physical"),
        },
        "memory": {
            "percent": mem.get("percent"),
            "totalHuman": mem.get("total_human"),
            "usedHuman": mem.get("used_human"),
            "availableHuman": _bytes_human(mem.get("available") or 0) if mem else None,
        },
        "diskSystem": system_disk,
        "diskFafoData": fafo_disk,
        "paths": {
            "fafoLocal": str(fafo_local),
            "toolboxRoot": str(toolbox_root),
            "secretsDir": str(_fafo_secrets_dir()),
        },
        "processes": procs,
        "toolbox": {
            "serverUp": True,  # this handler ran
            "bindHost": bind["host"],
            "bindPort": bind["port"],
            "endpoint": bind["endpoint"],
            "portListening": toolbox_listening,
            "healthPath": "/api/health",
        },
        "xeroPresence": _xero_presence(),
        "errors": errors,
        "securityNote": "No secrets/tokens/cmdlines returned. Presence and metrics only.",
    }

    with _lock:
        _health_cache["at"] = now
        _health_cache["data"] = payload
    return payload


def _format_uptime(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    s = int(seconds)
    days, s = divmod(s, 86400)
    hours, s = divmod(s, 3600)
    mins, _ = divmod(s, 60)
    if days:
        return f"{days}d {hours}h {mins}m"
    if hours:
        return f"{hours}h {mins}m"
    return f"{mins}m"


def get_secrets_presence(*, force: bool = False) -> dict[str, Any]:
    """
    Secrets Presence Console payload.
    Lists secret *names* and whether a DPAPI blob file exists. Never decrypts.
    """
    now = time.time()
    with _lock:
        if not force and _presence_cache["data"] and (now - float(_presence_cache["at"] or 0)) < _CACHE_TTL_SEC:
            return _presence_cache["data"]

    secrets_dir = _fafo_secrets_dir()
    found: dict[str, dict[str, Any]] = {}

    # Scan directory for *.xml secret files (name = stem) — existence + mtime only
    try:
        if secrets_dir.is_dir():
            for p in secrets_dir.iterdir():
                if not p.is_file():
                    continue
                if p.suffix.lower() != ".xml":
                    continue
                name = p.stem
                if not name or name.startswith("."):
                    continue
                # Reject path traversal / odd names
                if "/" in name or "\\" in name or ".." in name:
                    continue
                try:
                    mtime = p.stat().st_mtime
                    age = max(0, int(now - mtime))
                except OSError:
                    mtime = None
                    age = None
                found[name] = {
                    "name": name,
                    "has": True,
                    "ageSeconds": age,
                    "updatedAt": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat() if mtime else None,
                }
    except OSError as e:
        # degrade: empty found list
        found_error = str(e)[:160]
    else:
        found_error = None

    # Ensure known keys appear even when missing
    secrets_list: list[dict[str, Any]] = []
    names_seen = set()
    for name in KNOWN_SECRET_NAMES:
        names_seen.add(name)
        if name in found:
            secrets_list.append(found[name])
        else:
            secrets_list.append({
                "name": name,
                "has": False,
                "ageSeconds": None,
                "updatedAt": None,
            })
    # Additional files not in known list (still name-only)
    for name, row in sorted(found.items()):
        if name not in names_seen:
            secrets_list.append(row)

    # Boolean map for quick UI
    flags = {row["name"]: bool(row["has"]) for row in secrets_list}

    payload = {
        "ok": True,
        "generatedAt": _utc_now(),
        "cacheTtlSec": _CACHE_TTL_SEC,
        "secretsDir": str(secrets_dir),
        "secretsDirExists": secrets_dir.is_dir(),
        "secrets": secrets_list,
        "flags": flags,
        "xero": _xero_presence(),
        "storeHint": {
            "xero": "Open LedgerLink Console → Store Client Secret (DPAPI). Values are never shown here.",
            "abuseCh": "Malware Defender / security config stores abuse.ch key via DPAPI if configured.",
        },
        "links": {
            "ledgerLink": "Business Tax Preparedness/LedgerLink Console.html",
            "malwareDefender": "System Tools/Malware Defender.html",
        },
        "banner": "Values never shown in this UI — presence flags only.",
        "securityNote": "Never returns secret material, tokens, or DPAPI bytes.",
        "error": found_error,
    }

    with _lock:
        _presence_cache["at"] = now
        _presence_cache["data"] = payload
    return payload
