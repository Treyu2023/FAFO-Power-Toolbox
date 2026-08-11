"""
Windows Event Viewer helpers — sample System/Application logs,
group into plain-English themes for the Home Health Hub.
"""
from __future__ import annotations

import json
import platform
import re
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

IS_WINDOWS = platform.system() == "Windows"
_CREATE_FLAGS = subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0
_DATA_PATH = Path(__file__).resolve().parent / "data" / "event_themes.json"

_CACHE_LOCK = threading.Lock()
_CACHE: dict[str, Any] = {"key": None, "at": 0.0, "payload": None}
_CACHE_TTL = 45.0


def clear_cache() -> None:
    with _CACHE_LOCK:
        _CACHE["key"] = None
        _CACHE["at"] = 0.0
        _CACHE["payload"] = None

# Level: 1 Critical, 2 Error, 3 Warning (WinEvent)
_LEVEL_NAME = {1: "critical", 2: "error", 3: "warning", 4: "information", 5: "verbose"}
_LEVEL_TO_UI = {
    "critical": "error",
    "error": "error",
    "warning": "warn",
    "information": "info",
    "verbose": "info",
}
_LEVEL_RANK = {"ok": 0, "info": 1, "warn": 2, "error": 3}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _worse(a: str, b: str) -> str:
    return a if _LEVEL_RANK.get(a, 0) >= _LEVEL_RANK.get(b, 0) else b


def _load_themes() -> dict[str, Any]:
    try:
        return json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "themes": [],
            "defaultTheme": {
                "id": "unknown",
                "title": "Other messages",
                "plainEnglish": "Unclassified event log entries.",
                "care": "Review if something is broken",
                "level": "info",
            },
        }


def _run_ps(script: str, timeout: float = 45) -> tuple[str, str, int]:
    try:
        p = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=_CREATE_FLAGS,
            errors="replace",
        )
        return p.stdout or "", p.stderr or "", p.returncode
    except subprocess.TimeoutExpired:
        return "", "timeout", 124
    except OSError as e:
        return "", str(e), 1


def _query_events_raw(
    *,
    hours: int = 24,
    max_events: int = 400,
    log_names: list[str] | None = None,
    levels: list[int] | None = None,
) -> list[dict[str, Any]]:
    """Pull recent events via Get-WinEvent → JSON."""
    if not IS_WINDOWS:
        return []

    logs = log_names or ["System", "Application"]
    lvls = levels or [1, 2, 3]
    # Sanitize
    hours = max(1, min(int(hours), 168))
    max_events = max(10, min(int(max_events), 1000))
    safe_logs = [x for x in logs if re.match(r"^[A-Za-z0-9_\- /]+$", x)]
    if not safe_logs:
        safe_logs = ["System", "Application"]
    safe_levels = [int(x) for x in lvls if int(x) in (1, 2, 3, 4)]
    if not safe_levels:
        safe_levels = [1, 2, 3]

    logs_ps = ",".join(f"'{x}'" for x in safe_logs)
    levels_ps = ",".join(str(x) for x in safe_levels)

    # Per-log cap so one noisy log doesn't starve the other
    per = max(20, max_events // max(1, len(safe_logs)))

    script = f"""
$ErrorActionPreference = 'SilentlyContinue'
$start = (Get-Date).AddHours(-{hours})
$logs = @({logs_ps})
$levels = @({levels_ps})
$all = @()
foreach ($log in $logs) {{
  try {{
    $ev = Get-WinEvent -FilterHashtable @{{ LogName = $log; Level = $levels; StartTime = $start }} -MaxEvents {per}
    foreach ($e in $ev) {{
      $msg = ''
      try {{ $msg = $e.Message }} catch {{}}
      if ($msg -and $msg.Length -gt 500) {{ $msg = $msg.Substring(0, 500) }}
      $all += [pscustomobject]@{{
        id = [int]$e.Id
        level = [int]$e.Level
        levelDisplay = [string]$e.LevelDisplayName
        provider = [string]$e.ProviderName
        log = [string]$e.LogName
        time = $e.TimeCreated.ToUniversalTime().ToString('o')
        message = [string]$msg
      }}
    }}
  }} catch {{}}
}}
$all | Sort-Object time -Descending | Select-Object -First {max_events} | ConvertTo-Json -Compress -Depth 4
"""
    # Tighter timeout for lite samples; deep samples still get headroom
    ps_timeout = 25 if max_events <= 200 else (40 if max_events <= 450 else 55)
    out, err, code = _run_ps(script, timeout=ps_timeout)
    if not out.strip():
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return []

    rows = []
    for e in data:
        lvl_num = int(e.get("level") or 0)
        lvl_name = _LEVEL_NAME.get(lvl_num, (e.get("levelDisplay") or "unknown").lower())
        rows.append({
            "id": e.get("id"),
            "level": lvl_name,
            "levelNum": lvl_num,
            "uiLevel": _LEVEL_TO_UI.get(lvl_name, "info"),
            "provider": e.get("provider") or "",
            "log": e.get("log") or "",
            "time": e.get("time") or "",
            "message": e.get("message") or "",
        })
    return rows


def _match_theme(event: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    provider = (event.get("provider") or "").lower()
    message = (event.get("message") or "").lower()
    eid = event.get("id")

    for theme in catalog.get("themes") or []:
        # Event ID match (optional)
        ids = theme.get("eventIds") or []
        if ids and eid is not None and int(eid) in [int(x) for x in ids]:
            # Still require provider-ish if listed
            provs = [p.lower() for p in (theme.get("providers") or [])]
            if not provs or any(p in provider for p in provs):
                return theme

        for p in theme.get("providers") or []:
            pl = p.lower()
            if pl and pl in provider:
                return theme

        for needle in theme.get("messageIncludes") or []:
            n = needle.lower()
            if n and n in message:
                # Prefer if provider also soft-matches when providers listed
                return theme

    return catalog.get("defaultTheme") or {
        "id": "unknown",
        "title": "Other messages",
        "plainEnglish": "Unclassified event log entries.",
        "care": "Review if something is broken",
        "level": "info",
    }


def _aggregate_themes(events: list[dict[str, Any]], catalog: dict[str, Any]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for ev in events:
        theme = _match_theme(ev, catalog)
        tid = theme.get("id") or "unknown"
        if tid not in buckets:
            buckets[tid] = {
                "id": tid,
                "title": theme.get("title") or tid,
                "plainEnglish": theme.get("plainEnglish") or "",
                "care": theme.get("care") or "",
                "level": theme.get("level") or "info",
                "count": 0,
                "errorCount": 0,
                "warningCount": 0,
                "providers": set(),
                "sampleMessage": "",
                "latestTime": "",
            }
        b = buckets[tid]
        b["count"] += 1
        if ev.get("uiLevel") == "error":
            b["errorCount"] += 1
        elif ev.get("uiLevel") == "warn":
            b["warningCount"] += 1
        if ev.get("provider"):
            b["providers"].add(ev["provider"])
        if not b["sampleMessage"] and ev.get("message"):
            b["sampleMessage"] = (ev["message"] or "")[:240]
        t = ev.get("time") or ""
        if t and (not b["latestTime"] or t > b["latestTime"]):
            b["latestTime"] = t
        # Escalate theme level if raw events are worse and theme was soft
        if theme.get("level") in ("ok", "info") and ev.get("uiLevel") == "error" and tid == "unknown":
            b["level"] = "warn"

    out = []
    for b in buckets.values():
        out.append({
            "id": b["id"],
            "title": b["title"],
            "plainEnglish": b["plainEnglish"],
            "care": b["care"],
            "level": b["level"],
            "count": b["count"],
            "errorCount": b["errorCount"],
            "warningCount": b["warningCount"],
            "providers": sorted(b["providers"])[:12],
            "sampleMessage": b["sampleMessage"],
            "latestTime": b["latestTime"],
        })

    out.sort(key=lambda x: (-_LEVEL_RANK.get(x["level"], 0), -x["count"]))
    return out


def _filter_events(
    events: list[dict[str, Any]],
    *,
    provider: str = "",
    q: str = "",
    theme_id: str = "",
    catalog: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    catalog = catalog or _load_themes()
    provider_l = provider.lower().strip()
    q_l = q.lower().strip()
    out = []
    for ev in events:
        if provider_l and provider_l not in (ev.get("provider") or "").lower():
            continue
        if q_l:
            blob = f"{ev.get('provider','')} {ev.get('message','')} {ev.get('id','')}".lower()
            if q_l not in blob:
                continue
        if theme_id:
            th = _match_theme(ev, catalog)
            if (th.get("id") or "") != theme_id:
                continue
        # Attach theme id for UI
        th = _match_theme(ev, catalog)
        row = dict(ev)
        row["themeId"] = th.get("id")
        row["themeTitle"] = th.get("title")
        row["themeLevel"] = th.get("level")
        out.append(row)
    return out


def get_summary(hours: int = 24, max_events: int = 400) -> dict[str, Any]:
    """Cached summary + themes for hub and Event Viewer home."""
    hours = max(1, min(int(hours), 168))
    max_events = max(10, min(int(max_events), 1000))
    key = f"sum:{hours}:{max_events}"
    now = time.time()

    with _CACHE_LOCK:
        if _CACHE["key"] == key and _CACHE["payload"] and (now - _CACHE["at"]) < _CACHE_TTL:
            return _CACHE["payload"]

    if not IS_WINDOWS:
        payload = {
            "timestamp": _utc_now(),
            "platform": platform.system(),
            "supported": False,
            "windowHours": hours,
            "errorCount": 0,
            "warningCount": 0,
            "criticalCount": 0,
            "sampled": 0,
            "themes": [],
            "note": "Event log sampling is Windows-only.",
        }
        return payload

    events = _query_events_raw(hours=hours, max_events=max_events)
    catalog = _load_themes()
    themes = _aggregate_themes(events, catalog)

    err_n = sum(1 for e in events if e.get("level") in ("error", "critical"))
    warn_n = sum(1 for e in events if e.get("level") == "warning")
    crit_n = sum(1 for e in events if e.get("level") == "critical")

    # Hub-facing worst level from non-ok themes with real volume
    worst = "ok"
    for t in themes:
        if t["level"] in ("ok",) and t["id"] != "unknown":
            continue
        if t["level"] == "ok":
            continue
        # ok themes that are pure noise stay ok
        if t.get("level") == "ok":
            continue
        worst = _worse(worst, t["level"])

    # If only ok/info themes, stay info/ok even if raw warning counts high (DCOM etc.)
    actionable = [t for t in themes if t["level"] in ("warn", "error") and t["id"] != "unknown"]
    if actionable:
        worst = "ok"
        for t in actionable:
            worst = _worse(worst, t["level"])
    else:
        # All classified as fine/FYI
        if themes:
            worst = "ok" if all(t["level"] == "ok" for t in themes) else "info"
        else:
            worst = "ok"

    payload = {
        "timestamp": _utc_now(),
        "supported": True,
        "windowHours": hours,
        "errorCount": err_n,
        "warningCount": warn_n,
        "criticalCount": crit_n,
        "sampled": len(events),
        "level": worst,
        "themes": themes,
        "note": f"Sampled up to {max_events} System/Application errors & warnings from the last {hours}h.",
    }

    with _CACHE_LOCK:
        _CACHE["key"] = key
        _CACHE["at"] = now
        _CACHE["payload"] = payload
    return payload


def query_events(
    *,
    hours: int = 24,
    max_events: int = 200,
    log: str = "",
    level: str = "",
    provider: str = "",
    q: str = "",
    theme_id: str = "",
) -> dict[str, Any]:
    """Filtered event rows for Event Viewer timeline."""
    hours = max(1, min(int(hours), 168))
    max_events = max(10, min(int(max_events), 1000))

    logs = None
    if log:
        logs = [x.strip() for x in log.split(",") if x.strip()]

    levels = None
    if level:
        name_map = {
            "critical": 1,
            "error": 2,
            "warning": 3,
            "warn": 3,
            "information": 4,
            "info": 4,
        }
        levels = []
        for part in level.split(","):
            p = part.strip().lower()
            if p.isdigit():
                levels.append(int(p))
            elif p in name_map:
                levels.append(name_map[p])
        if not levels:
            levels = None

    raw = _query_events_raw(hours=hours, max_events=max(max_events, 400), log_names=logs, levels=levels)
    catalog = _load_themes()
    filtered = _filter_events(raw, provider=provider, q=q, theme_id=theme_id, catalog=catalog)
    total = len(filtered)
    limited = filtered[:max_events]

    return {
        "timestamp": _utc_now(),
        "supported": IS_WINDOWS,
        "windowHours": hours,
        "total": total,
        "limited": total > max_events,
        "events": limited,
    }


def get_themes_only(hours: int = 24) -> dict[str, Any]:
    s = get_summary(hours=hours)
    return {
        "timestamp": s.get("timestamp"),
        "windowHours": s.get("windowHours"),
        "level": s.get("level"),
        "themes": s.get("themes") or [],
        "sampled": s.get("sampled"),
        "errorCount": s.get("errorCount"),
        "warningCount": s.get("warningCount"),
    }


def hub_events_preview(hours: int = 24) -> dict[str, Any]:
    """Compact block for /api/health/dashboard."""
    try:
        # Keep hub light — full Event Viewer can pull a larger sample on demand
        s = get_summary(hours=hours, max_events=200)
    except Exception as e:
        return {
            "windowHours": hours,
            "errorCount": None,
            "warningCount": None,
            "themes": [],
            "level": "info",
            "note": f"Event sample failed: {e}",
            "supported": IS_WINDOWS,
        }

    themes = s.get("themes") or []
    # Prefer non-ok themes for hub cards; keep top few overall
    primary = [t for t in themes if t.get("level") in ("warn", "error")][:5]
    if len(primary) < 3:
        for t in themes:
            if t in primary:
                continue
            primary.append(t)
            if len(primary) >= 5:
                break

    return {
        "windowHours": s.get("windowHours"),
        "errorCount": s.get("errorCount"),
        "warningCount": s.get("warningCount"),
        "criticalCount": s.get("criticalCount"),
        "sampled": s.get("sampled"),
        "level": s.get("level") or "ok",
        "themes": primary,
        "note": s.get("note"),
        "supported": s.get("supported", True),
        "timestamp": s.get("timestamp"),
    }
