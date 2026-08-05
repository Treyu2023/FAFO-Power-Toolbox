from pathlib import Path
import re

theirs = Path("_theirs_launcher.html").read_text(encoding="utf-8", errors="replace")
launcher = Path("Toolbox Launcher.html").read_text(encoding="utf-8", errors="replace")

def extract_object_by_id(src: str, tool_id: str):
    needle = f"id: '{tool_id}'"
    i = src.find(needle)
    if i < 0:
        return None
    start = src.rfind("{", 0, i)
    if start < 0:
        return None
    depth = 0
    for j in range(start, len(src)):
        ch = src[j]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return src[start : j + 1] + ","
    return None

def extract_div_by_id(src: str, div_id: str):
    i = src.find(f'id="{div_id}"')
    if i < 0:
        return None
    start = src.rfind("<!--", max(0, i - 200), i)
    if start < 0 or "Watchdog" not in src[start:i]:
        start = src.rfind("<div", 0, i)
    div0 = src.find("<div", start)
    depth = 0
    k = div0
    while k < len(src):
        if src.startswith("<div", k):
            depth += 1
            k = src.find(">", k) + 1
            continue
        if src.startswith("</div>", k):
            depth -= 1
            k += 6
            if depth == 0:
                return src[start:k]
            continue
        k += 1
    return None

def extract_watchdog_js(src: str):
    start = src.find("Server Watchdog UI")
    if start < 0:
        start = src.find("function applyWatchdogStatus")
    if start < 0:
        return None
    start = src.rfind("\n", 0, start) + 1
    prev = src.rfind("\n", 0, start - 1)
    if prev >= 0 and "//" in src[prev:start]:
        start = prev + 1
    end = start
    for key in [
        "btnWatchdogRefresh",
        "btnWatchdogFolder",
        "btnWatchdogInstall",
        "btnWatchdogStatusTop",
        "btnWatchdogStatus",
        "btnWatchdogStart",
    ]:
        p = src.find(key, start)
        if p > end:
            end = p
    semi = src.find("});", end)
    if semi > 0:
        end = semi + 3
    else:
        end = src.find("\n\n", end)
    return src[start:end]

tools = {}
for tid in ["progress-map-mythos", "taxforge-mileage", "taxforge-quarterly", "tech-quest"]:
    obj = extract_object_by_id(theirs, tid)
    tools[tid] = obj
    bad = (not obj) or ("];" in obj) or (obj.count("{") != obj.count("}"))
    print(tid, "BAD" if bad else "ok", "len", len(obj or ""))

panel = extract_div_by_id(theirs, "watchdogPanel")
js = extract_watchdog_js(theirs)
print("panel", bool(panel), len(panel or 0))
print("js", bool(js), len(js or 0))
m = re.search(r'<button[^>]*id="btnWatchdogStatusTop"[^>]*>.*?</button>', theirs, re.S)
top_btn = m.group(0) if m else None
print("top", bool(top_btn))

def insert_tool_before(html, before_id, tool_obj):
    if not tool_obj:
        return html, False
    mid = re.search(r"id:\s*'([^']+)'", tool_obj)
    tid = mid.group(1) if mid else ""
    if tid and f"id: '{tid}'" in html:
        return html, True
    needle = f"id: '{before_id}'"
    i = html.find(needle)
    if i < 0:
        return html, False
    start = html.rfind("{", 0, i)
    line = html.rfind("\n", 0, start) + 1
    block = "            " + tool_obj.strip() + "\n"
    return html[:line] + block + html[line:], True

for tid, before in [
    ("progress-map-mythos", "git-manager"),
    ("taxforge-mileage", "loan-calc"),
    ("taxforge-quarterly", "loan-calc"),
    ("tech-quest", "empire-seed"),
]:
    launcher, ok = insert_tool_before(launcher, before, tools[tid])
    print("insert", tid, ok)

if top_btn and 'id="btnWatchdogStatusTop"' not in launcher:
    m = re.search(r'id="btnOpenBackups"[^>]*>.*?</button>\s*\n', launcher, re.S)
    if m:
        launcher = launcher[: m.end()] + "            " + top_btn + "\n" + launcher[m.end() :]
        print("top btn inserted")

if panel and 'id="watchdogPanel"' not in launcher:
    if 'id="launchPrefsPanel"' in launcher:
        i = launcher.find('id="launchPrefsPanel"')
        start = launcher.rfind("<div", 0, i)
        line = launcher.rfind("\n", 0, start) + 1
        launcher = launcher[:line] + "        " + panel + "\n\n        " + launcher[line:]
        print("panel before launchPrefs")
    else:
        print("no launchPrefs")

if js and "function applyWatchdogStatus" not in launcher:
    for key in ["const LAUNCHER_TUTORIAL", "function showGetStartedPanel"]:
        p = launcher.find(key)
        if p > 0:
            line = launcher.rfind("\n", 0, p) + 1
            launcher = launcher[:line] + "\n        " + js.strip() + "\n\n        " + launcher[line:]
            print("js inserted before", key)
            break

if "btnWatchdogStatusTop" in launcher and "btnWatchdogStatusTop')?.addEventListener" not in launcher:
    extra = "\n        document.getElementById('btnWatchdogStatusTop')?.addEventListener('click', () => runWatchdogAction('status'));\n"
    p = launcher.find("btnWatchdogStart')?.addEventListener")
    if p > 0:
        end = launcher.find(";", p) + 1
        launcher = launcher[:end] + extra + launcher[end:]
        print("top listener added")

assert "<<<<<<<" not in launcher
assert "function applyWatchdogStatus" in launcher
assert 'id="watchdogPanel"' in launcher
for tid in tools:
    assert f"id: '{tid}'" in launcher, tid
assert launcher.find("id: 'tech-quest'") < launcher.find("id: 'empire-seed'")
assert launcher.count("const grid = document.getElementById('toolGrid')") == 1

Path("Toolbox Launcher.html").write_text(launcher, encoding="utf-8", newline="\n")
print("LAUNCHER OK")
