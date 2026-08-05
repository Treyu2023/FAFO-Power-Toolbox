from pathlib import Path

def show(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    i = 0
    n = 0
    while i < len(lines):
        if lines[i].startswith("<<<<<<<"):
            n += 1
            start = i
            mid = end = None
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("=======") and mid is None:
                    mid = j
                if lines[j].startswith(">>>>>>>"):
                    end = j
                    break
            print(f"\n===== {path} conflict #{n} lines {start+1}-{end+1} =====")
            head = lines[start + 1 : mid]
            theirs = lines[mid + 1 : end]
            print(f"--- HEAD ({len(head)} lines) ---")
            for L in head[:50]:
                print(L[:180])
            if len(head) > 50:
                print(f"... +{len(head)-50} more")
            print(f"--- COMMIT ({len(theirs)} lines) ---")
            for L in theirs[:50]:
                print(L[:180])
            if len(theirs) > 50:
                print(f"... +{len(theirs)-50} more")
            i = end + 1
        else:
            i += 1

for p in [
    "Toolbox Launcher.html",
    "server/aitoolbox_server.py",
    "server/protocol_start.bat",
    "shared/aitoolbox-api.js",
    "shared/aitoolbox-cinematic.js",
]:
    show(p)
