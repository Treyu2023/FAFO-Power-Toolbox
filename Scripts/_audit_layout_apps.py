# -*- coding: utf-8 -*-
"""Audit modular layout adoption across production HTML tools."""
from __future__ import annotations

import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {
    "mcps",
    "node_modules",
    ".venv",
    "Reports",
    "device-local",
    "site-packages",
    "win32com",
    "win32comext",
    "isapi",
    "setuptools",
    "__pycache__",
}


class BalanceParser(HTMLParser):
    VOID = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in self.VOID:
            return
        self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.VOID:
            return
        if not self.stack:
            self.errors.append(f"extra </{tag}>")
            return
        # pop until match (lenient for browser-forgiving HTML)
        if tag in self.stack:
            while self.stack and self.stack[-1] != tag:
                self.errors.append(f"auto-close <{self.stack[-1]}> before </{tag}>")
                self.stack.pop()
            if self.stack and self.stack[-1] == tag:
                self.stack.pop()
        else:
            self.errors.append(f"unmatched </{tag}>")

    def unclosed(self) -> list[str]:
        return list(self.stack)


def should_scan(p: Path) -> bool:
    if p.suffix.lower() != ".html":
        return False
    if any(x in p.parts for x in SKIP):
        return False
    name = p.name.lower()
    if name.startswith("hud_report") or name.startswith("system-status"):
        return False
    if name.endswith("-auto.html"):
        return False
    return True


def depth_of(rel: str) -> int:
    return len(Path(rel).parts) - 1


def expected_prefix(depth: int) -> str:
    return "../" * depth if depth > 0 else ""


def audit_one(p: Path) -> dict:
    rel = str(p.relative_to(ROOT)).replace("\\", "/")
    text = p.read_text(encoding="utf-8", errors="replace")
    issues: list[str] = []
    depth = depth_of(rel)
    prefix = expected_prefix(depth)

    has_root = "data-fafo-layout-root" in text
    has_js = "aitoolbox-layout.js" in text
    has_css = "aitoolbox-layout.css" in text
    has_app = bool(re.search(r'data-fafo-layout-app="([^"]+)"', text))
    app_ids = re.findall(r'data-fafo-layout-app="([^"]+)"', text)
    panels = len(re.findall(r"data-fafo-panel=", text))
    sections = len(re.findall(r"data-fafo-section=", text))
    toolbar = "data-fafo-layout-toolbar" in text

    if has_root and not has_js:
        issues.append("layout-root without aitoolbox-layout.js")
    if has_root and not has_css:
        issues.append("layout-root without aitoolbox-layout.css")
    if has_js and not has_css:
        issues.append("layout.js without layout.css")
    if has_root and not has_app:
        issues.append("layout-root missing data-fafo-layout-app")
    if has_root and app_ids.count(app_ids[0]) != len(app_ids) if app_ids else False:
        issues.append(f"multiple different app ids: {app_ids}")
    if has_root and text.count("data-fafo-layout-root") > 1:
        issues.append(f"multiple layout-roots ({text.count('data-fafo-layout-root')})")

    # path depth check for assets
    if has_js:
        m = re.search(r'src="([^"]*aitoolbox-layout\.js)"', text)
        if m:
            src = m.group(1)
            # for depth d, expect d times ../ unless absolute-ish
            if not src.startswith("http") and not src.startswith("/"):
                ups = src.count("../")
                # special: root tools use shared/ (0 ups)
                if depth == 0 and ups != 0 and not src.startswith("shared/"):
                    issues.append(f"layout.js path odd for root tool: {src}")
                if depth > 0 and ups != depth and "shared/aitoolbox-layout.js" in src:
                    # e.g. depth 2 should be ../../shared/
                    issues.append(f"layout.js depth mismatch (file depth={depth}, ups={ups}): {src}")

    if has_css:
        m = re.search(r'href="([^"]*aitoolbox-layout\.css)"', text)
        if m:
            href = m.group(1)
            if not href.startswith("http") and not href.startswith("/"):
                ups = href.count("../")
                if depth > 0 and ups != depth and "shared/aitoolbox-layout.css" in href:
                    issues.append(f"layout.css depth mismatch (file depth={depth}, ups={ups}): {href}")

    # HTML balance (lenient)
    parser = BalanceParser()
    try:
        # strip scripts/styles for balance check of structure around body
        stripped = re.sub(r"<script[\s\S]*?</script>", "", text, flags=re.I)
        stripped = re.sub(r"<style[\s\S]*?</style>", "", stripped, flags=re.I)
        parser.feed(stripped)
        unclosed = parser.unclosed()
        # only flag if many unclosed structural tags
        bad = [t for t in unclosed if t in {"div", "section", "aside", "main", "nav", "header", "body", "html"}]
        if len(bad) > 3:
            issues.append(f"possibly unclosed structural tags: {Counter(bad).most_common(5)}")
        hard = [e for e in parser.errors if e.startswith("extra ") or e.startswith("unmatched")]
        if len(hard) > 5:
            issues.append(f"many hard HTML end-tag issues ({len(hard)})")
    except Exception as e:
        issues.append(f"html parse error: {e}")

    # broken wrap from body wrap without close
    if "fafo-auto-shell" in text and text.count("fafo-auto-shell") > 0:
        if text.count("fafo-auto-shell") != text.count("</div>") and False:
            pass
        # ensure closing before </body>
        if "fafo-auto-shell" in text and "</body>" in text.lower():
            # crude: open wrap after body should have matching
            pass

    # empty panel attribute
    if re.search(r'data-fafo-panel=""', text):
        issues.append('empty data-fafo-panel=""')
    if re.search(r'data-fafo-layout-app=""', text):
        issues.append('empty data-fafo-layout-app=""')

    # duplicate app ids across files checked later
    return {
        "rel": rel,
        "has_root": has_root,
        "has_js": has_js,
        "has_css": has_css,
        "app_ids": app_ids,
        "panels": panels,
        "sections": sections,
        "toolbar": toolbar,
        "issues": issues,
        "depth": depth,
    }


def main() -> None:
    rows = []
    for p in sorted(ROOT.rglob("*.html")):
        if not should_scan(p):
            continue
        rows.append(audit_one(p))

    with_root = [r for r in rows if r["has_root"]]
    with_js = [r for r in rows if r["has_js"]]
    problem = [r for r in rows if r["issues"]]
    root_no_js = [r for r in with_root if not r["has_js"]]
    root_no_panels = [r for r in with_root if r["panels"] == 0]  # relies on scaffold - OK
    no_toolbar = [r for r in with_root if not r["toolbar"]]

    # duplicate app ids
    id_map: dict[str, list[str]] = {}
    for r in with_root:
        for aid in r["app_ids"]:
            id_map.setdefault(aid, []).append(r["rel"])
    dup_ids = {k: v for k, v in id_map.items() if len(v) > 1}

    print("=== LAYOUT AUDIT ===")
    print(f"HTML tools scanned: {len(rows)}")
    print(f"With layout-root:   {len(with_root)}")
    print(f"With layout.js:     {len(with_js)}")
    print(f"With issues:        {len(problem)}")
    print(f"Root without JS:    {len(root_no_js)}")
    print(f"Root 0 explicit panels (scaffold): {len(root_no_panels)}")
    print(f"Root without toolbar host: {len(no_toolbar)}")
    print(f"Duplicate app ids:  {len(dup_ids)}")

    if root_no_js:
        print("\n-- ROOT WITHOUT JS --")
        for r in root_no_js:
            print(" ", r["rel"])

    if dup_ids:
        print("\n-- DUPLICATE APP IDS --")
        for aid, files in sorted(dup_ids.items()):
            print(f"  {aid}:")
            for f in files:
                print(f"    - {f}")

    if problem:
        print("\n-- ISSUES --")
        for r in problem:
            print(f"  {r['rel']}")
            for i in r["issues"]:
                print(f"    · {i}")

    if no_toolbar:
        print("\n-- NO TOOLBAR (first 25) --")
        for r in no_toolbar[:25]:
            print(" ", r["rel"])
        if len(no_toolbar) > 25:
            print(f"  ... +{len(no_toolbar)-25} more")

    # write machine-readable summary
    out = ROOT / "Scripts" / "_layout_audit_report.txt"
    lines = [
        f"scanned={len(rows)}",
        f"root={len(with_root)}",
        f"js={len(with_js)}",
        f"issues={len(problem)}",
        f"dup_ids={len(dup_ids)}",
    ]
    for r in problem:
        lines.append(f"ISSUE\t{r['rel']}\t{'; '.join(r['issues'])}")
    for aid, files in dup_ids.items():
        lines.append(f"DUPID\t{aid}\t{'; '.join(files)}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
