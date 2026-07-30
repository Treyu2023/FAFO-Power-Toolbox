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


def companion_status() -> dict[str, Any]:
    """Health of toolbox + FAFO meta companions."""
    meta_info = resolve_fafo_meta_root(persist=False)
    toolbox_listening = _port_open(TOOLBOX_HOST, TOOLBOX_PORT)
    meta_listening = _port_open(META_HOST, META_PORT)
    toolbox_health = (
        _http_health(f"http://{TOOLBOX_HOST}:{TOOLBOX_PORT}/api/health") if toolbox_listening else {"ok": False}
    )
    meta_health = (
        _http_health(f"http://{META_HOST}:{META_PORT}/api/health") if meta_listening else {"ok": False}
    )
    prefs = get_prefs()
    win = windows_startup_status()
    block = prefs.get("blockAutoStart") or {}
    one = prefs.get("startWithOneClick") or {}
    return {
        "prefs": prefs,
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
            "role": "Powers HTML Toolbox apps (media, Verifone, system tools, VSR, file tools)",
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
            "name": "S2 · FAFO Local Media Tagger",
            "shortName": "FAFO Tagger",
            "host": META_HOST,
            "port": META_PORT,
            "endpoint": f"http://{META_HOST}:{META_PORT}",
            "listening": meta_listening,
            "healthy": bool(meta_health.get("ok")),
            "autoStart": bool(one.get("fafoMetaServer")),
            "blockAutoStart": bool(block.get("fafoMetaServer")),
            "role": "Powers FAFO Local Media Chrome extension (tags, ratings, pairs, Explorer sync)",
            "serves": [
                "FAFO Local Media (Chrome new-tab extension)",
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
            },
            {
                "code": "S2",
                "name": "FAFO Local Media Tagger",
                "port": META_PORT,
                "endpoint": f"http://{META_HOST}:{META_PORT}",
            },
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


def _popen_hidden(args: list[str], cwd: Path) -> subprocess.Popen:
    """Start without a console. Prefer list-args (no shell) so paths with spaces work."""
    kwargs: dict[str, Any] = {
        "cwd": str(cwd),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
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
    return subprocess.Popen(args, **kwargs)


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
        _popen_hidden([str(py), str(server_py)], root / "server")
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
            _popen_hidden([str(py), str(server_py)], root)
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
    Start configured companion servers. None = use prefs.

    blockAutoStart in prefs blocks auto/one-click starts unless force=True
    (manual override from Startup command board).
    """
    prefs = get_prefs()
    block = prefs.get("blockAutoStart") or {}
    want_tb = prefs["startWithOneClick"]["toolboxServer"] if toolbox is None else bool(toolbox)
    want_meta = prefs["startWithOneClick"]["fafoMetaServer"] if fafo_meta is None else bool(fafo_meta)

    blocked: list[str] = []
    if want_tb and block.get("toolboxServer") and not force:
        want_tb = False
        blocked.append("toolboxServer")
    if want_meta and block.get("fafoMetaServer") and not force:
        want_meta = False
        blocked.append("fafoMetaServer")

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
        "ok": all(r.get("ok") for r in results if r.get("id") not in ("tray", "blocked")) if results else True,
        "started": results,
        "status": status,
        "wanted": {"toolboxServer": want_tb, "fafoMetaServer": want_meta},
        "blocked": blocked,
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
) -> dict[str, Any]:
    """Stop one or both servers. None = stop both (manual off). Does not clear prefs."""
    want_tb = True if toolbox is None else bool(toolbox)
    want_meta = True if fafo_meta is None else bool(fafo_meta)
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
        "status": companion_status(),
    }


def restart_companions(
    toolbox: bool | None = None,
    fafo_meta: bool | None = None,
    wait_sec: float = 15.0,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Stop then start companions (for tray / protocol relaunch)."""
    prefs = get_prefs()
    want_tb = prefs["startWithOneClick"]["toolboxServer"] if toolbox is None else bool(toolbox)
    want_meta = prefs["startWithOneClick"]["fafoMetaServer"] if fafo_meta is None else bool(fafo_meta)
    stopped = stop_companions(toolbox=want_tb, fafo_meta=want_meta)
    time.sleep(0.6)
    started = start_companions(toolbox=want_tb, fafo_meta=want_meta, wait_sec=wait_sec, force=force)
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
