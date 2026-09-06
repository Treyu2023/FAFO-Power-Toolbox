#!/usr/bin/env python3
"""Stamp live HTML to 3.0.0 and inject runtime/config/version before api.js.

- Replaces ?v=1.16.xx on script/link tags with ?v=3.0.0
- If a file includes aitoolbox-api.js but not aitoolbox-runtime.js, insert
  runtime.js immediately before api.js
- If a file includes aitoolbox-api.js but NOT aitoolbox-config.js, insert
  config.js then version.js then runtime.js before api.js

Skips snapshots/. Does not touch the freeze archive.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = "3.0.0"
SKIP_DIRS = {".git", ".venv", "node_modules", "snapshots", "mcps", "__pycache__"}

V_RE = re.compile(
    r'(?P<pre><(?:script|link)\b[^>]*?\b(?:src|href)=["\'][^"\']*?\?v=)1\.16\.\d+(?P<post>["\'])',
    re.I | re.S,
)
# Broader: any ?v=1.16.xx on src/href attributes
ATTR_V_RE = re.compile(
    r'(?P<pre>\b(?:src|href)=["\'][^"\']*?\?v=)1\.16\.\d+(?P<post>["\'])',
    re.I,
)

API_TAG_RE = re.compile(
    r'(?P<full><script\b(?P<attrs>[^>]*)\bsrc=(?P<q>["\'])(?P<path>[^"\']*?aitoolbox-api\.js)(?P<qs>\?[^"\']*)?(?P=q)(?P<rest>[^>]*)></script>)',
    re.I,
)


def iter_html() -> list[Path]:
    out: list[Path] = []
    for path in ROOT.rglob("*.html"):
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        out.append(path)
    return sorted(out)


def has_script(html: str, name: str) -> bool:
    return re.search(rf'aitoolbox-{re.escape(name)}\.js', html, re.I) is not None


def make_tag(api_path: str, filename: str, quote: str) -> str:
    prefix = api_path.rsplit("aitoolbox-api.js", 1)[0]
    src = f"{prefix}{filename}?v={VERSION}"
    return f"<script src={quote}{src}{quote}></script>"


def inject_before_api(html: str) -> str:
    if not has_script(html, "api"):
        return html
    need_config = not has_script(html, "config")
    need_runtime = not has_script(html, "runtime")
    if not need_config and not need_runtime:
        return html

    inserted_once = False

    def repl(m: re.Match) -> str:
        nonlocal inserted_once
        if inserted_once:
            return m.group("full")
        path = m.group("path")
        q = m.group("q")
        tags: list[str] = []
        if need_config:
            tags.append(make_tag(path, "aitoolbox-config.js", q))
            if not has_script(html, "version"):
                tags.append(make_tag(path, "aitoolbox-version.js", q))
            tags.append(make_tag(path, "aitoolbox-runtime.js", q))
        elif need_runtime:
            tags.append(make_tag(path, "aitoolbox-runtime.js", q))
        inserted_once = True
        return "\n".join(tags) + "\n" + m.group("full")

    return API_TAG_RE.sub(repl, html, count=1)


def process(html: str) -> str:
    html = ATTR_V_RE.sub(rf"\g<pre>{VERSION}\g<post>", html)
    html = inject_before_api(html)
    return html


def main() -> int:
    changed = 0
    for path in iter_html():
        text = path.read_text(encoding="utf-8")
        new = process(text)
        if new == text:
            continue
        path.write_text(new, encoding="utf-8")
        changed += 1
        print("STAMPED", path.relative_to(ROOT).as_posix())
    print(f"updated {changed} html files to {VERSION}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
