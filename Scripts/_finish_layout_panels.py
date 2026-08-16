# -*- coding: utf-8 -*-
"""
Finish modular layout: stamp explicit data-fafo-panel markers on every
layout-root that still relies only on runtime scaffold.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {".venv", "mcps", "node_modules", "Reports", "device-local", "site-packages"}

# Match opening tags with class containing token
CLASS_TAG = re.compile(
    r"<(?P<tag>div|aside|section|main|nav|header|article)\b(?P<pre>[^>]*?)\bclass=(?P<q>['\"])(?P<cls>[^'\"]*)(?P=q)(?P<post>[^>]*)>",
    re.I,
)


def class_has(cls: str, *tokens: str) -> bool:
    parts = set(re.split(r"\s+", cls.strip()))
    return any(t in parts for t in tokens)


def add_attr(open_tag: str, name: str, value: str) -> str:
    if re.search(rf"\b{re.escape(name)}=", open_tag):
        return open_tag
    if open_tag.endswith("/>"):
        return open_tag[:-2] + f' {name}="{value}" />'
    return open_tag[:-1] + f' {name}="{value}">'


def strip_scripts_styles(html: str) -> str:
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    html = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.I)
    html = re.sub(r"<style[\s\S]*?</style>", "", html, flags=re.I)
    return html


def find_root_span(html: str) -> tuple[int, int, str] | None:
    m = re.search(r"<([a-zA-Z0-9]+)([^>]*data-fafo-layout-root[^>]*)>", html)
    if not m:
        return None
    tag = m.group(1).lower()
    start = m.start()
    # find matching close of this element (depth count)
    i = m.end()
    depth = 1
    pat = re.compile(rf"</?{tag}\b[^>]*>", re.I)
    for mm in pat.finditer(html, i):
        tok = mm.group(0)
        if tok.startswith("</"):
            depth -= 1
            if depth == 0:
                return start, mm.end(), tag
        elif tok.endswith("/>"):
            continue
        else:
            depth += 1
    return start, len(html), tag


def stamp_panels_in_root(html: str) -> tuple[str, int]:
    """Add data-fafo-panel to direct structural children of layout root if missing."""
    span = find_root_span(html)
    if not span:
        return html, 0
    start, end, root_tag = span
    open_end = html.find(">", start) + 1
    root_open = html[start:open_end]
    inner = html[open_end : end - (len(root_tag) + 3)]  # rough; better use depth close

    # re-parse root more carefully
    m = re.search(r"<([a-zA-Z0-9]+)([^>]*data-fafo-layout-root[^>]*)>", html)
    assert m
    tag = m.group(1)
    open_end = m.end()
    # find close index
    depth = 1
    close_start = None
    for mm in re.finditer(rf"</?{tag}\b[^>]*>", html[open_end:], re.I):
        tok = mm.group(0)
        abs_i = open_end + mm.start()
        if tok.startswith("</"):
            depth -= 1
            if depth == 0:
                close_start = abs_i
                break
        elif not tok.endswith("/>"):
            depth += 1
    if close_start is None:
        return html, 0

    inner = html[open_end:close_start]
    if "data-fafo-panel=" in inner:
        # already has some panels — still fill gaps on unstamped major children
        pass

    # Walk top-level elements in inner (string-based, imperfect but ok for our HTML)
    # Find direct child open tags by tracking depth from 0 within inner
    children: list[tuple[int, int, str]] = []  # start, end_of_open, full_open
    depth = 0
    for mm in re.finditer(r"</?[a-zA-Z][^>]*>", inner):
        tok = mm.group(0)
        if tok.startswith("</"):
            depth = max(0, depth - 1)
            continue
        is_void = bool(re.match(r"<(br|hr|img|input|meta|link|source|area|col|embed|param|track|wbr)\b", tok, re.I))
        self_close = tok.endswith("/>") or is_void
        if depth == 0 and not self_close:
            children.append((mm.start(), mm.end(), tok))
        if not self_close:
            depth += 1

    if not children:
        return html, 0

    # classify
    typed: list[tuple[int, int, str, str, dict]] = []  # start, end, open, id, attrs
    used_ids: set[str] = set()

    def uniq(base: str) -> str:
        i = 0
        cand = base
        while cand in used_ids:
            i += 1
            cand = f"{base}-{i}"
        used_ids.add(cand)
        return cand

    for start_i, end_i, open_tag in children:
        if "data-fafo-panel=" in open_tag:
            # already stamped
            m = re.search(r'data-fafo-panel="([^"]+)"', open_tag)
            if m:
                used_ids.add(m.group(1))
            continue
        # skip pure toolbar hosts / scripts (shouldn't appear)
        if "data-fafo-layout-toolbar" in open_tag:
            continue
        if re.search(r"\bclass=(['\"])[^'\"]*\b(toast|modal|loading|overlay)\b", open_tag, re.I):
            continue

        cls_m = re.search(r"\bclass=(['\"])([^'\"]*)\1", open_tag)
        cls = cls_m.group(2) if cls_m else ""
        tag_m = re.match(r"<([a-zA-Z0-9]+)", open_tag)
        tag = (tag_m.group(1) if tag_m else "div").lower()
        title = None
        pid = None
        extra: dict[str, str] = {}

        if class_has(cls, "sidebar") or tag == "aside" and "sidebar" in cls:
            pid, title = uniq("sidebar"), "Sidebar"
            extra = {"data-fafo-panel-min": "160", "data-fafo-panel-default": "240"}
        elif class_has(cls, "detail", "detail-panel", "tags-panel") or "detail" in cls:
            pid, title = uniq("detail"), "Detail"
            extra = {"data-fafo-panel-min": "220", "data-fafo-panel-default": "320"}
        elif class_has(cls, "main", "center", "content", "workspace") or tag == "main":
            pid, title = uniq("main"), "Main"
            extra = {"data-fafo-flex": "1"}
        elif class_has(cls, "nav") and tag in ("div", "nav"):
            # sticky nav inside root — treat as compact panel
            pid, title = uniq("nav"), "Nav"
            extra = {"data-fafo-panel-min": "40", "data-fafo-panel-default": "56"}
        elif class_has(cls, "panel", "card", "ui-card", "side-card", "block", "section", "hero", "toolbar", "vitals", "stats"):
            # section-like top level cards
            # extract title later from following h2 - use class
            pid = uniq("block")
            title = "Block"
            extra = {"data-fafo-panel-min": "60", "data-fafo-panel-default": "140"}
        elif tag in ("section", "aside", "header", "article"):
            pid = uniq(tag)
            title = tag.title()
            extra = {"data-fafo-panel-min": "60", "data-fafo-panel-default": "120"}
        else:
            # only stamp substantial divs (has nested content markers)
            continue

        typed.append((start_i, end_i, open_tag, pid, {"title": title, **extra}))

    if not typed:
        # fallback: wrap all children in one main panel by stamping first large div
        for start_i, end_i, open_tag in children:
            if "data-fafo-panel=" in open_tag:
                continue
            if re.match(r"<div\b", open_tag, re.I):
                typed.append(
                    (
                        start_i,
                        end_i,
                        open_tag,
                        uniq("main"),
                        {"title": "Main", "data-fafo-flex": "1", "data-fafo-panel-min": "120"},
                    )
                )
                break

    if not typed:
        return html, 0

    # If we only got card-like blocks, ensure rows type and last flex
    only_blocks = all(x[3].startswith("block") or x[3] in ("nav",) for x in typed)
    multi_col = any(x[3].startswith("sidebar") or x[3].startswith("main") or x[3].startswith("detail") for x in typed)

    new_inner = inner
    # apply from end so offsets stable
    stamped = 0
    for start_i, end_i, open_tag, pid, meta in sorted(typed, key=lambda x: -x[0]):
        title = meta.pop("title", pid)
        new_open = open_tag
        new_open = add_attr(new_open, "data-fafo-panel", pid)
        new_open = add_attr(new_open, "data-fafo-panel-title", title)
        for k, v in meta.items():
            new_open = add_attr(new_open, k, v)
        new_inner = new_inner[:start_i] + new_open + new_inner[end_i:]
        stamped += 1

    # last block flex if rows of cards
    if only_blocks and stamped >= 2:
        # set last block as flex - find last data-fafo-panel="block
        def last_block_flex(s: str) -> str:
            matches = list(re.finditer(r'data-fafo-panel="block(?:-\d+)?"', s))
            if not matches:
                return s
            m = matches[-1]
            # insert flex after this attribute if missing nearby
            window = s[m.start() : m.start() + 200]
            if "data-fafo-flex=" in window:
                return s
            return s[: m.end()] + ' data-fafo-flex="1"' + s[m.end() :]

        new_inner = last_block_flex(new_inner)

    # fix layout type on root open
    new_root_open = root_open if "root_open" in dir() else html[m.start() : open_end]
    new_root_open = html[m.start() : open_end]
    if multi_col:
        if 'data-fafo-layout-type="rows"' in new_root_open:
            new_root_open = new_root_open.replace(
                'data-fafo-layout-type="rows"', 'data-fafo-layout-type="columns"'
            )
        elif "data-fafo-layout-type=" not in new_root_open:
            new_root_open = add_attr(new_root_open, "data-fafo-layout-type", "columns")
    else:
        if 'data-fafo-layout-type="columns"' in new_root_open and only_blocks:
            new_root_open = new_root_open.replace(
                'data-fafo-layout-type="columns"', 'data-fafo-layout-type="rows"'
            )
        elif "data-fafo-layout-type=" not in new_root_open:
            new_root_open = add_attr(new_root_open, "data-fafo-layout-type", "rows")

    out = html[: m.start()] + new_root_open + new_inner + html[close_start:]
    return out, stamped


def stamp_sections_in_panels(html: str) -> tuple[str, int]:
    """Inside each panel, mark .card/.panel/.sidebar-section as sections if none."""
    count = 0

    # find panels
    for pm in list(re.finditer(r"<([a-zA-Z0-9]+)([^>]*data-fafo-panel=\"([^\"]+)\"[^>]*)>", html)):
        tag = pm.group(1)
        panel_id = pm.group(3)
        open_end = pm.end()
        # find close
        depth = 1
        close_start = None
        for mm in re.finditer(rf"</?{tag}\b[^>]*>", html[open_end:], re.I):
            tok = mm.group(0)
            abs_i = open_end + mm.start()
            if tok.startswith("</"):
                depth -= 1
                if depth == 0:
                    close_start = abs_i
                    break
            elif not tok.endswith("/>"):
                depth += 1
        if close_start is None:
            continue
        inner = html[open_end:close_start]
        if "data-fafo-section=" in inner:
            continue
        # top-level section-like children
        depth = 0
        children = []
        for mm in re.finditer(r"</?[a-zA-Z][^>]*>", inner):
            tok = mm.group(0)
            if tok.startswith("</"):
                depth = max(0, depth - 1)
                continue
            void = bool(re.match(r"<(br|hr|img|input|meta|link|source)\b", tok, re.I))
            self_close = tok.endswith("/>") or void
            if depth == 0 and not self_close:
                children.append((mm.start(), mm.end(), tok))
            if not self_close:
                depth += 1
        section_kids = []
        for s, e, open_tag in children:
            if "data-fafo-section=" in open_tag:
                continue
            cls_m = re.search(r"\bclass=(['\"])([^'\"]*)\1", open_tag)
            cls = cls_m.group(2) if cls_m else ""
            if class_has(
                cls,
                "panel",
                "card",
                "ui-card",
                "side-card",
                "sidebar-section",
                "section",
                "block",
            ) or re.search(r"\bsection\b", cls):
                section_kids.append((s, e, open_tag))
        if len(section_kids) < 2:
            continue
        # stamp from end
        new_inner = inner
        for i, (s, e, open_tag) in enumerate(sorted(section_kids, key=lambda x: -x[0])):
            idx = len(section_kids) - 1 - i
            # title guess
            title = f"Section {idx + 1}"
            # look ahead in original inner for h2/h3 text nearby
            snippet = inner[e : e + 200]
            hm = re.search(r"<h[1-3][^>]*>(.*?)</h[1-3]>", snippet, re.I | re.S)
            if hm:
                title = re.sub(r"<[^>]+>", "", hm.group(1)).strip()[:40] or title
            new_open = add_attr(open_tag, "data-fafo-section", f"{panel_id}-sec-{idx}")
            new_open = add_attr(new_open, "data-fafo-section-title", title)
            new_inner = new_inner[:s] + new_open + new_inner[e:]
            count += 1
        html = html[:open_end] + new_inner + html[close_start:]
    return html, count


def ensure_toolbar(html: str) -> str:
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
    return re.sub(
        r"(data-fafo-layout-root[^>]*>)",
        r'\1\n  <div style="display:flex;justify-content:flex-end;gap:8px;padding:4px 0">'
        r'<span data-fafo-layout-toolbar></span></div>',
        html,
        count=1,
    )


def ensure_assets(html: str, rel: str) -> str:
    depth = len(Path(rel).parts) - 1
    prefix = "../" * depth if depth else ""
    css = f'<link rel="stylesheet" href="{prefix}shared/aitoolbox-layout.css">'
    js = f'<script src="{prefix}shared/aitoolbox-layout.js"></script>'
    if "aitoolbox-layout.css" not in html:
        if "aitoolbox-ui.css" in html:
            html = re.sub(
                r'(<link[^>]+aitoolbox-ui\.css"[^>]*>)',
                r"\1\n" + css,
                html,
                count=1,
                flags=re.I,
            )
        else:
            html = html.replace("</head>", css + "\n</head>", 1)
    if "aitoolbox-layout.js" not in html:
        if re.search(r"aitoolbox-ui\.js", html):
            html = re.sub(
                r'(<script[^>]+aitoolbox-ui\.js"[^>]*></script>)',
                r"\1\n" + js,
                html,
                count=1,
                flags=re.I,
            )
        elif re.search(r"aitoolbox-pro\.js", html):
            html = re.sub(
                r'(<script[^>]+aitoolbox-pro\.js"[^>]*></script>)',
                js + "\n" + r"\1",
                html,
                count=1,
                flags=re.I,
            )
        else:
            html = html.replace("</body>", js + "\n</body>", 1)
    return html


def main() -> None:
    total_panels = 0
    total_sections = 0
    files = 0
    for p in sorted(ROOT.rglob("*.html")):
        if any(x in p.parts for x in SKIP):
            continue
        if p.suffix != ".html":
            continue
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        if rel.endswith("Toolbox Launcher.html"):
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        if "data-fafo-layout-root" not in t:
            continue
        orig = t
        t = ensure_assets(t, rel)
        t = ensure_toolbar(t)
        t, n_panels = stamp_panels_in_root(t)
        t, n_secs = stamp_sections_in_panels(t)
        if t != orig:
            p.write_text(t, encoding="utf-8")
            files += 1
            total_panels += n_panels
            total_sections += n_secs
            print(f"OK +{n_panels}p +{n_secs}s  {rel}")
        else:
            print(f"-- {rel}")

    # Special fixes (always re-assert known good labels)
    # Task Manager Pro: class is .side not .sidebar
    p = ROOT / "System Tools/FAFO Task Manager Pro.html"
    if p.is_file():
        t = p.read_text(encoding="utf-8")
        t2 = re.sub(
            r'<aside class="side"(?![^>]*data-fafo-panel=)',
            '<aside class="side" data-fafo-panel="sidebar" data-fafo-panel-title="Nav" '
            'data-fafo-panel-min="160" data-fafo-panel-default="220"',
            t,
            count=1,
        )
        # upgrade generic aside labels
        t2 = t2.replace(
            'data-fafo-panel="aside" data-fafo-panel-title="Aside"',
            'data-fafo-panel="sidebar" data-fafo-panel-title="Nav"',
        )
        t2 = re.sub(
            r'(data-fafo-panel="sidebar"[^>]*?)data-fafo-panel-min="60"',
            r'\1data-fafo-panel-min="160"',
            t2,
            count=1,
        )
        t2 = re.sub(
            r'(data-fafo-panel="sidebar"[^>]*?)data-fafo-panel-default="120"',
            r'\1data-fafo-panel-default="220"',
            t2,
            count=1,
        )
        if t2 != t:
            p.write_text(t2, encoding="utf-8")
            print("fixed Task Manager Pro sidebar")

    # VSR: all tab panels with real ids/titles (overwrite generic block stamps)
    p = ROOT / "Movie File Manager/VSR Pipeline Manager.html"
    if p.is_file():
        t = p.read_text(encoding="utf-8")
        mapping = {
            "panel-rename": ("rename", "② Match & Rename"),
            "panel-teach": ("teach", "③ Teach Matcher"),
            "panel-dupes": ("dupes", "④ Duplicates"),
            "panel-tags": ("tags", "⑤ Tag Rules"),
        }
        for html_id, (name, title) in mapping.items():
            t = re.sub(
                rf'(<div class="panel" id="{html_id}")([^>]*)>',
                lambda m, n=name, ti=title: (
                    f'{m.group(1)} data-fafo-panel="{n}" data-fafo-panel-title="{ti}" '
                    f'data-fafo-flex="1">'
                    if "data-fafo-panel=" not in m.group(2)
                    else re.sub(
                        r'data-fafo-panel="[^"]*"',
                        f'data-fafo-panel="{n}"',
                        re.sub(
                            r'data-fafo-panel-title="[^"]*"',
                            f'data-fafo-panel-title="{ti}"',
                            m.group(0),
                            count=1,
                        ),
                        count=1,
                    )
                ),
                t,
                count=1,
            )
        t = re.sub(
            r'(data-fafo-layout-app="vsr-pipeline-manager"[^>]*?)data-fafo-layout-type="columns"',
            r'\1data-fafo-layout-type="rows"',
            t,
            count=1,
        )
        p.write_text(t, encoding="utf-8")
        print("fixed VSR panels")

    print(f"---\nupdated files={files} new_panels={total_panels} new_sections={total_sections}")


if __name__ == "__main__":
    main()
