# -*- coding: utf-8 -*-
"""Inject aitoolbox-ui.js (and api if needed) before pro/layout for pages missing UI kit."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {".venv", "mcps", "node_modules", "Reports", "device-local", "site-packages"}


def depth_prefix(rel: str) -> str:
    d = len(Path(rel).parts) - 1
    return "../" * d if d else ""


def inject(html: str, rel: str) -> tuple[str, list[str]]:
    notes = []
    if "aitoolbox-ui.js" in html:
        return html, notes
    prefix = depth_prefix(rel)
    ui = f'<script src="{prefix}shared/aitoolbox-ui.js"></script>'
    api = f'<script src="{prefix}shared/aitoolbox-api.js"></script>'

    # Prefer after api
    if "aitoolbox-api.js" in html and "aitoolbox-ui.js" not in html:
        html2, n = re.subn(
            r'(<script[^>]+aitoolbox-api\.js[^>]*>\s*</script>)',
            r"\1\n" + ui,
            html,
            count=1,
            flags=re.I,
        )
        if n:
            notes.append("ui after api")
            return html2, notes

    # Before pro
    if "aitoolbox-pro.js" in html:
        # also inject api if missing
        inject_block = ui
        if "aitoolbox-api.js" not in html:
            inject_block = api + "\n" + ui
            notes.append("api+ui before pro")
        else:
            notes.append("ui before pro")
        html2, n = re.subn(
            r'(<script[^>]+aitoolbox-pro\.js[^>]*>\s*</script>)',
            inject_block + "\n" + r"\1",
            html,
            count=1,
            flags=re.I,
        )
        if n:
            return html2, notes

    # Before layout
    if "aitoolbox-layout.js" in html:
        inject_block = ui
        if "aitoolbox-api.js" not in html:
            inject_block = api + "\n" + ui
        html2, n = re.subn(
            r'(<script[^>]+aitoolbox-layout\.js[^>]*>\s*</script>)',
            inject_block + "\n" + r"\1",
            html,
            count=1,
            flags=re.I,
        )
        if n:
            notes.append("ui before layout")
            return html2, notes

    # Before </body>
    if "</body>" in html.lower():
        inject_block = ui if "aitoolbox-api.js" in html else (api + "\n" + ui)
        html2 = re.sub(r"</body>", inject_block + "\n</body>", html, count=1, flags=re.I)
        notes.append("ui before body end")
        return html2, notes

    return html, notes


def main() -> None:
    n = 0
    for p in sorted(ROOT.rglob("*.html")):
        if any(x in p.parts for x in SKIP):
            continue
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        if rel == "Toolbox Launcher.html":
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        if "aitoolbox-ui.js" in t:
            continue
        # only pages that already use shared kit pieces
        if not any(x in t for x in ("aitoolbox-pro.js", "aitoolbox-layout.js", "aitoolbox-api.js", "aitoolbox-ui.css")):
            continue
        t2, notes = inject(t, rel)
        if t2 != t:
            p.write_text(t2, encoding="utf-8")
            n += 1
            print(f"OK {rel} ({', '.join(notes)})")
    print(f"---\ninjected={n}")


if __name__ == "__main__":
    main()
