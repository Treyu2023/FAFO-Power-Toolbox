from pathlib import Path
import re

launcher = Path("Toolbox Launcher.html").read_text(encoding="utf-8", errors="replace")
theirs = Path("_theirs_launcher.html").read_text(encoding="utf-8", errors="replace")
panel = Path("_snippet_watchdog.html").read_text(encoding="utf-8", errors="replace")
js = Path("_snippet_watchdog_js.js").read_text(encoding="utf-8", errors="replace")

def extract_tool(src, tool_id):
    # Match object starting with id: 'x' up to its closing },
    pat = re.compile(
        rf"(\{{\s*\n\s*id:\s*'{re.escape(tool_id)}',[\s\S]*?\n\s*\}}),",
        re.M,
    )
    m = pat.search(src)
    return m.group(1) + "," if m else None

tools_to_add = []
for tid in ["progress-map-mythos", "taxforge-mileage", "taxforge-quarterly", "tech-quest"]:
    if f"id: '{tid}'" in launcher:
        print("already have", tid)
        continue
    t = extract_tool(theirs, tid)
    if t:
        tools_to_add.append((tid, t))
        print("will add", tid)
    else:
        print("FAILED extract", tid)

# Insert tools before closing of tools array `        ];` that follows tool objects
# Prefer insert before empire-seed or before typing if games, and tax tools near taxforge-hub

def insert_before_id(html, before_id, block):
    needle = f"id: '{before_id}'"
    idx = html.find(needle)
    if idx < 0:
        return html, False
    # back to start of object `{`
    start = html.rfind("{", 0, idx)
    # include leading whitespace/newline
    line_start = html.rfind("\n", 0, start) + 1
    return html[:line_start] + block + "\n" + html[line_start:], True

# progress map near developer tools - insert before git-manager or after reg-qol
for tid, block in tools_to_add:
    if tid == "progress-map-mythos":
        launcher, ok = insert_before_id(launcher, "git-manager", block)
        if not ok:
            launcher, ok = insert_before_id(launcher, "reg-qol-tweaks", block)
        print("insert progress", ok)
    elif tid in ("taxforge-mileage", "taxforge-quarterly"):
        # after partner-period-desk if present else after taxforge hub path
        launcher, ok = insert_before_id(launcher, "loan-calc", block)
        if not ok:
            launcher, ok = insert_before_id(launcher, "partner-period-desk", block)
        print("insert", tid, ok)
    elif tid == "tech-quest":
        launcher, ok = insert_before_id(launcher, "empire-seed", block)
        if not ok:
            launcher, ok = insert_before_id(launcher, "typing-assistant-trainer", block)
        print("insert tech-quest", ok)

# Top Watchdog button after Backups
if 'id="btnWatchdogStatusTop"' not in launcher:
    btn = (
        '            <button class="ui-btn" id="btnWatchdogStatusTop" data-tip-title="Watchdog status" '
        'data-tip="Open S1/S2 monitor status page — auto-heal report.">📡 Watchdog</button>\n'
    )
    if 'id="btnOpenBackups"' in launcher:
        # insert after that button's closing
        m = re.search(r'id="btnOpenBackups"[^>]*>.*?</button>\s*\n', launcher)
        if m:
            launcher = launcher[: m.end()] + btn + launcher[m.end() :]
            print("inserted top watchdog btn after backups")
        else:
            print("could not find backups button end")
    else:
        print("no backups button")
else:
    print("top btn exists")

# Watchdog panel HTML - insert after server cards area / before launch prefs
if 'id="watchdogPanel"' not in launcher:
    # try after fafoMetaPathHint or chkStartFafoMeta section
    anchors = [
        'id="fafoMetaPathHint"',
        "2-Start-FAFO-Local-Media-Tagger.bat",
        'id="launchPrefsPanel"',
        "Named servers",
    ]
    inserted = False
    for a in anchors:
        idx = launcher.find(a)
        if idx < 0:
            continue
        # if launchPrefsPanel - insert BEFORE it
        if a == 'id="launchPrefsPanel"':
            start = launcher.rfind("<div", 0, idx)
            line_start = launcher.rfind("\n", 0, start) + 1
            launcher = launcher[:line_start] + panel + "\n\n        " + launcher[line_start:]
            inserted = True
            print("inserted panel before launchPrefs")
            break
        # else insert after the block containing anchor
        # find next closing section after bat files paragraph
        end_p = launcher.find("</p>", idx)
        if end_p > 0:
            # after surrounding div if possible
            after = end_p + 4
            # skip whitespace
            launcher = launcher[:after] + "\n\n        " + panel + launcher[after:]
            inserted = True
            print("inserted panel after", a)
            break
    if not inserted:
        print("FAILED to insert watchdog panel")
else:
    print("panel exists")

# JS insert - before end of DOMContentLoaded or after pollServers setup
if "function applyWatchdogStatus" not in launcher:
    # clean js snippet - ensure it starts at comment
    js_clean = js
    # strip leading broken fragment if starts mid-function
    if "Server Watchdog" in js_clean:
        js_clean = js_clean[js_clean.find("//") :]
    # find insertion point: after refreshServers or similar
    markers = [
        "refreshServers().catch",
        "pollServers",
        "btnStartServer",
        "DOMContentLoaded",
    ]
    # Prefer insert near other server UI wiring - search for btnStopAll or similar
    insert_at = -1
    for key in ["btnStopAll", "btnStartS2", "refreshServerStatus", "function updateServerDots"]:
        p = launcher.find(key)
        if p > 0:
            insert_at = p
    # find a safe spot: before final tutorial or at end of script init
    # Look for `// ── Server` style or just before LAUNCHER_TUTORIAL
    for key in ["const LAUNCHER_TUTORIAL", "function showGetStartedPanel", "// Boot", "initLauncher"]:
        p = launcher.find(key)
        if p > 0:
            insert_at = p
            break
    if insert_at > 0:
        line_start = launcher.rfind("\n", 0, insert_at) + 1
        launcher = launcher[:line_start] + "\n" + js_clean + "\n\n        " + launcher[line_start:]
        print("inserted watchdog JS before", launcher[insert_at : insert_at + 40])
    else:
        print("FAILED js insert")
else:
    print("watchdog JS exists")

# Wire top button if missing in listeners - js snippet should include it
if "btnWatchdogStatusTop" in launcher and "btnWatchdogStatusTop')?.addEventListener" not in launcher and 'btnWatchdogStatusTop")?.addEventListener' not in launcher:
    # add listener near other watchdog listeners if present
    if "btnWatchdogStart" in launcher:
        extra = (
            "\n        document.getElementById('btnWatchdogStatusTop')?.addEventListener('click', () => runWatchdogAction('status'));\n"
        )
        # after btnWatchdogStatus listener
        p = launcher.find("btnWatchdogStatus')?.addEventListener")
        if p < 0:
            p = launcher.find('btnWatchdogStatus")?.addEventListener')
        if p > 0:
            end = launcher.find(";", p) + 1
            launcher = launcher[:end] + extra + launcher[end:]
            print("added top btn listener")
        else:
            # append after applyWatchdogStatus block
            p = launcher.find("runWatchdogAction('start')")
            if p > 0:
                end = launcher.find("\n", p)
                launcher = launcher[:end] + extra + launcher[end:]
                print("added top btn listener (fallback)")

Path("Toolbox Launcher.html").write_text(launcher, encoding="utf-8", newline="\n")

# Verify
for needle in [
    "watchdogPanel",
    "btnWatchdogStart",
    "applyWatchdogStatus",
    "progress-map-mythos",
    "tech-quest",
    "taxforge-mileage",
    "taxforge-quarterly",
    "<<<<<<<",
]:
    print(("OK" if needle in launcher else "MISSING"), needle)

# Protocol bat - write merged clean version based on ours + watchdog
proto = Path("_ours_protocol.bat").read_text(encoding="utf-8", errors="replace")
if "watchdog" not in proto.lower() or "do_watchdog" not in proto:
    # Fix encoding-ish dashes if present by using clean content
    rem_line = "REM   aitoolbox://ghost          Ghost Device Cleaner (elevated UAC + picker)\n"
    rem_add = (
        "REM   aitoolbox://ghost          Ghost Device Cleaner (elevated UAC + picker)\n"
        "REM   aitoolbox://watchdog       Start S1/S2 server watchdog\n"
        "REM   aitoolbox://watchdog-status Open watchdog status HTML\n"
        "REM   aitoolbox://watchdog-install Install watchdog Startup + poll task\n"
        "REM   aitoolbox://watchdog-folder  Explorer select Start-Server-Watchdog.bat\n"
    )
    if "aitoolbox://ghost" in proto:
        proto = proto.replace(
            "REM   aitoolbox://ghost          Ghost Device Cleaner (elevated UAC + picker)\n",
            rem_add,
            1,
        )
    else:
        # try garbled
        proto = re.sub(
            r"REM\s+aitoolbox://ghost[^\n]*\n",
            rem_add,
            proto,
            count=1,
        )

    # After ghost action detection, add watchdog (more specific first)
    ghost_detect = 'echo %RAW%| findstr /I /C:"ghost" >nul && set "ACTION=ghost"\n'
    wd_detect = (
        'echo %RAW%| findstr /I /C:"ghost" >nul && set "ACTION=ghost"\n'
        '  echo %RAW%| findstr /I /C:"watchdog-status" >nul && set "ACTION=watchdog-status"\n'
        '  echo %RAW%| findstr /I /C:"watchdog-install" >nul && set "ACTION=watchdog-install"\n'
        '  echo %RAW%| findstr /I /C:"watchdog-folder" >nul && set "ACTION=watchdog-folder"\n'
        '  echo %RAW%| findstr /I /C:"watchdog" >nul && if /I not "%ACTION%"=="watchdog-status" if /I not "%ACTION%"=="watchdog-install" if /I not "%ACTION%"=="watchdog-folder" set "ACTION=watchdog"\n'
    )
    if ghost_detect in proto:
        proto = proto.replace(ghost_detect, wd_detect, 1)

    # Fix start line to exclude watchdog actions + ghost
    # Replace the long start line
    proto = re.sub(
        r'echo %RAW%\| findstr /I /C:"start" >nul && if /I not "%ACTION%"=="console".*\n',
        '  echo %RAW%| findstr /I /C:"start" >nul && if /I not "%ACTION%"=="console" if /I not "%ACTION%"=="folder" if /I not "%ACTION%"=="setup" if /I not "%ACTION%"=="launch" if /I not "%ACTION%"=="diagnostics" if /I not "%ACTION%"=="pack" if /I not "%ACTION%"=="restart" if /I not "%ACTION%"=="tray" if /I not "%ACTION%"=="ghost" if /I not "%ACTION%"=="watchdog" if /I not "%ACTION%"=="watchdog-status" if /I not "%ACTION%"=="watchdog-install" if /I not "%ACTION%"=="watchdog-folder" set "ACTION=start"\n',
        proto,
        count=1,
    )

    # folder/open should not steal watchdog-folder
    proto = proto.replace(
        'echo %RAW%| findstr /I /C:"folder" >nul && set "ACTION=folder"\n',
        'echo %RAW%| findstr /I /C:"folder" >nul && if /I not "%ACTION%"=="watchdog-folder" set "ACTION=folder"\n',
        1,
    )
    proto = proto.replace(
        'echo %RAW%| findstr /I /C:"open" >nul && set "ACTION=folder"\n',
        'echo %RAW%| findstr /I /C:"open" >nul && if /I not "%ACTION%"=="watchdog-folder" if /I not "%ACTION%"=="watchdog-status" set "ACTION=folder"\n',
        1,
    )

    # Dispatch after ghost
    proto = proto.replace(
        'if /I "%ACTION%"=="ghost" goto do_ghost\n',
        'if /I "%ACTION%"=="ghost" goto do_ghost\n'
        'if /I "%ACTION%"=="watchdog-status" goto do_watchdog_status\n'
        'if /I "%ACTION%"=="watchdog-install" goto do_watchdog_install\n'
        'if /I "%ACTION%"=="watchdog-folder" goto do_watchdog_folder\n'
        'if /I "%ACTION%"=="watchdog" goto do_watchdog\n',
        1,
    )

    # Labels before do_folder
    wd_labels = '''
:do_watchdog
if exist "%cd%\\Start-Server-Watchdog.bat" (
  start "" "%cd%\\Start-Server-Watchdog.bat"
) else if exist "%cd%\\server\\server_watchdog.py" (
  start "" /MIN "%cd%\\.venv\\Scripts\\pythonw.exe" "%cd%\\server\\server_watchdog.py"
)
exit /b 0

:do_watchdog_status
if exist "%cd%\\Open-Server-Watchdog-Status.bat" (
  start "" "%cd%\\Open-Server-Watchdog-Status.bat"
) else (
  start "" explorer.exe "%LOCALAPPDATA%\\FAFO\\Devices\\%COMPUTERNAME%\\Reports"
)
exit /b 0

:do_watchdog_install
if exist "%cd%\\Install-Server-Watchdog.bat" (
  start "" "%cd%\\Install-Server-Watchdog.bat"
)
exit /b 0

:do_watchdog_folder
if exist "%cd%\\Start-Server-Watchdog.bat" (
  start "" explorer.exe /select,"%cd%\\Start-Server-Watchdog.bat"
) else (
  start "" explorer.exe "%cd%"
)
exit /b 0

'''
    proto = proto.replace(":do_folder\n", wd_labels + ":do_folder\n", 1)
    Path("server/protocol_start.bat").write_text(proto, encoding="utf-8", newline="\r\n")
    print("protocol patched with watchdog")
else:
    print("protocol already has watchdog")

# Verify server.py has both
srv = Path("server/aitoolbox_server.py").read_text(encoding="utf-8", errors="replace")
print("server markers", "<<<<<<" in srv)
print("server watchdog", "/api/launch/watchdog" in srv)
print("server tools launch", "api_tools_launch" in srv or "/api/tools/launch" in srv)

api = Path("shared/aitoolbox-api.js").read_text(encoding="utf-8", errors="replace")
print("api markers", "<<<<<<" in api)
print("api watchdog", "watchdog" in api)
print("api ghost", "ghost" in api)

cine = Path("shared/aitoolbox-cinematic.js").read_text(encoding="utf-8", errors="replace")
print("cine markers", "<<<<<<" in cine)
print("cine PROXY", "PROXY_SECONDS" in cine)
