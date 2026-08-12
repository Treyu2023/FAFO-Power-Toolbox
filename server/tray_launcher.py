"""
FAFO system tray — independent control for two separate products:

  S1  HTML Toolbox Server     (127.0.0.87:18765)  — AI HTML Toolbox apps
  S2  Ultimate Tab / Tagger   (127.0.0.1:8765)    — Chrome Ultimate Tab (not Toolbox)

Right-click the tray icon to Sleep / Wake each server so they do not keep
burning RAM and CPU when you are not using that product. Sleep is sticky:
the watchdog will not auto-restart a sleeping server.
"""
from __future__ import annotations

import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent
TOOLBOX_ROOT = SERVER_DIR.parent

if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

try:
    import launch_ops
except ImportError:
    launch_ops = None  # type: ignore

# How often to check / auto-heal servers (seconds)
WATCH_INTERVAL_SEC = 12
# Don't hammer restarts if something is deeply broken
RESTART_COOLDOWN_SEC = 20
_TRAY_MUTEX = "Local\\FAFO_Tray_Launcher_v1"


def _tray_log(msg: str) -> None:
    try:
        import os
        from datetime import datetime

        pc = os.environ.get("COMPUTERNAME", "PC")
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        log_dir = base / "FAFO" / "Devices" / pc / "Logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n"
        with (log_dir / "tray-launcher.log").open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def _acquire_tray_mutex():
    """Prevent duplicate tray processes (they can block each other's heals)."""
    if sys.platform != "win32":
        return True
    try:
        import ctypes

        handle = ctypes.windll.kernel32.CreateMutexW(None, False, _TRAY_MUTEX)  # type: ignore[attr-defined]
        if ctypes.windll.kernel32.GetLastError() == 183:  # type: ignore[attr-defined]
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
            return None
        return handle
    except Exception:
        return True


def _chrome_path() -> Path | None:
    import os

    local = os.environ.get("LOCALAPPDATA", "")
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    for p in (
        Path(pf) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(pf86) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(local) / "Google" / "Chrome" / "Application" / "chrome.exe",
    ):
        if p.is_file():
            return p
    return None


def open_launcher(*, wake_s1: bool = True) -> None:
    """Open Toolbox Launcher. Optionally wake S1 so the page can talk to the API."""
    if wake_s1 and launch_ops:
        try:
            if launch_ops.is_server_sleeping("s1") or not (
                launch_ops._port_open(launch_ops.TOOLBOX_HOST, launch_ops.TOOLBOX_PORT)
            ):
                _tray_log("open_launcher → wake S1 (HTML Toolbox)")
                launch_ops.wake_companions(toolbox=True, fafo_meta=False, wait_sec=10)
        except Exception as e:
            _tray_log(f"open_launcher wake S1 failed: {e}")

    page = TOOLBOX_ROOT / "Toolbox Launcher.html"
    chrome = _chrome_path()
    if chrome and page.is_file():
        try:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            subprocess.Popen(
                [str(chrome), f"--app={page}", "--new-window", "--window-size=1400,900"],
                cwd=str(TOOLBOX_ROOT),
                creationflags=flags,
            )
            return
        except OSError:
            pass
    if page.is_file():
        webbrowser.open(page.as_uri())
    else:
        webbrowser.open("http://127.0.0.87:18765/")


def ensure_servers() -> dict:
    """Lifecycle: S1 with Toolbox session, S2 with Chrome — never force both."""
    if launch_ops:
        try:
            if hasattr(launch_ops, "apply_lifecycle"):
                result = launch_ops.apply_lifecycle(ensure_tray=False)
            else:
                result = launch_ops.start_companions(wait_sec=8, force=False)
            st = result.get("status") or {}
            tb = st.get("toolbox") or {}
            meta = st.get("fafoMeta") or {}
            _tray_log(
                f"lifecycle ok={result.get('ok')} actions={result.get('actions')} "
                f"want={result.get('want')} chrome={result.get('chromeRunning')} "
                f"S1={tb.get('healthy') or tb.get('listening')} sleep={tb.get('sleeping')} sess={tb.get('sessionActive')} "
                f"S2={meta.get('healthy') or meta.get('listening')} sleep={meta.get('sleeping')}"
            )
            return result
        except Exception as e:
            _tray_log(f"ensure_servers error: {e}")
            return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "no launch helper"}


def restart_servers() -> dict:
    if launch_ops and hasattr(launch_ops, "restart_companions"):
        return launch_ops.restart_companions(wait_sec=15, force=True)
    return ensure_servers()


def sleep_s1() -> dict:
    if not launch_ops:
        return {"ok": False}
    _tray_log("sleep S1 HTML Toolbox")
    return launch_ops.sleep_companions(toolbox=True, fafo_meta=False)


def sleep_s2() -> dict:
    if not launch_ops:
        return {"ok": False}
    _tray_log("sleep S2 Ultimate Tab")
    return launch_ops.sleep_companions(toolbox=False, fafo_meta=True)


def sleep_both() -> dict:
    if not launch_ops:
        return {"ok": False}
    _tray_log("sleep S1+S2")
    return launch_ops.sleep_companions(toolbox=True, fafo_meta=True)


def wake_s1() -> dict:
    if not launch_ops:
        return {"ok": False}
    _tray_log("wake S1 HTML Toolbox")
    return launch_ops.wake_companions(toolbox=True, fafo_meta=False, wait_sec=12)


def wake_s2() -> dict:
    if not launch_ops:
        return {"ok": False}
    _tray_log("wake S2 Ultimate Tab")
    return launch_ops.wake_companions(toolbox=False, fafo_meta=True, wait_sec=12)


def wake_both() -> dict:
    if not launch_ops:
        return {"ok": False}
    _tray_log("wake S1+S2")
    return launch_ops.wake_companions(toolbox=True, fafo_meta=True, wait_sec=15)


def stop_all_servers() -> None:
    """Legacy: hard stop both + mark sleeping."""
    if not launch_ops:
        return
    try:
        launch_ops.sleep_companions(toolbox=True, fafo_meta=True)
    except Exception:
        try:
            launch_ops.stop_listener_on_port(launch_ops.TOOLBOX_PORT, launch_ops.TOOLBOX_HOST)
            launch_ops.stop_listener_on_port(launch_ops.META_PORT, launch_ops.META_HOST)
        except Exception:
            pass


def _need_heal() -> bool:
    """True if a host-bound server should be up but is down (or S2 should stop)."""
    if not launch_ops:
        return False
    try:
        prefs = launch_ops.get_prefs()
        st = launch_ops.companion_status()
        tb_up = bool(st["toolbox"].get("healthy") or st["toolbox"].get("listening"))
        meta_up = bool(st["fafoMeta"].get("healthy") or st["fafoMeta"].get("listening"))
        want_s1 = launch_ops.should_auto_run_s1(prefs)
        want_s2 = launch_ops.should_auto_run_s2(prefs)
        if want_s1 and not tb_up:
            return True
        if want_s2 and not meta_up:
            return True
        # Chrome closed → stop S2 to free resources
        if (not want_s2) and meta_up and not launch_ops.servers_sleeping(prefs).get("fafoMetaServer"):
            return True
        return False
    except Exception:
        return True


def status_line(watching: bool = True) -> str:
    if not launch_ops:
        return "FAFO"
    try:
        st = launch_ops.companion_status()
        sleep = st.get("serversSleeping") or {}
        tb = st.get("toolbox") or {}
        meta = st.get("fafoMeta") or {}
        chrome = bool(st.get("chromeRunning"))

        def _part(up: bool, sleeping: bool, label: str, host: str) -> str:
            if sleeping and not up:
                return f"{label} sleep"
            if up:
                return f"{label} ON"
            return f"{label} off ({host})"

        s1 = _part(
            bool(tb.get("healthy") or tb.get("listening")),
            bool(sleep.get("toolboxServer") or tb.get("sleeping")),
            "S1 Toolbox",
            "open Toolbox",
        )
        s2 = _part(
            bool(meta.get("healthy") or meta.get("listening")),
            bool(sleep.get("fafoMetaServer") or meta.get("sleeping")),
            "S2 Tab",
            "Chrome" if not chrome else "starting",
        )
        base = f"FAFO  ·  {s1}  ·  {s2}"
        return base + ("  ·  lifecycle" if watching else "  ·  paused")
    except Exception:
        return "FAFO  ·  S1 w/ Toolbox  ·  S2 w/ Chrome"


def main() -> None:
    mutex = _acquire_tray_mutex()
    if mutex is None:
        _tray_log("duplicate tray exit — another tray_launcher already holds mutex")
        try:
            ensure_servers()
        except Exception:
            pass
        return

    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        print("Install: pip install pystray pillow  (use INSTALL-PYTHON.bat / .venv)")
        ensure_servers()
        last = 0.0
        while True:
            time.sleep(WATCH_INTERVAL_SEC)
            if time.time() - last < RESTART_COOLDOWN_SEC:
                continue
            if _need_heal():
                _tray_log("headless heal")
                ensure_servers()
                last = time.time()
        return

    state = {"busy": False, "last_heal": 0.0, "watch": True}
    _tray_log("tray started (S1=HTML Toolbox, S2=Ultimate Tab — independent)")

    # First bring-up: only non-sleeping servers
    threading.Thread(target=ensure_servers, daemon=True).start()

    img = Image.new("RGB", (64, 64), (5, 5, 12))
    d = ImageDraw.Draw(img)
    d.rectangle([8, 8, 56, 56], outline=(0, 243, 255), width=3)
    d.text((16, 20), "AI", fill=(0, 243, 255))

    def _run_bg(fn, icon=None):
        if state["busy"]:
            return

        def work():
            state["busy"] = True
            try:
                fn()
            finally:
                state["busy"] = False
                try:
                    if icon:
                        icon.title = status_line(state["watch"])
                except Exception:
                    pass

        threading.Thread(target=work, daemon=True).start()

    def on_open(icon, item):
        def job():
            open_launcher(wake_s1=True)
            state["last_heal"] = time.time()

        _run_bg(job, icon)

    def on_wake_s1(icon, item):
        def job():
            wake_s1()
            state["last_heal"] = time.time()

        _run_bg(job, icon)

    def on_sleep_s1(icon, item):
        def job():
            sleep_s1()
            state["last_heal"] = time.time()

        _run_bg(job, icon)

    def on_wake_s2(icon, item):
        def job():
            wake_s2()
            state["last_heal"] = time.time()

        _run_bg(job, icon)

    def on_sleep_s2(icon, item):
        def job():
            sleep_s2()
            state["last_heal"] = time.time()

        _run_bg(job, icon)

    def on_sleep_both(icon, item):
        def job():
            sleep_both()
            state["last_heal"] = time.time()

        _run_bg(job, icon)

    def on_wake_both(icon, item):
        def job():
            wake_both()
            state["last_heal"] = time.time()

        _run_bg(job, icon)

    def on_apply_lifecycle(icon, item):
        def job():
            ensure_servers()
            state["last_heal"] = time.time()

        _run_bg(job, icon)

    def on_restart(icon, item):
        def job():
            restart_servers()
            state["last_heal"] = time.time()

        _run_bg(job, icon)

    def on_toggle_watch(icon, item):
        state["watch"] = not state["watch"]
        icon.title = status_line(state["watch"])

    def on_quit_tray(icon, item):
        # Leave servers running (or sleeping) as-is
        icon.stop()

    def on_sleep_and_quit(icon, item):
        def job():
            state["watch"] = False
            sleep_both()

        _run_bg(job, icon)

        def later():
            time.sleep(0.8)
            icon.stop()

        threading.Thread(target=later, daemon=True).start()

    menu = pystray.Menu(
        pystray.MenuItem("Open HTML Toolbox (starts S1)", on_open, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "S1 · HTML Toolbox (with Toolbox)",
            pystray.Menu(
                pystray.MenuItem("▶ Start / wake S1", on_wake_s1),
                pystray.MenuItem("💤 Sleep S1 (free resources)", on_sleep_s1),
            ),
        ),
        pystray.MenuItem(
            "S2 · Ultimate Tab (with Chrome)",
            pystray.Menu(
                pystray.MenuItem("▶ Start / wake S2 (manual)", on_wake_s2),
                pystray.MenuItem("💤 Sleep S2 (block auto)", on_sleep_s2),
            ),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("▶ Apply lifecycle now (S1=Toolbox, S2=Chrome)", on_apply_lifecycle),
        pystray.MenuItem("💤 Sleep both (free resources)", on_sleep_both),
        pystray.MenuItem(
            "Lifecycle auto (S1↔Toolbox, S2↔Chrome)",
            on_toggle_watch,
            checked=lambda item: state["watch"],
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit tray (leave servers as-is)", on_quit_tray),
        pystray.MenuItem("Sleep both & quit tray", on_sleep_and_quit),
    )

    icon = pystray.Icon("fafo_toolbox", img, status_line(True), menu)

    def watchdog_loop():
        """While tray is open: heal only non-sleeping companions that should be up."""
        while True:
            time.sleep(WATCH_INTERVAL_SEC)
            try:
                icon.title = status_line(state["watch"])
            except Exception:
                break
            if not state["watch"] or state["busy"]:
                continue
            now = time.time()
            if now - state["last_heal"] < RESTART_COOLDOWN_SEC:
                continue
            if _need_heal():
                _tray_log("watchdog heal triggered (non-sleeping only)")
                state["busy"] = True
                try:
                    ensure_servers()
                    state["last_heal"] = time.time()
                except Exception as e:
                    _tray_log(f"watchdog heal error: {e}")
                finally:
                    state["busy"] = False
                try:
                    icon.title = status_line(state["watch"])
                except Exception:
                    break

    threading.Thread(target=watchdog_loop, daemon=True).start()
    icon.run()


if __name__ == "__main__":
    main()
