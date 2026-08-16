# -*- coding: utf-8 -*-
"""Audit production HTML tools for navigation dead-ends and related UX gaps."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {".venv", "mcps", "node_modules", "Reports", "device-local", "site-packages", "Scripts"}

# Heuristic "most used" first (from launcher featured / ops day-to-day)
PRIORITY = [
    "Toolbox Launcher.html",
    "File Tools/Duplicate File Manager.html",
    "Movie File Manager/Media Library Manager.html",
    "Movie File Manager/File Organizer.html",
    "Movie File Manager/VSR Pipeline Manager.html",
    "Movie File Manager/Media Hub.html",
    "Movie File Manager/Compare Hub.html",
    "Movie File Manager/Pair Review Queue.html",
    "System Tools/PC Diagnostics HUD.html",
    "System Tools/System Health Dashboard.html",
    "System Tools/LAN Task Manager.html",
    "System Tools/FAFO Task Manager Pro.html",
    "System Tools/Event Viewer.html",
    "System Tools/Malware Defender.html",
    "Developer Tools/Git Repository Manager.html",
    "Video Tools/FAFO_VID_TRIM.html",
    "Video Tools/Video Comparison Slider Tool.html",
    "Verifone Tools/Commander Site Console.html",
    "Verifone Tools/Commander Status HUD.html",
    "Setup Configurator.html",
    "Startup Command Board.html",
]


def depth_prefix(rel: str) -> str:
    d = len(Path(rel).parts) - 1
    return "../" * d if d else ""


def audit_file(p: Path) -> dict:
    rel = str(p.relative_to(ROOT)).replace("\\", "/")
    t = p.read_text(encoding="utf-8", errors="replace")
    depth = len(Path(rel).parts) - 1
    expect = depth_prefix(rel) + "Toolbox Launcher.html"

    has_launcher_href = bool(re.search(r"Toolbox\s*Launcher\.html", t, re.I))
    # Wrong depth e.g. root tool linking ../ or nested with no ../
    wrong_depth = []
    for m in re.finditer(r'href=["\']([^"\']*Toolbox\s*Launcher\.html)["\']', t, re.I):
        href = m.group(1).replace("\\", "/")
        # ignore absolute / protocol
        if href.startswith(("http:", "https:", "file:", "/")):
            continue
        # normalize
        if href != expect and not href.endswith(expect):
            # allow ./Toolbox or Toolbox at root
            if depth == 0 and href in ("Toolbox Launcher.html", "./Toolbox Launcher.html"):
                continue
            if depth > 0 and href == expect:
                continue
            # compute ups
            ups = href.count("../")
            if ups != depth and "Toolbox Launcher" in href:
                wrong_depth.append(href)

    has_nav = bool(re.search(r"<nav\b|class=[\"'][^\"']*\bnav\b", t, re.I))
    has_server_pill = bool(re.search(r"serverPill|server-pill|status-pill", t, re.I))
    has_start_server = bool(re.search(r"Start\s*Server|startServer|/api/server/start", t, re.I))
    uses_api = bool(re.search(r"/api/|aitoolbox-api|AIToolbox\.|fetch\(", t, re.I))
    has_offline_hint = bool(re.search(r"offline|server\s+offline|Start Server|S1", t, re.I))
    history_only = "history.back" in t and not has_launcher_href
    # tab panels with no back within multi-step
    has_tabs = bool(re.search(r"data-tab=|class=[\"'][^\"']*tab", t, re.I))
    # modal without close
    open_modals = len(re.findall(r"class=[\"'][^\"']*modal", t, re.I))
    # hub links among media tools
    cross_links = len(re.findall(r'href=["\'][^"\']+\.html["\']', t))

    issues = []
    if rel != "Toolbox Launcher.html" and not has_launcher_href:
        issues.append("NO_TOOLBOX_LINK")
    if wrong_depth:
        issues.append(f"WRONG_LAUNCHER_DEPTH:{','.join(wrong_depth[:3])}")
    if history_only:
        issues.append("HISTORY_BACK_ONLY")
    if uses_api and not has_offline_hint and not has_start_server:
        # many pure client tools use fetch lightly — only flag if heavy api
        api_hits = len(re.findall(r"/api/", t))
        if api_hits >= 3:
            issues.append("API_NO_OFFLINE_HINT")
    if uses_api and has_server_pill is False and rel.startswith(("Movie File Manager", "System Tools", "File Tools", "Developer Tools", "Verifone Tools")):
        api_hits = len(re.findall(r"/api/", t))
        if api_hits >= 5 and not has_start_server:
            issues.append("NO_SERVER_STATUS")

    return {
        "rel": rel,
        "depth": depth,
        "has_launcher": has_launcher_href,
        "has_nav": has_nav,
        "uses_api": uses_api,
        "issues": issues,
        "cross_links": cross_links,
        "has_tabs": has_tabs,
    }


def main() -> None:
    rows = []
    for p in sorted(ROOT.rglob("*.html")):
        if any(x in p.parts for x in SKIP):
            continue
        if p.name.endswith(".bak-before-sync"):
            continue
        rows.append(audit_file(p))

    no_link = [r for r in rows if "NO_TOOLBOX_LINK" in r["issues"]]
    other = [r for r in rows if r["issues"] and "NO_TOOLBOX_LINK" not in r["issues"]]
    print("=== NO TOOLBOX LINK ===", len(no_link))
    for r in no_link:
        print(f"  {r['rel']}")
    print("\n=== OTHER ISSUES ===", len(other))
    for r in other:
        print(f"  {r['rel']}: {', '.join(r['issues'])}")

    print("\n=== PRIORITY PASS ===")
    by_rel = {r["rel"]: r for r in rows}
    for rel in PRIORITY:
        r = by_rel.get(rel)
        if not r:
            print(f"  MISSING FILE {rel}")
            continue
        flag = "OK" if not r["issues"] else "FIX"
        print(f"  {flag} {rel}  issues={r['issues'] or '-'}  launcher={r['has_launcher']} nav={r['has_nav']}")

    out = ROOT / "Scripts" / "_nav_ux_audit.txt"
    lines = []
    for r in rows:
        lines.append(f"{';'.join(r['issues']) or 'OK'}\t{r['rel']}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
