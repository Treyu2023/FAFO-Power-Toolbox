"""
FAFO Server Watchdog — independent monitor for S1 + S2.

Runs as a single-instance process (Scheduled Task or manual). Every poll it:
  • Health-checks S1 (127.0.0.87:18765/api/health) and S2 (127.0.0.1:8765/api/health)
  • Auto-starts / recovers configured companions via launch_ops
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


def _trim_duplicate_trays() -> int:
    """Keep the newest tray_launcher; kill older duplicates."""
    try:
        import psutil  # type: ignore
    except ImportError:
        return 0
    trays: list[Any] = []
    for p in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
        try:
            name = (p.info.get("name") or "").lower()
            if name not in ("python.exe", "pythonw.exe"):
                continue
            cmd = " ".join(str(x) for x in (p.info.get("cmdline") or [])).lower()
            if "tray_launcher.py" in cmd:
                trays.append(p)
        except Exception:
            continue
    if len(trays) <= 1:
        return 0
    trays.sort(key=lambda p: p.info.get("create_time") or 0, reverse=True)
    killed = 0
    for old in trays[1:]:
        try:
            old.terminate()
            try:
                old.wait(timeout=2)
            except Exception:
                old.kill()
            killed += 1
            log(f"killed duplicate tray PID {old.pid}", "WARN")
        except Exception as e:
            log(f"could not kill tray PID {old.pid}: {e}", "WARN")
    return killed


def _trim_duplicate_s2() -> int:
    """If multiple explorer-meta server.py processes, keep the one holding port 8765.

    Only acts when the port is confirmed listening and at least one holder PID is known.
    Never kills all S2 processes — that would take the service down.
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
    for p in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
        try:
            name = (p.info.get("name") or "").lower()
            if name not in ("python.exe", "pythonw.exe"):
                continue
            cmd = " ".join(str(x) for x in (p.info.get("cmdline") or [])).lower()
            if "explorer-meta" in cmd and "server.py" in cmd:
                procs.append(p)
        except Exception:
            continue
    if len(procs) <= 1:
        return 0
    killed = 0
    for p in procs:
        if p.pid in holders:
            continue
        # Never kill if it would leave zero holders
        try:
            p.terminate()
            try:
                p.wait(timeout=2)
            except Exception:
                p.kill()
            killed += 1
            log(f"killed orphan S2 PID {p.pid} (holder={sorted(holders)})", "WARN")
        except Exception as e:
            log(f"could not kill S2 PID {p.pid}: {e}", "WARN")
    # Verify S2 still up; if not, start it immediately
    if not launch_ops._port_open(launch_ops.META_HOST, launch_ops.META_PORT):
        log("S2 port dropped after orphan trim — restarting S2", "ERROR")
        try:
            launch_ops.start_fafo_meta_server()
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
    prefs = st.get("prefs") or {}
    want = prefs.get("startWithOneClick") or {}
    tb = st.get("toolbox") or {}
    meta = st.get("fafoMeta") or {}
    want_tb = bool(want.get("toolboxServer", True))
    want_meta = bool(want.get("fafoMetaServer", True))
    tb_up = bool(tb.get("healthy") or tb.get("listening"))
    meta_up = bool(meta.get("healthy") or meta.get("listening"))
    issues: list[dict[str, str]] = []

    if want_tb and not tb.get("listening"):
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

    if want_meta and not meta.get("listening"):
        root_ok = bool((meta.get("root") or {}).get("ok"))
        issues.append(
            {
                "code": "S2_DOWN",
                "severity": "critical" if root_ok else "warning",
                "message": (
                    "S2 FAFO Local Media Tagger is not listening on 127.0.0.1:8765"
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

    trays = _count_cmd_matches("tray_launcher.py")
    if len(trays) > 1:
        issues.append(
            {
                "code": "DUP_TRAY",
                "severity": "warning",
                "message": f"Multiple tray watchdogs running (PIDs {trays}) — can block clean heals",
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

    meta_procs = _count_cmd_matches("explorer-meta") + _count_cmd_matches(
        "server.py"
    )
    # rough: count server.py under explorer-meta only
    meta_only = _count_cmd_matches("explorer-meta" + os.sep + "server.py".replace("\\", ""))
    if not meta_only:
        meta_only = [p for p in _count_cmd_matches("server.py") if True]
        # filter via cmdline containing explorer-meta
        try:
            import psutil  # type: ignore

            meta_only = []
            for p in psutil.process_iter(["pid", "cmdline"]):
                cmd = " ".join(str(x) for x in (p.info.get("cmdline") or [])).lower()
                if "explorer-meta" in cmd and "server.py" in cmd:
                    meta_only.append(int(p.info["pid"]))
        except Exception:
            meta_only = []
    if len(meta_only) > 1:
        issues.append(
            {
                "code": "DUP_S2",
                "severity": "warning",
                "message": f"Multiple S2 server.py processes (PIDs {meta_only}) — port fights possible",
            }
        )

    critical = [i for i in issues if i["severity"] == "critical"]
    starting = [i for i in issues if i["code"] in ("S1_STARTING", "S2_STARTING")]
    # "attention" only for hard downs — not for transient starting health blips
    attention = bool(critical)
    return {
        "want_tb": want_tb,
        "want_meta": want_meta,
        "tb_up": tb_up,
        "meta_up": meta_up,
        "tb_healthy": bool(tb.get("healthy")),
        "meta_healthy": bool(meta.get("healthy")),
        "tb_listening": bool(tb.get("listening")),
        "meta_listening": bool(meta.get("listening")),
        "tray_pids": trays,
        "s2_pids": meta_only,
        "issues": issues,
        "attention": attention,
        "starting": bool(starting),
        "all_ok": (not want_tb or tb_up) and (not want_meta or meta_up) and not critical,
    }


def _write_status_html(payload: dict[str, Any]) -> None:
    st = payload.get("servers") or {}
    issues = payload.get("issues") or []
    att = payload.get("attentionRequired")
    color = "#ff4466" if att else "#00ff88"
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
.ok{{color:#00ff88}} .bad{{color:#ff4466}} .muted{{color:#888}}
</style></head><body>
<h1>FAFO Server Watchdog</h1>
<p class="badge">{"ATTENTION REQUIRED" if att else "ALL CLEAR"}</p>
<p class="muted">Updated {payload.get("updatedAt")} · poll every {POLL_SEC}s · auto-heal enabled</p>
<div class="card">
<strong>S1 HTML Toolbox</strong>
<span class="{"ok" if st.get("s1_up") else "bad"}">{"UP" if st.get("s1_up") else "DOWN"}</span>
· http://127.0.0.87:18765<br>
<strong>S2 FAFO Tagger</strong>
<span class="{"ok" if st.get("s2_up") else "bad"}">{"UP" if st.get("s2_up") else "DOWN"}</span>
· http://127.0.0.1:8765<br>
<strong>Heals (session)</strong> {payload.get("healsSession", 0)}
· <strong>Failed heals (10m)</strong> {payload.get("failedHealsWindow", 0)}
</div>
<div class="card"><h3>Issues</h3>
<table><tr><th>Severity</th><th>Code</th><th>Message</th></tr>{rows}</table>
</div>
<div class="card muted">
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
            "s2_up": snap["meta_up"],
            "s2_healthy": snap["meta_healthy"],
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


def heal_if_needed(session: dict[str, Any]) -> list[str]:
    """Return list of heal actions taken."""
    actions: list[str] = []
    now = time.time()
    st = launch_ops.companion_status()
    snap = _server_state(st)

    # Housekeeping: duplicate trays / orphan S2 fight heals
    if len(snap["tray_pids"]) > 1:
        n = _trim_duplicate_trays()
        if n:
            actions.append(f"trimmed_{n}_dup_trays")
    if len(snap.get("s2_pids") or []) > 1:
        n2 = _trim_duplicate_s2()
        if n2:
            actions.append(f"trimmed_{n2}_orphan_s2")

    need = False
    if snap["want_tb"] and not snap["tb_up"]:
        need = True
    if snap["want_meta"] and not snap["meta_up"]:
        need = True

    # Listening but health-fail: require consecutive fails before hard restart
    # (avoids "process may be wedged" spam right after a cold start / reload)
    UNHEALTHY_STREAK_NEED = 3
    if snap["want_tb"] and st["toolbox"].get("listening") and not st["toolbox"].get("healthy"):
        streak = int(session.get("s1_unhealthy_streak", 0)) + 1
        session["s1_unhealthy_streak"] = streak
        log(f"S1 health soft-fail streak {streak}/{UNHEALTHY_STREAK_NEED}", "WARN")
        if streak >= UNHEALTHY_STREAK_NEED:
            need = True
            if now - session.get("last_heal", 0) >= HEAL_COOLDOWN_SEC:
                log("S1 health failed repeatedly — hard restart", "WARN")
                try:
                    launch_ops.stop_companions(toolbox=True, fafo_meta=False)
                    time.sleep(0.5)
                except Exception as e:
                    log(f"S1 stop failed: {e}", "ERROR")
                session["s1_unhealthy_streak"] = 0
    else:
        session["s1_unhealthy_streak"] = 0

    if snap["want_meta"] and st["fafoMeta"].get("listening") and not st["fafoMeta"].get("healthy"):
        streak2 = int(session.get("s2_unhealthy_streak", 0)) + 1
        session["s2_unhealthy_streak"] = streak2
        log(f"S2 health soft-fail streak {streak2}/{UNHEALTHY_STREAK_NEED}", "WARN")
        if streak2 >= UNHEALTHY_STREAK_NEED:
            need = True
            if now - session.get("last_heal", 0) >= HEAL_COOLDOWN_SEC:
                log("S2 health failed repeatedly — hard restart", "WARN")
                try:
                    launch_ops.stop_companions(toolbox=False, fafo_meta=True)
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
        f"heal: S1={'down' if not snap['tb_up'] else 'ok'} "
        f"S2={'down' if not snap['meta_up'] else 'ok'}",
        "WARN",
    )
    try:
        result = launch_ops.start_companions(wait_sec=18)
        session["last_heal"] = time.time()
        session["healsSession"] = int(session.get("healsSession", 0)) + 1
        actions.append("start_companions")
        ok = bool(result.get("ok"))
        st2 = result.get("status") or launch_ops.companion_status()
        snap2 = _server_state(st2)
        if snap2["all_ok"] or (
            (not snap["want_tb"] or snap2["tb_up"])
            and (not snap["want_meta"] or snap2["meta_up"])
        ):
            log(
                f"heal success — S1={'UP' if snap2['tb_up'] else 'down'} "
                f"S2={'UP' if snap2['meta_up'] else 'down'}"
            )
            session["s1_unhealthy_streak"] = 0
            session["s2_unhealthy_streak"] = 0
            session.setdefault("fail_times", [])
            # clear old fails on success
            session["fail_times"] = [
                t for t in session.get("fail_times", []) if now - t < FAIL_WINDOW_SEC
            ]
        else:
            log(f"heal incomplete: {json.dumps(result.get('started'), default=str)[:400]}", "ERROR")
            session.setdefault("fail_times", []).append(now)
            session["fail_times"] = [t for t in session["fail_times"] if now - t < FAIL_WINDOW_SEC]
            if not ok:
                actions.append("heal_failed")
    except Exception as e:
        session["last_heal"] = time.time()
        session.setdefault("fail_times", []).append(now)
        log(f"heal exception: {e}\n{traceback.format_exc()}", "ERROR")
        actions.append("heal_exception")

    return actions


def cycle(session: dict[str, Any]) -> dict[str, Any]:
    healed = heal_if_needed(session)
    st = launch_ops.companion_status()
    snap = _server_state(st)
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
        # Another instance is alive — run a single status/heal attempt that
        # no-ops heavy work if the main loop is healthy, but still write status.
        log("another watchdog is already running — exiting (--once style)", "INFO")
        # Light touch: if servers down, still try heal once (race-safe enough)
        session = {"healsSession": 0, "fail_times": [], "last_heal": 0.0}
        try:
            payload = cycle(session)
            if payload.get("attentionRequired"):
                return 2
        except Exception as e:
            log(f"secondary cycle failed: {e}", "ERROR")
        return 0

    atexit.register(lambda: _release_mutex(handle))
    log(f"watchdog started · toolbox={TOOLBOX_ROOT}")
    session: dict[str, Any] = {
        "healsSession": 0,
        "fail_times": [],
        "last_heal": 0.0,
        "toast_key": None,
        "toast_crash": False,
    }
    # Immediate first cycle
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
