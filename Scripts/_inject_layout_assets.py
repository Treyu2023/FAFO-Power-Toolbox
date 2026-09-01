"""One-shot: inject aitoolbox-layout.css/js into multi-panel tools."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def vtag(path: str) -> str:
    return f"{path}?v={VERSION}"

TARGETS = [
    ("Movie File Manager/File Organizer.html", 1),
    ("Movie File Manager/Media Library Manager.html", 1),
    ("Movie File Manager/Media Hub.html", 1),
    ("Movie File Manager/VSR Pipeline Manager.html", 1),
    ("Developer Tools/Git Repository Manager.html", 1),
    ("System Tools/LAN Task Manager.html", 1),
    ("System Tools/System Health Dashboard.html", 1),
    ("System Tools/System Health Desk.html", 1),
    ("System Tools/FAFO Task Manager Pro.html", 1),
    ("System Tools/Disk Space Analyzer.html", 1),
    ("System Tools/Event Viewer.html", 1),
    ("System Tools/Event Deep Dive.html", 1),
    ("System Tools/Hardware Board Map.html", 1),
    ("System Tools/Startup Service Manager.html", 1),
    ("System Tools/Malware Defender.html", 1),
    ("Verifone Tools/Commander Site Console.html", 1),
    ("Video Tools/FAFO_VID_TRIM.html", 1),
    ("Startup Command Board.html", 0),
    ("Setup Configurator.html", 0),
]


def inject_assets(html: str, depth: int) -> str:
    prefix = "../" * depth
    css_tag = f'<link rel="stylesheet" href="{vtag(prefix + "shared/aitoolbox-layout.css")}">'
    js_tag = f'<script src="{vtag(prefix + "shared/aitoolbox-layout.js")}"></script>'
    if "aitoolbox-layout.css" not in html:
        html2, n = re.subn(
            r'(<link[^>]+aitoolbox-ui\.css"[^>]*>)',
            r"\1\n" + css_tag,
            html,
            count=1,
            flags=re.I,
        )
        html = html2 if n else html.replace("</head>", css_tag + "\n</head>", 1)
    if "aitoolbox-layout.js" not in html:
        html2, n = re.subn(
            r'(<script[^>]+aitoolbox-ui\.js"[^>]*></script>)',
            r"\1\n" + js_tag,
            html,
            count=1,
            flags=re.I,
        )
        if n:
            html = html2
        else:
            html2, n = re.subn(
                r'(<script[^>]+aitoolbox-pro\.js"[^>]*></script>)',
                js_tag + "\n" + r"\1",
                html,
                count=1,
                flags=re.I,
            )
            html = html2 if n else html
    return html


def main() -> None:
    for rel, depth in TARGETS:
        p = ROOT / rel
        if not p.is_file():
            print("MISSING", rel)
            continue
        text = p.read_text(encoding="utf-8")
        new = inject_assets(text, depth)
        if new != text:
            p.write_text(new, encoding="utf-8")
            print("assets", rel)
        else:
            print("skip-assets", rel)


if __name__ == "__main__":
    main()
