from pathlib import Path
import re

theirs = Path("_theirs_launcher.html").read_text(encoding="utf-8", errors="replace")
ours = Path("Toolbox Launcher.html").read_text(encoding="utf-8", errors="replace")

# Find watchdog panel by id
i = theirs.find('id="watchdogPanel"')
print("watchdogPanel idx", i)
if i > 0:
    # back up to comment or div start
    start = theirs.rfind("<!-- Server Watchdog", 0, i)
    if start < 0:
        start = theirs.rfind("<div", 0, i)
    # find matching close - look for next section comment or launch prefs end
    end = theirs.find("<!-- Named servers", i)
    if end < 0:
        end = theirs.find("id=\"launchPrefsPanel\"", i)
    if end < 0:
        end = theirs.find("</div>\n        </div>\n\n", i)
    print("start end", start, end)
    # better: from start, track div depth
    if start >= 0:
        j = start
        # skip to first <div after comment
        div0 = theirs.find("<div", start)
        depth = 0
        k = div0
        while k < len(theirs):
            if theirs.startswith("<div", k):
                depth += 1
                k = theirs.find(">", k) + 1
                continue
            if theirs.startswith("</div>", k):
                depth -= 1
                k += 6
                if depth == 0:
                    end = k
                    break
                continue
            k += 1
        snippet = theirs[start:end]
        Path("_snippet_watchdog.html").write_text(snippet, encoding="utf-8")
        print("panel len", len(snippet), "lines", snippet.count("\n"))
        print(snippet[:200])
        print("...")
        print(snippet[-200:])

# JS: find applyWatchdogStatus through end of watchdog wiring
a = theirs.find("function applyWatchdogStatus")
b = theirs.find("function applyWatchdogStatus")
# find refreshWatchdog and event listeners
c = theirs.find("// Server Watchdog")
if c < 0:
    c = theirs.find("Server Watchdog UI")
print("js markers", a, c)
# find btnWatchdogStart addEventListener block end
s = theirs.find("btnWatchdogStart")
# expand to include applyWatchdogStatus
start_js = theirs.rfind("\n        //", 0, a if a > 0 else s)
if start_js < 0:
    start_js = theirs.rfind("\n        function applyWatchdog", 0, s+1)
# end after all watchdog listeners - search for last btnWatchdog
last = 0
for key in ["btnWatchdogRefresh", "btnWatchdogFolder", "btnWatchdogInstall", "btnWatchdogStatus", "btnWatchdogStart", "btnWatchdogStatusTop"]:
    p = theirs.find(key, s if s>0 else 0)
    if p > last: last = p
# from last, find end of statement block
end_js = theirs.find("\n\n        ", last)
if end_js < 0:
    end_js = last + 500
# include applyWatchdogStatus function before listeners
if a > 0:
    start_js = min(start_js if start_js > 0 else a, a) - 20
    # back to line start
    start_js = theirs.rfind("\n", 0, start_js) + 1
js = theirs[start_js:end_js]
Path("_snippet_watchdog_js.js").write_text(js, encoding="utf-8")
print("js len", len(js))
print(js[:300])
print("---")
print(js[-400:])

# top button near Start All
top_i = theirs.find("btnWatchdogStatusTop")
print("top button contexts")
print(theirs[top_i-200:top_i+350] if top_i>0 else "none")
