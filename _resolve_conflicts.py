from pathlib import Path

def merge_both(text: str) -> str:
    """Replace each conflict with HEAD + COMMIT (both sides), in order."""
    out = []
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("<<<<<<<"):
            i += 1
            head = []
            while i < len(lines) and not lines[i].startswith("======="):
                head.append(lines[i])
                i += 1
            if i < len(lines) and lines[i].startswith("======="):
                i += 1
            theirs = []
            while i < len(lines) and not lines[i].startswith(">>>>>>>"):
                theirs.append(lines[i])
                i += 1
            if i < len(lines) and lines[i].startswith(">>>>>>>"):
                i += 1
            out.extend(head)
            # Avoid exact duplicate consecutive blocks
            if theirs and theirs != head:
                out.extend(theirs)
        else:
            out.append(line)
            i += 1
    return "".join(out)

def take_head(text: str) -> str:
    out = []
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("<<<<<<<"):
            i += 1
            while i < len(lines) and not lines[i].startswith("======="):
                out.append(lines[i])
                i += 1
            if i < len(lines) and lines[i].startswith("======="):
                i += 1
            while i < len(lines) and not lines[i].startswith(">>>>>>>"):
                i += 1
            if i < len(lines) and lines[i].startswith(">>>>>>>"):
                i += 1
        else:
            out.append(line)
            i += 1
    return "".join(out)

# Launcher: special — keep both tool entries; for tax category prefer HEAD (more complete remote name)
launcher = Path("Toolbox Launcher.html").read_text(encoding="utf-8", errors="replace")
# conflict 3 is tax category — take head only by temporarily marking
# Use merge_both for all then fix tax category if duplicate
launcher = merge_both(launcher)
# If both tax category names appear consecutively, keep TaxForge & Books block only
import re
# Collapse accidental double-comma / empty object issues
launcher = re.sub(r",\s*,", ",", launcher)
Path("Toolbox Launcher.html").write_text(launcher, encoding="utf-8", newline="\n")

# server: both
p = Path("server/aitoolbox_server.py")
p.write_text(merge_both(p.read_text(encoding="utf-8", errors="replace")), encoding="utf-8", newline="\n")

# protocol: both
p = Path("server/protocol_start.bat")
p.write_text(merge_both(p.read_text(encoding="utf-8", errors="replace")), encoding="utf-8", newline="\n")

# api: both
p = Path("shared/aitoolbox-api.js")
p.write_text(merge_both(p.read_text(encoding="utf-8", errors="replace")), encoding="utf-8", newline="\n")

# cinematic: prefer HEAD (remote proxy polish is more advanced)
p = Path("shared/aitoolbox-cinematic.js")
p.write_text(take_head(p.read_text(encoding="utf-8", errors="replace")), encoding="utf-8", newline="\n")

# Verify no markers left
left = []
for path in [
    "Toolbox Launcher.html",
    "server/aitoolbox_server.py",
    "server/protocol_start.bat",
    "shared/aitoolbox-api.js",
    "shared/aitoolbox-cinematic.js",
    "Business Tax Preparedness/README.md",
    "Business Tax Preparedness/TaxForge Hub.html",
    "Business Tax Preparedness/Write-Off Workshop.html",
    "Business Tax Preparedness/Year-End War Room.html",
    "Business Tax Preparedness/taxforge-shared.css",
]:
    t = Path(path).read_text(encoding="utf-8", errors="replace")
    c = t.count("<<<<<<<")
    if c:
        left.append(f"{path}: {c}")
print("remaining markers:", left or "NONE")

# Sanity snippets
for needle, path in [
    ("watchdog", "server/aitoolbox_server.py"),
    ("api_tools_launch", "server/aitoolbox_server.py"),
    ("progress-map-mythos", "Toolbox Launcher.html"),
    ("phone-assist-navigator", "Toolbox Launcher.html"),
    ("tech-quest", "Toolbox Launcher.html"),
    ("typing-assistant-trainer", "Toolbox Launcher.html"),
    (":do_ghost", "server/protocol_start.bat"),
    (":do_watchdog", "server/protocol_start.bat"),
    ("ghost-device-cleaner", "shared/aitoolbox-api.js"),
    ("watchdog-status", "shared/aitoolbox-api.js"),
    ("PROXY_SECONDS", "shared/aitoolbox-cinematic.js"),
]:
    t = Path(path).read_text(encoding="utf-8", errors="replace")
    print(("OK" if needle in t else "MISSING"), needle, "in", path)
