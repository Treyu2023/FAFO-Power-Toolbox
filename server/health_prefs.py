"""Device-local Health Hub alert prefs — snooze / dismiss (not in git)."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _device_id() -> str:
    name = os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "LOCAL"
    return re.sub(r"[^\w.\-]+", "-", name).upper()


def prefs_path() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "FAFO" / "Devices" / _device_id()
    return root / "Prefs" / "health-alerts.json"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_prefs() -> dict[str, Any]:
    path = prefs_path()
    if not path.is_file():
        return {"snoozed": {}, "dismissed": {}, "updatedAt": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"snoozed": {}, "dismissed": {}, "updatedAt": None}
    data.setdefault("snoozed", {})
    data.setdefault("dismissed", {})
    return data


def save_prefs(data: dict[str, Any]) -> dict[str, Any]:
    path = prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updatedAt"] = _iso(_utc_now())
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def _valid_alert_id(alert_id: str) -> bool:
    if not alert_id or len(alert_id) > 240:
        return False
    if any(c in alert_id for c in "\n\r\0"):
        return False
    return True


def snooze_alert(alert_id: str, hours: float = 24, reason: str = "") -> dict[str, Any]:
    if not _valid_alert_id(alert_id):
        raise ValueError("Invalid alert id")
    hours = max(0.25, min(float(hours), 24 * 30))  # 15m … 30d
    prefs = load_prefs()
    until = _utc_now() + timedelta(hours=hours)
    prefs["snoozed"][alert_id] = {
        "until": _iso(until),
        "hours": hours,
        "reason": reason or "",
        "at": _iso(_utc_now()),
    }
    # unsnooze dismiss if present
    prefs.get("dismissed", {}).pop(alert_id, None)
    save_prefs(prefs)
    return {"ok": True, "alertId": alert_id, "until": _iso(until), "prefs": get_public_prefs()}


def dismiss_alert(alert_id: str, reason: str = "") -> dict[str, Any]:
    if not _valid_alert_id(alert_id):
        raise ValueError("Invalid alert id")
    prefs = load_prefs()
    prefs.setdefault("dismissed", {})[alert_id] = {
        "at": _iso(_utc_now()),
        "reason": reason or "",
    }
    prefs.get("snoozed", {}).pop(alert_id, None)
    save_prefs(prefs)
    return {"ok": True, "alertId": alert_id, "prefs": get_public_prefs()}


def clear_alert(alert_id: str) -> dict[str, Any]:
    prefs = load_prefs()
    prefs.get("snoozed", {}).pop(alert_id, None)
    prefs.get("dismissed", {}).pop(alert_id, None)
    save_prefs(prefs)
    return {"ok": True, "alertId": alert_id, "prefs": get_public_prefs()}


def clear_all() -> dict[str, Any]:
    prefs = {"snoozed": {}, "dismissed": {}}
    save_prefs(prefs)
    return {"ok": True, "prefs": get_public_prefs()}


def get_public_prefs() -> dict[str, Any]:
    prefs = load_prefs()
    now = _utc_now()
    # prune expired snoozes in memory (lazy write)
    snoozed = {}
    dirty = False
    for aid, meta in list((prefs.get("snoozed") or {}).items()):
        until = _parse_iso((meta or {}).get("until"))
        if until and until > now:
            snoozed[aid] = meta
        else:
            dirty = True
    if dirty:
        prefs["snoozed"] = snoozed
        save_prefs(prefs)
    return {
        "snoozed": snoozed,
        "dismissed": prefs.get("dismissed") or {},
        "updatedAt": prefs.get("updatedAt"),
        "path": str(prefs_path()),
    }


def filter_alerts(alerts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Returns (visible_alerts, hidden_meta).
    Hidden alerts get snoozedUntil / dismissed flags for UI if needed.
    """
    prefs = get_public_prefs()
    snoozed = prefs.get("snoozed") or {}
    dismissed = prefs.get("dismissed") or {}
    now = _utc_now()
    visible = []
    hidden = []
    for a in alerts:
        aid = a.get("id") or ""
        if aid in dismissed:
            row = dict(a)
            row["dismissed"] = True
            row["hiddenReason"] = "dismissed"
            hidden.append(row)
            continue
        meta = snoozed.get(aid)
        if meta:
            until = _parse_iso(meta.get("until"))
            if until and until > now:
                row = dict(a)
                row["snoozedUntil"] = meta.get("until")
                row["hiddenReason"] = "snoozed"
                hidden.append(row)
                continue
        # pass through with cleared snooze marker
        row = dict(a)
        row["snoozedUntil"] = None
        visible.append(row)
    return visible, hidden
