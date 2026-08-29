"""
Multi-server launch prefs + Windows startup helpers.

Machine-local prefs (never in git):
  %LOCALAPPDATA%\\FAFO\\launch-prefs.json

Servers (clear names → which programs they power):

  S1  HTML Toolbox Server     127.0.0.87:18765
      Powers: Toolbox Launcher, Media Library, VSR, File Organizer, Verifone
      Commander tools, System Tools, Git Manager, shared Explorer tags API.

  S2  FAFO Local Media Tagger 127.0.0.1:8765
      Powers: FAFO Local Media Chrome extension (tags, ratings, pairs, Explorer
      metadata). Lives under repos\\html\\fafo-chrome-extensions\\...\\explorer-meta.

Windows Startup folder shortcuts (current user only):
  FAFO Toolbox Servers.lnk  → Start-FAFOServers.ps1 (servers only, minimized)
  FAFO Toolbox App.lnk      → Launch-AI-HTML-Toolbox.bat (servers + Chrome shell)

Per-PC data (Backups / Logs / Reports) lives under:
  %LOCALAPPDATA%\\FAFO\\Devices\\<COMPUTERNAME>\\
Production folder may expose those as junctions named Backups, Logs, Reports.
"""
from __future__ import annotations

import json
import os
import platform
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

IS_WINDOWS = platform.system() == "Windows"
# Hidden + detached so users never get a closable console window
_CREATE_FLAGS = 0
if IS_WINDOWS:
    _CREATE_FLAGS = (
        subprocess.CREATE_NO_WINDOW
        | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
    )

PREFS_VERSION = 1
TOOLBOX_HOST = "127.0.0.87"
TOOLBOX_PORT = 18765
META_HOST = "127.0.0.1"
META_PORT = 8765

STARTUP_SERVERS_NAME = "FAFO Toolbox Servers.lnk"
STARTUP_APP_NAME = "FAFO Toolbox App.lnk"


def _localappdata() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))


def prefs_path() -> Path:
    return _localappdata() / "FAFO" / "launch-prefs.json"


def local_paths_path() -> Path:
    return _localappdata() / "FAFO" / "local-paths.json"


def toolbox_root() -> Path:
    return Path(__file__).resolve().parent.parent


def startup_folder() -> Path:
    appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _default_prefs() -> dict[str, Any]:
    return {
        "version": PREFS_VERSION,
        # Auto-run policy (NOT "start both with toolbox"):
        #   toolboxServer  → S1 while toolbox session is active (open Toolbox)
        #   fafoMetaServer → S2 while Google Chrome is running (Ultimate Tab)
        "startWithOneClick": {
            "toolboxServer": True,
            "fafoMetaServer": True,
        },
        "windowsStartup": {
            "servers": False,
            "app": False,
        },
        # Manual command-board overrides — block auto-start / one-click / Windows startup
        # for a server without uninstalling. force=True on start APIs can still launch.
        "blockAutoStart": {
            "toolboxServer": False,
            "fafoMetaServer": False,
        },
        # Sleep = user put this server down on purpose. Tray + watchdog MUST NOT auto-heal
        # sleeping servers (frees RAM/CPU until you Wake / Start / open the toolbox).
        # S1 toolboxServer  = HTML Toolbox apps
        # S2 fafoMetaServer = Ultimate Tab / FAFO Local Media Chrome extension (separate product)
        "serversSleeping": {
            "toolboxServer": False,
            "fafoMetaServer": False,
        },
        # Host-app sessions drive auto-heal (independent products):
        #   toolboxActive = True after Open Toolbox / wake S1; False after Sleep S1
        #   S2 has no session flag — bound to chrome.exe presence
        "sessions": {
            "toolboxActive": False,
        },
        # Manual hold: user explicitly started a server (Start All / Start S2 / wake).
        # Keeps it up until Sleep even if Chrome is closed (S2) or Toolbox session ends (S1).
        # Auto lifecycle (Chrome open/close) still works when hold is false.
        "manualHold": {
            "toolboxServer": False,
            "fafoMetaServer": False,
        },
        "fafoMetaRoot": None,
        "updatedAt": None,
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def get_prefs() -> dict[str, Any]:
    raw = _read_json(prefs_path()) or {}
    prefs = _default_prefs()
    if isinstance(raw.get("startWithOneClick"), dict):
        prefs["startWithOneClick"].update(
            {k: bool(v) for k, v in raw["startWithOneClick"].items() if k in prefs["startWithOneClick"]}
        )
    if isinstance(raw.get("windowsStartup"), dict):
        prefs["windowsStartup"].update(
            {k: bool(v) for k, v in raw["windowsStartup"].items() if k in prefs["windowsStartup"]}
        )
    if isinstance(raw.get("blockAutoStart"), dict):
        prefs["blockAutoStart"].update(
            {k: bool(v) for k, v in raw["blockAutoStart"].items() if k in prefs["blockAutoStart"]}
        )
    if isinstance(raw.get("serversSleeping"), dict):
        prefs["serversSleeping"].update(
            {k: bool(v) for k, v in raw["serversSleeping"].items() if k in prefs["serversSleeping"]}
        )
    # Legacy single bool from early sleep experiments
    if "serversSleeping" in raw and isinstance(raw["serversSleeping"], bool):
        prefs["serversSleeping"]["toolboxServer"] = bool(raw["serversSleeping"])
        prefs["serversSleeping"]["fafoMetaServer"] = bool(raw["serversSleeping"])
    if isinstance(raw.get("sessions"), dict):
        prefs["sessions"].update(
            {k: bool(v) for k, v in raw["sessions"].items() if k in prefs["sessions"]}
        )
    if isinstance(raw.get("manualHold"), dict):
        prefs["manualHold"].update(
            {k: bool(v) for k, v in raw["manualHold"].items() if k in prefs["manualHold"]}
        )
    meta = raw.get("fafoMetaRoot") or raw.get("ExplorerMetaRoot")
    if isinstance(meta, str) and meta.strip():
        prefs["fafoMetaRoot"] = meta.strip()
    prefs["updatedAt"] = raw.get("updatedAt")
    prefs["path"] = str(prefs_path())
    # Mirror path from local-paths.json if prefs empty
    if not prefs.get("fafoMetaRoot"):
        lp = _read_json(local_paths_path()) or {}
        for key in ("ExplorerMetaRoot", "FafoMetaRoot", "fafoMetaRoot"):
            val = lp.get(key)
            if isinstance(val, str) and val.strip():
                prefs["fafoMetaRoot"] = val.strip()
                break
    env_meta = os.environ.get("FAFO_META_ROOT", "").strip()
    if env_meta:
        prefs["fafoMetaRoot"] = env_meta
    return prefs


def save_prefs(updates: dict[str, Any] | None = None) -> dict[str, Any]:
    prefs = get_prefs()
    updates = updates or {}
    if isinstance(updates.get("startWithOneClick"), dict):
        for k, v in updates["startWithOneClick"].items():
            if k in prefs["startWithOneClick"]:
                prefs["startWithOneClick"][k] = bool(v)
    if isinstance(updates.get("windowsStartup"), dict):
        for k, v in updates["windowsStartup"].items():
            if k in prefs["windowsStartup"]:
                prefs["windowsStartup"][k] = bool(v)
    if isinstance(updates.get("blockAutoStart"), dict):
        for k, v in updates["blockAutoStart"].items():
            if k in prefs["blockAutoStart"]:
                prefs["blockAutoStart"][k] = bool(v)
    if isinstance(updates.get("serversSleeping"), dict):
        for k, v in updates["serversSleeping"].items():
            if k in prefs["serversSleeping"]:
                prefs["serversSleeping"][k] = bool(v)
    if isinstance(updates.get("sessions"), dict):
        for k, v in updates["sessions"].items():
            if k in prefs["sessions"]:
                prefs["sessions"][k] = bool(v)
    if isinstance(updates.get("manualHold"), dict):
        for k, v in updates["manualHold"].items():
            if k in prefs["manualHold"]:
                prefs["manualHold"][k] = bool(v)
    if "fafoMetaRoot" in updates:
        val = updates["fafoMetaRoot"]
        if val is None or (isinstance(val, str) and not val.strip()):
            prefs["fafoMetaRoot"] = None
        else:
            p = Path(str(val).strip())
            prefs["fafoMetaRoot"] = str(p.resolve()) if p.exists() else str(p)
    from datetime import datetime, timezone

    prefs["updatedAt"] = datetime.now(timezone.utc).isoformat()
    store = {
        "version": PREFS_VERSION,
        "startWithOneClick": prefs["startWithOneClick"],
        "windowsStartup": prefs["windowsStartup"],
        "blockAutoStart": prefs["blockAutoStart"],
        "serversSleeping": prefs["serversSleeping"],
        "sessions": prefs["sessions"],
        "manualHold": prefs["manualHold"],
        "fafoMetaRoot": prefs.get("fafoMetaRoot"),
        "updatedAt": prefs["updatedAt"],
    }
    _write_json(prefs_path(), store)
    # Keep local-paths in sync for other FAFO tools
    if prefs.get("fafoMetaRoot"):
        lp = _read_json(local_paths_path()) or {}
        lp["ExplorerMetaRoot"] = prefs["fafoMetaRoot"]
        lp["UpdatedAt"] = prefs["updatedAt"]
        lp["Machine"] = os.environ.get("COMPUTERNAME", "")
        _write_json(local_paths_path(), lp)
    return get_prefs()


def _candidate_meta_roots() -> list[Path]:
    prefs = get_prefs()
    roots: list[Path] = []
    if prefs.get("fafoMetaRoot"):
        roots.append(Path(str(prefs["fafoMetaRoot"])))
    env = os.environ.get("FAFO_META_ROOT", "").strip()
    if env:
        roots.append(Path(env))
    # Canonical home first, then legacy aliases / siblings
    extra = [
        # New single home: C:\_Git\repos\html\fafo-chrome-extensions
        toolbox_root().parent.parent / "fafo-chrome-extensions" / "FAFO Local Media LOAD THIS" / "explorer-meta",
        toolbox_root().parent / "fafo-chrome-extensions" / "FAFO Local Media LOAD THIS" / "explorer-meta",
        Path(r"C:\_Git\repos\html\fafo-chrome-extensions\FAFO Local Media LOAD THIS\explorer-meta"),
        # Junction / old D: path (if still linked)
        Path(r"D:\Chrome python_HTML AI apps\FAFO Local Media LOAD THIS\explorer-meta"),
        Path(r"D:\Chrome python_HTML AI apps\FAFO Local Media\explorer-meta"),
        Path(r"D:\Chrome python_HTML AI apps\FAFO Ultimate Tab\explorer-meta"),
        Path.home() / "Documents" / "FAFO Ultimate Tab" / "explorer-meta",
        Path.home() / "Desktop" / "FAFO Ultimate Tab" / "explorer-meta",
        toolbox_root().parent / "FAFO Ultimate Tab" / "explorer-meta",
        toolbox_root() / "explorer-meta",
        toolbox_root() / "companion" / "explorer-meta",
    ]
    onedrive = os.environ.get("OneDrive")
    if onedrive:
        extra.append(Path(onedrive) / "Desktop" / "FAFO Ultimate Tab" / "explorer-meta")
        extra.append(Path(onedrive) / "Documents" / "FAFO Ultimate Tab" / "explorer-meta")
    roots.extend(extra)
    # Dedupe while preserving order
    seen: set[str] = set()
    out: list[Path] = []
    for r in roots:
        key = str(r).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def resolve_fafo_meta_root(persist: bool = False) -> dict[str, Any]:
    for root in _candidate_meta_roots():
        server_py = root / "server.py"
        start_bat = root / "START_META_SERVER.bat"
        if server_py.is_file() or start_bat.is_file():
            resolved = str(root.resolve()) if root.exists() else str(root)
            if persist:
                save_prefs({"fafoMetaRoot": resolved})
            return {
                "ok": True,
                "path": resolved,
                "hasServerPy": server_py.is_file(),
                "hasStartBat": start_bat.is_file(),
            }
    return {
        "ok": False,
        "path": None,
        "hasServerPy": False,
        "hasStartBat": False,
        "hint": (
            "Set fafoMetaRoot to FAFO Local Media explorer-meta "
            "(…\\fafo-chrome-extensions\\FAFO Local Media LOAD THIS\\explorer-meta)."
        ),
    }


def _port_open(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_health(url: str, timeout: float = 1.5) -> dict[str, Any]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "FAFO-launch-ops"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            data = {}
            try:
                data = json.loads(body) if body.strip().startswith("{") else {"raw": body[:200]}
            except json.JSONDecodeError:
                data = {"raw": body[:200]}
            return {"ok": True, "status": getattr(resp, "status", 200), "body": data}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return {"ok": False, "error": str(e)}


def _http_health_resilient(url: str) -> dict[str, Any]:
    """Health check with a short retry — avoids false 'wedged' during cold start / reload."""
    first = _http_health(url, timeout=1.2)
    if first.get("ok"):
        return first
    time.sleep(0.35)
    second = _http_health(url, timeout=3.0)
    if second.get("ok"):
        second["retried"] = True
        return second
    # Prefer the more informative error
    err = second.get("error") or first.get("error") or "health failed"
    return {"ok": False, "error": err, "retried": True}


def servers_sleeping(prefs: dict[str, Any] | None = None) -> dict[str, bool]:
    """Per-server sleep flags. Sleeping servers must not be auto-healed."""
    p = prefs or get_prefs()
    sleep = p.get("serversSleeping") or {}
    return {
        "toolboxServer": bool(sleep.get("toolboxServer")),
        "fafoMetaServer": bool(sleep.get("fafoMetaServer")),
    }


def chrome_running() -> bool:
    """True if Google Chrome browser process is running (S2 host app)."""
    if not IS_WINDOWS:
        return False
    try:
        import psutil  # type: ignore

        for p in psutil.process_iter(["name"]):
            try:
                name = (p.info.get("name") or "").lower()
                if name in ("chrome.exe", "chrome"):
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def get_sessions(prefs: dict[str, Any] | None = None) -> dict[str, bool]:
    p = prefs or get_prefs()
    s = p.get("sessions") or {}
    return {"toolboxActive": bool(s.get("toolboxActive"))}


def set_toolbox_session(active: bool) -> dict[str, Any]:
    """Mark HTML Toolbox session (S1 host). Open Toolbox → True; Sleep S1 → False."""
    return save_prefs({"sessions": {"toolboxActive": bool(active)}})


def manual_hold(prefs: dict[str, Any] | None = None) -> dict[str, bool]:
    p = prefs or get_prefs()
    mh = p.get("manualHold") or {}
    return {
        "toolboxServer": bool(mh.get("toolboxServer")),
        "fafoMetaServer": bool(mh.get("fafoMetaServer")),
    }


def set_manual_hold(
    *,
    toolbox: bool | None = None,
    fafo_meta: bool | None = None,
) -> dict[str, Any]:
    """Set manual-hold flags. None = leave unchanged."""
    cur = manual_hold()
    updates = {
        "toolboxServer": cur["toolboxServer"] if toolbox is None else bool(toolbox),
        "fafoMetaServer": cur["fafoMetaServer"] if fafo_meta is None else bool(fafo_meta),
    }
    return save_prefs({"manualHold": updates})


def should_auto_run_s1(prefs: dict[str, Any] | None = None) -> bool:
    """S1 with Toolbox session, or manual hold after explicit Start/Wake."""
    p = prefs or get_prefs()
    if servers_sleeping(p).get("toolboxServer"):
        return False
    if p.get("blockAutoStart", {}).get("toolboxServer"):
        return False
    if not p.get("startWithOneClick", {}).get("toolboxServer", True):
        return False
    if bool(get_sessions(p).get("toolboxActive")):
        return True
    return bool(manual_hold(p).get("toolboxServer"))


def should_auto_run_s2(prefs: dict[str, Any] | None = None) -> bool:
    """S2 with Chrome, or manual hold after explicit Start/Wake (any time)."""
    p = prefs or get_prefs()
    if servers_sleeping(p).get("fafoMetaServer"):
        return False
    if p.get("blockAutoStart", {}).get("fafoMetaServer"):
        return False
    if not p.get("startWithOneClick", {}).get("fafoMetaServer", True):
        return False
    if chrome_running():
        return True
    return bool(manual_hold(p).get("fafoMetaServer"))


def apply_lifecycle(*, ensure_tray: bool = True) -> dict[str, Any]:
    """Align S1/S2 with host apps + manual holds (tray + watchdog).

    S1 HTML Toolbox  → toolbox session or manual hold
    S2 Ultimate Tab  → Chrome process or manual hold (explicit Start/Wake)
    """
    prefs = get_prefs()
    actions: list[str] = []
    want_s1 = should_auto_run_s1(prefs)
    want_s2 = should_auto_run_s2(prefs)
    s1_up = _port_open(TOOLBOX_HOST, TOOLBOX_PORT)
    s2_up = _port_open(META_HOST, META_PORT)
    hold = manual_hold(prefs)

    if want_s1 and not s1_up:
        r = start_toolbox_server()
        actions.append(f"start_s1:{r.get('started') or r.get('alreadyRunning') or r.get('error')}")
    # Do not auto-stop S1 when session ends — user Sleep is explicit

    if want_s2 and not s2_up:
        r = start_fafo_meta_server()
        actions.append(f"start_s2:{r.get('started') or r.get('alreadyRunning') or r.get('error')}")
    elif (
        (not want_s2)
        and s2_up
        and not servers_sleeping(prefs).get("fafoMetaServer")
        and not hold.get("fafoMetaServer")
        and not chrome_running()
    ):
        # Chrome closed and no manual hold — free resources; do not mark user-sleep
        killed = stop_companions(toolbox=False, fafo_meta=True, mark_sleep=False)
        actions.append(f"stop_s2_chrome_gone:killed={killed.get('killed')}")

    tray_info: dict[str, Any] = {}
    if ensure_tray:
        tray_info = start_tray()
        if tray_info.get("started"):
            actions.append("start_tray")

    return {
        "ok": True,
        "actions": actions,
        "want": {"s1": want_s1, "s2": want_s2},
        "chromeRunning": chrome_running(),
        "sessions": get_sessions(),
        "serversSleeping": servers_sleeping(),
        "status": companion_status(),
        "tray": tray_info,
    }


def is_server_sleeping(which: str, prefs: dict[str, Any] | None = None) -> bool:
    """which: 'toolbox' | 'toolboxServer' | 's1' | 'fafoMeta' | 'fafoMetaServer' | 's2'."""
    sleep = servers_sleeping(prefs)
    key = (which or "").strip().lower()
    if key in ("toolbox", "toolboxserver", "s1", "html", "htmltoolbox"):
        return sleep["toolboxServer"]
    if key in ("fafometa", "fafometaserver", "s2", "meta", "ultimatetab", "tagger"):
        return sleep["fafoMetaServer"]
    return False


def set_servers_sleeping(
    *,
    toolbox: bool | None = None,
    fafo_meta: bool | None = None,
) -> dict[str, Any]:
    """Set sleep flags without starting/stopping processes. None = leave unchanged."""
    cur = servers_sleeping()
    updates: dict[str, bool] = {}
    if toolbox is not None:
        updates["toolboxServer"] = bool(toolbox)
    else:
        updates["toolboxServer"] = cur["toolboxServer"]
    if fafo_meta is not None:
        updates["fafoMetaServer"] = bool(fafo_meta)
    else:
        updates["fafoMetaServer"] = cur["fafoMetaServer"]
    return save_prefs({"serversSleeping": updates})


def sleep_companions(
    toolbox: bool | None = True,
    fafo_meta: bool | None = True,
) -> dict[str, Any]:
    """Stop selected servers and mark them sleeping so tray/watchdog will not revive them.

    Independent products:
      S1 toolbox  — HTML Toolbox apps (also ends toolbox session)
      S2 fafo_meta — Ultimate Tab / Local Media Chrome extension
    """
    want_tb = True if toolbox is None else bool(toolbox)
    want_meta = True if fafo_meta is None else bool(fafo_meta)
    # Mark sleep FIRST so a concurrent heal does not race a restart
    set_servers_sleeping(
        toolbox=True if want_tb else None,
        fafo_meta=True if want_meta else None,
    )
    # Clear manual holds so lifecycle does not keep restarting after Sleep
    set_manual_hold(
        toolbox=False if want_tb else None,
        fafo_meta=False if want_meta else None,
    )
    if want_tb:
        set_toolbox_session(False)
    stopped = stop_companions(
        toolbox=want_tb if want_tb else False,
        fafo_meta=want_meta if want_meta else False,
        mark_sleep=False,  # already set above
    )
    return {
        "ok": True,
        "action": "sleep",
        "sleeping": servers_sleeping(),
        "sessions": get_sessions(),
        "killed": stopped.get("killed", {}),
        "status": companion_status(),
    }


def wake_companions(
    toolbox: bool | None = True,
    fafo_meta: bool | None = True,
    wait_sec: float = 12.0,
) -> dict[str, Any]:
    """Clear sleep flags for selected servers and start them (force past blocks).

    Waking S1 opens a toolbox session (S1 lifecycle).
    Waking S2 starts tagger even if Chrome is not open yet (manual override / hold).
    """
    want_tb = True if toolbox is None else bool(toolbox)
    want_meta = True if fafo_meta is None else bool(fafo_meta)
    set_servers_sleeping(
        toolbox=False if want_tb else None,
        fafo_meta=False if want_meta else None,
    )
    set_manual_hold(
        toolbox=True if want_tb else None,
        fafo_meta=True if want_meta else None,
    )
    if want_tb:
        set_toolbox_session(True)
    started = start_companions(
        toolbox=want_tb if want_tb else False,
        fafo_meta=want_meta if want_meta else False,
        wait_sec=wait_sec,
        force=True,
    )
    return {
        "ok": bool(started.get("ok")),
        "action": "wake",
        "sleeping": servers_sleeping(),
        "sessions": get_sessions(),
        **started,
    }


def companion_status() -> dict[str, Any]:
    """Health of toolbox + FAFO meta companions."""
    meta_info = resolve_fafo_meta_root(persist=False)
    toolbox_listening = _port_open(TOOLBOX_HOST, TOOLBOX_PORT)
    meta_listening = _port_open(META_HOST, META_PORT)
    toolbox_health = (
        _http_health_resilient(f"http://{TOOLBOX_HOST}:{TOOLBOX_PORT}/api/health")
        if toolbox_listening
        else {"ok": False}
    )
    meta_health = (
        _http_health_resilient(f"http://{META_HOST}:{META_PORT}/api/health")
        if meta_listening
        else {"ok": False}
    )
    prefs = get_prefs()
    win = windows_startup_status()
    block = prefs.get("blockAutoStart") or {}
    one = prefs.get("startWithOneClick") or {}
    sleep = servers_sleeping(prefs)
    sessions = get_sessions(prefs)
    chrome_up = chrome_running()
    return {
        "prefs": prefs,
        "serversSleeping": sleep,
        "sessions": sessions,
        "chromeRunning": chrome_up,
        "lifecycle": {
            "s1": "with_toolbox_or_manual",
            "s2": "with_chrome_or_manual",
            "s1_should_run": should_auto_run_s1(prefs),
            "s2_should_run": should_auto_run_s2(prefs),
            "manualHold": manual_hold(prefs),
        },
        "toolbox": {
            "id": "toolbox",
            "code": "S1",
            "name": "S1 · HTML Toolbox Server",
            "shortName": "HTML Toolbox",
            "host": TOOLBOX_HOST,
            "port": TOOLBOX_PORT,
            "endpoint": f"http://{TOOLBOX_HOST}:{TOOLBOX_PORT}",
            "listening": toolbox_listening,
            "healthy": bool(toolbox_health.get("ok")),
            "autoStart": bool(one.get("toolboxServer")),
            "blockAutoStart": bool(block.get("toolboxServer")),
            "sleeping": sleep["toolboxServer"],
            "sessionActive": sessions.get("toolboxActive"),
            "lifecycle": "with_toolbox",
            "role": "Powers HTML Toolbox apps only — starts when you open the Toolbox",
            "serves": [
                "Toolbox Launcher",
                "Media Library / VSR / File Organizer",
                "Verifone Commander tools",
                "System Tools (health, events, task manager)",
                "Git Repository Manager",
            ],
        },
        "fafoMeta": {
            "id": "fafo_meta",
            "code": "S2",
            "name": "S2 · Ultimate Tab / Local Media Tagger",
            "shortName": "Ultimate Tab",
            "host": META_HOST,
            "port": META_PORT,
            "endpoint": f"http://{META_HOST}:{META_PORT}",
            "listening": meta_listening,
            "healthy": bool(meta_health.get("ok")),
            "autoStart": bool(one.get("fafoMetaServer")),
            "blockAutoStart": bool(block.get("fafoMetaServer")),
            "sleeping": sleep["fafoMetaServer"],
            "chromeRunning": chrome_up,
            "lifecycle": "with_chrome",
            "role": (
                "Separate product: starts when Google Chrome is running "
                "(Ultimate Tab extension) — not launched by HTML Toolbox"
            ),
            "serves": [
                "FAFO Ultimate Tab / Local Media (Chrome extension)",
                "On-play tags / ratings → Explorer metadata",
                "Pairs & library index companion",
            ],
            "root": meta_info,
        },
        "windowsStartup": win,
        "legend": [
            {
                "code": "S1",
                "name": "HTML Toolbox Server",
                "port": TOOLBOX_PORT,
                "endpoint": f"http://{TOOLBOX_HOST}:{TOOLBOX_PORT}",
                "product": "AI HTML Toolbox",
                "lifecycle": "Opens with Toolbox · Sleep from tray when done",
            },
            {
                "code": "S2",
                "name": "Ultimate Tab / Local Media Tagger",
                "port": META_PORT,
                "endpoint": f"http://{META_HOST}:{META_PORT}",
                "product": "FAFO Ultimate Tab (Chrome extension)",
                "lifecycle": "Starts with Chrome · stops when Chrome exits",
            },
        ],
        "stack": runtime_stack(
            toolbox_listening=toolbox_listening,
            toolbox_health=toolbox_health,
            meta_listening=meta_listening,
            meta_health=meta_health,
            chrome_up=chrome_up,
            sleep=sleep,
            prefs=prefs,
        ),
    }


def _running_images() -> set[str]:
    names: set[str] = set()
    if not IS_WINDOWS:
        return names
    try:
        import psutil  # type: ignore

        for p in psutil.process_iter(["name"]):
            try:
                n = (p.info.get("name") or "").lower()
                if n:
                    names.add(n)
            except Exception:
                continue
    except Exception:
        pass
    return names


def _level(*, up: bool, required: bool, expected: bool = False, degraded: bool = False) -> str:
    """green good · yellow issue · orange problem · red failure"""
    if up and not degraded:
        return "good"
    if up and degraded:
        return "issue"
    if required:
        return "failure"
    if expected:
        return "problem"
    return "issue"


def runtime_stack(
    toolbox_listening: bool | None = None,
    toolbox_health: dict[str, Any] | None = None,
    meta_listening: bool | None = None,
    meta_health: dict[str, Any] | None = None,
    chrome_up: bool | None = None,
    sleep: dict[str, bool] | None = None,
    prefs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Monitor S1/S2 plus companion apps/windows the toolbox needs to run smoothly."""
    if toolbox_listening is None:
        toolbox_listening = _port_open(TOOLBOX_HOST, TOOLBOX_PORT)
    if toolbox_health is None:
        toolbox_health = (
            _http_health_resilient(f"http://{TOOLBOX_HOST}:{TOOLBOX_PORT}/api/health")
            if toolbox_listening
            else {"ok": False}
        )
    if meta_listening is None:
        meta_listening = _port_open(META_HOST, META_PORT)
    if meta_health is None:
        meta_health = (
            _http_health_resilient(f"http://{META_HOST}:{META_PORT}/api/health")
            if meta_listening
            else {"ok": False}
        )
    if chrome_up is None:
        chrome_up = chrome_running()
    sleep = sleep or servers_sleeping(prefs)
    prefs = prefs or get_prefs()
    one = prefs.get("startWithOneClick") or {}
    images = _running_images()
    venv = _server_python()
    body = toolbox_health.get("body") if isinstance(toolbox_health.get("body"), dict) else {}
    ffmpeg_ok = bool(body.get("ffmpeg")) if toolbox_health.get("ok") else False
    vault_up = _port_open("127.0.0.1", 18767)
    vault_h = _http_health("http://127.0.0.1:18767/health", timeout=0.6) if vault_up else {"ok": False}
    try:
        wd = watchdog_status()
    except Exception:
        wd = {"running": False, "attentionRequired": False}
    git_ok = False
    try:
        import shutil

        git_ok = bool(shutil.which("git"))
    except Exception:
        git_ok = False

    s1_up = bool(toolbox_listening and toolbox_health.get("ok"))
    s1_listen_only = bool(toolbox_listening and not toolbox_health.get("ok"))
    s2_up = bool(meta_listening and (meta_health.get("ok") or meta_listening))
    s2_expected = bool(chrome_up and not sleep.get("fafoMetaServer") and one.get("fafoMetaServer", True))
    pinokio = "pinokio.exe" in images
    chrome = chrome_up or "chrome.exe" in images

    items = [
        {
            "id": "s1",
            "name": "S1 Toolbox Server",
            "kind": "server",
            "required": True,
            "up": s1_up,
            "level": "issue" if s1_listen_only else _level(up=s1_up, required=True),
            "detail": "127.0.0.87:18765" + (" · listening but health failed" if s1_listen_only else ""),
            "how": "Start All / ▶ Start S1. Powers nearly every HTML tool (media, Verifone, system, git).",
            "apps": [
                "Media Hub / Library / Organizer / Duplicates",
                "Compare Hub / Guided Pair / VSR companion / VID TRIM",
                "Commander Console / HUD / Phone Assist / Punch List",
                "PC Diagnostics, Health Desk, Event Viewer, Task Pro, LAN, Disk, Git",
                "Transfer Monitor launch, Batch convert (ffmpeg), IP profiles",
            ],
        },
        {
            "id": "s2",
            "name": "S2 Media Tagger",
            "kind": "server",
            "required": False,
            "up": s2_up,
            "level": _level(up=s2_up, required=False, expected=s2_expected),
            "detail": "127.0.0.1:8765" + (" · expected while Chrome is open" if s2_expected and not s2_up else ""),
            "how": "Starts with Chrome (Ultimate Tab). ▶ Start S2 if tags/ratings are dead.",
            "apps": ["FAFO Local Media Chrome extension", "Explorer on-play tags", "Pairs index"],
        },
        {
            "id": "chrome",
            "name": "Google Chrome",
            "kind": "app",
            "required": False,
            "up": chrome,
            "level": _level(up=chrome, required=False, expected=s2_expected),
            "detail": "Host for Toolbox shell, Ultimate Tab, grok.com/imagine",
            "how": "Open Chrome or Launch-AI-HTML-Toolbox.bat",
            "apps": ["Toolbox Chrome shell", "S2 Ultimate Tab", "Imagine tab painter"],
        },
        {
            "id": "python",
            "name": "Python .venv",
            "kind": "runtime",
            "required": True,
            "up": bool(venv and venv.is_file()),
            "level": _level(up=bool(venv and venv.is_file()), required=True),
            "detail": str(venv) if venv else "Missing .venv — run INSTALL-PYTHON.bat / SETUP",
            "how": "SETUP (run once).bat or Install FAFO Toolbox.bat",
            "apps": ["S1", "S2", "Imagine Vault", "tray", "watchdog"],
        },
        {
            "id": "ffmpeg",
            "name": "FFmpeg",
            "kind": "runtime",
            "required": False,
            "up": ffmpeg_ok,
            "level": _level(up=ffmpeg_ok, required=False, expected=s1_up),
            "detail": "S1 reports ffmpeg " + ("ok" if ffmpeg_ok else "missing"),
            "how": "Install ffmpeg on PATH. Needed for convert / VID TRIM / probe.",
            "apps": ["Batch Media Converter", "FAFO VID TRIM", "video probe"],
        },
        {
            "id": "imagine-vault",
            "name": "Imagine Vault",
            "kind": "server",
            "required": False,
            "up": bool(vault_h.get("ok") or vault_up),
            "level": _level(up=bool(vault_h.get("ok") or vault_up), required=False),
            "detail": "127.0.0.1:18767 HAVE/MISS download checker",
            "how": "Imagine Vault page → Start vault (Launch-ImagineVault.vbs)",
            "apps": ["Imagine Tracker", "grok.com/imagine overlay"],
        },
        {
            "id": "watchdog",
            "name": "Server Watchdog",
            "kind": "monitor",
            "required": False,
            "up": bool(wd.get("running")),
            "level": (
                "problem"
                if wd.get("attentionRequired")
                else _level(up=bool(wd.get("running")), required=False)
            ),
            "detail": "auto-heal S1/S2 every 15s" + (" · ATTENTION" if wd.get("attentionRequired") else ""),
            "how": "Start monitor on this page / Start-Server-Watchdog.bat",
            "apps": ["S1", "S2"],
        },
        {
            "id": "git",
            "name": "Git",
            "kind": "runtime",
            "required": False,
            "up": git_ok,
            "level": _level(up=git_ok, required=False),
            "detail": "git on PATH" if git_ok else "git not on PATH",
            "how": "Install Git for Windows. Used by Git Repository Manager.",
            "apps": ["Git Repository Manager"],
        },
        {
            "id": "pinokio",
            "name": "Pinokio",
            "kind": "app",
            "required": False,
            "up": pinokio,
            "level": _level(up=pinokio, required=False),
            "detail": "Pinokio.exe " + ("running" if pinokio else "not running"),
            "how": "Start Pinokio when using Pinokio Dock / FlashVSR from Pinokio.",
            "apps": ["Pinokio Dock", "FlashVSR (Pinokio)"],
        },
    ]

    order = {"failure": 0, "problem": 1, "issue": 2, "good": 3}
    worst = "good"
    for it in items:
        if order.get(it["level"], 9) < order.get(worst, 9):
            worst = it["level"]
    counts = {k: sum(1 for i in items if i["level"] == k) for k in ("good", "issue", "problem", "failure")}
    return {
        "ok": worst in ("good", "issue"),
        "worst": worst,
        "counts": counts,
        "items": items,
        "legend": [
            {"level": "good", "color": "green", "means": "Running / healthy"},
            {"level": "issue", "color": "yellow", "means": "Optional down or degraded"},
            {"level": "problem", "color": "orange", "means": "Should be up (lifecycle) but is not"},
            {"level": "failure", "color": "red", "means": "Required piece is down"},
        ],
    }


def _venv_python(prefer_windowless: bool = True) -> Path | None:
    """Resolve venv interpreter.

    Servers: prefer python.exe + CREATE_NO_WINDOW (more reliable than pythonw for uvicorn).
    Tray/GUI helpers: prefer pythonw when prefer_windowless=True and caller wants GUI-less.
    """
    root = toolbox_root()
    # python.exe first for server workloads; CREATE_NO_WINDOW hides the console
    names = ("python.exe", "pythonw.exe") if not prefer_windowless else ("pythonw.exe", "python.exe")
    # Default call sites for *servers* should pass prefer_windowless=False
    for name in names:
        p = root / ".venv" / "Scripts" / name
        if p.is_file():
            return p
    return None


def _server_python() -> Path | None:
    return _venv_python(prefer_windowless=False)


def _device_logs_dir() -> Path:
    pc = os.environ.get("COMPUTERNAME", "PC")
    root = _localappdata() / "FAFO" / "Devices" / pc / "Logs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _popen_hidden(
    args: list[str],
    cwd: Path,
    log_stem: str | None = None,
) -> subprocess.Popen:
    """Start without a console. Prefer list-args (no shell) so paths with spaces work.

    When log_stem is set, stdout/stderr append to device Logs (so crashes are diagnosable).
    """
    stdout = subprocess.DEVNULL
    stderr = subprocess.DEVNULL
    log_handles: list[Any] = []
    if log_stem:
        try:
            log_path = _device_logs_dir() / f"{log_stem}.log"
            # line-buffered text not available for Popen binary; append bytes
            fh = open(log_path, "ab", buffering=0)
            fh.write(f"\n--- start {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n".encode("utf-8", "replace"))
            log_handles.append(fh)
            stdout = fh
            stderr = fh
        except OSError:
            stdout = subprocess.DEVNULL
            stderr = subprocess.DEVNULL
    # Force UTF-8 stdio in children. Windows default (cp1252) + redirected log
    # files made S1 crash on Unicode banner prints (UnicodeEncodeError).
    child_env = os.environ.copy()
    child_env.setdefault("PYTHONIOENCODING", "utf-8")
    child_env.setdefault("PYTHONUTF8", "1")
    kwargs: dict[str, Any] = {
        "cwd": str(cwd),
        "stdin": subprocess.DEVNULL,
        "stdout": stdout,
        "stderr": stderr,
        "env": child_env,
    }
    if IS_WINDOWS:
        # CREATE_NO_WINDOW alone is enough; DETACHED can drop child reliability on some builds
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0  # SW_HIDE
            kwargs["startupinfo"] = si
        except Exception:
            pass
    proc = subprocess.Popen(args, **kwargs)
    # Keep file handles open for process lifetime; store on process to avoid GC close
    if log_handles:
        setattr(proc, "_fafo_log_handles", log_handles)
    return proc


def _tray_running() -> bool:
    if not IS_WINDOWS:
        return False
    try:
        import psutil  # type: ignore

        for p in psutil.process_iter(["name", "cmdline"]):
            try:
                name = (p.info.get("name") or "").lower()
                if name not in ("python.exe", "pythonw.exe"):
                    continue
                cmd = p.info.get("cmdline") or []
                joined = " ".join(str(x) for x in cmd).lower()
                if "tray_launcher.py" in joined:
                    return True
            except (psutil.Error, TypeError):
                continue
    except Exception:
        pass
    return False


def start_tray() -> dict[str, Any]:
    """Ensure system tray helper is running (watchdog + relaunch UI)."""
    if _tray_running():
        return {"ok": True, "alreadyRunning": True, "id": "tray"}
    # Tray prefers pythonw (no console attached to icon process)
    py = _venv_python(prefer_windowless=True) or _server_python()
    tray = toolbox_root() / "server" / "tray_launcher.py"
    if not py or not tray.is_file():
        return {"ok": False, "id": "tray", "error": "python or tray_launcher.py missing"}
    try:
        _popen_hidden([str(py), str(tray)], toolbox_root() / "server")
        return {"ok": True, "started": True, "id": "tray"}
    except OSError as e:
        return {"ok": False, "id": "tray", "error": str(e)}


def start_toolbox_server() -> dict[str, Any]:
    if _port_open(TOOLBOX_HOST, TOOLBOX_PORT):
        return {"ok": True, "alreadyRunning": True, "id": "toolbox", "hidden": True}
    root = toolbox_root()
    py = _server_python()
    if not py:
        return {"ok": False, "error": "No .venv Python — run INSTALL-PYTHON.bat", "id": "toolbox"}
    server_py = root / "server" / "aitoolbox_server.py"
    if not server_py.is_file():
        return {"ok": False, "error": f"Missing {server_py}", "id": "toolbox"}
    try:
        _popen_hidden([str(py), str(server_py)], root / "server", log_stem="S1-toolbox-server")
        return {"ok": True, "started": True, "via": "python-hidden", "id": "toolbox", "hidden": True}
    except OSError as e:
        return {"ok": False, "error": str(e), "id": "toolbox"}


def start_fafo_meta_server() -> dict[str, Any]:
    if _port_open(META_HOST, META_PORT):
        return {"ok": True, "alreadyRunning": True, "id": "fafo_meta", "hidden": True}
    meta = resolve_fafo_meta_root(persist=True)
    if not meta.get("ok") or not meta.get("path"):
        return {
            "ok": False,
            "id": "fafo_meta",
            "error": meta.get("hint")
            or "FAFO explorer-meta folder not found. Point prefs.fafoMetaRoot at it.",
        }
    root = Path(str(meta["path"]))
    py = _server_python()
    server_py = root / "server.py"
    try:
        if py and server_py.is_file():
            _popen_hidden([str(py), str(server_py)], root, log_stem="S2-fafo-meta-server")
            return {
                "ok": True,
                "started": True,
                "via": "python-hidden",
                "id": "fafo_meta",
                "path": str(root),
                "hidden": True,
            }
        return {"ok": False, "id": "fafo_meta", "error": f"No server.py in {root}"}
    except OSError as e:
        return {"ok": False, "id": "fafo_meta", "error": str(e)}


def start_companions(
    toolbox: bool | None = None,
    fafo_meta: bool | None = None,
    wait_sec: float = 12.0,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """
    Start companion servers — keep it simple:

    AUTO (force=False, flags None):
      S1 only if Toolbox session is active
      S2 only if Chrome is running

    MANUAL (force=True, or toolbox/fafo_meta explicitly True):
      Start that server NOW — ignore Chrome / session / sleep.
      User clicked Start All / Start S1 / Start S2 / Wake / protocol start.
    """
    prefs = get_prefs()
    block = prefs.get("blockAutoStart") or {}
    sleep = servers_sleeping(prefs)

    # Manual = force flag or explicit True on a server
    manual = bool(force) or toolbox is True or fafo_meta is True

    if toolbox is None:
        # force without specifying which → start S1 (Start All)
        want_tb = True if force else should_auto_run_s1(prefs)
    else:
        want_tb = bool(toolbox)

    if fafo_meta is None:
        # force without specifying which → start S2 (Start All), Chrome optional
        want_meta = True if force else should_auto_run_s2(prefs)
    else:
        want_meta = bool(fafo_meta)

    # Manual start: clear sleep + set hold so auto lifecycle does not kill it immediately
    if want_tb and (force or toolbox is True):
        if sleep.get("toolboxServer"):
            set_servers_sleeping(toolbox=False)
            sleep = servers_sleeping()
        set_toolbox_session(True)
        set_manual_hold(toolbox=True)
    if want_meta and (force or fafo_meta is True):
        if sleep.get("fafoMetaServer"):
            set_servers_sleeping(fafo_meta=False)
            sleep = servers_sleeping()
        set_manual_hold(fafo_meta=True)

    blocked: list[str] = []
    sleeping_skip: list[str] = []
    lifecycle_skip: list[str] = []

    # blockAutoStart only applies to AUTO mode — never block a manual click
    if want_tb and block.get("toolboxServer") and not manual and toolbox is not True:
        want_tb = False
        blocked.append("toolboxServer")
    if want_meta and block.get("fafoMetaServer") and not manual and fafo_meta is not True:
        want_meta = False
        blocked.append("fafoMetaServer")

    # Sleep only blocks AUTO heals
    if want_tb and sleep.get("toolboxServer") and not manual and toolbox is not True:
        want_tb = False
        sleeping_skip.append("toolboxServer")
    if want_meta and sleep.get("fafoMetaServer") and not manual and fafo_meta is not True:
        want_meta = False
        sleeping_skip.append("fafoMetaServer")

    # AUTO only: host apps required (Chrome / Toolbox session)
    if not manual:
        if want_meta and fafo_meta is not True and not chrome_running() and not manual_hold().get("fafoMetaServer"):
            want_meta = False
            lifecycle_skip.append("fafoMetaServer")
        if want_tb and toolbox is not True and not get_sessions().get("toolboxActive") and not manual_hold().get("toolboxServer"):
            want_tb = False
            lifecycle_skip.append("toolboxServer")

    results: list[dict[str, Any]] = []
    if want_tb:
        results.append(start_toolbox_server())
    if want_meta:
        results.append(start_fafo_meta_server())
    for b in blocked:
        results.append(
            {
                "ok": False,
                "id": "blocked",
                "server": b,
                "skipped": True,
                "reason": "blockAutoStart — enable from Startup board or pass force=true",
            }
        )
    for s in sleeping_skip:
        results.append(
            {
                "ok": False,
                "id": "sleeping",
                "server": s,
                "skipped": True,
                "reason": "serversSleeping — Wake from tray or Start with force=true",
            }
        )
    for s in lifecycle_skip:
        reason = (
            "S1 auto-runs with Toolbox session (open Toolbox, or Start/Wake S1 manually)"
            if s == "toolboxServer"
            else "S2 auto-runs with Chrome (or Start/Wake S2 manually anytime)"
        )
        results.append(
            {
                "ok": False,
                "id": "lifecycle",
                "server": s,
                "skipped": True,
                "reason": reason,
            }
        )

    deadline = time.time() + max(0.0, wait_sec)
    while time.time() < deadline and (want_tb or want_meta):
        st = companion_status()
        tb_ok = (not want_tb) or st["toolbox"]["healthy"] or st["toolbox"]["listening"]
        meta_ok = (not want_meta) or st["fafoMeta"]["healthy"] or st["fafoMeta"]["listening"]
        if tb_ok and meta_ok:
            break
        time.sleep(0.5)

    tray = start_tray()
    results.append(tray)

    status = companion_status()
    status["tray"] = {"running": _tray_running(), **{k: v for k, v in tray.items() if k != "id"}}
    return {
        "ok": all(
            r.get("ok")
            for r in results
            if r.get("id") not in ("tray", "blocked", "sleeping", "lifecycle")
        )
        if results
        else True,
        "started": results,
        "status": status,
        "wanted": {"toolboxServer": want_tb, "fafoMetaServer": want_meta},
        "blocked": blocked,
        "sleepingSkipped": sleeping_skip,
        "lifecycleSkipped": lifecycle_skip,
        "force": force,
        "hidden": True,
    }


def stop_listener_on_port(port: int, host_hint: str | None = None) -> list[int]:
    """Terminate process(es) listening on port. Returns killed PIDs."""
    killed: list[int] = []
    try:
        import psutil  # type: ignore
    except ImportError:
        return killed
    for conn in psutil.net_connections(kind="inet"):
        try:
            if conn.status != psutil.CONN_LISTEN:
                continue
            if not conn.laddr or int(conn.laddr.port) != int(port):
                continue
            if host_hint and conn.laddr.ip not in (host_hint, "0.0.0.0", "::", "127.0.0.1"):
                # still allow any local listen on that port
                pass
            pid = conn.pid
            if not pid or pid in killed:
                continue
            p = psutil.Process(pid)
            p.terminate()
            try:
                p.wait(timeout=3)
            except psutil.TimeoutExpired:
                p.kill()
            killed.append(pid)
        except (psutil.Error, ValueError, TypeError):
            continue
    return killed


def stop_companions(
    toolbox: bool | None = None,
    fafo_meta: bool | None = None,
    *,
    mark_sleep: bool = True,
) -> dict[str, Any]:
    """Stop one or both servers. None = stop both (manual off).

    By default marks stopped servers as sleeping so tray/watchdog will not
    immediately auto-restart them (that was the resource-hog bug).
    Pass mark_sleep=False only for internal restart sequences.
    """
    want_tb = True if toolbox is None else bool(toolbox)
    want_meta = True if fafo_meta is None else bool(fafo_meta)
    if mark_sleep and (want_tb or want_meta):
        set_servers_sleeping(
            toolbox=True if want_tb else None,
            fafo_meta=True if want_meta else None,
        )
    killed: dict[str, list[int]] = {"toolbox": [], "fafo_meta": []}
    # Stop tagger first so S1 can still answer the stop API call
    if want_meta:
        killed["fafo_meta"] = stop_listener_on_port(META_PORT, META_HOST)
    if want_tb:
        killed["toolbox"] = stop_listener_on_port(TOOLBOX_PORT, TOOLBOX_HOST)
    return {
        "ok": True,
        "killed": killed,
        "stopped": {"toolboxServer": want_tb, "fafoMetaServer": want_meta},
        "serversSleeping": servers_sleeping(),
        "status": companion_status(),
    }


def restart_companions(
    toolbox: bool | None = None,
    fafo_meta: bool | None = None,
    wait_sec: float = 15.0,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Stop then start — user Relaunch always starts both (unless a flag is False)."""
    # None on relaunch = that server is requested (Start All / Relaunch All)
    want_tb = True if toolbox is None else bool(toolbox)
    want_meta = True if fafo_meta is None else bool(fafo_meta)
    stopped = stop_companions(toolbox=want_tb, fafo_meta=want_meta, mark_sleep=False)
    if want_tb or want_meta:
        set_servers_sleeping(
            toolbox=False if want_tb else None,
            fafo_meta=False if want_meta else None,
        )
    time.sleep(0.6)
    started = start_companions(
        toolbox=want_tb, fafo_meta=want_meta, wait_sec=wait_sec, force=True
    )
    return {
        "ok": started.get("ok", False),
        "killed": stopped.get("killed", {}),
        **started,
    }


def _shortcut_exists(name: str) -> bool:
    return (startup_folder() / name).is_file()


def windows_startup_status() -> dict[str, Any]:
    folder = startup_folder()
    servers = folder / STARTUP_SERVERS_NAME
    app = folder / STARTUP_APP_NAME
    # Legacy shortcut from install_autostart.bat
    legacy = folder / "AI Toolbox Server.lnk"
    return {
        "folder": str(folder),
        "servers": {
            "enabled": servers.is_file(),
            "path": str(servers),
            "name": STARTUP_SERVERS_NAME,
        },
        "app": {
            "enabled": app.is_file(),
            "path": str(app),
            "name": STARTUP_APP_NAME,
        },
        "legacyServer": {
            "enabled": legacy.is_file(),
            "path": str(legacy),
            "name": "AI Toolbox Server.lnk",
        },
    }


def _create_shortcut(link_path: Path, target: str, workdir: str, description: str, args: str = "") -> None:
    if not IS_WINDOWS:
        raise RuntimeError("Windows only")
    link_path.parent.mkdir(parents=True, exist_ok=True)
    # Escape for PowerShell single-quoted strings
    def q(s: str) -> str:
        return s.replace("'", "''")

    ps = (
        f"$s = New-Object -ComObject WScript.Shell; "
        f"$l = $s.CreateShortcut('{q(str(link_path))}'); "
        f"$l.TargetPath = '{q(target)}'; "
        f"$l.WorkingDirectory = '{q(workdir)}'; "
        f"$l.WindowStyle = 7; "
        f"$l.Description = '{q(description)}'; "
    )
    if args:
        ps += f"$l.Arguments = '{q(args)}'; "
    ico = toolbox_root() / "assets" / "AI-HTML-Toolbox.ico"
    if ico.is_file():
        ps += f"$l.IconLocation = '{q(str(ico))},0'; "
    ps += "$l.Save()"
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        capture_output=True,
        text=True,
        timeout=30,
        creationflags=_CREATE_FLAGS,
    )
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "shortcut failed").strip())


def _remove_shortcut(link_path: Path) -> bool:
    if link_path.is_file():
        link_path.unlink()
        return True
    return False


def set_windows_startup(servers: bool | None = None, app: bool | None = None) -> dict[str, Any]:
    """Enable/disable current-user Startup shortcuts. None = leave unchanged."""
    if not IS_WINDOWS:
        raise RuntimeError("Windows startup is only supported on Windows")
    root = toolbox_root()
    folder = startup_folder()
    status_before = windows_startup_status()

    if servers is not None:
        link = folder / STARTUP_SERVERS_NAME
        if servers:
            ps1 = root / "Scripts" / "Start-FAFOServers.ps1"
            if not ps1.is_file():
                raise FileNotFoundError(f"Missing {ps1}")
            _create_shortcut(
                link,
                target=str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"),
                workdir=str(root),
                description="FAFO Toolbox companion servers (toolbox + FAFO tagging)",
                args=f'-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{ps1}" -ToolboxRoot "{root}"',
            )
            # Prefer new multi-server shortcut over legacy tray-only
            _remove_shortcut(folder / "AI Toolbox Server.lnk")
        else:
            _remove_shortcut(link)

    if app is not None:
        link = folder / STARTUP_APP_NAME
        if app:
            bat = root / "Launch-AI-HTML-Toolbox.bat"
            if not bat.is_file():
                raise FileNotFoundError(f"Missing {bat}")
            _create_shortcut(
                link,
                target=str(bat),
                workdir=str(root),
                description="FAFO AI HTML Toolbox app + servers",
            )
        else:
            _remove_shortcut(link)

    # Persist preference flags to match actual shortcuts
    after = windows_startup_status()
    save_prefs(
        {
            "windowsStartup": {
                "servers": after["servers"]["enabled"],
                "app": after["app"]["enabled"],
            }
        }
    )
    return {
        "ok": True,
        "before": status_before,
        "after": after,
        "prefs": get_prefs(),
    }


def apply_prefs_and_startup(body: dict[str, Any]) -> dict[str, Any]:
    """Save launch prefs and optionally sync Windows startup shortcuts."""
    prefs_update: dict[str, Any] = {}
    if "startWithOneClick" in body:
        prefs_update["startWithOneClick"] = body["startWithOneClick"]
    if "blockAutoStart" in body and isinstance(body["blockAutoStart"], dict):
        prefs_update["blockAutoStart"] = body["blockAutoStart"]
    if "serversSleeping" in body and isinstance(body["serversSleeping"], dict):
        prefs_update["serversSleeping"] = body["serversSleeping"]
    if "fafoMetaRoot" in body:
        prefs_update["fafoMetaRoot"] = body["fafoMetaRoot"]
    if "windowsStartup" in body and isinstance(body["windowsStartup"], dict):
        # Save desired flags; then apply shortcuts if keys present
        prefs_update["windowsStartup"] = body["windowsStartup"]

    prefs = save_prefs(prefs_update) if prefs_update else get_prefs()

    win_body = body.get("windowsStartup") if isinstance(body.get("windowsStartup"), dict) else None
    win_result = None
    if win_body is not None and ("servers" in win_body or "app" in win_body):
        win_result = set_windows_startup(
            servers=win_body["servers"] if "servers" in win_body else None,
            app=win_body["app"] if "app" in win_body else None,
        )
        prefs = win_result.get("prefs") or get_prefs()

    return {
        "ok": True,
        "prefs": prefs,
        "windowsStartup": windows_startup_status(),
        "applied": win_result,
        "companions": companion_status(),
    }


# ── Server Watchdog (S1/S2 monitor) ──────────────────────────────────────────

WATCHDOG_BATS = {
    "start": "Start-Server-Watchdog.bat",
    "install": "Install-Server-Watchdog.bat",
    "status": "Open-Server-Watchdog-Status.bat",
}


def _device_reports() -> Path:
    pc = os.environ.get("COMPUTERNAME", "PC")
    return _localappdata() / "FAFO" / "Devices" / pc / "Reports"


def _device_logs() -> Path:
    pc = os.environ.get("COMPUTERNAME", "PC")
    return _localappdata() / "FAFO" / "Devices" / pc / "Logs"


def watchdog_paths() -> dict[str, Any]:
    root = toolbox_root()
    reports = _device_reports()
    logs = _device_logs()
    bats = {k: str(root / v) for k, v in WATCHDOG_BATS.items()}
    return {
        "toolboxRoot": str(root),
        "bats": bats,
        "statusHtml": str(reports / "server-watchdog-status.html"),
        "statusJson": str(reports / "server-watchdog-status.json"),
        "attentionFlag": str(reports / "ATTENTION-SERVERS.txt"),
        "log": str(logs / "server-watchdog.log"),
        "script": str(root / "server" / "server_watchdog.py"),
    }


def _watchdog_running() -> list[int]:
    pids: list[int] = []
    try:
        import psutil  # type: ignore

        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                name = (p.info.get("name") or "").lower()
                if name not in ("python.exe", "pythonw.exe"):
                    continue
                cmd = " ".join(str(x) for x in (p.info.get("cmdline") or [])).lower()
                if "server_watchdog.py" in cmd:
                    pids.append(int(p.info["pid"]))
            except Exception:
                continue
    except Exception:
        pass
    return pids


def watchdog_status() -> dict[str, Any]:
    paths = watchdog_paths()
    status_json = Path(paths["statusJson"])
    attention = Path(paths["attentionFlag"])
    report: dict[str, Any] | None = None
    if status_json.is_file():
        try:
            report = json.loads(status_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            report = None
    pids = _watchdog_running()
    return {
        "ok": True,
        "running": len(pids) > 0,
        "pids": pids,
        "attentionRequired": bool(attention.is_file())
        or bool(report and report.get("attentionRequired")),
        "report": report,
        "paths": paths,
        "batsPresent": {
            k: Path(v).is_file() for k, v in (paths.get("bats") or {}).items()
        },
    }


def _popen_bat(bat_path: Path) -> dict[str, Any]:
    if not bat_path.is_file():
        return {"ok": False, "error": f"Missing {bat_path.name}", "path": str(bat_path)}
    try:
        # cmd /c start so bat opens independently and returns immediately
        if IS_WINDOWS:
            subprocess.Popen(
                ["cmd.exe", "/c", "start", "", str(bat_path)],
                cwd=str(bat_path.parent),
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen([str(bat_path)], cwd=str(bat_path.parent))
        return {"ok": True, "launched": str(bat_path)}
    except OSError as e:
        return {"ok": False, "error": str(e), "path": str(bat_path)}


def watchdog_start() -> dict[str, Any]:
    """Start the long-running server_watchdog process (or bat)."""
    if _watchdog_running():
        return {"ok": True, "alreadyRunning": True, "status": watchdog_status()}
    root = toolbox_root()
    py = _server_python()
    script = root / "server" / "server_watchdog.py"
    if py and script.is_file():
        try:
            # Prefer pythonw when available
            pyw = Path(str(py).replace("python.exe", "pythonw.exe"))
            exe = pyw if pyw.is_file() else py
            _popen_hidden([str(exe), str(script)], root / "server", log_stem="server-watchdog-run")
            time.sleep(0.8)
            return {"ok": True, "started": True, "via": "python", "status": watchdog_status()}
        except OSError as e:
            bat = root / WATCHDOG_BATS["start"]
            r = _popen_bat(bat)
            r["pythonError"] = str(e)
            r["status"] = watchdog_status()
            return r
    return {**_popen_bat(root / WATCHDOG_BATS["start"]), "status": watchdog_status()}


def watchdog_install() -> dict[str, Any]:
    """Register Startup entry + 5-min poll task, then start watchdog."""
    root = toolbox_root()
    py = _server_python()
    script = root / "server" / "server_watchdog.py"
    result: dict[str, Any] = {"ok": False}
    if py and script.is_file():
        try:
            r = subprocess.run(
                [str(py), str(script), "--install-task"],
                cwd=str(root / "server"),
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=_CREATE_FLAGS if IS_WINDOWS else 0,
            )
            try:
                result = json.loads(r.stdout or "{}")
            except json.JSONDecodeError:
                result = {
                    "ok": r.returncode == 0,
                    "stdout": (r.stdout or "")[:800],
                    "stderr": (r.stderr or "")[:400],
                }
        except Exception as e:
            result = {"ok": False, "error": str(e)}
    else:
        result = _popen_bat(root / WATCHDOG_BATS["install"])
    started = watchdog_start()
    return {
        "ok": bool(result.get("ok")) or bool(started.get("ok")),
        "install": result,
        "start": started,
        "status": watchdog_status(),
    }


def watchdog_open_status() -> dict[str, Any]:
    """Open the HTML status page (generate with --once if missing)."""
    paths = watchdog_paths()
    html = Path(paths["statusHtml"])
    if not html.is_file():
        # One-shot generate
        root = toolbox_root()
        py = _server_python()
        script = root / "server" / "server_watchdog.py"
        if py and script.is_file():
            try:
                subprocess.run(
                    [str(py), str(script), "--once"],
                    cwd=str(root / "server"),
                    capture_output=True,
                    text=True,
                    timeout=45,
                    creationflags=_CREATE_FLAGS if IS_WINDOWS else 0,
                )
            except Exception:
                pass
    if html.is_file() and IS_WINDOWS:
        try:
            os.startfile(str(html))  # type: ignore[attr-defined]
            return {"ok": True, "opened": str(html), "status": watchdog_status()}
        except OSError as e:
            return {"ok": False, "error": str(e), "path": str(html)}
    # Fallback bat
    r = _popen_bat(toolbox_root() / WATCHDOG_BATS["status"])
    r["status"] = watchdog_status()
    return r


def watchdog_open_bats_folder() -> dict[str, Any]:
    """Open Explorer at toolbox root, preferably selecting Start-Server-Watchdog.bat."""
    root = toolbox_root()
    bat = root / WATCHDOG_BATS["start"]
    if not IS_WINDOWS:
        return {"ok": False, "error": "Windows only", "path": str(root)}
    try:
        if bat.is_file():
            subprocess.Popen(
                ["explorer.exe", f"/select,{bat}"],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return {"ok": True, "selected": str(bat), "folder": str(root)}
        subprocess.Popen(
            ["explorer.exe", str(root)],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return {"ok": True, "folder": str(root)}
    except OSError as e:
        return {"ok": False, "error": str(e), "folder": str(root)}
