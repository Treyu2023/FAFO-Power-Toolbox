"""System tray launcher — runs server in background with tray icon."""
from __future__ import annotations

import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

SERVER_DIR = Path(__file__).parent
TOOLBOX_ROOT = SERVER_DIR.parent
LAUNCHER = TOOLBOX_ROOT / "Toolbox Launcher.html"


def run_server():
    subprocess.run(
        [sys.executable, str(SERVER_DIR / "aitoolbox_server.py")],
        cwd=str(SERVER_DIR),
    )


def open_launcher():
    webbrowser.open(LAUNCHER.as_uri())


def main():
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        print("Install: pip install pystray pillow")
        run_server()
        return

    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    img = Image.new("RGB", (64, 64), (5, 5, 12))
    d = ImageDraw.Draw(img)
    d.rectangle([8, 8, 56, 56], outline=(0, 243, 255), width=3)
    d.text((18, 22), "AI", fill=(0, 243, 255))

    def on_open(icon, item):
        open_launcher()

    def on_quit(icon, item):
        icon.stop()
        sys.exit(0)

    icon = pystray.Icon(
        "aitoolbox",
        img,
        "AI Toolbox Server",
        menu=pystray.Menu(
            pystray.MenuItem("Open Launcher", on_open),
            pystray.MenuItem("Quit", on_quit),
        ),
    )
    print("AI Toolbox running in system tray.")
    icon.run()


if __name__ == "__main__":
    main()