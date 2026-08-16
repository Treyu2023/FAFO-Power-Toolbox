# -*- coding: utf-8 -*-
"""Deeper nav audit: wrong relative depth, missing Esc, no hub cluster links."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {".venv", "mcps", "node_modules", "Reports", "device-local", "site-packages"}

MEDIA = {
    "Movie File Manager/Media Library Manager.html",
    "Movie File Manager/Media Hub.html",
    "Movie File Manager/File Organizer.html",
    "Movie File Manager/VSR Pipeline Manager.html",
    "Movie File Manager/Compare Hub.html",
    "Movie File Manager/Guided Pair Match.html",
    "Movie File Manager/Pair Review Queue.html",
    "File Tools/Duplicate File Manager.html",
}
SYS = {
    "System Tools/PC Diagnostics HUD.html",
    "System Tools/System Health Dashboard.html",
    "System Tools/System Health Desk.html",
    "System Tools/Hardware Board Map.html",
    "System Tools/Disk Space Analyzer.html",
    "System Tools/Event Viewer.html",
    "System Tools/Event Deep Dive.html",
    "System Tools/FAFO Task Manager Pro.html",
    "System Tools/LAN Task Manager.html",
    "System Tools/Malware Defender.html",
    "System Tools/Startup Service Manager.html",
    "System Tools/PC Reports and Log Viewer/index.html",
}


def depth(rel: str) -> int:
    return len(Path(rel).parts) - 1


def main() -> None:
    print("=== WRONG LAUNCHER DEPTH ===")
    for p in sorted(ROOT.rglob("*.html")):
        if any(x in p.parts for x in SKIP):
            continue
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        if rel == "Toolbox Launcher.html":
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        d = depth(rel)
        expect_ups = d
        for m in re.finditer(r'''(?:href|onclick)=["']([^"']*Toolbox\s*Launcher\.html[^"']*)["']''', t, re.I):
            href = m.group(1).split("?")[0].replace("\\", "/")
            if href.startswith(("http", "file:", "/toolbox")):
                continue
            ups = href.count("../")
            # location.href='../Toolbox...'
            if "Toolbox" not in href:
                continue
            if ups != expect_ups:
                print(f"  {rel}: href={href!r} ups={ups} expect={expect_ups}")

        # location.href patterns
        for m in re.finditer(r'''location\.href\s*=\s*["']([^"']*Toolbox\s*Launcher\.html[^"']*)["']''', t, re.I):
            href = m.group(1).split("?")[0]
            ups = href.count("../")
            if ups != expect_ups and not href.startswith("http"):
                print(f"  {rel}: loc={href!r} ups={ups} expect={expect_ups}")

    print("\n=== MEDIA CLUSTER CROSS-LINKS ===")
    want = {
        "Media Hub": "Media Hub.html",
        "Library": "Media Library Manager.html",
        "VSR": "VSR Pipeline Manager.html",
        "Compare": "Compare Hub.html",
        "Launcher": "Toolbox Launcher.html",
    }
    for rel in sorted(MEDIA):
        p = ROOT / rel
        if not p.is_file():
            print(" missing", rel)
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        miss = []
        for label, frag in want.items():
            if frag not in t and (label != "Launcher" or "Toolbox Launcher" not in t):
                miss.append(label)
        # Pair review / guided only need hub not all
        print(f"  {rel}: miss={miss or 'none'}")

    print("\n=== SYS CLUSTER: Diagnostics ↔ Health ↔ Reports ===")
    for rel in sorted(SYS):
        p = ROOT / rel
        if not p.is_file():
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        links = {
            "Health": "System Health Dashboard" in t or "System Health Desk" in t,
            "Diag": "PC Diagnostics" in t,
            "Reports": "PC Reports" in t or "Log Viewer" in t,
            "Launcher": "Toolbox Launcher" in t,
        }
        print(f"  {Path(rel).name}: {links}")

    print("\n=== ESC → launcher? ===")
    for rel in list(MEDIA) + list(SYS)[:8]:
        p = ROOT / rel
        if not p.is_file():
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        has_esc = bool(re.search(r"Escape|key\s*===\s*['\"]Escape['\"]|keyCode\s*===\s*27", t))
        esc_launcher = bool(re.search(r"Escape[\s\S]{0,200}Launcher|launcherHref|Toolbox Launcher", t, re.I))
        print(f"  {Path(rel).name}: esc_handler={has_esc} esc_mentions_launcher={esc_launcher}")


if __name__ == "__main__":
    main()
