"""
FAFO / AI HTML Toolbox system tray + watchdog.

While this tray process is running it:
  • Keeps companion servers alive (hidden — no console windows)
  • Polls health every few seconds and auto-restarts if they die
  • Offers Open Launcher / Restart / Stop without browsing install folders

No UAC required (loopback only).
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


def open_launcher() -> None:
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
    if launch_ops:
        # start_companions also ensures tray — already running, fine
        return launch_ops.start_companions(wait_sec=10)
    ps1 = TOOLBOX_ROOT / "Scripts" / "Start-FAFOServers.ps1"
    if ps1.is_file():
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-WindowStyle",
                "Hidden",
                "-File",
                str(ps1),
                "-ToolboxRoot",
                str(TOOLBOX_ROOT),
                "-Quiet",
                "-NoTray",
            ],
            creationflags=flags,
        )
        return {"ok": True, "via": "Start-FAFOServers.ps1"}
    return {"ok": False, "error": "no launch helper"}


def restart_servers() -> dict:
    if launch_ops and hasattr(launch_ops, "restart_companions"):
        return launch_ops.restart_companions(wait_sec=15)
    return ensure_servers()


def stop_all_servers() -> None:
    if not launch_ops:
        return
    try:
        launch_ops.stop_listener_on_port(launch_ops.TOOLBOX_PORT, launch_ops.TOOLBOX_HOST)
        launch_ops.stop_listener_on_port(launch_ops.META_PORT, launch_ops.META_HOST)
    except Exception:
        pass


def _need_heal() -> bool:
    """True if a configured companion is down."""
    if not launch_ops:
        return False
    try:
        prefs = launch_ops.get_prefs()
        st = launch_ops.companion_status()
        want_tb = prefs.get("startWithOneClick", {}).get("toolboxServer", True)
        want_meta = prefs.get("startWithOneClick", {}).get("fafoMetaServer", True)
        tb_up = bool(st["toolbox"].get("healthy") or st["toolbox"].get("listening"))
        meta_up = bool(st["fafoMeta"].get("healthy") or st["fafoMeta"].get("listening"))
        if want_tb and not tb_up:
            return True
        if want_meta and not meta_up:
            # Only auto-heal meta if we know where it lives
            root = st.get("fafoMeta", {}).get("root") or {}
            if root.get("ok") or prefs.get("fafoMetaRoot"):
                return True
        return False
    except Exception:
        return True  # assume need ensure on status failure


def status_line(watching: bool = True) -> str:
    if not launch_ops:
        return "FAFO Toolbox"
    try:
        st = launch_ops.companion_status()
        tb = "ON" if st["toolbox"].get("healthy") or st["toolbox"].get("listening") else "off"
        meta = "ON" if st["fafoMeta"].get("healthy") or st["fafoMeta"].get("listening") else "off"
        base = f"FAFO  ·  S1 Toolbox {tb}  ·  S2 Tagger {meta}"
        return base + ("  ·  auto-keep" if watching else "")
    except Exception:
        return "FAFO  ·  S1/S2  ·  auto-keep"


def main() -> None:
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        print("Install: pip install pystray pillow  (use INSTALL-PYTHON.bat / .venv)")
        ensure_servers()
        # Headless watchdog without tray UI
        last = 0.0
        while True:
            time.sleep(WATCH_INTERVAL_SEC)
            if time.time() - last < RESTART_COOLDOWN_SEC:
                continue
            if _need_heal():
                ensure_servers()
                last = time.time()
        return

    state = {"busy": False, "last_heal": 0.0, "watch": True}

    # First bring-up
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
        open_launcher()

    def on_ensure(icon, item):
        _run_bg(ensure_servers, icon)

    def on_restart(icon, item):
        def job():
            restart_servers()
            state["last_heal"] = time.time()

        _run_bg(job, icon)

    def on_toggle_watch(icon, item):
        state["watch"] = not state["watch"]
        icon.title = status_line(state["watch"])

    def on_quit_tray(icon, item):
        # Leave servers running
        icon.stop()

    def on_stop_all(icon, item):
        def job():
            state["watch"] = False
            stop_all_servers()

        _run_bg(job, icon)

        def later():
            time.sleep(0.8)
            icon.stop()

        threading.Thread(target=later, daemon=True).start()

    menu = pystray.Menu(
        pystray.MenuItem("Open Toolbox Launcher", on_open, default=True),
        pystray.MenuItem("Start / recover S1+S2", on_ensure),
        pystray.MenuItem("Restart S1+S2", on_restart),
        pystray.MenuItem(
            "Auto-keep S1+S2 running",
            on_toggle_watch,
            checked=lambda item: state["watch"],
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit tray (keep servers)", on_quit_tray),
        pystray.MenuItem("Stop S1+S2 & quit tray", on_stop_all),
    )

    icon = pystray.Icon("fafo_toolbox", img, status_line(True), menu)

    def watchdog_loop():
        """While tray is open: heal dead companions automatically."""
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
                state["busy"] = True
                try:
                    ensure_servers()
                    state["last_heal"] = time.time()
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
