"""
Setup status for AI HTML Toolbox first-run UX.

Machine-local marker (success only):
  %LOCALAPPDATA%/FAFO/Setup/setup-state.json

Last run log (always written by Complete-FAFOSetup.ps1):
  %LOCALAPPDATA%/FAFO/Setup/last-setup-run.json

First-run panel should show when complete is false (no success marker + critical checks).
"""
from __future__ import annotations

import json
import os
import winreg
from pathlib import Path
from typing import Any


def _localappdata() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))


def marker_path() -> Path:
    return _localappdata() / "FAFO" / "Setup" / "setup-state.json"


def last_run_path() -> Path:
    return _localappdata() / "FAFO" / "Setup" / "last-setup-run.json"


def _toolbox_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _read_marker() -> dict[str, Any] | None:
    return _read_json(marker_path())


def _read_last_run() -> dict[str, Any] | None:
    return _read_json(last_run_path())


def _protocol_registered() -> bool:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Software\Classes\aitoolbox\shell\open\command"
        ) as key:
            val, _ = winreg.QueryValueEx(key, None)
            return isinstance(val, str) and (
                "protocol_start.bat" in val or "aitoolbox" in val.lower()
            )
    except OSError:
        return False


def _chrome_found() -> bool:
    local = os.environ.get("LOCALAPPDATA", "")
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    for p in (
        Path(pf) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(pf86) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(local) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(pf) / "Google" / "Chrome Beta" / "Application" / "chrome.exe",
        Path(local) / "Google" / "Chrome Beta" / "Application" / "chrome.exe",
        Path(local) / "Google" / "Chrome SxS" / "Application" / "chrome.exe",
    ):
        if p.is_file():
            return True
    return False


def _desktop_shortcut_exists() -> bool:
    """Prefer real Desktop folder (OneDrive-redirected), then classic Desktop."""
    candidates: list[Path] = []
    # USERPROFILE\Desktop is often correct; OneDrive may redirect
    user = os.environ.get("USERPROFILE", str(Path.home()))
    candidates.append(Path(user) / "Desktop" / "AI HTML Toolbox.lnk")
    onedrive = os.environ.get("OneDrive")
    if onedrive:
        candidates.append(Path(onedrive) / "Desktop" / "AI HTML Toolbox.lnk")
    candidates.append(Path.home() / "Desktop" / "AI HTML Toolbox.lnk")
    return any(p.is_file() for p in candidates)


def get_setup_status() -> dict[str, Any]:
    """Return setup completeness for first-run UI.

    complete / showFirstRun:
      - complete = critical files + protocol + chrome + success marker
      - showFirstRun = not complete (panel hides only after logged success)
    Server process implies venv imports work (we are already running).
    """
    root = _toolbox_root()
    marker = _read_marker()
    last_run = _read_last_run()
    marker_complete = bool(marker and marker.get("complete"))
    venv_py = root / ".venv" / "Scripts" / "python.exe"

    checks = {
        "launcherHtml": (root / "Toolbox Launcher.html").is_file(),
        "launchBat": (root / "Launch-AI-HTML-Toolbox.bat").is_file(),
        "protocolBat": (root / "server" / "protocol_start.bat").is_file(),
        "venvPython": venv_py.is_file(),
        "venvImportsOk": True,  # server is running in this interpreter
        "protocolRegistered": _protocol_registered(),
        "chromeFound": _chrome_found(),
        "desktopShortcut": _desktop_shortcut_exists(),
        "markerPresent": marker_complete,
        "lastRunLogged": last_run is not None,
    }
    critical_ok = all(
        [
            checks["launcherHtml"],
            checks["launchBat"],
            checks["protocolBat"],
            checks["venvPython"],
            checks["protocolRegistered"],
            checks["chromeFound"],
        ]
    )
    complete = bool(critical_ok and marker_complete)
    missing: list[str] = []
    if not checks["venvPython"]:
        missing.append("Python virtual environment (.venv)")
    if not checks["protocolRegistered"]:
        missing.append("aitoolbox:// protocol registration")
    if not checks["chromeFound"]:
        missing.append("Google Chrome")
    if not checks["desktopShortcut"]:
        missing.append("Desktop shortcut (optional)")
    if not checks["markerPresent"]:
        missing.append("First-run setup completion marker")

    last_run_summary = None
    if last_run:
        last_run_summary = {
            "ok": bool(last_run.get("ok")),
            "complete": bool(last_run.get("complete")),
            "ranAt": last_run.get("ranAt"),
            "failed": bool(last_run.get("failed")),
        }

    return {
        "complete": complete,
        "readyToLaunch": critical_ok,
        "showFirstRun": not complete,
        "toolboxRoot": str(root),
        "markerPath": str(marker_path()),
        "lastRunPath": str(last_run_path()),
        "completedAt": (marker or {}).get("completedAt"),
        "lastRun": last_run_summary,
        "checks": checks,
        "missing": missing,
    }
