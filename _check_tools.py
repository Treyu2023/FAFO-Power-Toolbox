from pathlib import Path
import re
html = Path("Toolbox Launcher.html").read_text(encoding="utf-8", errors="replace")
for tid in ["empire-seed", "typing-assistant-trainer", "tech-quest", "bloodmoon", "loan-calc", "taxforge-mileage"]:
    print(tid, html.count(f"id: '{tid}'"))

# Find tools array end occurrences
for m in re.finditer(r"^\s*\];\s*$", html, re.M):
    pos = m.start()
    ctx = html[max(0,pos-120):pos+80]
    if "tool" in ctx.lower() or "offlineOk" in ctx or "featured" in ctx or "Games" in ctx:
        print("--- ]; at", pos, "---")
        print(ctx)
        print()

# Count tool objects roughly
print("total id: count in file", len(re.findall(r"id:\s*'", html)))
# Check if empire-seed appears after tech-quest close
tq = html.find("id: 'tech-quest'")
es = html.find("id: 'empire-seed'")
print("tech-quest pos", tq, "empire-seed pos", es)
if tq > 0 and es > 0:
    print("between them:", html[tq:es][-200:])
    print("empire after:", html[es:es+300])
