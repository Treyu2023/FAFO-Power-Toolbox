# -*- coding: utf-8 -*-
"""Stamp modular layout root + assets onto every remaining production tool HTML."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SKIP_PARTS = {
    "mcps",
    "node_modules",
    "__pycache__",
    ".venv",
    "Reports",
    "device-local",
    "site-packages",
    "win32com",
    "win32comext",
    "isapi",
    "setuptools",
}

# Tools that already have full layout — leave alone
# We still ensure assets exist.

# Human-readable app ids
APP_ID_OVERRIDES = {
    "Toolbox Launcher.html": "toolbox-launcher",
    "Bloodmoon Survivor.html": "bloodmoon-survivor",
    "Empire Seed.html": "empire-seed",
    "Solar System Debris Tracker.html": "solar-system-debris-tracker",
    "Typing Assistant Trainer.html": "typing-assistant-trainer",
    "Investor Portal.html": "investor-portal",
}


def app_id_for(rel: str) -> str:
    name = Path(rel).name
    if name in APP_ID_OVERRIDES:
        return APP_ID_OVERRIDES[name]
    stem = Path(name).stem
    # path-based
    parts = Path(rel).parts
    base = re.sub(r"[^\w]+", "-", stem).strip("-").lower()
    if len(parts) > 1:
        folder = re.sub(r"[^\w]+", "-", parts[0]).strip("-").lower()
        return f"{folder}-{base}"[:80]
    return base[:80]


def depth_for(rel: str) -> int:
    return len(Path(rel).parts) - 1


def inject_assets(html: str, depth: int) -> str:
    prefix = "../" * depth if depth > 0 else ""
    # root-level tools use shared/ without ../
    if depth == 0:
        prefix = ""
    css_href = f"{prefix}shared/aitoolbox-layout.css"
    js_src = f"{prefix}shared/aitoolbox-layout.js"
    css_tag = f'<link rel="stylesheet" href="{css_href}">'
    js_tag = f'<script src="{js_src}"></script>'

    if "aitoolbox-layout.css" not in html:
        m = re.search(r'<link[^>]+aitoolbox-ui\.css"[^>]*>', html, re.I)
        if m:
            html = html[: m.end()] + "\n" + css_tag + html[m.end() :]
        else:
            html = html.replace("</head>", css_tag + "\n</head>", 1)

    if "aitoolbox-layout.js" not in html:
        m = re.search(r'<script[^>]+aitoolbox-ui\.js"[^>]*></script>', html, re.I)
        if m:
            html = html[: m.end()] + "\n" + js_tag + html[m.end() :]
        else:
            m = re.search(r'<script[^>]+aitoolbox-pro\.js"[^>]*></script>', html, re.I)
            if m:
                html = html[: m.start()] + js_tag + "\n" + html[m.start() :]
            else:
                # before first app script or end body
                html = html.replace("</body>", js_tag + "\n</body>", 1)
    return html


def pick_root_open_tag(html: str) -> re.Match | None:
    """Find best outer shell open tag to stamp layout attributes onto."""
    patterns = [
        r'<div class="main"[^>]*>',
        r'<div class="app"[^>]*>',
        r'<div class="shell"[^>]*>',
        r'<div class="layout"[^>]*>',
        r'<div class="wrap"[^>]*>',
        r'<div class="hub-grid"[^>]*>',
        r'<div class="content"[^>]*>',
        r'<div class="container"[^>]*>',
        r'<main class="main"[^>]*>',
        r'<main[^>]*>',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.I)
        if m and "data-fafo-layout-root" not in m.group(0):
            return m
    return None


def stamp_root(html: str, app_id: str) -> tuple[str, str]:
    if "data-fafo-layout-root" in html:
        return html, "already"
    m = pick_root_open_tag(html)
    if not m:
        # wrap body content
        bm = re.search(r"<body([^>]*)>", html, re.I)
        if not bm:
            return html, "no-body"
        insert = (
            f'<div data-fafo-layout-root data-fafo-layout-app="{app_id}" '
            f'data-fafo-layout-type="rows" class="fafo-auto-shell" style="min-height:100vh;display:flex;flex-direction:column">'
        )
        html = html[: bm.end()] + "\n" + insert + html[bm.end() :]
        html = html.replace("</body>", "</div>\n</body>", 1)
        return html, "wrapped-body"

    tag = m.group(0)
    # inject attributes before closing >
    if tag.endswith("/>"):
        return html, "void"
    attrs = f' data-fafo-layout-root data-fafo-layout-app="{app_id}"'
    if "data-fafo-layout-type" not in tag:
        # columns if looks multi-col, else rows
        attrs += ' data-fafo-layout-type="columns"'
    new_tag = tag[:-1] + attrs + ">"
    html = html[: m.start()] + new_tag + html[m.end() :]
    return html, "stamped"


def add_toolbar(html: str) -> str:
    if "data-fafo-layout-toolbar" in html:
        return html
    if re.search(r"</nav>", html, re.I):
        return re.sub(r"</nav>", '  <span data-fafo-layout-toolbar></span>\n</nav>', html, count=1, flags=re.I)
    if re.search(r"</header>", html, re.I):
        return re.sub(
            r"</header>",
            '  <span data-fafo-layout-toolbar></span>\n</header>',
            html,
            count=1,
            flags=re.I,
        )
    # inject a small bar after body open
    return re.sub(
        r"<body([^>]*)>",
        r'<body\1>\n<div style="padding:6px 10px;display:flex;justify-content:flex-end"><span data-fafo-layout-toolbar></span></div>',
        html,
        count=1,
        flags=re.I,
    )


def should_process(path: Path) -> bool:
    if any(part in SKIP_PARTS for part in path.parts):
        return False
    if path.suffix.lower() != ".html":
        return False
    # skip generated reports under PC reports
    if "hud_report" in path.name or "system-status-" in path.name:
        return False
    if path.name.endswith("-auto.html"):
        return False
    return True


def main() -> None:
    stamped = 0
    skipped = 0
    for p in sorted(ROOT.rglob("*.html")):
        if not should_process(p):
            continue
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        text = p.read_text(encoding="utf-8", errors="ignore")
        # skip empty stubs
        if len(text) < 200:
            skipped += 1
            continue
        # Launcher has its own chrome — assets only (no layout root)
        if rel.replace("\\", "/").endswith("Toolbox Launcher.html"):
            depth = depth_for(rel)
            new = inject_assets(text, depth)
            if new != text:
                p.write_text(new, encoding="utf-8")
                print("launcher-assets", rel)
            else:
                skipped += 1
            continue
        depth = depth_for(rel)
        app_id = app_id_for(rel)
        new = inject_assets(text, depth)
        new, how = stamp_root(new, app_id)
        if how == "already":
            # still ensure assets
            if new != text:
                p.write_text(new, encoding="utf-8")
                print("assets-only", rel)
            else:
                skipped += 1
            continue
        if how in ("no-body", "void"):
            print("skip", how, rel)
            skipped += 1
            continue
        new = add_toolbar(new)
        if new != text:
            p.write_text(new, encoding="utf-8")
            print(how, app_id, rel)
            stamped += 1
        else:
            skipped += 1

    # recount
    marked = 0
    for p in ROOT.rglob("*.html"):
        if not should_process(p):
            continue
        if "data-fafo-layout-root" in p.read_text(encoding="utf-8", errors="ignore"):
            marked += 1
    print("---")
    print("stamped this run", stamped)
    print("total marked tools", marked)


if __name__ == "__main__":
    main()
