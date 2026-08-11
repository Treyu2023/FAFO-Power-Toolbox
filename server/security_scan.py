"""
Malware Defender — open-source threat intel, AV remnant detection, quarantine.
Updates hash databases from public feeds on each scan run.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import psutil

IS_WINDOWS = platform.system() == "Windows"
SERVER_DIR = Path(__file__).resolve().parent
DATA_DIR = SERVER_DIR / "data"
QUARANTINE_DIR = SERVER_DIR / "quarantine"
INTEL_DB = SERVER_DIR / "threat_intel.db"
REMANTS_FILE = DATA_DIR / "av_remnants.json"
CONFIG_FILE = SERVER_DIR / "security_config.json"

# Non-secret prefs only. Real auth keys never live here.
# Secret load order for abuse.ch (see _get_abuse_ch_auth_key):
#   1) os.environ["ABUSE_CH_AUTH_KEY"]  (e.g. after Initialize-FAFOSession.ps1)
#   2) DPAPI blob at %LOCALAPPDATA%\FAFO\Secrets\ABUSE_CH_AUTH_KEY.xml
#   3) empty string (feature disabled) — never read a real key from security_config.json
ABUSE_CH_SECRET_NAME = "ABUSE_CH_AUTH_KEY"
FAFO_SECRETS_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "FAFO" / "Secrets"

HASH_FEEDS = [
    {
        "name": "malicious-hash-md5",
        "url": "https://raw.githubusercontent.com/romainmarcoux/malicious-hash/main/full-hash-md5-aa.txt",
        "hash_type": "md5",
        "source": "romainmarcoux/malicious-hash (abuse.ch, URLhaus, OTX)",
    },
    {
        "name": "malicious-hash-sha1",
        "url": "https://raw.githubusercontent.com/romainmarcoux/malicious-hash/main/full-hash-sha1-aa.txt",
        "hash_type": "sha1",
        "source": "romainmarcoux/malicious-hash (abuse.ch, URLhaus, OTX)",
    },
    {
        "name": "malicious-hash-sha256",
        "url": "https://raw.githubusercontent.com/romainmarcoux/malicious-hash/main/full-hash-sha256-aa.txt",
        "hash_type": "sha256",
        "source": "romainmarcoux/malicious-hash (abuse.ch, URLhaus, OTX)",
    },
]

SCANNABLE_EXT = {
    ".exe", ".dll", ".sys", ".scr", ".com", ".bat", ".cmd", ".ps1", ".vbs", ".js",
    ".jar", ".msi", ".msp", ".hta", ".wsf", ".cpl", ".inf", ".reg",
}

ProgressFn = Callable[[str, str, dict[str, Any] | None], None]

_intel_cache: dict[str, set[str]] = {}
_intel_cache_time = 0.0
_scan_lock = threading.Lock()
_active_scan: dict[str, Any] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _expand_path(p: str) -> Path:
    expanded = os.path.expandvars(p)
    return Path(expanded)


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi_protect(plain: bytes) -> bytes:
    """Windows DPAPI CurrentUser encrypt (same family as PowerShell ProtectedData)."""
    if not IS_WINDOWS:
        raise RuntimeError("DPAPI is only available on Windows")
    blob_in = _DATA_BLOB(len(plain), ctypes.create_string_buffer(plain, len(plain)))
    blob_out = _DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise OSError("CryptProtectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _dpapi_unprotect(encrypted: bytes) -> bytes:
    """Windows DPAPI CurrentUser decrypt."""
    if not IS_WINDOWS:
        raise RuntimeError("DPAPI is only available on Windows")
    blob_in = _DATA_BLOB(len(encrypted), ctypes.create_string_buffer(encrypted, len(encrypted)))
    blob_out = _DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise OSError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _secret_path(name: str) -> Path:
    return FAFO_SECRETS_DIR / f"{name}.xml"


def _read_dpapi_secret(name: str) -> str:
    path = _secret_path(name)
    if not path.is_file():
        return ""
    try:
        return _dpapi_unprotect(path.read_bytes()).decode("utf-8")
    except (OSError, UnicodeDecodeError, ValueError):
        return ""


def _write_dpapi_secret(name: str, value: str) -> None:
    FAFO_SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    path = _secret_path(name)
    path.write_bytes(_dpapi_protect(value.encode("utf-8")))


def _get_abuse_ch_auth_key() -> str:
    """
    Resolve abuse.ch auth key without using plaintext JSON.

    Order:
      1. Environment variable ABUSE_CH_AUTH_KEY (prefer pre-load via Initialize-FAFOSession.ps1)
      2. DPAPI file %LOCALAPPDATA%\\FAFO\\Secrets\\ABUSE_CH_AUTH_KEY.xml
      3. Empty string (MalwareBazaar recent feed skipped)
    Never falls back to security_config.json for the real key.
    """
    env_val = (os.environ.get(ABUSE_CH_SECRET_NAME) or "").strip()
    if env_val:
        return env_val
    return _read_dpapi_secret(ABUSE_CH_SECRET_NAME).strip()


def _store_abuse_ch_auth_key(value: str) -> None:
    """Persist key via DPAPI + process env. Never write the secret into JSON."""
    value = (value or "").strip()
    if not value:
        path = _secret_path(ABUSE_CH_SECRET_NAME)
        if path.is_file():
            path.unlink()
        os.environ.pop(ABUSE_CH_SECRET_NAME, None)
        return
    _write_dpapi_secret(ABUSE_CH_SECRET_NAME, value)
    os.environ[ABUSE_CH_SECRET_NAME] = value


def _load_config() -> dict[str, Any]:
    """Load non-secret security prefs only (never returns a real auth key)."""
    data: dict[str, Any] = {}
    if CONFIG_FILE.is_file():
        try:
            raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data = raw
        except (OSError, json.JSONDecodeError):
            data = {}
    # Strip any legacy plaintext key fields if present
    data.pop("abuse_ch_auth_key", None)
    data["has_abuse_ch_key"] = bool(_get_abuse_ch_auth_key())
    return data


def save_config(data: dict[str, Any]) -> dict[str, Any]:
    """
    Update security prefs. If abuse_ch_auth_key is supplied (e.g. from Malware Defender UI),
    store it in DPAPI + env — never in security_config.json.
    """
    payload = dict(data or {})
    if "abuse_ch_auth_key" in payload:
        _store_abuse_ch_auth_key(str(payload.pop("abuse_ch_auth_key") or ""))

    current = _load_config()
    # Only persist non-secret flags to disk
    current.pop("abuse_ch_auth_key", None)
    for k, v in payload.items():
        if k == "abuse_ch_auth_key":
            continue
        current[k] = v
    current["has_abuse_ch_key"] = bool(_get_abuse_ch_auth_key())
    CONFIG_FILE.write_text(
        json.dumps({"has_abuse_ch_key": current["has_abuse_ch_key"]}, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "ok": True,
        "has_abuse_ch_key": current["has_abuse_ch_key"],
    }


def _init_db() -> None:
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(INTEL_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS threat_hashes (
            hash TEXT NOT NULL,
            hash_type TEXT NOT NULL,
            source TEXT,
            feed TEXT,
            updated_at TEXT,
            PRIMARY KEY (hash, hash_type)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS intel_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quarantine_log (
            id TEXT PRIMARY KEY,
            original_path TEXT,
            quarantine_path TEXT,
            threat_type TEXT,
            threat_name TEXT,
            sha256 TEXT,
            quarantined_at TEXT,
            restored INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


_init_db()


def _set_meta(key: str, value: str) -> None:
    conn = sqlite3.connect(INTEL_DB)
    conn.execute(
        "INSERT OR REPLACE INTO intel_meta (key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()
    conn.close()


def _get_meta(key: str, default: str = "") -> str:
    conn = sqlite3.connect(INTEL_DB)
    row = conn.execute("SELECT value FROM intel_meta WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row[0] if row else default


def _download_url(url: str, timeout: float = 60.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "AI-Toolbox-MalwareDefender/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _fetch_abuse_ch_hashes(auth_key: str) -> list[tuple[str, str, str]]:
    """Optional MalwareBazaar recent hashes if user provides free abuse.ch key."""
    if not auth_key:
        return []
    url = f"https://mb-api.abuse.ch/v2/files/exports/{auth_key}/recent.csv"
    try:
        text = _download_url(url, timeout=45)
    except (urllib.error.URLError, TimeoutError, OSError):
        return []
    rows = []
    lines = text.strip().splitlines()
    if len(lines) < 2:
        return []
    header = [h.strip().lower() for h in lines[0].split(",")]
    sha_idx = next((i for i, h in enumerate(header) if "sha256" in h), None)
    if sha_idx is None:
        return []
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) > sha_idx:
            h = parts[sha_idx].strip().strip('"').lower()
            if len(h) == 64:
                rows.append((h, "sha256", "MalwareBazaar/recent"))
    return rows


def update_threat_intel(
    on_progress: ProgressFn | None = None,
) -> dict[str, Any]:
    global _intel_cache, _intel_cache_time

    def prog(phase: str, msg: str, extra: dict | None = None):
        if on_progress:
            on_progress(phase, msg, extra)

    prog("update", "Starting threat intelligence update…")
    conn = sqlite3.connect(INTEL_DB)
    now = _utc_now()
    total_added = 0
    feed_results = []

    for feed in HASH_FEEDS:
        prog("update", f"Downloading {feed['name']}…", {"feed": feed["name"]})
        try:
            text = _download_url(feed["url"], timeout=90)
            hashes = [ln.strip().lower() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
            conn.execute("DELETE FROM threat_hashes WHERE feed = ?", (feed["name"],))
            batch = [(h, feed["hash_type"], feed["source"], feed["name"], now) for h in hashes if len(h) >= 32]
            conn.executemany(
                "INSERT OR REPLACE INTO threat_hashes (hash, hash_type, source, feed, updated_at) VALUES (?, ?, ?, ?, ?)",
                batch,
            )
            conn.commit()
            total_added += len(batch)
            feed_results.append({"feed": feed["name"], "count": len(batch), "ok": True})
            prog("update", f"{feed['name']}: {len(batch):,} hashes", {"count": len(batch)})
        except Exception as e:
            feed_results.append({"feed": feed["name"], "count": 0, "ok": False, "error": str(e)})
            prog("update", f"{feed['name']} failed: {e}", {"error": str(e)})

    abuse_rows = _fetch_abuse_ch_hashes(_get_abuse_ch_auth_key())
    if abuse_rows:
        conn.executemany(
            "INSERT OR REPLACE INTO threat_hashes (hash, hash_type, source, feed, updated_at) VALUES (?, ?, ?, ?, ?)",
            [(h, t, s, "malwarebazaar-recent", now) for h, t, s in abuse_rows],
        )
        conn.commit()
        total_added += len(abuse_rows)
        feed_results.append({"feed": "malwarebazaar-recent", "count": len(abuse_rows), "ok": True})
        prog("update", f"MalwareBazaar recent: {len(abuse_rows):,} hashes")

    conn.close()
    _intel_cache.clear()
    _intel_cache_time = 0
    _set_meta("last_update", now)
    _set_meta("total_hashes", str(total_added))

    result = {
        "ok": any(f["ok"] for f in feed_results),
        "updated_at": now,
        "total_hashes": total_added,
        "feeds": feed_results,
    }
    prog("update", f"Database updated — {total_added:,} total hashes", result)
    return result


def get_intel_status() -> dict[str, Any]:
    conn = sqlite3.connect(INTEL_DB)
    counts = conn.execute(
        "SELECT hash_type, COUNT(*) FROM threat_hashes GROUP BY hash_type"
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM threat_hashes").fetchone()[0]
    conn.close()
    elevated = False
    if sys.platform == "win32":
        try:
            import ctypes

            elevated = bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
        except Exception:
            elevated = False
    needs = []
    if not elevated:
        needs.append(
            {
                "id": "elevation",
                "level": "info",
                "title": "Server not elevated",
                "detail": (
                    "Scans of user folders and process lists work without admin. "
                    "Quarantine/delete under protected paths (Program Files, System32) may fail — "
                    "restart the toolbox server as Administrator for full remediations."
                ),
            }
        )
    if not _get_abuse_ch_auth_key():
        needs.append(
            {
                "id": "abuse_ch",
                "level": "info",
                "title": "Optional abuse.ch key",
                "detail": "Live MalwareBazaar recent hashes need a free Auth-Key (saved via FAFO Secrets / this page).",
            }
        )
    if total <= 0:
        needs.append(
            {
                "id": "threat_db",
                "level": "warn",
                "title": "Threat DB empty",
                "detail": "Run Update DB or a Full/Quick scan once to pull open hash feeds.",
            }
        )
    return {
        "last_update": _get_meta("last_update"),
        "total_hashes": total,
        "by_type": {t: c for t, c in counts},
        "feeds": [f["name"] for f in HASH_FEEDS],
        "has_abuse_ch_key": bool(_get_abuse_ch_auth_key()),
        "quarantine_dir": str(QUARANTINE_DIR),
        "is_elevated": elevated,
        "capabilities": {
            "scan_user_space": True,
            "scan_processes": True,
            "quarantine_user_files": True,
            "quarantine_protected_paths": elevated,
            "hosts_style_system_writes": elevated,
        },
        "needs": needs,
    }


def _load_hash_sets() -> dict[str, set[str]]:
    global _intel_cache, _intel_cache_time
    now = time.time()
    if _intel_cache and now - _intel_cache_time < 120:
        return _intel_cache

    conn = sqlite3.connect(INTEL_DB)
    sets: dict[str, set[str]] = {"md5": set(), "sha1": set(), "sha256": set()}
    for row in conn.execute("SELECT hash, hash_type FROM threat_hashes"):
        h, ht = row[0].lower(), row[1].lower()
        if ht in sets:
            sets[ht].add(h)
    conn.close()
    _intel_cache = sets
    _intel_cache_time = now
    return sets


def _file_hashes(path: Path) -> dict[str, str]:
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                md5.update(chunk)
                sha1.update(chunk)
                sha256.update(chunk)
    except OSError:
        return {}
    return {
        "md5": md5.hexdigest().lower(),
        "sha1": sha1.hexdigest().lower(),
        "sha256": sha256.hexdigest().lower(),
    }


def _match_hash(hashes: dict[str, str], intel: dict[str, set[str]]) -> str | None:
    for ht in ("sha256", "sha1", "md5"):
        h = hashes.get(ht)
        if h and h in intel.get(ht, set()):
            return ht
    return None


def _load_remnants() -> dict[str, Any]:
    return json.loads(REMANTS_FILE.read_text(encoding="utf-8"))


def _path_exists_pattern(pattern: str) -> list[dict[str, str]]:
    base = _expand_path(pattern)
    if "*" in pattern:
        parent = base.parent
        glob_pat = base.name
        if not parent.exists():
            return []
        return [{"path": str(p), "type": "path"} for p in parent.glob(glob_pat) if p.exists()]
    if base.exists():
        return [{"path": str(base), "type": "path"}]
    return []


def _scan_av_remnants(intel: dict[str, set[str]], on_progress: ProgressFn | None = None) -> list[dict[str, Any]]:
    data = _load_remnants()
    findings: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(item: dict[str, Any]):
        key = f"{item['threat_type']}:{item.get('path') or item.get('name')}"
        if key not in seen:
            seen.add(key)
            findings.append(item)

    for product in data.get("products", []):
        pname = product["name"]
        if on_progress:
            on_progress("scan", f"Checking {pname} remnants…", {"product": pname})

        for pat in product.get("paths", []):
            for hit in _path_exists_pattern(pat):
                add({
                    "id": str(uuid.uuid4()),
                    "threat_type": "expired_av",
                    "threat_name": f"{pname} leftover files",
                    "severity": product.get("risk", "medium"),
                    "path": hit["path"],
                    "detail": f"Expired/trial AV remnant: {pname}",
                    "product_id": product["id"],
                    "removable": True,
                    "action": "quarantine_or_delete",
                })

        for proc_name in product.get("processes", []):
            for p in psutil.process_iter(["pid", "name", "exe"]):
                try:
                    name = (p.info.get("name") or "").lower()
                    if proc_name.lower().replace("*", "") in name or (
                        "*" in proc_name and re.match(proc_name.replace("*", ".*"), name, re.I)
                    ):
                        exe = p.info.get("exe") or ""
                        add({
                            "id": str(uuid.uuid4()),
                            "threat_type": "expired_av",
                            "threat_name": f"{pname} running process",
                            "severity": product.get("risk", "medium"),
                            "path": exe,
                            "pid": p.info["pid"],
                            "detail": f"Active process from expired AV: {proc_name}",
                            "product_id": product["id"],
                            "removable": True,
                            "action": "kill_process",
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        if IS_WINDOWS:
            for svc_pat in product.get("services", []):
                try:
                    out = subprocess.run(
                        ["sc", "query", "state=", "all"],
                        capture_output=True, text=True, timeout=15,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    for block in out.stdout.split("SERVICE_NAME:"):
                        m = re.search(r"^\s*(.+)", block)
                        if not m:
                            continue
                        svc = m.group(1).strip()
                        if _wildcard_match(svc_pat, svc):
                            add({
                                "id": str(uuid.uuid4()),
                                "threat_type": "expired_av",
                                "threat_name": f"{pname} service",
                                "severity": product.get("risk", "medium"),
                                "path": svc,
                                "detail": f"Windows service from expired AV",
                                "product_id": product["id"],
                                "removable": True,
                                "action": "disable_service",
                            })
                except (subprocess.TimeoutExpired, OSError):
                    pass

            for task_pat in product.get("scheduled_tasks", []):
                try:
                    out = subprocess.run(
                        ["schtasks", "/Query", "/FO", "CSV", "/NH"],
                        capture_output=True, text=True, timeout=20,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    for line in out.stdout.splitlines():
                        if not line.strip():
                            continue
                        task = line.split(",")[0].strip('"')
                        if _wildcard_match(task_pat, task):
                            add({
                                "id": str(uuid.uuid4()),
                                "threat_type": "expired_av",
                                "threat_name": f"{pname} scheduled task",
                                "severity": product.get("risk", "low"),
                                "path": task,
                                "detail": "Scheduled task from expired AV subscription",
                                "product_id": product["id"],
                                "removable": True,
                                "action": "delete_task",
                            })
                except (subprocess.TimeoutExpired, OSError):
                    pass

    return findings


def _wildcard_match(pattern: str, value: str) -> bool:
    if "*" not in pattern:
        return pattern.lower() in value.lower()
    return bool(re.match("^" + re.escape(pattern).replace("\\*", ".*") + "$", value, re.I))


def _scan_processes(intel: dict[str, set[str]], on_progress: ProgressFn | None = None) -> list[dict[str, Any]]:
    findings = []
    suspicious_paths = [p.lower() for p in _load_remnants().get("suspicious_patterns", {}).get("process_paths", [])]

    for p in psutil.process_iter(["pid", "name", "exe", "username"]):
        try:
            info = p.info
            exe = info.get("exe") or ""
            if not exe:
                continue
            exe_path = Path(exe)
            if not exe_path.is_file():
                continue

            hashes = _file_hashes(exe_path)
            match = _match_hash(hashes, intel)
            if match:
                findings.append({
                    "id": str(uuid.uuid4()),
                    "threat_type": "malware_hash",
                    "threat_name": f"Known malware ({match})",
                    "severity": "critical",
                    "path": exe,
                    "pid": info["pid"],
                    "hashes": hashes,
                    "detail": f"Process matches open-source threat database ({match})",
                    "removable": True,
                    "action": "kill_and_quarantine",
                })
                continue

            exe_lower = exe.lower()
            for sp in suspicious_paths:
                if sp in exe_lower:
                    findings.append({
                        "id": str(uuid.uuid4()),
                        "threat_type": "heuristic",
                        "threat_name": "Suspicious process location",
                        "severity": "high",
                        "path": exe,
                        "pid": info["pid"],
                        "detail": f"Executable running from suspicious path: {sp}",
                        "removable": True,
                        "action": "kill_and_quarantine",
                    })
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue

    if on_progress:
        on_progress("scan", f"Scanned {len(findings)} suspicious processes", {"count": len(findings)})
    return findings


def _scan_startup(intel: dict[str, set[str]], on_progress: ProgressFn | None = None) -> list[dict[str, Any]]:
    findings = []
    startup_dirs = []
    if IS_WINDOWS:
        startup_dirs = [
            Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup",
            Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup",
        ]
    else:
        startup_dirs = [
            Path.home() / ".config" / "autostart",
        ]

    for sdir in startup_dirs:
        if not sdir.is_dir():
            continue
        for item in sdir.iterdir():
            target = item
            if item.suffix.lower() in (".lnk",) and IS_WINDOWS:
                continue
            if item.is_file() and item.suffix.lower() in SCANNABLE_EXT | {".lnk"}:
                if item.suffix.lower() in SCANNABLE_EXT:
                    hashes = _file_hashes(item)
                    if _match_hash(hashes, intel):
                        findings.append({
                            "id": str(uuid.uuid4()),
                            "threat_type": "malware_hash",
                            "threat_name": "Malware in startup",
                            "severity": "critical",
                            "path": str(item),
                            "hashes": hashes,
                            "detail": "Startup item matches threat database",
                            "removable": True,
                            "action": "quarantine_or_delete",
                        })
                else:
                    findings.append({
                        "id": str(uuid.uuid4()),
                        "threat_type": "startup",
                        "threat_name": "Startup entry",
                        "severity": "info",
                        "path": str(item),
                        "detail": "Review this startup item",
                        "removable": True,
                        "action": "quarantine_or_delete",
                    })

    if IS_WINDOWS:
        run_keys = [
            (r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run", "HKCU"),
            (r"HKLM\Software\Microsoft\Windows\CurrentVersion\Run", "HKLM"),
        ]
        for key, hive in run_keys:
            try:
                out = subprocess.run(
                    ["reg", "query", key],
                    capture_output=True, text=True, timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                for line in out.stdout.splitlines():
                    m = re.match(r"\s+(\S+)\s+REG_\w+\s+(.+)", line)
                    if m:
                        name, val = m.group(1), m.group(2).strip()
                        findings.append({
                            "id": str(uuid.uuid4()),
                            "threat_type": "startup",
                            "threat_name": f"Registry Run: {name}",
                            "severity": "medium",
                            "path": f"{key}\\{name}",
                            "detail": val,
                            "removable": True,
                            "action": "delete_registry",
                        })
            except (subprocess.TimeoutExpired, OSError):
                pass

    return findings


def _scan_directories(
    intel: dict[str, set[str]],
    roots: list[Path],
    max_files: int = 3000,
    on_progress: ProgressFn | None = None,
) -> list[dict[str, Any]]:
    findings = []
    scanned = 0
    patterns = _load_remnants().get("suspicious_patterns", {}).get("double_extensions", [])

    for root in roots:
        if not root.exists():
            continue
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d.lower() not in {
                    "node_modules", ".git", "windows", "program files", "program files (x86)",
                }]
                for fname in filenames:
                    if scanned >= max_files:
                        return findings
                    path = Path(dirpath) / fname
                    ext = path.suffix.lower()
                    if ext not in SCANNABLE_EXT:
                        lower = fname.lower()
                        if not any(lower.endswith(de) for de in patterns):
                            continue
                    try:
                        if path.stat().st_size > 80 * 1024 * 1024:
                            continue
                    except OSError:
                        continue
                    scanned += 1
                    if scanned % 100 == 0 and on_progress:
                        on_progress("scan", f"Scanning files… {scanned}", {"scanned": scanned})

                    hashes = _file_hashes(path)
                    match = _match_hash(hashes, intel)
                    if match:
                        findings.append({
                            "id": str(uuid.uuid4()),
                            "threat_type": "malware_hash",
                            "threat_name": f"Known malware file ({match})",
                            "severity": "critical",
                            "path": str(path),
                            "hashes": hashes,
                            "detail": f"File hash matches threat intel ({match})",
                            "removable": True,
                            "action": "quarantine_or_delete",
                        })
                    elif any(fname.lower().endswith(de) for de in patterns):
                        findings.append({
                            "id": str(uuid.uuid4()),
                            "threat_type": "heuristic",
                            "threat_name": "Double extension file",
                            "severity": "high",
                            "path": str(path),
                            "detail": "Suspicious double extension (common malware trick)",
                            "removable": True,
                            "action": "quarantine_or_delete",
                        })
        except (PermissionError, OSError):
            continue

    return findings


def _default_scan_roots() -> list[Path]:
    home = Path.home()
    roots = [
        home / "Downloads",
        home / "Desktop",
        home / "Documents",
        Path(os.environ.get("TEMP", home / "AppData" / "Local" / "Temp")),
        Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")),
    ]
    return [r for r in roots if r.exists()]


def run_scan(
    scan_type: str = "full",
    update_first: bool = True,
    on_progress: ProgressFn | None = None,
) -> dict[str, Any]:
    global _active_scan

    with _scan_lock:
        if _active_scan and _active_scan.get("running"):
            raise RuntimeError("A scan is already in progress")

    scan_id = str(uuid.uuid4())
    _active_scan = {"id": scan_id, "running": True, "type": scan_type}

    def prog(phase: str, msg: str, extra: dict | None = None):
        if on_progress:
            on_progress(phase, msg, extra)

    try:
        update_result = None
        if update_first:
            update_result = update_threat_intel(on_progress=prog)

        intel = _load_hash_sets()
        total_intel = sum(len(s) for s in intel.values())
        if total_intel == 0:
            raise RuntimeError("Threat database is empty — could not download feeds. Check internet connection.")

        prog("scan", f"Threat DB loaded: {total_intel:,} hashes", {"hashes": total_intel})
        findings: list[dict[str, Any]] = []

        if scan_type in ("full", "quick", "remnants"):
            prog("scan", "Scanning expired antivirus remnants…")
            findings.extend(_scan_av_remnants(intel, prog))

        if scan_type in ("full", "quick"):
            prog("scan", "Scanning running processes…")
            findings.extend(_scan_processes(intel, prog))
            prog("scan", "Scanning startup entries…")
            findings.extend(_scan_startup(intel, prog))

        if scan_type == "full":
            prog("scan", "Deep file scan (Downloads, Desktop, Temp…)…")
            findings.extend(_scan_directories(intel, _default_scan_roots(), on_progress=prog))

        # Deduplicate by path
        deduped: list[dict[str, Any]] = []
        seen_paths: set[str] = set()
        for f in findings:
            key = f.get("path", f["id"])
            if key not in seen_paths:
                seen_paths.add(key)
                deduped.append(f)

        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        deduped.sort(key=lambda x: severity_order.get(x.get("severity", "info"), 5))

        by_type: dict[str, int] = {}
        for f in deduped:
            by_type[f["threat_type"]] = by_type.get(f["threat_type"], 0) + 1

        result = {
            "scan_id": scan_id,
            "scan_type": scan_type,
            "completed_at": _utc_now(),
            "findings": deduped,
            "finding_count": len(deduped),
            "by_type": by_type,
            "intel_hashes": total_intel,
            "update": update_result,
        }
        prog("done", f"Scan complete — {len(deduped)} findings", {"count": len(deduped)})
        return result
    finally:
        with _scan_lock:
            _active_scan = {"id": scan_id, "running": False}


def _kill_pid(pid: int) -> bool:
    try:
        p = psutil.Process(pid)
        p.kill()
        return True
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def _disable_service(name: str) -> bool:
    if not IS_WINDOWS:
        return False
    try:
        subprocess.run(["sc", "stop", name], capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.run(["sc", "config", name, "start=", "disabled"], capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except (subprocess.TimeoutExpired, OSError):
        return False


def _delete_task(name: str) -> bool:
    if not IS_WINDOWS:
        return False
    try:
        subprocess.run(["schtasks", "/Delete", "/TN", name, "/F"], capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except (subprocess.TimeoutExpired, OSError):
        return False


def _delete_registry(path: str) -> bool:
    if not IS_WINDOWS:
        return False
    try:
        subprocess.run(["reg", "delete", path, "/f"], capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except (subprocess.TimeoutExpired, OSError):
        return False


def _is_process_elevated() -> bool:
    if not IS_WINDOWS:
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
    except Exception:
        return False


def is_protected_path(path: str) -> bool:
    """True for OS / Program Files paths that usually need elevation to remediate."""
    if not path:
        return False
    p = str(path).replace("/", "\\").lower().strip()
    # Normalize drive-relative
    prefixes = (
        r"c:\windows",
        r"c:\program files",
        r"c:\program files (x86)",
        r"c:\programdata",
        r"\windows\system32",
        r"\windows\syswow64",
        r"\program files",
        r"\program files (x86)",
        r"\programdata",
    )
    if any(p.startswith(pref) for pref in prefixes):
        return True
    # Also match without drive letter
    bare = p[2:] if len(p) > 2 and p[1] == ":" else p
    return any(bare.startswith(pref.lstrip("c:")) for pref in prefixes if pref.startswith(r"c:"))


def quarantine_item(path: str, threat_type: str = "", threat_name: str = "") -> dict[str, Any]:
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    qid = str(uuid.uuid4())[:8]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^\w.\-]", "_", src.name)[:80]
    dest = QUARANTINE_DIR / f"{ts}_{qid}_{safe_name}"

    hashes = _file_hashes(src) if src.is_file() else {}
    if src.is_file():
        shutil.move(str(src), str(dest))
    elif src.is_dir():
        shutil.move(str(src), str(dest))
    else:
        raise ValueError(f"Cannot quarantine: {path}")

    conn = sqlite3.connect(INTEL_DB)
    conn.execute(
        "INSERT INTO quarantine_log (id, original_path, quarantine_path, threat_type, threat_name, sha256, quarantined_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (qid, str(src), str(dest), threat_type, threat_name, hashes.get("sha256", ""), _utc_now()),
    )
    conn.commit()
    conn.close()

    return {"ok": True, "quarantine_path": str(dest), "original_path": str(src), "id": qid}


def remove_item(
    path: str,
    action: str = "quarantine_or_delete",
    pid: int | None = None,
    threat_type: str = "",
    threat_name: str = "",
    permanent: bool = False,
    *,
    allow_protected: bool = False,
) -> dict[str, Any]:
    results: dict[str, Any] = {"ok": True, "actions": [], "protected_path": is_protected_path(path)}

    if action in ("kill_process", "kill_and_quarantine") and pid:
        ok = _kill_pid(pid)
        results["actions"].append({"action": "kill_process", "pid": pid, "ok": ok})
        time.sleep(0.5)

    if action == "disable_service" and IS_WINDOWS:
        ok = _disable_service(path)
        results["actions"].append({"action": "disable_service", "path": path, "ok": ok})
        return results

    if action == "delete_task" and IS_WINDOWS:
        ok = _delete_task(path)
        results["actions"].append({"action": "delete_task", "path": path, "ok": ok})
        return results

    if action == "delete_registry" and IS_WINDOWS:
        ok = _delete_registry(path)
        results["actions"].append({"action": "delete_registry", "path": path, "ok": ok})
        return results

    target = Path(path)
    if not target.exists():
        results["ok"] = False
        results["error"] = "Path no longer exists"
        return results

    # Gate file remediations under protected OS/program paths
    if results["protected_path"]:
        elevated = _is_process_elevated()
        if not elevated:
            results["ok"] = False
            results["error"] = (
                "Protected path — restart the toolbox server as Administrator, "
                "then enable Protected-path remediation."
            )
            results["needs_elevation"] = True
            return results
        if not allow_protected:
            results["ok"] = False
            results["error"] = (
                "Protected path — enable Protected-path remediation mode in Malware Defender "
                "to quarantine/delete under Program Files / Windows."
            )
            results["needs_protected_mode"] = True
            return results

    if permanent:
        if target.is_file():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        results["actions"].append({"action": "delete", "path": path, "ok": True})
    else:
        q = quarantine_item(path, threat_type, threat_name)
        results["actions"].append({"action": "quarantine", **q})

    return results


def remove_findings(
    items: list[dict[str, Any]],
    permanent: bool = False,
    *,
    allow_protected: bool = False,
) -> dict[str, Any]:
    results = []
    for item in items:
        try:
            r = remove_item(
                path=item.get("path", ""),
                action=item.get("action", "quarantine_or_delete"),
                pid=item.get("pid"),
                threat_type=item.get("threat_type", ""),
                threat_name=item.get("threat_name", ""),
                permanent=permanent,
                allow_protected=allow_protected,
            )
            results.append({"item": item, **r})
        except Exception as e:
            results.append({"item": item, "ok": False, "error": str(e)})

    ok_count = sum(1 for r in results if r.get("ok"))
    skipped_protected = sum(
        1 for r in results if r.get("needs_protected_mode") or r.get("needs_elevation")
    )
    return {
        "ok": ok_count == len(results),
        "processed": len(results),
        "succeeded": ok_count,
        "skipped_protected": skipped_protected,
        "elevated": _is_process_elevated(),
        "allow_protected": allow_protected,
        "results": results,
    }


def list_quarantine() -> list[dict[str, Any]]:
    conn = sqlite3.connect(INTEL_DB)
    rows = conn.execute(
        "SELECT id, original_path, quarantine_path, threat_type, threat_name, sha256, quarantined_at, restored FROM quarantine_log WHERE restored = 0 ORDER BY quarantined_at DESC"
    ).fetchall()
    conn.close()
    return [
        {
            "id": r[0], "original_path": r[1], "quarantine_path": r[2],
            "threat_type": r[3], "threat_name": r[4], "sha256": r[5],
            "quarantined_at": r[6],
        }
        for r in rows
    ]


def restore_quarantine(qid: str) -> dict[str, Any]:
    conn = sqlite3.connect(INTEL_DB)
    row = conn.execute(
        "SELECT original_path, quarantine_path FROM quarantine_log WHERE id = ? AND restored = 0",
        (qid,),
    ).fetchone()
    if not row:
        conn.close()
        raise FileNotFoundError("Quarantine entry not found")

    original, quarantine = Path(row[0]), Path(row[1])
    original.parent.mkdir(parents=True, exist_ok=True)
    if quarantine.exists():
        shutil.move(str(quarantine), str(original))
    conn.execute("UPDATE quarantine_log SET restored = 1 WHERE id = ?", (qid,))
    conn.commit()
    conn.close()
    return {"ok": True, "restored_to": str(original)}