"""
Fleet-level tech defaults (local machine only) — SSH maint shell, help-desk login, etc.

Stored under %LOCALAPPDATA%\\FAFO\\fleet-tech-defaults.json (DPAPI not required for
fleet shared laptop defaults, but file is machine-local and never in git).

Seeded once with the field procedure the tech team uses for Commander shell recovery.
Sites can override host/password in Liferaft.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "FAFO.FleetTechDefaults/1"

# Procedure text (safe to ship in repo). Passwords live only in local defaults file.
SSH_RECOVERY_PLAYBOOK = """Open PuTTY
Click SSH button, enter {host} port {port} with your LAN cable plugged into the switch
(like when you're loading a site).

user: {user}
password: (see fleet / site vault)

If you get a Warning - Potential Security breach press Yes.

Go to maint on the Commander and enable Help Desk login and enter the token.
You're in. Type "help" to list commands.

To reset the Manager password:
  resetpw manager
  then Enter
It prints the new temporary password. Log into Config Client / Manager with it —
Commander will force you to set a new Manager password (use next letter + base).
"""


def _fafo_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    d = base / "FAFO"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path() -> Path:
    return _fafo_dir() / "fleet-tech-defaults.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_payload() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "updatedAt": None,
        "commanderShell": {
            "label": "Commander Linux shell (PuTTY/SSH)",
            "protocol": "SSH",
            "port": 22,
            "username": "maint",
            # Seeded on first write from ensure_seeded(); not committed to git.
            "password": "",
            "defaultHostHint": "192.168.31.11",
            "hostNotes": (
                "Use the site Commander LAN IP (often .11 on store LAN). "
                "Laptop LAN cable on the same switch as when loading SMS."
            ),
            "securityWarningNote": "If PuTTY shows Potential Security Breach / host key change → Yes (on known site rebuilds).",
            "helpDeskLogin": (
                "On Commander: go to maint UI and enable Help Desk login, enter the token, then SSH session is authorized."
            ),
            "resetManagerCmd": "resetpw manager",
            "resetManagerNotes": (
                "After resetpw manager, note the printed temp password. Log in as Manager and complete the forced change "
                "(fleet letter cycle A–E + site digit base). Update Liferaft last-change date + letter."
            ),
            "playbook": SSH_RECOVERY_PLAYBOOK,
            "lastVerifiedAt": "",
            "worksOnBase": "55+ (verify per site; older bases may differ)",
        },
        "phoneAssist": {
            "note": "Use Verifone Tools → Phone Assist Navigator for CSR / Commander / TLS menu walk-throughs.",
        },
    }


def ensure_seeded() -> dict[str, Any]:
    """
    Create local defaults if missing.

    Password stays empty in the repo and in a fresh seed. Set it on this PC via
    fleet-tech-defaults (LocalAppData) or a site override — never commit it.
    Existing LocalAppData files are left as-is (not overwritten).
    """
    p = _path()
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("schema"):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    data = default_payload()
    data["commanderShell"]["username"] = "maint"
    data["commanderShell"]["port"] = 22
    data["commanderShell"]["defaultHostHint"] = "192.168.31.11"
    data["commanderShell"]["lastVerifiedAt"] = _utc_now()
    data["updatedAt"] = _utc_now()
    data["seedNote"] = (
        "Password is empty until set on this PC (Toolbox fleet-tech-defaults). "
        "Never commit fleet-tech-defaults.json or a live maint password to git."
    )
    save_defaults(data)
    return data


def get_defaults(*, include_password: bool = True) -> dict[str, Any]:
    data = ensure_seeded()
    out = json.loads(json.dumps(data))  # deep copy
    if not include_password:
        shell = out.get("commanderShell") or {}
        if shell.get("password"):
            shell["password"] = "••••••••"
            shell["hasPassword"] = True
        out["commanderShell"] = shell
    else:
        shell = out.get("commanderShell") or {}
        shell["hasPassword"] = bool(shell.get("password"))
        out["commanderShell"] = shell
    # Render playbook with host placeholder
    shell = out.get("commanderShell") or {}
    play = shell.get("playbook") or SSH_RECOVERY_PLAYBOOK
    out["commanderShell"]["playbookRendered"] = play.format(
        host=shell.get("defaultHostHint") or "192.168.x.x",
        port=shell.get("port") or 22,
        user=shell.get("username") or "maint",
    )
    out["path"] = str(_path())
    out["ok"] = True
    return out


def save_defaults(data: dict[str, Any]) -> dict[str, Any]:
    data = dict(data or {})
    data["schema"] = SCHEMA
    data["updatedAt"] = _utc_now()
    p = _path()
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(p), "updatedAt": data["updatedAt"]}


def shell_for_site(
    *,
    host: str | None = None,
    site_password: str | None = None,
    site_user: str | None = None,
    site_port: int | None = None,
) -> dict[str, Any]:
    """Merge fleet defaults with optional per-site overrides."""
    fleet = get_defaults(include_password=True)
    shell = dict(fleet.get("commanderShell") or {})
    if host:
        shell["host"] = host
    else:
        shell["host"] = shell.get("defaultHostHint") or ""
    if site_user:
        shell["username"] = site_user
    if site_password:
        shell["password"] = site_password
    if site_port:
        shell["port"] = site_port
    shell["playbookRendered"] = (shell.get("playbook") or SSH_RECOVERY_PLAYBOOK).format(
        host=shell.get("host") or "192.168.x.x",
        port=shell.get("port") or 22,
        user=shell.get("username") or "maint",
    )
    return shell
