"""Windows REG QoL tweaks — status probe + allowlisted apply.

Loopback toolbox only. Never run arbitrary registry paths from the browser:
each tweak id maps to a frozen catalog of keys.
"""
from __future__ import annotations

import os
import platform
import subprocess
from typing import Any

IS_WINDOWS = platform.system() == "Windows"
try:
    import winreg  # type: ignore
except ImportError:
    winreg = None  # type: ignore

_CREATE = subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0

HIVES = {
    "HKCU": getattr(winreg, "HKEY_CURRENT_USER", None) if winreg else None,
    "HKLM": getattr(winreg, "HKEY_LOCAL_MACHINE", None) if winreg else None,
    "HKCR": getattr(winreg, "HKEY_CLASSES_ROOT", None) if winreg else None,
}

# Classic Win11 context-menu blocker CLSID
_CLASSIC_MENU_CLSID = r"Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32"
_COPY_TO = "{C2FBB630-2971-11D1-A18C-00C04FD75D13}"
_MOVE_TO = "{C2FBB631-2971-11D1-A18C-00C04FD75D13}"


def _tweak(
    id: str,
    cat: str,
    name: str,
    file: str,
    desc: str,
    checks: list[dict[str, Any]],
    sets: list[dict[str, Any]],
    *,
    optional: bool = False,
    needs_admin: bool = False,
    restart_explorer: bool = False,
    deletes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": id,
        "cat": cat,
        "name": name,
        "file": file,
        "desc": desc,
        "optional": optional,
        "needsAdmin": needs_admin,
        "restartExplorer": restart_explorer,
        "checks": checks,
        "sets": sets,
        "deletes": deletes or [],
    }


CATALOG: list[dict[str, Any]] = [
    _tweak(
        "classic-menu",
        "Explorer",
        "Restore Classic Right-Click Menu",
        "restore classic context menu.bat",
        "Windows 11 hides third-party tools behind Show more options. Restores the classic Windows 10 context menu so Notepad++, ExifTool, and scripts appear immediately.",
        checks=[{"hive": "HKCU", "key": _CLASSIC_MENU_CLSID, "name": "", "op": "exists"}],
        sets=[{"hive": "HKCU", "key": _CLASSIC_MENU_CLSID, "name": "", "type": "sz", "value": ""}],
        restart_explorer=True,
    ),
    _tweak(
        "long-paths",
        "AI / Dev",
        "Enable Win32 Long Paths",
        "Enable Win32 Long Paths Crucial for AIDocker.bat",
        "Removes the 260-character path limit. Essential for ComfyUI, Pinokio, Docker, and nested AI node installs that otherwise fail silently. May need reboot / admin.",
        checks=[{
            "hive": "HKLM",
            "key": r"SYSTEM\CurrentControlSet\Control\FileSystem",
            "name": "LongPathsEnabled",
            "op": "eq",
            "value": 1,
        }],
        sets=[{
            "hive": "HKLM",
            "key": r"SYSTEM\CurrentControlSet\Control\FileSystem",
            "name": "LongPathsEnabled",
            "type": "dword",
            "value": 1,
        }],
        needs_admin=True,
    ),
    _tweak(
        "file-sniff",
        "Explorer",
        "Speed Up Explorer (Disable Folder Sniffing)",
        "1 Disable File Sniff on open in windows to speed system up.bat",
        "Stops Windows from scanning folder contents to auto-apply Video/Picture layouts. Heavy media folders open as a generic list instantly; also tames Downloads date grouping.",
        checks=[{
            "hive": "HKCU",
            "key": r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\Bags\AllFolders\Shell",
            "name": "FolderType",
            "op": "eq",
            "value": "NotSpecified",
        }],
        sets=[{
            "hive": "HKCU",
            "key": r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\Bags\AllFolders\Shell",
            "name": "FolderType",
            "type": "sz",
            "value": "NotSpecified",
        }],
        deletes=[
            {"hive": "HKCU", "key": r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\Bags"},
            {"hive": "HKCU", "key": r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\BagMRU"},
        ],
        restart_explorer=True,
    ),
    _tweak(
        "copy-move",
        "Explorer",
        "Add Copy To / Move To Menu",
        "2 Add Copy To and Move To in the Right-Click Menu.bat",
        "Adds Copy To folder and Move To folder on the right-click menu so you can route files across drives without accidental drag-drops.",
        checks=[
            {
                "hive": "HKCU",
                "key": r"Software\Classes\AllFilesystemObjects\shellex\ContextMenuHandlers\Copy To",
                "name": "",
                "op": "eq",
                "value": _COPY_TO,
            },
            {
                "hive": "HKCU",
                "key": r"Software\Classes\AllFilesystemObjects\shellex\ContextMenuHandlers\Move To",
                "name": "",
                "op": "eq",
                "value": _MOVE_TO,
            },
        ],
        sets=[
            {
                "hive": "HKCU",
                "key": r"Software\Classes\AllFilesystemObjects\shellex\ContextMenuHandlers\Copy To",
                "name": "",
                "type": "sz",
                "value": _COPY_TO,
            },
            {
                "hive": "HKCU",
                "key": r"Software\Classes\AllFilesystemObjects\shellex\ContextMenuHandlers\Move To",
                "name": "",
                "type": "sz",
                "value": _MOVE_TO,
            },
        ],
        restart_explorer=True,
    ),
    _tweak(
        "show-ext",
        "Explorer",
        "Force Show Extensions & Hidden Files",
        "3. Force Show File Extensions and Hidden Files.bat",
        "Always show .mp4 / .mkv / .png / .webp and unhide system/app data folders (.git, .docker caches) — critical when managing mixed media and code.",
        checks=[
            {
                "hive": "HKCU",
                "key": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                "name": "HideFileExt",
                "op": "eq",
                "value": 0,
            },
            {
                "hive": "HKCU",
                "key": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                "name": "Hidden",
                "op": "eq",
                "value": 1,
            },
        ],
        sets=[
            {
                "hive": "HKCU",
                "key": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                "name": "HideFileExt",
                "type": "dword",
                "value": 0,
            },
            {
                "hive": "HKCU",
                "key": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                "name": "Hidden",
                "type": "dword",
                "value": 1,
            },
        ],
        restart_explorer=True,
    ),
    _tweak(
        "notepad",
        "Apps",
        "Regedit Fix Notepad",
        "regedit fix notepad.bat",
        "Rebuilds .txt as a real text file with New > Text Document on the desktop when Store Notepad or a broken association gets in the way.",
        checks=[
            {"hive": "HKCU", "key": r"Software\Classes\.txt", "name": "", "op": "eq", "value": "txtfile"},
            {"hive": "HKCU", "key": r"Software\Classes\.txt\ShellNew", "name": "NullFile", "op": "exists"},
        ],
        sets=[
            {"hive": "HKCU", "key": r"Software\Classes\.txt", "name": "", "type": "sz", "value": "txtfile"},
            {"hive": "HKCU", "key": r"Software\Classes\.txt", "name": "Content Type", "type": "sz", "value": "text/plain"},
            {"hive": "HKCU", "key": r"Software\Classes\.txt", "name": "PerceivedType", "type": "sz", "value": "text"},
            {"hive": "HKCU", "key": r"Software\Classes\.txt\ShellNew", "name": "NullFile", "type": "sz", "value": ""},
            {"hive": "HKCU", "key": r"Software\Classes\txtfile", "name": "", "type": "sz", "value": "Text Document"},
        ],
        restart_explorer=True,
    ),
    _tweak(
        "no-bing",
        "Start / Taskbar",
        "Disable Bing Web Search in Start",
        "4 Disable Bing Search in Start.bat",
        "Stops Start search from querying Bing. Local apps, settings, and files come back instantly on a fast machine.",
        checks=[
            {
                "hive": "HKCU",
                "key": r"Software\Microsoft\Windows\CurrentVersion\Search",
                "name": "BingSearchEnabled",
                "op": "eq",
                "value": 0,
            },
            {
                "hive": "HKCU",
                "key": r"Software\Policies\Microsoft\Windows\Explorer",
                "name": "DisableSearchBoxSuggestions",
                "op": "eq",
                "value": 1,
            },
        ],
        sets=[
            {
                "hive": "HKCU",
                "key": r"Software\Microsoft\Windows\CurrentVersion\Search",
                "name": "BingSearchEnabled",
                "type": "dword",
                "value": 0,
            },
            {
                "hive": "HKCU",
                "key": r"Software\Microsoft\Windows\CurrentVersion\Search",
                "name": "CortanaConsent",
                "type": "dword",
                "value": 0,
            },
            {
                "hive": "HKCU",
                "key": r"Software\Policies\Microsoft\Windows\Explorer",
                "name": "DisableSearchBoxSuggestions",
                "type": "dword",
                "value": 1,
            },
        ],
        optional=True,
        restart_explorer=True,
    ),
    _tweak(
        "taskbar-seconds",
        "Start / Taskbar",
        "Show Seconds on the Clock",
        "5 Show Seconds on Taskbar Clock.bat",
        "Puts seconds on the notification-area clock. Handy when timing encodes, captures, or waiting on a reboot.",
        checks=[{
            "hive": "HKCU",
            "key": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
            "name": "ShowSecondsInSystemClock",
            "op": "eq",
            "value": 1,
        }],
        sets=[{
            "hive": "HKCU",
            "key": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
            "name": "ShowSecondsInSystemClock",
            "type": "dword",
            "value": 1,
        }],
        optional=True,
        restart_explorer=True,
    ),
    _tweak(
        "hide-widgets",
        "Start / Taskbar",
        "Hide Widgets / News Button",
        "6 Hide Widgets News Button.bat",
        "Removes the Widgets / News and Interests button from the taskbar so weather and MSN feed clicks stop stealing focus.",
        checks=[{
            "hive": "HKCU",
            "key": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
            "name": "TaskbarDa",
            "op": "eq",
            "value": 0,
        }],
        sets=[{
            "hive": "HKCU",
            "key": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
            "name": "TaskbarDa",
            "type": "dword",
            "value": 0,
        }],
        optional=True,
        restart_explorer=True,
    ),
    _tweak(
        "end-task",
        "Start / Taskbar",
        "End Task from the Taskbar",
        "7 Enable End Task on Taskbar.bat",
        "Adds End task to a right-click on a running app’s taskbar icon — faster than opening Task Manager for a stuck preview or encode.",
        checks=[{
            "hive": "HKCU",
            "key": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
            "name": "TaskbarEndTask",
            "op": "eq",
            "value": 1,
        }],
        sets=[{
            "hive": "HKCU",
            "key": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
            "name": "TaskbarEndTask",
            "type": "dword",
            "value": 1,
        }],
        optional=True,
    ),
    _tweak(
        "this-pc",
        "Explorer",
        "Explorer Opens to This PC",
        "8 Explorer Opens to This PC.bat",
        "File Explorer starts on This PC instead of Home / Quick Access, so drives and project folders are the first thing you see.",
        checks=[{
            "hive": "HKCU",
            "key": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
            "name": "LaunchTo",
            "op": "eq",
            "value": 1,
        }],
        sets=[{
            "hive": "HKCU",
            "key": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
            "name": "LaunchTo",
            "type": "dword",
            "value": 1,
        }],
        optional=True,
    ),
    _tweak(
        "no-shake",
        "Explorer",
        "Disable Aero Shake Minimize",
        "9 Disable Aero Shake.bat",
        "Stops grabbing a window title bar and shaking it from minimizing everything else — a common accident on a crowded compare / preview desktop.",
        checks=[{
            "hive": "HKCU",
            "key": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
            "name": "DisallowShaking",
            "op": "eq",
            "value": 1,
        }],
        sets=[{
            "hive": "HKCU",
            "key": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
            "name": "DisallowShaking",
            "type": "dword",
            "value": 1,
        }],
        optional=True,
    ),
    _tweak(
        "fast-menus",
        "Input",
        "Instant Menus (No Hover Delay)",
        "10 Instant Menus.bat",
        "Sets MenuShowDelay to 0 so cascading right-click menus open immediately instead of waiting ~400 ms.",
        checks=[{
            "hive": "HKCU",
            "key": r"Control Panel\Desktop",
            "name": "MenuShowDelay",
            "op": "eq",
            "value": "0",
        }],
        sets=[{
            "hive": "HKCU",
            "key": r"Control Panel\Desktop",
            "name": "MenuShowDelay",
            "type": "sz",
            "value": "0",
        }],
        optional=True,
        restart_explorer=True,
    ),
    _tweak(
        "no-suggestions",
        "Start / Taskbar",
        "Disable Start & Lock Suggestions",
        "11 Disable Start and Lock Suggestions.bat",
        "Turns off lock-screen fun facts, Start suggestions, and silent Store app installs so the machine stops advertising at you.",
        checks=[
            {
                "hive": "HKCU",
                "key": r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
                "name": "SystemPaneSuggestionsEnabled",
                "op": "eq",
                "value": 0,
            },
            {
                "hive": "HKCU",
                "key": r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
                "name": "SilentInstalledAppsEnabled",
                "op": "eq",
                "value": 0,
            },
            {
                "hive": "HKCU",
                "key": r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
                "name": "RotatingLockScreenOverlayEnabled",
                "op": "eq",
                "value": 0,
            },
        ],
        sets=[
            {
                "hive": "HKCU",
                "key": r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
                "name": "SystemPaneSuggestionsEnabled",
                "type": "dword",
                "value": 0,
            },
            {
                "hive": "HKCU",
                "key": r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
                "name": "SilentInstalledAppsEnabled",
                "type": "dword",
                "value": 0,
            },
            {
                "hive": "HKCU",
                "key": r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
                "name": "SoftLandingEnabled",
                "type": "dword",
                "value": 0,
            },
            {
                "hive": "HKCU",
                "key": r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
                "name": "RotatingLockScreenOverlayEnabled",
                "type": "dword",
                "value": 0,
            },
            {
                "hive": "HKCU",
                "key": r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
                "name": "SubscribedContent-338387Enabled",
                "type": "dword",
                "value": 0,
            },
            {
                "hive": "HKCU",
                "key": r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
                "name": "SubscribedContent-338388Enabled",
                "type": "dword",
                "value": 0,
            },
            {
                "hive": "HKCU",
                "key": r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
                "name": "SubscribedContent-338389Enabled",
                "type": "dword",
                "value": 0,
            },
        ],
        optional=True,
    ),
    _tweak(
        "no-sticky",
        "Input",
        "Disable Sticky Keys Popup",
        "12 Disable Sticky Keys Popup.bat",
        "Stops the Sticky Keys / Filter Keys accessibility prompt when Shift is held — a frequent interrupt during long keyboard work.",
        checks=[
            {
                "hive": "HKCU",
                "key": r"Control Panel\Accessibility\StickyKeys",
                "name": "Flags",
                "op": "eq",
                "value": "506",
            },
            {
                "hive": "HKCU",
                "key": r"Control Panel\Accessibility\Keyboard Response",
                "name": "Flags",
                "op": "eq",
                "value": "122",
            },
        ],
        sets=[
            {
                "hive": "HKCU",
                "key": r"Control Panel\Accessibility\StickyKeys",
                "name": "Flags",
                "type": "sz",
                "value": "506",
            },
            {
                "hive": "HKCU",
                "key": r"Control Panel\Accessibility\Keyboard Response",
                "name": "Flags",
                "type": "sz",
                "value": "122",
            },
            {
                "hive": "HKCU",
                "key": r"Control Panel\Accessibility\ToggleKeys",
                "name": "Flags",
                "type": "sz",
                "value": "58",
            },
        ],
        optional=True,
    ),
    _tweak(
        "verbose-status",
        "System",
        "Verbose Startup / Shutdown Status",
        "13 Verbose Startup Shutdown Status.bat",
        "Shows the real driver / service names during boot and shutdown instead of generic Please wait. Needs admin; helps when a hang is on a specific service.",
        checks=[{
            "hive": "HKLM",
            "key": r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System",
            "name": "VerboseStatus",
            "op": "eq",
            "value": 1,
        }],
        sets=[{
            "hive": "HKLM",
            "key": r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System",
            "name": "VerboseStatus",
            "type": "dword",
            "value": 1,
        }],
        optional=True,
        needs_admin=True,
    ),
]

BY_ID = {t["id"]: t for t in CATALOG}


def catalog_public() -> list[dict[str, Any]]:
    """UI-safe catalog (no apply payloads required, but sets stay — they are allowlisted)."""
    out = []
    for t in CATALOG:
        out.append({
            "id": t["id"],
            "cat": t["cat"],
            "name": t["name"],
            "file": t["file"],
            "desc": t["desc"],
            "optional": t["optional"],
            "needsAdmin": t["needsAdmin"],
            "restartExplorer": t["restartExplorer"],
            "checks": t["checks"],
        })
    return out


def _norm(val: Any) -> Any:
    if isinstance(val, bool):
        return int(val)
    if isinstance(val, bytes):
        try:
            return val.decode("utf-16le").rstrip("\x00")
        except Exception:
            return val
    return val


def _read(hive: str, key: str, name: str) -> tuple[bool, Any]:
    if not IS_WINDOWS or not winreg:
        return False, None
    h = HIVES.get(hive)
    if h is None:
        return False, None
    try:
        with winreg.OpenKey(h, key) as k:  # type: ignore[union-attr]
            val, _typ = winreg.QueryValueEx(k, name if name else None)  # type: ignore[union-attr]
            return True, _norm(val)
    except OSError:
        return False, None


def _check_one(spec: dict[str, Any]) -> dict[str, Any]:
    present, val = _read(spec["hive"], spec["key"], spec.get("name") or "")
    op = spec.get("op") or "exists"
    expected = spec.get("value")
    ok = False
    if op == "exists":
        ok = present
    elif op == "eq":
        if present:
            if isinstance(expected, int):
                try:
                    ok = int(val) == int(expected)
                except (TypeError, ValueError):
                    ok = False
            else:
                ok = str(val) == str(expected)
    return {
        "hive": spec["hive"],
        "key": spec["key"],
        "name": spec.get("name") or "(default)",
        "op": op,
        "expected": expected,
        "present": present,
        "actual": val if present else None,
        "ok": ok,
    }


def evaluate(tweak: dict[str, Any]) -> dict[str, Any]:
    details = [_check_one(c) for c in tweak.get("checks") or []]
    if not details:
        applied: bool | None = None
    elif not IS_WINDOWS:
        applied = None
    else:
        applied = all(d["ok"] for d in details)
    return {
        "id": tweak["id"],
        "applied": applied,
        "readable": IS_WINDOWS and winreg is not None,
        "details": details,
    }


def status() -> dict[str, Any]:
    rows = [evaluate(t) for t in CATALOG]
    applied_n = sum(1 for r in rows if r["applied"] is True)
    missing_n = sum(1 for r in rows if r["applied"] is False)
    unknown_n = sum(1 for r in rows if r["applied"] is None)
    return {
        "ok": True,
        "live": bool(IS_WINDOWS and winreg),
        "platform": platform.system(),
        "applied": applied_n,
        "missing": missing_n,
        "unknown": unknown_n,
        "count": len(rows),
        "tweaks": rows,
        "catalog": catalog_public(),
    }


def _set_value(spec: dict[str, Any]) -> None:
    if not IS_WINDOWS or not winreg:
        raise RuntimeError("Registry writes only run on Windows")
    hive = spec["hive"]
    h = HIVES.get(hive)
    if h is None:
        raise RuntimeError("Unknown hive " + hive)
    key = spec["key"]
    name = spec.get("name") or ""
    typ = (spec.get("type") or "sz").lower()
    value = spec.get("value")
    access = winreg.KEY_SET_VALUE  # type: ignore[union-attr]
    k = winreg.CreateKeyEx(h, key, 0, access)  # type: ignore[union-attr]
    try:
        value_name = name if name else None
        if typ == "dword":
            winreg.SetValueEx(k, value_name, 0, winreg.REG_DWORD, int(value))  # type: ignore[union-attr]
        else:
            winreg.SetValueEx(k, value_name, 0, winreg.REG_SZ, "" if value is None else str(value))  # type: ignore[union-attr]
    finally:
        winreg.CloseKey(k)  # type: ignore[union-attr]


def _delete_key(spec: dict[str, Any]) -> None:
    if not IS_WINDOWS or not winreg:
        return
    h = HIVES.get(spec["hive"])
    if h is None:
        return
    key = spec["key"]
    parent, _, leaf = key.rpartition("\\")
    if not parent or not leaf:
        return
    try:
        with winreg.OpenKey(h, parent, 0, winreg.KEY_WRITE) as k:  # type: ignore[union-attr]
            _delete_tree(k, leaf)
    except OSError:
        return


def _delete_tree(parent: Any, name: str) -> None:
    if not winreg:
        return
    try:
        with winreg.OpenKey(parent, name, 0, winreg.KEY_READ | winreg.KEY_WRITE) as k:  # type: ignore[union-attr]
            while True:
                try:
                    sub = winreg.EnumKey(k, 0)  # type: ignore[union-attr]
                except OSError:
                    break
                _delete_tree(k, sub)
        winreg.DeleteKey(parent, name)  # type: ignore[union-attr]
    except OSError:
        return


def apply(tweak_id: str, restart_explorer: bool = False) -> dict[str, Any]:
    tid = (tweak_id or "").strip().lower()
    tweak = BY_ID.get(tid)
    if not tweak:
        raise ValueError("Unknown tweak id")
    if not IS_WINDOWS or not winreg:
        raise RuntimeError("Registry writes only run on Windows")

    wrote: list[str] = []
    errors: list[str] = []
    needs_admin = False

    for d in tweak.get("deletes") or []:
        try:
            _delete_key(d)
            wrote.append("del " + d.get("key", ""))
        except OSError as e:
            errors.append(str(e)[:160])

    for spec in tweak.get("sets") or []:
        try:
            _set_value(spec)
            label = spec["hive"] + "\\" + spec["key"] + "\\" + (spec.get("name") or "(default)")
            wrote.append(label)
        except OSError as e:
            msg = str(e)
            if spec.get("hive") == "HKLM" or "Access is denied" in msg or getattr(e, "winerror", None) == 5:
                needs_admin = True
            errors.append(msg[:160])
        except PermissionError as e:
            needs_admin = True
            errors.append(str(e)[:160])

    restarted = False
    if restart_explorer and tweak.get("restartExplorer") and not errors:
        restarted = _restart_explorer()

    after = evaluate(tweak)
    return {
        "ok": after.get("applied") is True or (not errors and bool(wrote)),
        "id": tid,
        "wrote": wrote,
        "errors": errors,
        "needsAdmin": needs_admin or tweak.get("needsAdmin") and after.get("applied") is not True,
        "restartedExplorer": restarted,
        "applied": after.get("applied"),
        "details": after.get("details"),
        "name": tweak["name"],
    }


def _restart_explorer() -> bool:
    if not IS_WINDOWS:
        return False
    try:
        subprocess.run(["taskkill", "/f", "/im", "explorer.exe"], capture_output=True, timeout=8, creationflags=_CREATE)
        subprocess.Popen(["explorer.exe"], shell=False, creationflags=_CREATE)
        return True
    except Exception:
        return False


def restart_explorer() -> dict[str, Any]:
    ok = _restart_explorer()
    return {"ok": ok, "restartedExplorer": ok}


def bats_dir() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "REG Tweak AI Bat Files")
