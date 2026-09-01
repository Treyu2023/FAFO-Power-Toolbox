#!/usr/bin/env python3
"""Stamp ?v=<VERSION> onto shared JS/CSS tags in every toolbox HTML file.

Run after bumping /VERSION (or this script can be called by a release helper).
Idempotent: existing ?v= values are replaced with the current VERSION.

  python Scripts/stamp_shared_cachebust.py
  python Scripts/stamp_shared_cachebust.py --check   # exit 1 if HTML is stale
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "snapshots",
    "mcps",
    "Reports",
    "Logs",
    "Backups",
    "__pycache__",
}

ASSET_RE = re.compile(
    r'(?P<pre>(?:src|href)=["\'])'
    r'(?P<path>[^"\']*?shared/[^"\'?\\]+?\.(?:js|css))'
    r'(?:\?[^"\']*)?'
    r'(?P<post>["\'])',
    re.I,
)


def read_version() -> str:
    raw = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not raw or any(c in raw for c in " \t\n\r\"'<>"):
        raise SystemExit(f"Bad VERSION file: {raw!r}")
    return raw


def busted(html: str, version: str) -> str:
    repl = rf"\g<pre>\g<path>?v={version}\g<post>"
    return ASSET_RE.sub(repl, html)


def iter_html() -> list[Path]:
    out: list[Path] = []
    for path in ROOT.rglob("*.html"):
        rel_parts = set(path.relative_to(ROOT).parts)
        if rel_parts & SKIP_DIRS:
            continue
        out.append(path)
    return sorted(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="Do not write; fail if stamps are missing")
    args = ap.parse_args()
    version = read_version()
    changed = 0
    checked = 0
    for path in iter_html():
        text = path.read_text(encoding="utf-8")
        if "shared/" not in text:
            continue
        checked += 1
        new = busted(text, version)
        if new == text:
            continue
        changed += 1
        rel = path.relative_to(ROOT).as_posix()
        if args.check:
            print("STALE", rel)
        else:
            path.write_text(new, encoding="utf-8", newline="\n")
            print("stamped", rel)
    print(f"{'would update' if args.check else 'updated'} {changed}/{checked} html files → v={version}")
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    sys.exit(main())
