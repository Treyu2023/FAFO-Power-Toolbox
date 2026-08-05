from pathlib import Path
import re
html = Path("Toolbox Launcher.html").read_text(encoding="utf-8", errors="replace")

# Count applyWatchdogStatus
print("applyWatchdogStatus count", html.count("function applyWatchdogStatus"))
print("watchdogPanel count", html.count('id="watchdogPanel"'))

# Extract tools array and try to parse with a rough check for duplicate ids
ids = re.findall(r"id:\s*'([^']+)'", html)
from collections import Counter
c = Counter(ids)
dups = {k:v for k,v in c.items() if v>1 and k in (
  "progress-map-mythos","tech-quest","taxforge-mileage","taxforge-quarterly",
  "taxforge-hub","empire-seed","git-manager","loan-calc"
)}
print("dup ids of interest", dups)

# Show tech-quest block
m = re.search(r"id:\s*'tech-quest'[\s\S]{0,800}", html)
print("--- tech-quest vicinity ---")
print(m.group(0)[:800] if m else "missing")

# Show progress-map
m = re.search(r"id:\s*'progress-map-mythos'[\s\S]{0,500}", html)
print("--- progress-map ---")
print(m.group(0)[:500] if m else "missing")

# Check JS brace balance roughly around watchdog
idx = html.find("function applyWatchdogStatus")
print("js around watchdog start:")
print(html[idx-100:idx+200])
# Find if nested wrongly
print("btnWatchdogStart listener count", html.count("btnWatchdogStart"))

# Syntax: extract script and check with node - extract tools array only
# Validate no conflict markers
print("conflict markers", html.count("<<<<<<<"))

# protocol check
p = Path("server/protocol_start.bat").read_text(encoding="utf-8", errors="replace")
print("protocol do_watchdog", ":do_watchdog" in p)
print("protocol do_ghost", ":do_ghost" in p)
print("protocol conflict", "<<<<<<<" in p)
