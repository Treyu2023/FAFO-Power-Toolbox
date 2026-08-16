# -*- coding: utf-8 -*-
"""Thorough UX hang-up audit for all production HTML tools."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {".venv", "mcps", "node_modules", "Reports", "device-local", "site-packages", "Scripts"}


def depth(rel: str) -> int:
    return len(Path(rel).parts) - 1


def expect_launcher(rel: str) -> str:
    d = depth(rel)
    return ("../" * d) + "Toolbox Launcher.html" if d else "Toolbox Launcher.html"


def main() -> None:
    rows = []
    for p in sorted(ROOT.rglob("*.html")):
        if any(x in p.parts for x in SKIP):
            continue
        if ".bak" in p.name:
            continue
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        t = p.read_text(encoding="utf-8", errors="replace")
        issues = []
        notes = []

        is_launcher = rel == "Toolbox Launcher.html"
        has_tb = bool(re.search(r"Toolbox\s*Launcher\.html", t, re.I))
        if not is_launcher and not has_tb:
            issues.append("NO_TOOLBOX")

        # wrong relative depth for launcher links
        exp = expect_launcher(rel)
        for m in re.finditer(r'''(?:href|onclick)=["']([^"']*Toolbox\s*Launcher\.html[^"']*)["']''', t, re.I):
            href = m.group(1).split("?")[0].replace("\\", "/")
            if href.startswith(("http", "file:", "/toolbox", "javascript")):
                continue
            ups = href.count("../")
            if ups != depth(rel) and "Toolbox" in href:
                issues.append(f"BAD_DEPTH:{href}")

        has_ui = "aitoolbox-ui.js" in t
        has_api = "aitoolbox-api.js" in t or re.search(r"/api/", t)
        has_pro = "aitoolbox-pro.js" in t
        api_hits = len(re.findall(r"/api/", t))
        has_start = bool(re.search(r"Start\s*Server|startServer|btnStartServer", t, re.I))
        has_esc_off = 'data-tb-esc="off"' in t or "data-tb-esc='off'" in t
        # polish Esc→launcher capture that fights games
        steal_esc = bool(
            re.search(
                r"key\s*!==\s*['\"]Escape['\"][\s\S]{0,200}location\.href\s*=\s*launcherHref",
                t,
            )
            or re.search(
                r"if\s*\(\s*e\.key\s*!==\s*['\"]Escape['\"][\s\S]{0,120}location\.href",
                t,
            )
        )
        if steal_esc and not has_esc_off:
            # many tools intentionally Esc→launcher; flag games/overlays specially
            if re.search(r"canvas|game|playing|paused|requestAnimationFrame", t, re.I):
                if "pause" in t.lower() or "overlay" in t.lower():
                    issues.append("ESC_MAY_STEAL_GAME")

        if api_hits >= 4 and not has_start and not is_launcher:
            if not re.search(r"demo|localStorage only|no server", t, re.I):
                issues.append("API_NO_START_SERVER")

        if has_pro and not has_ui and not is_launcher:
            issues.append("PRO_WITHOUT_UI")

        # empty dead-ends: empty class without button/link nearby
        empties = len(re.findall(r'class=["\'][^"\']*empty', t, re.I))
        empty_cta = len(re.findall(r"empty-cta|btnEmpty|data-cmd-empty|emptyBoot", t, re.I))
        if empties >= 2 and empty_cta == 0 and api_hits >= 2:
            notes.append(f"empty_blocks={empties}_no_cta")

        # history.back only
        if "history.back" in t and not has_tb:
            issues.append("HISTORY_BACK_ONLY")

        # missing body escape for known games
        if any(x in rel for x in ("Bloodmoon", "Empire Seed", "Tech Quest", "Solar System", "Typing Assistant")):
            if not has_esc_off and steal_esc:
                issues.append("INTERACTIVE_ESC_HIJACK")

        rows.append(
            {
                "rel": rel,
                "issues": issues,
                "notes": notes,
                "has_tb": has_tb,
                "has_ui": has_ui,
                "api_hits": api_hits,
                "has_start": has_start,
            }
        )

    problem = [r for r in rows if r["issues"] or r["notes"]]
    print(f"scanned={len(rows)} problem={len(problem)}")
    print("\n=== ISSUES ===")
    for r in problem:
        if not r["issues"]:
            continue
        print(f"  {r['rel']}")
        for i in r["issues"]:
            print(f"    - {i}")
    print("\n=== NOTES (soft) ===")
    for r in problem:
        if not r["notes"]:
            continue
        print(f"  {r['rel']}: {', '.join(r['notes'])}")

    out = ROOT / "Scripts" / "_ux_thorough_report.txt"
    lines = []
    for r in rows:
        flag = ",".join(r["issues"] + r["notes"]) or "OK"
        lines.append(f"{flag}\t{r['rel']}\ttb={r['has_tb']}\tui={r['has_ui']}\tapi={r['api_hits']}\tstart={r['has_start']}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
