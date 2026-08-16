# -*- coding: utf-8 -*-
"""Polish generic Block/Aside panel titles using nearby h1/h2 or id attrs."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {".venv", "mcps", "node_modules", "Reports", "device-local", "site-packages"}

# Known app-specific renames: (app id, panel id) -> (new_id, new_title)
# Applied after generic heuristics when still weak.
HAND_FIXES: dict[str, dict[str, tuple[str, str]]] = {}


def title_from_inner(inner: str) -> str | None:
    for pat in (
        r"<h[1-3][^>]*>(.*?)</h[1-3]>",
        r'class=["\']nav-btn[^"\']*["\'][^>]*>(.*?)</',
        r"<strong>(.*?)</strong>",
    ):
        m = re.search(pat, inner, re.I | re.S)
        if m:
            t = re.sub(r"<[^>]+>", "", m.group(1))
            t = re.sub(r"\s+", " ", t).strip()
            t = t.replace("&amp;", "&")[:48]
            if t and t.lower() not in ("block", "aside", "main", "section"):
                return t
    return None


def polish_file(path: Path) -> list[str]:
    t = path.read_text(encoding="utf-8", errors="replace")
    if "data-fafo-layout-root" not in t:
        return []
    orig = t
    notes: list[str] = []

    # Collect replacements (apply from end so offsets stay valid)
    changes: list[tuple[int, int, str, str]] = []  # start, end, new_open, note

    for m in re.finditer(r"<([a-zA-Z0-9]+)([^>]*\bdata-fafo-panel=\"([^\"]+)\"[^>]*)>", t):
        tag, attrs, pid = m.group(1), m.group(2), m.group(3)
        full_open = m.group(0)
        title_m = re.search(r'data-fafo-panel-title="([^"]*)"', attrs)
        title = title_m.group(1) if title_m else ""
        is_generic = (
            pid.startswith("block")
            or title in ("Block", "Aside", "Section")
            or (pid == "aside" and title == "Aside")
        )
        if not is_generic:
            continue

        open_end = m.end()
        depth = 1
        close_start = None
        for mm in re.finditer(rf"</?{tag}\b[^>]*>", t[open_end:], re.I):
            tok = mm.group(0)
            abs_i = open_end + mm.start()
            if tok.startswith("</"):
                depth -= 1
                if depth == 0:
                    close_start = abs_i
                    break
            elif not tok.endswith("/>"):
                depth += 1
        inner = t[open_end:close_start] if close_start else t[open_end : open_end + 400]

        id_m = re.search(r'\bid="([^"]+)"', attrs)
        elem_id = id_m.group(1) if id_m else ""

        new_pid, new_title = pid, title
        if elem_id.startswith("panel-"):
            new_pid = elem_id.replace("panel-", "")
            new_title = title_from_inner(inner) or new_pid.replace("-", " ").title()
        elif pid.startswith("block") or title == "Block":
            guessed = title_from_inner(inner)
            if guessed:
                new_title = guessed
                slug = re.sub(r"[^a-z0-9]+", "-", guessed.lower()).strip("-")[:32] or pid
                if pid.startswith("block"):
                    new_pid = slug
            elif elem_id:
                new_pid, new_title = elem_id, elem_id.replace("-", " ").title()
        elif pid == "aside" or title == "Aside":
            new_pid, new_title = "sidebar", "Nav"

        if new_pid == pid and new_title == title:
            continue

        new_open = full_open
        new_open = re.sub(
            rf'data-fafo-panel="{re.escape(pid)}"',
            f'data-fafo-panel="{new_pid}"',
            new_open,
            count=1,
        )
        if title_m:
            new_open = re.sub(
                rf'data-fafo-panel-title="{re.escape(title)}"',
                f'data-fafo-panel-title="{new_title}"',
                new_open,
                count=1,
            )
        else:
            new_open = new_open[:-1] + f' data-fafo-panel-title="{new_title}">'
        if new_pid == "sidebar" and 'data-fafo-panel-min="60"' in new_open:
            new_open = new_open.replace('data-fafo-panel-min="60"', 'data-fafo-panel-min="160"')
            new_open = new_open.replace(
                'data-fafo-panel-default="120"', 'data-fafo-panel-default="220"'
            )

        changes.append((m.start(), m.end(), new_open, f"{pid}/{title} -> {new_pid}/{new_title}"))

    for start, end, new_open, note in sorted(changes, key=lambda x: -x[0]):
        t = t[:start] + new_open + t[end:]
        notes.append(note)

    if t != orig:
        path.write_text(t, encoding="utf-8")
    return notes


def list_apps_for_docs() -> list[tuple[str, str]]:
    rows = []
    for p in sorted(ROOT.rglob("*.html")):
        if any(x in p.parts for x in SKIP):
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        apps = re.findall(r'data-fafo-layout-app="([^"]+)"', t)
        if not apps:
            continue
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        name = p.stem
        rows.append((name, apps[0], rel))
    return rows


def main() -> None:
    changed = 0
    for p in sorted(ROOT.rglob("*.html")):
        if any(x in p.parts for x in SKIP):
            continue
        notes = polish_file(p)
        if notes:
            changed += 1
            rel = str(p.relative_to(ROOT)).replace("\\", "/")
            print(f"OK {rel}")
            for n in notes:
                print(f"   {n}")
    print(f"---\npolished files={changed}")

    # dump app list for docs
    rows = list_apps_for_docs()
    out = ROOT / "Scripts" / "_layout_app_ids.txt"
    lines = [f"{r[1]}\t{r[0]}\t{r[2]}" for r in rows]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"app ids: {len(rows)} -> {out}")


if __name__ == "__main__":
    main()
