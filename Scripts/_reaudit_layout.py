from __future__ import annotations

import re
from pathlib import Path

root = Path(r"C:\_Git\repos\html\HTML Toolbox AI tools\production")
SKIP = {"mcps", "node_modules", ".venv", "Reports", "device-local", "site-packages"}
issues = []
marked = 0
ids: dict[str, list[str]] = {}

for p in sorted(root.rglob("*.html")):
    if any(x in p.parts for x in SKIP):
        continue
    if p.suffix != ".html":
        continue
    t = p.read_text(encoding="utf-8", errors="replace")
    s = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    s = re.sub(r"<style[\s\S]*?</style>", "", s, flags=re.I)
    s = re.sub(r"<script[\s\S]*?</script>", "", s, flags=re.I)
    roots = len(re.findall(r"data-fafo-layout-root", s))
    if not roots:
        continue
    marked += 1
    rel = str(p.relative_to(root)).replace("\\", "/")
    if roots > 1:
        issues.append((rel, f"multi-root {roots}"))
    if "aitoolbox-layout.js" not in t:
        issues.append((rel, "missing js"))
    if "aitoolbox-layout.css" not in t:
        issues.append((rel, "missing css"))
    apps = re.findall(r'data-fafo-layout-app="([^"]+)"', s)
    if not apps:
        issues.append((rel, "missing app id"))
    for a in apps:
        ids.setdefault(a, []).append(rel)
    if "data-fafo-layout-toolbar" not in t:
        issues.append((rel, "no toolbar"))

    # depth check
    depth = len(Path(rel).parts) - 1
    m = re.search(r'src="([^"]*aitoolbox-layout\.js)"', t)
    if m and depth > 0:
        src = m.group(1)
        ups = src.count("../")
        if "shared/aitoolbox-layout.js" in src and ups != depth:
            issues.append((rel, f"js path depth {ups} != {depth}: {src}"))

dups = {k: v for k, v in ids.items() if len(v) > 1}
print("marked", marked)
print("issues", len(issues))
for rel, msg in issues:
    print(" ", rel, "->", msg)
print("dup ids", len(dups))
for k, v in dups.items():
    print(" ", k, v)

# Key explicit multi-panel apps must have explicit panels
critical = [
    "File Tools/Duplicate File Manager.html",
    "Movie File Manager/Media Library Manager.html",
    "Movie File Manager/File Organizer.html",
    "Developer Tools/Git Repository Manager.html",
    "System Tools/PC Diagnostics HUD.html",
    "System Tools/LAN Task Manager.html",
    "System Tools/System Health Dashboard.html",
]
print("\ncritical apps:")
for rel in critical:
    p = root / rel
    t = p.read_text(encoding="utf-8", errors="replace")
    panels = len(re.findall(r"data-fafo-panel=", t))
    ok = (
        "data-fafo-layout-root" in t
        and "aitoolbox-layout.js" in t
        and "aitoolbox-layout.css" in t
        and panels >= 2
    )
    print(f"  {'OK' if ok else 'BAD'} {rel} panels={panels}")
