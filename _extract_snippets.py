from pathlib import Path
import re

theirs = Path("_theirs_launcher.html").read_text(encoding="utf-8", errors="replace")
ours = Path("Toolbox Launcher.html").read_text(encoding="utf-8", errors="replace")

# Extract tool object by id from theirs
def extract_tool(src, tool_id):
    m = re.search(rf"\{{\s*id:\s*'{re.escape(tool_id)}'[\s\S]*?\n\s*\}},", src)
    if not m:
        m = re.search(rf"\{{\s*id:\s*'{re.escape(tool_id)}'[\s\S]*?\n\s*\}}", src)
    return m.group(0) if m else None

for tid in ["progress-map-mythos", "tech-quest", "taxforge-mileage", "taxforge-quarterly", "taxforge-hub", "taxforge-writeoffs", "taxforge-war-room"]:
    t = extract_tool(theirs, tid)
    print(tid, "FOUND" if t else "MISSING", "len", len(t or ""))

# Extract watchdog panel HTML block
wm = re.search(r"<!-- Server Watchdog[\s\S]*?Install-Server-Watchdog\.bat</code>\s*</div>\s*</div>", theirs)
print("watchdog panel", "FOUND" if wm else "MISSING")
if wm:
    Path("_snippet_watchdog.html").write_text(wm.group(0), encoding="utf-8")
    print("watchdog lines", wm.group(0).count("\n")+1)

# Extract JS for watchdog from theirs
# Between // Server Watchdog and next major section
jm = re.search(r"//[^\n]*Server Watchdog[\s\S]*?(?=\n\s*//[^\n]{8,}|\n\s*function showGetStarted|\n\s*async function pollServers|\n\s*// =+\n)", theirs)
print("watchdog js heuristic", "FOUND" if jm else "MISSING", "len", len(jm.group(0)) if jm else 0)

# Find btnWatchdog handlers region more simply
idx = theirs.find("btnWatchdogStart")
print("btnWatchdogStart idx", idx)
if idx > 0:
    start = theirs.rfind("function", 0, idx)
    # expand to a larger block containing all watchdog functions
    block_start = theirs.rfind("//", max(0, idx-800), idx)
    block_end = theirs.find("\n        // ", idx + 50)
    if block_end < 0:
        block_end = theirs.find("\n        async function", idx)
    print("block", block_start, block_end)
    if block_start > 0 and block_end > block_start:
        Path("_snippet_watchdog_js.js").write_text(theirs[block_start:block_end], encoding="utf-8")
        print("js snippet len", block_end-block_start)

# top button
if "btnWatchdogStatusTop" in theirs and "btnWatchdogStatusTop" not in ours:
    print("need top watchdog btn")
else:
    print("top btn already?", "btnWatchdogStatusTop" in ours)
