"""
FAFO Server Watchdog — independent monitor for S1 + S2.

Runs as a single-instance process (Scheduled Task or manual). Every poll it:
  • Health-checks S1 (127.0.0.87:18765/api/health) and S2 (127.0.0.1:8765/api/health)
  • Auto-starts / recovers configured companions via launch_ops
  • Enforces ONE process tree each for: this watchdog, tray, S1, S2
    (venv parent+child re-exec is one tree — never split)
  • Detects crash loops, duplicate processes, listen-without-health
  • Writes status JSON + HTML report under %LOCALAPPDATA%\\FAFO\\Devices\\<PC>\\
  • Raises Windows toast / balloon when attention is required

Usage:
  python server_watchdog.py              # run forever
  python server_watchdog.py --once       # single check + heal
  python server_watchdog.py --status     # print status JSON and exit
  python server_watchdog.py --install-task   # register logon Scheduled Task
  python server_watchdog.py --uninstall-task
"""
from __future__ import annotations

import argparse
import atexit
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SERVER_DIR = Path(__file__).resolve().parent
TOOLBOX_ROOT = SERVER_DIR.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import launch_ops  # noqa: E402

POLL_SEC = 15
# After this many failed heals in a rolling window → ATTENTION
FAIL_WINDOW_SEC = 600
FAIL_THRESHOLD = 4
# Don't restart more often than this per server
HEAL_COOLDOWN_SEC = 18
TASK_NAME = "FAFO-Server-Watchdog"
MUTEX_NAME = "Global\\FAFO_Server_Watchdog_v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _device_root() -> Path:
    pc = os.environ.get("COMPUTERNAME", "PC")
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    root = base / "FAFO" / "Devices" / pc
    (root / "Logs").mkdir(parents=True, exist_ok=True)
    (root / "Reports").mkdir(parents=True, exist_ok=True)
    (root / "Prefs").mkdir(parents=True, exist_ok=True)
    return root


def _log_path() -> Path:
    return _device_root() / "Logs" / "server-watchdog.log"


def _status_json_path() -> Path:
    return _device_root() / "Reports" / "server-watchdog-status.json"


def _status_html_path() -> Path:
    return _device_root() / "Reports" / "server-watchdog-status.html"


def log(msg: str, level: str = "INFO") -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {msg}"
    try:
        with _log_path().open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    try:
        print(line, flush=True)
    except Exception:
        pass


def _acquire_mutex() -> Any | None:
    """Return a live mutex handle, or None if another watchdog is already running."""
    if sys.platform != "win32":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        last = kernel32.GetLastError()
        # ERROR_ALREADY_EXISTS = 183
        if last == 183:
            if handle:
                kernel32.CloseHandle(handle)
            return None
        return handle
    except Exception as e:
        log(f"mutex unavailable ({e}) — continuing without single-instance lock", "WARN")
        return True


def _release_mutex(handle: Any) -> None:
    if handle is True or handle is None:
        return
    try:
        import ctypes

        ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
    except Exception:
        pass


def _count_cmd_matches(needle: str) -> list[int]:
    pids: list[int] = []
    try:
        import psutil  # type: ignore

        n = needle.lower()
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                name = (p.info.get("name") or "").lower()
                if name not in ("python.exe", "pythonw.exe"):
                    continue
                cmd = " ".join(str(x) for x in (p.info.get("cmdline") or [])).lower()
                if n in cmd:
                    pids.append(int(p.info["pid"]))
            except Exception:
                continue
    except Exception:
        pass
    return pids


def _tree_roots(pids: list[int]) -> list[int]:
    """Return PIDs whose parent is not also in the set (one entry per process tree).

    venv pythonw often re-execs to system pythonw, so one tray/S2 shows as 2 PIDs.
    Counting roots avoids false DUP_* and deadly parent/child trims.
    """
    if not pids:
        return []
    pid_set = set(pids)
    roots: list[int] = []
    try:
        import psutil  # type: ignore

        for pid in pids:
            try:
                ppid = int(psutil.Process(pid).ppid())
            except Exception:
                ppid = -1
            if ppid not in pid_set:
                roots.append(pid)
    except Exception:
        return list(pids)
    return roots


def _pids_in_trees(root_pids: list[int], candidate_pids: list[int]) -> set[int]:
    """Expand root_pids to include any candidates in the same parent/child trees."""
    if not root_pids or not candidate_pids:
        return set(root_pids or [])
    try:
        import psutil  # type: ignore
    except ImportError:
        return set(root_pids)

    cand = set(int(p) for p in candidate_pids)
    protected: set[int] = set(int(r) for r in root_pids) & cand
    # ancestors within candidate set
    for rid in list(protected):
        try:
            cur = psutil.Process(rid)
            for _ in range(8):
                ppid = cur.ppid()
                if not ppid or ppid <= 4:
                    break
                if ppid in cand:
                    protected.add(ppid)
                try:
                    cur = psutil.Process(ppid)
                except Exception:
                    break
        except Exception:
            continue
    # descendants within candidate set
    ppid_of: dict[int, int] = {}
    for pid in cand:
        try:
            ppid_of[pid] = int(psutil.Process(pid).ppid())
        except Exception:
            ppid_of[pid] = 0
    changed = True
    while changed:
        changed = False
        for pid, ppid in ppid_of.items():
            if pid in protected:
                continue
            if ppid in protected:
                protected.add(pid)
                changed = True
    return protected


def _iter_python_cmd_matches(needles: list[str] | tuple[str, ...]) -> list[Any]:
    """Return psutil Process objects for python/pythonw whose cmdline contains all needles."""
    try:
        import psutil  # type: ignore
    except ImportError:
        return []
    needles_l = [n.lower() for n in needles]
    found: list[Any] = []
    for p in psutil.process_iter(["pid", "name", "cmdline", "create_time", "ppid"]):
        try:
            name = (p.info.get("name") or "").lower()
            if name not in ("python.exe", "pythonw.exe"):
                continue
            cmd = " ".join(str(x) for x in (p.info.get("cmdline") or [])).lower()
            if all(n in cmd for n in needles_l):
                found.append(p)
        except Exception:
            continue
    return found


def _kill_proc(p: Any, reason: str) -> bool:
    try:
        pid = int(p.pid)
        p.terminate()
        try:
            p.wait(timeout=2)
        except Exception:
            p.kill()
        log(f"killed {reason} PID {pid}", "WARN")
        return True
    except Exception as e:
        try:
            pid = int(p.pid)
        except Exception:
            pid = -1
        log(f"could not kill {reason} PID {pid}: {e}", "WARN")
        return False


def _trim_extra_trees(
    label: str,
    procs: list[Any],
    *,
    keep_root: int | None = None,
    prefer_newest: bool = True,
) -> int:
    """Keep one process tree; kill all other independent trees. Returns kill count.

    Parent+child re-exec (venv → system python) is one tree and is never split.
    """
    if len(procs) <= 1:
        return 0
    by_pid: dict[int, Any] = {}
    for p in procs:
        try:
            by_pid[int(p.pid)] = p
        except Exception:
            continue
    all_pids = list(by_pid.keys())
    roots = _tree_roots(all_pids)
    if len(roots) <= 1:
        return 0

    if keep_root is not None and keep_root in all_pids:
        # Map keep pid to its tree root
        keep = keep_root
        # If keep_root is a child, its root is the tree root containing it
        for r in roots:
            if keep_root in _pids_in_trees([r], all_pids):
                keep = r
                break
    else:
        roots_sorted = sorted(
            roots,
            key=lambda pid: (by_pid[pid].info.get("create_time") or 0) if pid in by_pid else 0,
            reverse=prefer_newest,
        )
        keep = roots_sorted[0]

    protected = _pids_in_trees([keep], all_pids)
    killed = 0
    for pid, p in by_pid.items():
        if pid in protected:
            continue
        if _kill_proc(
            p,
            f"duplicate {label} (kept root={keep}, protected={sorted(protected)})",
        ):
            killed += 1
    return killed


def _self_watchdog_tree_pids() -> set[int]:
    """PIDs in this process's server_watchdog tree (self + ancestors/descendants matching)."""
    me = os.getpid()
    procs = _iter_python_cmd_matches(["server_watchdog.py"])
    all_pids = []
    for p in procs:
        try:
            all_pids.append(int(p.pid))
        except Exception:
            continue
    if me not in all_pids:
        all_pids.append(me)
    return _pids_in_trees([me], all_pids) or {me}


def _trim_duplicate_watchdogs() -> int:
    """Leave only this watchdog's process tree; kill any other independent instances."""
    procs = _iter_python_cmd_matches(["server_watchdog.py"])
    if len(procs) <= 1:
        return 0
    return _trim_extra_trees("watchdog", procs, keep_root=os.getpid(), prefer_newest=True)


def _trim_duplicate_trays() -> int:
    """Keep one tray_launcher tree; kill only independent extra trees.

    Critical: venv pythonw re-execs to system pythonw — both show tray_launcher.py.
    Killing the parent of that pair drops the tray (NO_TRAY thrash loop).
    """
    trays = _iter_python_cmd_matches(["tray_launcher.py"])
    return _trim_extra_trees("tray", trays, prefer_newest=True)


def _trim_duplicate_s1() -> int:
    """If multiple aitoolbox_server trees, keep the one that owns S1 port (or newest)."""
    try:
        import psutil  # type: ignore
    except ImportError:
        return 0
    procs = _iter_python_cmd_matches(["aitoolbox_server.py"])
    if len(procs) <= 1:
        return 0
    holders: set[int] = set()
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.status != psutil.CONN_LISTEN:
                continue
            if (
                conn.laddr
                and int(conn.laddr.port) == launch_ops.TOOLBOX_PORT
                and conn.pid
            ):
                holders.add(int(conn.pid))
    except Exception:
        holders = set()
    keep = next(iter(holders), None)
    return _trim_extra_trees("S1", procs, keep_root=keep, prefer_newest=True)


def _trim_duplicate_s2() -> int:
    """If multiple explorer-meta server.py processes, keep the tree that owns port 8765.

    Critical: the LISTEN PID is often a *child* of the launcher process. Killing the
    parent takes S2 down. Protect holders AND all their ancestors/descendants.
    Only kill processes in completely separate trees.
    """
    try:
        import psutil  # type: ignore
    except ImportError:
        return 0
    if not launch_ops._port_open(launch_ops.META_HOST, launch_ops.META_PORT):
        return 0
    holders: set[int] = set()
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.status != psutil.CONN_LISTEN:
                continue
            if conn.laddr and int(conn.laddr.port) == launch_ops.META_PORT and conn.pid:
                holders.add(int(conn.pid))
    except Exception:
        return 0
    if not holders:
        return 0  # can't identify owner — do not risk killing live S2

    procs: list[Any] = []
    by_pid: dict[int, Any] = {}
    for p in psutil.process_iter(["pid", "name", "cmdline", "ppid", "create_time"]):
        try:
            name = (p.info.get("name") or "").lower()
            if name not in ("python.exe", "pythonw.exe"):
                continue
            cmd = " ".join(str(x) for x in (p.info.get("cmdline") or [])).lower()
            if "explorer-meta" in cmd and "server.py" in cmd:
                procs.append(p)
                by_pid[int(p.info["pid"])] = p
        except Exception:
            continue
    if len(procs) <= 1:
        return 0

    # Protected = holder + walk parents + walk children within S2 set
    protected: set[int] = set(holders)
    # ancestors
    for hid in list(holders):
        try:
            cur = psutil.Process(hid)
            for _ in range(8):
                ppid = cur.ppid()
                if not ppid or ppid <= 4:
                    break
                if ppid in by_pid:
                    protected.add(ppid)
                try:
                    cur = psutil.Process(ppid)
                except Exception:
                    break
        except Exception:
            continue
    # descendants (any S2 whose parent chain hits protected)
    changed = True
    while changed:
        changed = False
        for pid, p in by_pid.items():
            if pid in protected:
                continue
            try:
                ppid = int(p.info.get("ppid") or 0)
            except Exception:
                try:
                    ppid = int(psutil.Process(pid).ppid())
                except Exception:
                    ppid = 0
            if ppid in protected:
                protected.add(pid)
                changed = True

    killed = 0
    for p in procs:
        pid = int(p.pid)
        if pid in protected:
            continue
        try:
            p.terminate()
            try:
                p.wait(timeout=2)
            except Exception:
                p.kill()
            killed += 1
            log(
                f"killed orphan S2 PID {pid} (protected tree={sorted(protected)}, "
                f"holders={sorted(holders)})",
                "WARN",
            )
        except Exception as e:
            log(f"could not kill S2 PID {pid}: {e}", "WARN")

    # Verify S2 still up; if not, start it immediately
    time.sleep(0.4)
    if not launch_ops._port_open(launch_ops.META_HOST, launch_ops.META_PORT):
        log("S2 port dropped after orphan trim — restarting S2", "ERROR")
        try:
            launch_ops.start_fafo_meta_server()
            # brief wait for bind
            for _ in range(12):
                time.sleep(0.5)
                if launch_ops._port_open(launch_ops.META_HOST, launch_ops.META_PORT):
                    break
        except Exception as e:
            log(f"S2 restart after trim failed: {e}", "ERROR")
    return killed


def _windows_toast(title: str, body: str) -> None:
    """Best-effort user-visible alert (no admin). Non-blocking; never hangs the watchdog."""
    if sys.platform != "win32":
        return
    try:
        import subprocess

        # Write a simple attention popup via mshta (fast, no PS runtime toast quirks)
        msg = _ps_escape(f"{title}\n\n{body}")
        # Also append to a desktop-visible attention log
        try:
            att = _device_root() / "Reports" / "last-toast.txt"
            att.write_text(f"{_utc_now()}\n{title}\n{body}\n", encoding="utf-8")
        except OSError:
            pass
        # Fire-and-forget; short timeout parent doesn't wait
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-WindowStyle",
                "Hidden",
                "-Command",
                f"try {{ "
                f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null; "
                f"$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
                f"[Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
                f"$n = $t.GetElementsByTagName('text'); "
                f"$n.Item(0).AppendChild($t.CreateTextNode('{_ps_escape(title)}')) | Out-Null; "
                f"$n.Item(1).AppendChild($t.CreateTextNode('{_ps_escape(body)}')) | Out-Null; "
                f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('FAFO Watchdog')"
                f".Show([Windows.UI.Notifications.ToastNotification]::new($t)) "
                f"}} catch {{ }}",
            ],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        log(f"toast failed: {e}", "WARN")


def _ps_escape(s: str) -> str:
    return s.replace("'", "''").replace("\n", " ").replace("\r", " ")[:240]


def _server_state(st: dict[str, Any]) -> dict[str, Any]:
    """Build issues list. Critical attention only when a host-bound server *should* be up."""
    prefs = st.get("prefs") or {}
    sleep = st.get("serversSleeping") or prefs.get("serversSleeping") or {}
    tb = st.get("toolbox") or {}
    meta = st.get("fafoMeta") or {}
    sleep_tb = bool(sleep.get("toolboxServer") or tb.get("sleeping"))
    sleep_meta = bool(sleep.get("fafoMetaServer") or meta.get("sleeping"))
    # Prefer lifecycle helpers (session / Chrome / manual hold) over bare one-click flags
    try:
        want_tb = bool(launch_ops.should_auto_run_s1(prefs))
        want_meta = bool(launch_ops.should_auto_run_s2(prefs))
    except Exception:
        want = prefs.get("startWithOneClick") or {}
        want_tb = bool(want.get("toolboxServer", True)) and not sleep_tb
        want_meta = bool(want.get("fafoMetaServer", True)) and not sleep_meta
    tb_up = bool(tb.get("healthy") or tb.get("listening"))
    meta_up = bool(meta.get("healthy") or meta.get("listening"))
    issues: list[dict[str, str]] = []

    if sleep_tb and not tb_up:
        issues.append(
            {
                "code": "S1_SLEEPING",
                "severity": "info",
                "message": (
                    "S1 HTML Toolbox is sleeping (user stopped it) — "
                    "wake from tray: S1 · HTML Toolbox → Start / wake S1"
                ),
            }
        )
    elif want_tb and not tb.get("listening"):
        issues.append(
            {
                "code": "S1_DOWN",
                "severity": "critical",
                "message": "S1 HTML Toolbox Server is not listening on 127.0.0.87:18765",
            }
        )
    elif want_tb and tb.get("listening") and not tb.get("healthy"):
        # Port open + failed health is often "still booting" after a start — not always wedged
        issues.append(
            {
                "code": "S1_STARTING",
                "severity": "warning",
                "message": "S1 is listening but health not ready yet (starting or overloaded)",
            }
        )
    elif (not want_tb) and (not sleep_tb) and (not tb_up):
        issues.append(
            {
                "code": "S1_IDLE",
                "severity": "info",
                "message": "S1 idle — open HTML Toolbox or Start All to run the server",
            }
        )

    if sleep_meta and not meta_up:
        issues.append(
            {
                "code": "S2_SLEEPING",
                "severity": "info",
                "message": (
                    "S2 Ultimate Tab / Local Media is sleeping (user stopped it) — "
                    "wake from tray: S2 · Ultimate Tab → Start / wake S2"
                ),
            }
        )
    elif want_meta and not meta.get("listening"):
        root_ok = bool((meta.get("root") or {}).get("ok"))
        issues.append(
            {
                "code": "S2_DOWN",
                "severity": "critical" if root_ok else "warning",
                "message": (
                    "S2 Ultimate Tab / Local Media Tagger is not listening on 127.0.0.1:8765"
                    if root_ok
                    else "S2 down and explorer-meta path not resolved — set fafoMetaRoot"
                ),
            }
        )
    elif want_meta and meta.get("listening") and not meta.get("healthy"):
        issues.append(
            {
                "code": "S2_STARTING",
                "severity": "warning",
                "message": "S2 is listening but health not ready yet (starting or overloaded)",
            }
        )
    elif (not want_meta) and (not sleep_meta) and (not meta_up):
        issues.append(
            {
                "code": "S2_IDLE",
                "severity": "info",
                "message": "S2 idle — opens with Chrome, or Start S2 / Start All anytime",
            }
        )

    trays = _count_cmd_matches("tray_launcher.py")
    tray_roots = _tree_roots(trays)
    if len(tray_roots) > 1:
        issues.append(
            {
                "code": "DUP_TRAY",
                "severity": "warning",
                "message": (
                    f"Multiple tray trees running (roots={tray_roots}, pids={trays}) "
                    f"— auto-trim keeps one"
                ),
            }
        )
    if len(trays) == 0:
        issues.append(
            {
                "code": "NO_TRAY",
                "severity": "info",
                "message": "Tray icon not running (watchdog still covers auto-heal)",
            }
        )

    wd_pids = _count_cmd_matches("server_watchdog.py")
    wd_roots = _tree_roots(wd_pids)
    if len(wd_roots) > 1:
        issues.append(
            {
                "code": "DUP_WATCHDOG",
                "severity": "warning",
                "message": (
                    f"Multiple watchdog trees (roots={wd_roots}, pids={wd_pids}) "
                    f"— auto-trim keeps this instance"
                ),
            }
        )

    # S2 process list: uvicorn/spawn often shows parent+child (2 PIDs) for ONE server.
    # Only warn when there are multiple independent process trees (true duplicates).
    meta_only: list[int] = []
    try:
        import psutil  # type: ignore

        for p in psutil.process_iter(["pid", "ppid", "cmdline"]):
            try:
                cmd = " ".join(str(x) for x in (p.info.get("cmdline") or [])).lower()
                if "explorer-meta" in cmd and "server.py" in cmd:
                    meta_only.append(int(p.info["pid"]))
            except Exception:
                continue
    except Exception:
        meta_only = _count_cmd_matches("explorer-meta")

    meta_roots = _tree_roots(meta_only)

    # Multiple LISTEN holders on 8765 is a real port fight
    s2_holders: list[int] = []
    try:
        import psutil  # type: ignore

        for conn in psutil.net_connections(kind="inet"):
            try:
                if conn.status != psutil.CONN_LISTEN:
                    continue
                if conn.laddr and int(conn.laddr.port) == launch_ops.META_PORT and conn.pid:
                    s2_holders.append(int(conn.pid))
            except Exception:
                continue
        s2_holders = sorted(set(s2_holders))
    except Exception:
        s2_holders = []

    if len(s2_holders) > 1 or len(meta_roots) > 1:
        issues.append(
            {
                "code": "DUP_S2",
                "severity": "warning",
                "message": (
                    f"Multiple S2 instances (trees={meta_roots}, listen={s2_holders or meta_only}) "
                    f"— auto-trim keeps the listener tree"
                ),
            }
        )

    s1_pids = _count_cmd_matches("aitoolbox_server.py")
    s1_roots = _tree_roots(s1_pids)
    if len(s1_roots) > 1:
        issues.append(
            {
                "code": "DUP_S1",
                "severity": "warning",
                "message": (
                    f"Multiple S1 instances (trees={s1_roots}, pids={s1_pids}) "
                    f"— auto-trim keeps the listener tree"
                ),
            }
        )

    critical = [i for i in issues if i["severity"] == "critical"]
    starting = [i for i in issues if i["code"] in ("S1_STARTING", "S2_STARTING")]
    # "attention" only for hard downs — not for transient starting health blips or sleep
    attention = bool(critical)
    return {
        "want_tb": want_tb,
        "want_meta": want_meta,
        "sleep_tb": sleep_tb,
        "sleep_meta": sleep_meta,
        "tb_up": tb_up,
        "meta_up": meta_up,
        "tb_healthy": bool(tb.get("healthy")),
        "meta_healthy": bool(meta.get("healthy")),
        "tb_listening": bool(tb.get("listening")),
        "meta_listening": bool(meta.get("listening")),
        "tray_pids": trays,
        "tray_roots": tray_roots,
        "watchdog_pids": wd_pids,
        "watchdog_roots": wd_roots,
        "s1_pids": s1_pids,
        "s1_roots": s1_roots,
        "s2_pids": meta_only,
        "s2_roots": meta_roots,
        "s2_holders": s2_holders,
        "issues": issues,
        "attention": attention,
        "starting": bool(starting),
        "all_ok": (not want_tb or tb_up) and (not want_meta or meta_up) and not critical,
    }


def _write_status_html(payload: dict[str, Any]) -> None:
    st = payload.get("servers") or {}
    issues = payload.get("issues") or []
    att = payload.get("attentionRequired")
    s1_sleep = bool(st.get("s1_sleeping"))
    s2_sleep = bool(st.get("s2_sleeping"))
    both_sleep = s1_sleep and s2_sleep and not st.get("s1_up") and not st.get("s2_up")
    color = "#ff4466" if att else ("#ffcc44" if (s1_sleep or s2_sleep) else "#00ff88")
    badge = (
        "ATTENTION REQUIRED"
        if att
        else ("SLEEPING (resources freed)" if both_sleep else ("PARTIAL SLEEP" if (s1_sleep or s2_sleep) else "ALL CLEAR"))
    )

    def _s_label(up: bool, sleeping: bool) -> str:
        if up:
            return "UP"
        if sleeping:
            return "SLEEP"
        return "DOWN"

    def _s_cls(up: bool, sleeping: bool) -> str:
        if up:
            return "ok"
        if sleeping:
            return "sleep"
        return "bad"

    rows = ""
    for i in issues:
        rows += (
            f"<tr><td>{i.get('severity')}</td><td><code>{i.get('code')}</code></td>"
            f"<td>{i.get('message')}</td></tr>"
        )
    if not rows:
        rows = "<tr><td colspan=3>No issues</td></tr>"
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="30">
<title>FAFO Server Watchdog</title>
<style>
body{{font-family:Segoe UI,system-ui,sans-serif;background:#0a0a10;color:#e8e8ec;padding:24px}}
h1{{color:#00f3ff;font-weight:300;letter-spacing:2px}}
.badge{{display:inline-block;padding:6px 12px;border-radius:999px;background:{color}22;
border:1px solid {color};color:{color};font-weight:700}}
.card{{background:#12121a;border:1px solid #00f3ff33;border-radius:12px;padding:16px;margin:12px 0}}
table{{width:100%;border-collapse:collapse}} td,th{{padding:8px;border-bottom:1px solid #ffffff12;text-align:left}}
.ok{{color:#00ff88}} .bad{{color:#ff4466}} .sleep{{color:#ffcc44}} .muted{{color:#888}}
</style></head><body>
<h1>FAFO Server Watchdog</h1>
<p class="badge">{badge}</p>
<p class="muted">Updated {payload.get("updatedAt")} · poll every {POLL_SEC}s ·
auto-heal only for <em>non-sleeping</em> servers · tray Sleep is sticky</p>
<div class="card">
<strong>S1 HTML Toolbox</strong>
<span class="{_s_cls(bool(st.get("s1_up")), s1_sleep)}">{_s_label(bool(st.get("s1_up")), s1_sleep)}</span>
· http://127.0.0.87:18765
<span class="muted">(Toolbox apps only)</span><br>
<strong>S2 Ultimate Tab / Local Media</strong>
<span class="{_s_cls(bool(st.get("s2_up")), s2_sleep)}">{_s_label(bool(st.get("s2_up")), s2_sleep)}</span>
· http://127.0.0.1:8765
<span class="muted">(Chrome Ultimate Tab — not Toolbox)</span><br>
<strong>Heals (session)</strong> {payload.get("healsSession", 0)}
· <strong>Failed heals (10m)</strong> {payload.get("failedHealsWindow", 0)}
</div>
<div class="card"><h3>Issues</h3>
<table><tr><th>Severity</th><th>Code</th><th>Message</th></tr>{rows}</table>
</div>
<div class="card muted">
Tray: right-click → S1 / S2 Sleep or Wake independently.<br>
Log: {_log_path()}<br>
JSON: {_status_json_path()}<br>
This page auto-refreshes every 30s.
</div>
</body></html>
"""
    try:
        _status_html_path().write_text(html, encoding="utf-8")
    except OSError as e:
        log(f"html status write failed: {e}", "WARN")


def build_report(
    st: dict[str, Any],
    state_extra: dict[str, Any],
    healed: list[str] | None = None,
) -> dict[str, Any]:
    snap = _server_state(st)
    payload = {
        "updatedAt": _utc_now(),
        "attentionRequired": snap["attention"] or bool(state_extra.get("crashLoop")),
        "attentionReason": state_extra.get("attentionReason"),
        "servers": {
            "s1_up": snap["tb_up"],
            "s1_healthy": snap["tb_healthy"],
            "s1_sleeping": snap.get("sleep_tb", False),
            "s2_up": snap["meta_up"],
            "s2_healthy": snap["meta_healthy"],
            "s2_sleeping": snap.get("sleep_meta", False),
            "want_s1": snap["want_tb"],
            "want_s2": snap["want_meta"],
            "tray_pids": snap["tray_pids"],
            "s2_pids": snap["s2_pids"],
        },
        "issues": snap["issues"],
        "healedThisCycle": healed or [],
        "healsSession": state_extra.get("healsSession", 0),
        "failedHealsWindow": state_extra.get("failedHealsWindow", 0),
        "crashLoop": bool(state_extra.get("crashLoop")),
        "companionStatus": {
            "toolbox": st.get("toolbox"),
            "fafoMeta": {k: v for k, v in (st.get("fafoMeta") or {}).items() if k != "serves"},
            "windowsStartup": st.get("windowsStartup"),
        },
        "paths": {
            "log": str(_log_path()),
            "statusJson": str(_status_json_path()),
            "statusHtml": str(_status_html_path()),
            "toolboxRoot": str(TOOLBOX_ROOT),
        },
    }
    return payload


def save_report(payload: dict[str, Any]) -> None:
    try:
        _status_json_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as e:
        log(f"json status write failed: {e}", "WARN")
    _write_status_html(payload)
    # Attention flag for other tools
    flag = _device_root() / "Reports" / "ATTENTION-SERVERS.txt"
    try:
        if payload.get("attentionRequired"):
            flag.write_text(
                f"ATTENTION REQUIRED @ {payload.get('updatedAt')}\n"
                f"{payload.get('attentionReason') or ''}\n"
                + "\n".join(
                    f"- [{i.get('severity')}] {i.get('code')}: {i.get('message')}"
                    for i in (payload.get("issues") or [])
                ),
                encoding="utf-8",
            )
        elif flag.is_file():
            flag.unlink()
    except OSError:
        pass


def enforce_single_instances(*, include_watchdog: bool = True) -> list[str]:
    """Every poll: leave only one process tree for tray, S1, S2 (and optionally watchdog).

    Parent+child re-exec pairs count as one tree and are never split.
    Safe to call every cycle — no-ops when already single-instance.

    include_watchdog=False for --once so a one-shot check never kills the
    long-running monitor.
    """
    actions: list[str] = []
    if include_watchdog:
        n_wd = _trim_duplicate_watchdogs()
        if n_wd:
            actions.append(f"trimmed_{n_wd}_dup_watchdogs")
    n_tray = _trim_duplicate_trays()
    if n_tray:
        actions.append(f"trimmed_{n_tray}_dup_trays")
    n_s1 = _trim_duplicate_s1()
    if n_s1:
        actions.append(f"trimmed_{n_s1}_dup_s1")
    n_s2 = _trim_duplicate_s2()
    if n_s2:
        actions.append(f"trimmed_{n_s2}_orphan_s2")
    return actions


def heal_if_needed(session: dict[str, Any]) -> list[str]:
    """Return list of heal actions taken.

    Sleeping servers (user Sleep from tray / Stop) are never auto-started.
    S1 = HTML Toolbox; S2 = Ultimate Tab — independent products, independent sleep.
    """
    actions: list[str] = []
    now = time.time()

    # Always first: collapse multi-instance races to one tree each.
    actions.extend(
        enforce_single_instances(
            include_watchdog=bool(session.get("primary_loop", False))
        )
    )

    st = launch_ops.companion_status()
    snap = _server_state(st)

    if snap.get("sleep_tb") and snap.get("sleep_meta"):
        # Both intentionally off — free resources; keep tray so user can Wake
        if not session.get("logged_both_sleep"):
            log("both S1+S2 sleeping — auto-heal suspended (wake from tray)", "INFO")
            session["logged_both_sleep"] = True
        if not snap.get("tray_pids"):
            try:
                r = launch_ops.start_tray()
                if r.get("started"):
                    actions.append("start_tray_while_sleeping")
                    log("started tray (servers still sleeping — use tray to wake)")
            except Exception as e:
                log(f"tray start while sleeping failed: {e}", "WARN")
        return actions
    session["logged_both_sleep"] = False

    # Lifecycle: S1 with Toolbox session, S2 with Chrome (independent products)
    want_s1 = launch_ops.should_auto_run_s1(st.get("prefs") or launch_ops.get_prefs())
    want_s2 = launch_ops.should_auto_run_s2(st.get("prefs") or launch_ops.get_prefs())
    # Override snap wants with lifecycle (sleep already folded into should_auto_*)
    snap["want_tb"] = want_s1
    snap["want_meta"] = want_s2

    need = False
    if want_s1 and not snap["tb_up"]:
        need = True
    if want_s2 and not snap["meta_up"]:
        need = True
    # Chrome gone → stop S2
    if (not want_s2) and snap["meta_up"] and not snap.get("sleep_meta"):
        need = True

    # Listening but health-fail: require consecutive fails before hard restart
    # (avoids "process may be wedged" spam right after a cold start / reload)
    UNHEALTHY_STREAK_NEED = 3
    if want_s1 and st["toolbox"].get("listening") and not st["toolbox"].get("healthy"):
        streak = int(session.get("s1_unhealthy_streak", 0)) + 1
        session["s1_unhealthy_streak"] = streak
        log(f"S1 health soft-fail streak {streak}/{UNHEALTHY_STREAK_NEED}", "WARN")
        if streak >= UNHEALTHY_STREAK_NEED:
            need = True
            if now - session.get("last_heal", 0) >= HEAL_COOLDOWN_SEC:
                log("S1 health failed repeatedly — hard restart", "WARN")
                try:
                    launch_ops.stop_companions(toolbox=True, fafo_meta=False, mark_sleep=False)
                    time.sleep(0.5)
                except Exception as e:
                    log(f"S1 stop failed: {e}", "ERROR")
                session["s1_unhealthy_streak"] = 0
    else:
        session["s1_unhealthy_streak"] = 0

    if want_s2 and st["fafoMeta"].get("listening") and not st["fafoMeta"].get("healthy"):
        streak2 = int(session.get("s2_unhealthy_streak", 0)) + 1
        session["s2_unhealthy_streak"] = streak2
        log(f"S2 health soft-fail streak {streak2}/{UNHEALTHY_STREAK_NEED}", "WARN")
        if streak2 >= UNHEALTHY_STREAK_NEED:
            need = True
            if now - session.get("last_heal", 0) >= HEAL_COOLDOWN_SEC:
                log("S2 health failed repeatedly — hard restart", "WARN")
                try:
                    launch_ops.stop_companions(toolbox=False, fafo_meta=True, mark_sleep=False)
                    time.sleep(0.4)
                except Exception as e:
                    log(f"S2 stop failed: {e}", "ERROR")
                session["s2_unhealthy_streak"] = 0
    else:
        session["s2_unhealthy_streak"] = 0

    if not need:
        # still ensure tray exists for UI
        if not snap["tray_pids"]:
            try:
                r = launch_ops.start_tray()
                if r.get("started"):
                    actions.append("start_tray")
                    log("started tray icon")
            except Exception as e:
                log(f"tray start failed: {e}", "WARN")
        return actions

    if now - session.get("last_heal", 0) < HEAL_COOLDOWN_SEC:
        return actions

    log(
        f"lifecycle heal: S1 want={want_s1} up={snap['tb_up']} | "
        f"S2 want={want_s2} up={snap['meta_up']} chrome={launch_ops.chrome_running()}",
        "WARN",
    )
    try:
        result = launch_ops.apply_lifecycle(ensure_tray=True)
        session["last_heal"] = time.time()
        session["healsSession"] = int(session.get("healsSession", 0)) + 1
        actions.append("apply_lifecycle")
        actions.extend(result.get("actions") or [])
        st2 = result.get("status") or launch_ops.companion_status()
        snap2 = _server_state(st2)
        ok_s1 = (not want_s1) or snap2["tb_up"]
        ok_s2 = (not want_s2) or snap2["meta_up"]
        if ok_s1 and ok_s2:
            log(
                f"lifecycle ok — S1={'UP' if snap2['tb_up'] else 'idle'} "
                f"S2={'UP' if snap2['meta_up'] else 'idle'} "
                f"actions={result.get('actions')}"
            )
            session["s1_unhealthy_streak"] = 0
            session["s2_unhealthy_streak"] = 0
            # Recovery = clear crash-loop history immediately (do not keep
            # fail_times for the full 10m window or UI stays on "crash loop N").
            if session.get("fail_times"):
                log(
                    f"cleared {len(session.get('fail_times') or [])} failed-heal "
                    f"marker(s) after successful recovery",
                    "INFO",
                )
            session["fail_times"] = []
            session["toast_crash"] = False
        else:
            log(f"lifecycle incomplete: {result.get('actions')}", "ERROR")
            session.setdefault("fail_times", []).append(now)
            session["fail_times"] = [t for t in session["fail_times"] if now - t < FAIL_WINDOW_SEC]
            actions.append("heal_failed")
    except Exception as e:
        session["last_heal"] = time.time()
        session.setdefault("fail_times", []).append(now)
        log(f"heal exception: {e}\n{traceback.format_exc()}", "ERROR")
        actions.append("heal_exception")

    return actions


def _clear_stale_attention_artifacts(reason: str = "recovered") -> None:
    """Wipe toast / attention flag files so UI does not show yesterday's crash loop."""
    root = _device_root() / "Reports"
    try:
        toast = root / "last-toast.txt"
        if toast.is_file():
            toast.write_text(
                f"{_utc_now()}\nALL CLEAR\n{reason}\n",
                encoding="utf-8",
            )
    except OSError:
        pass
    try:
        flag = root / "ATTENTION-SERVERS.txt"
        if flag.is_file():
            flag.unlink()
    except OSError:
        pass


def cycle(session: dict[str, Any]) -> dict[str, Any]:
    healed = heal_if_needed(session)
    st = launch_ops.companion_status()
    snap = _server_state(st)

    # If wanted servers are up and no critical issues, drop crash-loop history.
    # Previously fail_times lingered for FAIL_WINDOW_SEC after recovery → sticky
    # "Crash loop: N failed heals" attention even when S1/S2 were already UP.
    if not snap["attention"] and snap.get("all_ok"):
        if session.get("fail_times"):
            log(
                f"servers healthy — clearing {len(session['fail_times'])} "
                f"crash-loop fail marker(s)",
                "INFO",
            )
            session["fail_times"] = []
            session["toast_crash"] = False
        if session.get("announced_recovery") is not True:
            _clear_stale_attention_artifacts("servers healthy — crash loop cleared")
            session["announced_recovery"] = True
    else:
        session["announced_recovery"] = False

    fails = [t for t in session.get("fail_times", []) if time.time() - t < FAIL_WINDOW_SEC]
    session["fail_times"] = fails
    crash_loop = len(fails) >= FAIL_THRESHOLD
    attention_reason = None
    if crash_loop:
        attention_reason = (
            f"Crash loop: {len(fails)} failed heals in {FAIL_WINDOW_SEC // 60} minutes — "
            "needs immediate attention"
        )
        if not session.get("toast_crash"):
            _windows_toast(
                "FAFO servers need attention",
                attention_reason,
            )
            session["toast_crash"] = True
            log(attention_reason, "CRITICAL")
    elif snap["attention"]:
        attention_reason = "; ".join(i["message"] for i in snap["issues"] if i["severity"] == "critical")
        # Toast once per down episode
        key = "|".join(sorted(i["code"] for i in snap["issues"] if i["severity"] == "critical"))
        if key and session.get("toast_key") != key:
            _windows_toast("FAFO server issue", attention_reason or "Server down — auto-heal running")
            session["toast_key"] = key
            log(f"attention: {attention_reason}", "WARN")
    else:
        session["toast_key"] = None
        session["toast_crash"] = False

    payload = build_report(
        st,
        {
            "healsSession": session.get("healsSession", 0),
            "failedHealsWindow": len(fails),
            "crashLoop": crash_loop,
            "attentionReason": attention_reason,
        },
        healed=healed,
    )
    # If still attention after heal, mark attention
    if crash_loop or any(i["severity"] == "critical" for i in payload["issues"]):
        payload["attentionRequired"] = True
    else:
        payload["attentionRequired"] = False
        payload["attentionReason"] = None
        payload["crashLoop"] = False
    save_report(payload)
    return payload


def _install_startup_shortcut(exe: Path, script: Path) -> dict[str, Any]:
    """User Startup folder .lnk — works without elevated schtasks ONLOGON rights."""
    startup = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    startup.mkdir(parents=True, exist_ok=True)
    lnk = startup / "FAFO Server Watchdog.lnk"
    # VBScript is reliable for .lnk without admin
    vbs = (
        f'Set o = CreateObject("WScript.Shell")\n'
        f'Set s = o.CreateShortcut("{str(lnk).replace(chr(92), chr(92)+chr(92))}")\n'
        f's.TargetPath = "{str(exe).replace(chr(92), chr(92)+chr(92))}"\n'
        f's.Arguments = """{str(script)}"""\n'
        f's.WorkingDirectory = "{str(SERVER_DIR).replace(chr(92), chr(92)+chr(92))}"\n'
        f's.WindowStyle = 7\n'
        f's.Description = "FAFO S1+S2 Server Watchdog"\n'
        f's.Save\n'
    )
    # Simpler: write a tiny .cmd launcher into Startup (no COM rights issues)
    cmd_path = startup / "FAFO Server Watchdog.cmd"
    cmd_path.write_text(
        f'@echo off\r\n'
        f'start "" /MIN "{exe}" "{script}"\r\n',
        encoding="utf-8",
    )
    # Remove old lnk if we use cmd
    try:
        if lnk.is_file():
            lnk.unlink()
    except OSError:
        pass
    return {"ok": True, "path": str(cmd_path)}


def install_task() -> dict[str, Any]:
    """Register keep-alive: Startup folder (logon) + 5-minute Scheduled Task poll."""
    if sys.platform != "win32":
        return {"ok": False, "error": "Windows only"}
    py = launch_ops._server_python() or Path(sys.executable)
    script = SERVER_DIR / "server_watchdog.py"
    pyw = Path(str(py).replace("python.exe", "pythonw.exe"))
    exe = pyw if pyw.is_file() else Path(str(py))
    tr = f'"{exe}" "{script}"'
    import subprocess

    # Logon via Startup folder (no admin; ONLOGON schtasks often Access Denied for limited users)
    startup_info = _install_startup_shortcut(exe, script)

    # Delete old logon task if present (optional)
    subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True,
        text=True,
    )
    # 5-minute keep-alive: second instance exits if mutex held, but still heals if primary died
    subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME + "-Poll", "/F"],
        capture_output=True,
        text=True,
    )
    r2 = subprocess.run(
        [
            "schtasks",
            "/Create",
            "/TN",
            TASK_NAME + "-Poll",
            "/TR",
            tr,
            "/SC",
            "MINUTE",
            "/MO",
            "5",
            "/RL",
            "LIMITED",
            "/F",
        ],
        capture_output=True,
        text=True,
    )
    try:
        launch_ops.save_prefs({"windowsStartup": {"servers": True}})
    except Exception:
        pass
    ok = bool(startup_info.get("ok")) and r2.returncode == 0
    log(
        f"install: startup={startup_info.get('path')} poll_rc={r2.returncode}"
    )
    return {
        "ok": ok,
        "startup": startup_info,
        "pollTask": TASK_NAME + "-Poll",
        "command": tr,
        "stdout": r2.stdout or "",
        "stderr": r2.stderr or "",
    }


def uninstall_task() -> dict[str, Any]:
    import subprocess

    outs = []
    for name in (TASK_NAME, TASK_NAME + "-Poll"):
        r = subprocess.run(
            ["schtasks", "/Delete", "/TN", name, "/F"],
            capture_output=True,
            text=True,
        )
        outs.append({"name": name, "rc": r.returncode, "out": r.stdout or r.stderr})
    return {"ok": True, "results": outs}


def run_loop() -> int:
    handle = _acquire_mutex()
    if handle is None:
        # Mutex says another instance holds the lock. If that process is real,
        # exit quietly (no competing heal). If only our re-exec parent holds it
        # we still exit; the holder keeps the loop.
        other = [
            p
            for p in _count_cmd_matches("server_watchdog.py")
            if p not in _self_watchdog_tree_pids()
        ]
        if other:
            log(
                f"another watchdog already running (pids={other}) — leaving one instance, exiting",
                "INFO",
            )
        else:
            log(
                "watchdog mutex already held (same tree or race) — exiting duplicate start",
                "INFO",
            )
        return 0

    atexit.register(lambda: _release_mutex(handle))
    # Claim sole instance immediately (kills other independent trees only)
    try:
        n = _trim_duplicate_watchdogs()
        if n:
            log(f"startup: removed {n} extra watchdog process(es)", "WARN")
    except Exception as e:
        log(f"startup watchdog trim failed: {e}", "WARN")

    log(f"watchdog started · toolbox={TOOLBOX_ROOT}")
    session: dict[str, Any] = {
        "healsSession": 0,
        "fail_times": [],
        "last_heal": 0.0,
        "toast_key": None,
        "toast_crash": False,
        "primary_loop": True,  # may trim other watchdog trees
    }
    # Immediate first cycle (includes enforce_single_instances for S1/S2/tray)
    try:
        cycle(session)
    except Exception as e:
        log(f"first cycle error: {e}\n{traceback.format_exc()}", "ERROR")

    while True:
        time.sleep(POLL_SEC)
        try:
            cycle(session)
        except Exception as e:
            log(f"cycle error: {e}\n{traceback.format_exc()}", "ERROR")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FAFO S1/S2 server watchdog")
    parser.add_argument("--once", action="store_true", help="Single check + heal then exit")
    parser.add_argument("--status", action="store_true", help="Print status JSON and exit")
    parser.add_argument("--install-task", action="store_true", help="Register Scheduled Tasks")
    parser.add_argument("--uninstall-task", action="store_true", help="Remove Scheduled Tasks")
    args = parser.parse_args(argv)

    if args.install_task:
        print(json.dumps(install_task(), indent=2))
        return 0
    if args.uninstall_task:
        print(json.dumps(uninstall_task(), indent=2))
        return 0
    if args.status:
        st = launch_ops.companion_status()
        snap = _server_state(st)
        print(json.dumps({"status": snap, "raw": st}, indent=2, default=str))
        return 0 if snap["all_ok"] else 2
    if args.once:
        session: dict[str, Any] = {
            "healsSession": 0,
            "fail_times": [],
            "last_heal": 0.0,
        }
        payload = cycle(session)
        print(json.dumps(payload, indent=2, default=str))
        return 0 if not payload.get("attentionRequired") else 2

    return run_loop() or 0


if __name__ == "__main__":
    raise SystemExit(main())
