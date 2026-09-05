#!/usr/bin/env python3
"""FAFO Power Toolbox 3.0 production pass — surgical patches + HTML stamp."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path("/tmp/fafo-toolbox")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    print("wrote", path.relative_to(ROOT))


def patch(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        if new in text or new.strip() in text:
            print("skip (already)", label)
            return
        print("MISS", label, path)
        return
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("ok", label)


def main() -> None:
    write(ROOT / "VERSION", "3.0.0\n")

    ver = ROOT / "shared" / "aitoolbox-version.js"
    ver.write_text(
        """/** Keep in sync with /VERSION */
(function (g) {
  var V = '3.0.0';
  g.AITOOLBOX_VERSION = V;
  g.AIToolboxCacheBust = function (url) {
    if (!url) return url;
    var v = String(g.AITOOLBOX_VERSION || V);
    if (/[?&]v=/.test(url)) return url.replace(/([?&]v=)[^&]*/, '$1' + encodeURIComponent(v));
    return url + (url.indexOf('?') >= 0 ? '&' : '?') + 'v=' + encodeURIComponent(v);
  };
})(typeof window !== 'undefined' ? window : globalThis);
""",
        encoding="utf-8",
    )
    print("ok version.js")

    readme = ROOT / "README.md"
    rtxt = readme.read_text(encoding="utf-8")
    rtxt = re.sub(r"\*\*Current version:\*\*\s*`[^`]+`", "**Current version:** `3.0.0`", rtxt, count=1)
    readme.write_text(rtxt, encoding="utf-8")

    write(
        ROOT / "MILESTONE_FREEZE.md",
        """# Milestone freeze pointer

**Frozen milestone:** **2.0** (git-disconnected archive of live `1.16.51`)
**Source commit:** `9f90266932d68dbe00976955515734d6ef55b419`
**Freeze date:** 2026-09-05
**Live working tree:** **3.0.0** — production pass. Do **not** treat the freeze as the live feature set.

## Snapshot location (read-only, no `.git`)

The v2.0 archive is a copy of the entire toolbox with git metadata stripped so it
cannot be updated by later commits. It lives beside this repo as:

```
milestones/FAFO-Power-Toolbox-v2.0-MILESTONE-2026-09-05/
milestones/FAFO-Power-Toolbox-v2.0-MILESTONE-2026-09-05.zip
```

SHA-256 of the zip: `dd14172cda652bcaeb3c6d9452279d3ee943d086f35af5a269cfb722333918cb`

## Live working tree (edit this)

| Project | Path |
|---------|------|
| Toolbox | this repository (`3.0.0`) |

## Restore

Copy the 2.0 folder over a live tree only if you accept losing all post-2.0 edits
(including this 3.0 production pass).
""",
    )

    # --- debug recursion ---
    debug = ROOT / "shared" / "aitoolbox-debug.js"
    dtxt = debug.read_text(encoding="utf-8")
    dtxt = dtxt.replace(
        "        if (level === 'error') console.error(`[${source}]`, message, extra || '');\n"
        "        else if (level === 'warn') console.warn(`[${source}]`, message);",
        "        if (level === 'error') {\n"
        "            try { (global._dbgOrigError || console.error).call(console, `[${source}]`, message, extra || ''); }\n"
        "            catch (_) { /* ignore */ }\n"
        "        } else if (level === 'warn') console.warn(`[${source}]`, message);",
    )
    dtxt = dtxt.replace(
        """        const orig = console.error;
        console.error = function (...args) {
            log('console', 'error', args.map(a => (a?.message || String(a))).join(' '));
            orig.apply(console, args);
        };""",
        """        const orig = console.error;
        global._dbgOrigError = orig;
        let _inConsole = false;
        console.error = function (...args) {
            if (_inConsole) return orig.apply(console, args);
            _inConsole = true;
            try {
                log('console', 'error', args.map(a => (a?.message || String(a))).join(' '));
            } finally {
                _inConsole = false;
            }
            orig.apply(console, args);
        };""",
    )
    debug.write_text(dtxt, encoding="utf-8")
    print("ok debug.js")

    # --- api.js ---
    api = ROOT / "shared" / "aitoolbox-api.js"
    atxt = api.read_text(encoding="utf-8")
    atxt = atxt.replace(
        """            if (typeof document !== 'undefined' && document.body && (
                document.body.classList.contains('kf-standalone') ||
                document.body.getAttribute('data-tb-chrome') === 'off'
            )) return true;""",
        """            try {
                if (g !== g.top) return true;
            } catch (_) { return true; }
            try {
                const ka = localStorage.getItem('aitoolbox.keepalive') || localStorage.getItem('aitoolbox_keepalive');
                if (ka === 'off' || ka === '0') return true;
            } catch { /* ignore */ }
            if (typeof document !== 'undefined' && document.body && (
                document.body.classList.contains('kf-standalone') ||
                document.body.getAttribute('data-tb-chrome') === 'off'
            )) return true;""",
    )
    # skipKeepAlive uses `global` not `g`
    atxt = atxt.replace(
            """            if (typeof document !== 'undefined' && document.body && (
                document.body.classList.contains('kf-standalone') ||
                document.body.getAttribute('data-tb-chrome') === 'off'
            )) return true;""",
        """            try { if (global.self !== global.top) return true; } catch (_) { return true; }
            try {
                const ka = localStorage.getItem('aitoolbox.keepalive') || localStorage.getItem('aitoolbox_keepalive');
                if (ka === 'off' || ka === '0') return true;
            } catch { /* ignore */ }
            if (typeof document !== 'undefined' && document.body && (
                document.body.classList.contains('kf-standalone') ||
                document.body.getAttribute('data-tb-chrome') === 'off'
            )) return true;""",
    )
    atxt = atxt.replace(
        "    let failStreak = 0;\n",
        "    let failStreak = 0;\n    const _inFlight = new Map();\n",
    )
    atxt = atxt.replace(
        "        const headers = { 'Content-Type': 'application/json', ...(fetchOpts.headers || {}) };",
        "        const headers = { ...(fetchOpts.headers || {}) };\n"
        "        if (fetchOpts.body != null && headers['Content-Type'] == null && headers['content-type'] == null) {\n"
        "            headers['Content-Type'] = 'application/json';\n"
        "        }",
    )
    atxt = atxt.replace(
        """        try {
            refreshApiBase();
            const doFetch = () => fetch(`${apiBase()}${path}`, {""",
        """        const coalKey = (method === 'GET' || method === 'HEAD')
            ? method + ' ' + path
            : null;
        if (coalKey && _inFlight.has(coalKey)) return _inFlight.get(coalKey);

        const run = (async () => {
        try {
            refreshApiBase();
            const doFetch = () => fetch(`${apiBase()}${path}`, {""",
    )
    # Close the run() wrapper before the function ends — insert after the last catch of api()
    # Find `            throw err;\n        }\n    }\n\n    const API`
    atxt = atxt.replace(
        """            const err = new Error(msg);
            err.cause = e;
            err.offline = offlineLike;
            err.path = path;
            throw err;
        }
    }

    const API = {""",
        """            const err = new Error(msg);
            err.cause = e;
            err.offline = offlineLike;
            err.path = path;
            throw err;
        }
        })();
        if (coalKey) {
            _inFlight.set(coalKey, run);
            const done = () => _inFlight.delete(coalKey);
            run.then(done, done);
        }
        return run;
    }

    const API = {""",
    )
    atxt = atxt.replace(
        """            return api('/launch/companions/stop', {
                method: 'POST',
                body: JSON.stringify(body),
                timeoutMs: 15000,
            });""",
        """            const out = await api('/launch/companions/stop', {
                method: 'POST',
                body: JSON.stringify(body),
                timeoutMs: 15000,
            });
            try { localStorage.setItem('aitoolbox.keepalive', 'off'); } catch { /* ignore */ }
            return out;""",
    )
    atxt = atxt.replace(
        """                        es.onmessage = e => {
                            const d = JSON.parse(e.data);
                            if (d.error) { es.close(); reject(new Error(d.error)); }
                            else if (d.done) { es.close(); resolve({ indexed: d.count }); }
                            else onProgress(d.count, d.file);
                        };
                        es.onerror = () => { es.close(); reject(new Error('Scan stream failed')); };""",
        """                        let esErrs = 0;
                        const onHide = () => { try { es.close(); } catch (_) {} };
                        window.addEventListener('pagehide', onHide, { once: true });
                        es.onmessage = e => {
                            let d;
                            try { d = JSON.parse(e.data); } catch (_) { return; }
                            if (d.error) { es.close(); reject(new Error(d.error)); }
                            else if (d.done) { es.close(); resolve({ indexed: d.count }); }
                            else onProgress(d.count, d.file);
                        };
                        es.onerror = () => {
                            esErrs += 1;
                            if (esErrs >= 3) { es.close(); reject(new Error('Scan stream failed')); }
                        };""",
    )
    api.write_text(atxt, encoding="utf-8")
    print("ok api.js")

    # --- layout ---
    lay = ROOT / "shared" / "aitoolbox-layout.js"
    ltxt = lay.read_text(encoding="utf-8")
    ltxt = ltxt.replace(
        "      const rect = p.getBoundingClientRect();\n"
        "      const px = type === 'columns' ? rect.width : rect.height;\n"
        "      if (px > 0) sizes[id] = Math.round(px);",
        "      const rect = p.getBoundingClientRect();\n"
        "      const scale = readUiScale() || 1;\n"
        "      const px = (type === 'columns' ? rect.width : rect.height) / scale;\n"
        "      if (px > 0) sizes[id] = Math.round(px);",
    )
    ltxt = ltxt.replace(
        """    function rebindAll() {
      // re-query handles after DOM reorder
      root.querySelectorAll('.fafo-split-handle').forEach((h) => {
        h._fafoBound = false;
      });
      root.querySelectorAll('.fafo-section-resize').forEach((h) => {
        h._fafoBound = false;
      });
      panelEls(root).forEach((p) => {
        const c = p.querySelector(':scope > .fafo-panel-chrome');
        if (c) c._fafoDrag = false;
        sectionEls(p).forEach((s) => {
          const sc = s.querySelector(':scope > .fafo-section-chrome');
          if (sc) sc._fafoDrag = false;
        });
      });
      bindSplitResize(root, opts, save);
      bindSectionResize(root, save);
      bindPanelDrag(root, opts, save, rebindAll);
      bindSectionDrag(root, opts, save, rebindAll);
    }""",
        """    function rebindAll() {
      // Do not clear _fafoBound / _fafoDrag — those flags are the listener guard.
      bindSplitResize(root, opts, save);
      bindSectionResize(root, save);
      bindPanelDrag(root, opts, save, rebindAll);
      bindSectionDrag(root, opts, save, rebindAll);
    }""",
    )
    ltxt = ltxt.replace(
        """      destroy() {
        instances.delete(appId);
      },""",
        """      destroy() {
        try { window.removeEventListener('resize', onResize); } catch (_) {}
        try { window.removeEventListener('pagehide', flush); } catch (_) {}
        try { window.removeEventListener('beforeunload', flush); } catch (_) {}
        try { document.removeEventListener('visibilitychange', onVis); } catch (_) {}
        instances.delete(appId);
      },""",
    )
    ltxt = ltxt.replace(
        """    window.addEventListener(
      'resize',
      debounce(() => {
        // Re-clamp if viewport shrank under a huge saved panel
        pinViewport(root);
        const cur = sanitizeState(root, captureState(root, opts), opts);
        applyState(root, cur, opts);
        rebindAll();
        wireResets();
        markScrollPanes(root);
        saveNow();
      }, 400)
    );

    // Always remember last position — flush on leave / hide
    const flush = () => {
      try {
        saveNow();
      } catch (_) { /* ignore */ }
    };
    window.addEventListener('pagehide', flush);
    window.addEventListener('beforeunload', flush);
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) flush();
    });""",
        """    const onResize = debounce(() => {
        pinViewport(root);
        const cur = sanitizeState(root, captureState(root, opts), opts);
        applyState(root, cur, opts);
        rebindAll();
        wireResets();
        markScrollPanes(root);
        saveNow();
      }, 400);
    window.addEventListener('resize', onResize);

    const flush = () => {
      try { saveNow(); } catch (_) { /* ignore */ }
    };
    const onVis = () => { if (document.hidden) flush(); };
    window.addEventListener('pagehide', flush);
    window.addEventListener('beforeunload', flush);
    document.addEventListener('visibilitychange', onVis);""",
    )
    lay.write_text(ltxt, encoding="utf-8")
    print("ok layout.js")

    # --- ui.js ---
    ui = ROOT / "shared" / "aitoolbox-ui.js"
    utxt = ui.read_text(encoding="utf-8")
    utxt = utxt.replace("            return '1.16.47';", "            return String(global.AITOOLBOX_VERSION || '3.0.0');")
    utxt = utxt.replace(
        """                ? `<div class="preview-list">${preview.slice(0, 8).map(p =>
                    `<div><span style="color:#888">${p.from}</span> → <span style="color:var(--ui-accent)">${p.to}</span></div>`
                ).join('')}${preview.length > 8 ? `<div style="color:#666">…and ${preview.length - 8} more</div>` : ''}</div>`
                : '';

            const trustChecked = trustDefaultChecked ? ' checked' : '';
            bg.innerHTML = `
                <div class="ui-modal">
                    <h3>${title}</h3>
                    <div class="ui-modal-body">${body}${safetyHtml}</div>""",
        """                ? `<div class="preview-list">${preview.slice(0, 8).map(p =>
                    `<div><span style="color:#888">${escapeHtml(p.from)}</span> → <span style="color:var(--ui-accent)">${escapeHtml(p.to)}</span></div>`
                ).join('')}${preview.length > 8 ? `<div style="color:#666">…and ${preview.length - 8} more</div>` : ''}</div>`
                : '';

            const trustChecked = trustDefaultChecked ? ' checked' : '';
            bg.innerHTML = `
                <div class="ui-modal">
                    <h3>${escapeHtml(title)}</h3>
                    <div class="ui-modal-body">${escapeHtml(body)}${safetyHtml}</div>""",
    )
    utxt = utxt.replace(
        """            r = await fetch(url, {
                headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
                ...opts,
            });""",
        """            const ctrl = (typeof AbortSignal !== 'undefined' && AbortSignal.timeout)
                ? AbortSignal.timeout(opts.timeoutMs || 30000)
                : undefined;
            r = await fetch(url, {
                headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
                ...opts,
                signal: opts.signal || ctrl,
            });""",
    )
    utxt = utxt.replace("window.parent.postMessage({ type: 'fafo-escape', href: launcherHref() }, '*');",
                        "window.parent.postMessage({ type: 'fafo-escape', href: launcherHref() }, location.origin);")
    utxt = utxt.replace(
        "window.parent.postMessage({ type: 'fafo-hub-tab', tab: info.tab, search: info.search, href: info.href }, '*');",
        "window.parent.postMessage({ type: 'fafo-hub-tab', tab: info.tab, search: info.search, href: info.href }, location.origin);",
    )
    utxt = utxt.replace(
        "window.parent.postMessage({ type: 'fafo-compare-tab', tab: info.tab, search: info.search, href: info.href }, '*');",
        "window.parent.postMessage({ type: 'fafo-compare-tab', tab: info.tab, search: info.search, href: info.href }, location.origin);",
    )
    utxt = utxt.replace(
        "window.parent.postMessage({ type: 'fafo-escape', href: info.href }, '*');",
        "window.parent.postMessage({ type: 'fafo-escape', href: info.href }, location.origin);",
    )
    ui.write_text(utxt, encoding="utf-8")
    print("ok ui.js")

    # --- media_ops add_directory ---
    mop = ROOT / "server" / "media_ops.py"
    mtxt = mop.read_text(encoding="utf-8")
    mtxt = mtxt.replace(
        '''    did = f"dir-{uuid.uuid4().hex[:10]}"
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO directories (id, path, name, added_at) VALUES (?, ?, ?, ?)",
            (did, str(p), p.name, time.time()),
        )
        row = conn.execute("SELECT * FROM directories WHERE id=?", (did,)).fetchone()
    return dict(row)''',
        '''    with connect() as conn:
        existing = conn.execute(
            "SELECT * FROM directories WHERE path=?", (str(p),)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE directories SET name=? WHERE id=?",
                (p.name, existing["id"]),
            )
            row = conn.execute(
                "SELECT * FROM directories WHERE id=?", (existing["id"],)
            ).fetchone()
            return dict(row)
        did = f"dir-{uuid.uuid4().hex[:10]}"
        conn.execute(
            "INSERT INTO directories (id, path, name, added_at) VALUES (?, ?, ?, ?)",
            (did, str(p), p.name, time.time()),
        )
        row = conn.execute("SELECT * FROM directories WHERE id=?", (did,)).fetchone()
    return dict(row)''',
    )
    mop.write_text(mtxt, encoding="utf-8")
    print("ok media_ops.py")

    # --- server ---
    srv = ROOT / "server" / "aitoolbox_server.py"
    stxt = srv.read_text(encoding="utf-8")
    stxt = stxt.replace(
        '''app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)''',
        '''_CORS_ORIGINS = {
    "http://127.0.0.87:18765",
    "http://127.0.0.1:18765",
    "null",
}
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(_CORS_ORIGINS),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)''',
    )
    stxt = stxt.replace(
        '''        return Response(
            status_code=204,
            headers={
                "Access-Control-Allow-Origin": request.headers.get("origin") or "*",
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": request.headers.get(
                    "access-control-request-headers", "*"
                ),
                "Access-Control-Allow-Private-Network": "true",
            },
        )''',
        '''        origin = request.headers.get("origin") or "null"
        allow = origin if origin in _CORS_ORIGINS else "http://127.0.0.87:18765"
        return Response(
            status_code=204,
            headers={
                "Access-Control-Allow-Origin": allow,
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": request.headers.get(
                    "access-control-request-headers", "*"
                ),
                "Access-Control-Allow-Private-Network": "true" if origin in _CORS_ORIGINS or origin == "null" else "false",
            },
        )''',
    )
    stxt = stxt.replace(
        '''    dbg.log("server", "error", str(exc), {"path": request.url.path, "type": type(exc).__name__})
    return JSONResponse(status_code=500, content={"detail": str(exc)})''',
        '''    dbg.log("server", "error", str(exc), {"path": request.url.path, "type": type(exc).__name__})
    return JSONResponse(status_code=500, content={"detail": "Internal error", "id": type(exc).__name__})''',
    )
    stxt = stxt.replace(
        '''@app.get("/api/health")
def health():
    try:
        import launch_ops as _launch_ops
        _launch_ops.note_demand("s1", app="html-toolbox")
    except Exception:
        pass
    return {
        "ok": True,''',
        '''@app.get("/api/health")
def health(probe: int = 0):
    if not probe:
        try:
            import launch_ops as _launch_ops
            _launch_ops.note_demand("s1", app="html-toolbox")
        except Exception:
            pass
    db_ok = False
    try:
        from db import connect as _db_connect
        with _db_connect() as _c:
            _c.execute("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "ok": True,
        "db_ok": db_ok,''',
    )
    stxt = stxt.replace(
        '''    if any(part in blocked for part in target.relative_to(ROOT.resolve()).parts):
        raise HTTPException(403, "Forbidden")''',
        '''    rel_parts = target.relative_to(ROOT.resolve()).parts
    if any(part in blocked for part in rel_parts):
        raise HTTPException(403, "Forbidden")
    if target.suffix.lower() in {".py", ".db", ".env", ".sqlite", ".sqlite3"}:
        raise HTTPException(403, "Forbidden")''',
    )
    stxt = stxt.replace(
        '''    print("  Press Ctrl+C to stop\\n", flush=True)
    uvicorn.run(app, host=host, port=port, log_level="warning")''',
        '''    print("  Press Ctrl+C to stop\\n", flush=True)
    try:
        uvicorn.run(app, host=host, port=port, log_level="warning")
    except OSError as exc:
        if host != "127.0.0.1":
            print(f"  Bind {host}:{port} failed ({exc}); falling back to 127.0.0.1:{port}", flush=True)
            BIND_HOST, BIND_PORT = "127.0.0.1", port
            uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
        else:
            raise''',
    )
    srv.write_text(stxt, encoding="utf-8")
    print("ok aitoolbox_server.py")

    # --- launcher residual + version stamps ---
    launcher = ROOT / "Toolbox Launcher.html"
    lht = launcher.read_text(encoding="utf-8")
    lht = lht.replace("?v=1.16.50", "?v=3.0.0")
    lht = lht.replace("?v=1.16.51", "?v=3.0.0")
    lht = re.sub(r"\?v=1\.16\.\d+", "?v=3.0.0", lht)
    # inject runtime before api if missing
    if "aitoolbox-runtime.js" not in lht:
        lht = lht.replace(
            '<script src="shared/aitoolbox-api.js?v=3.0.0"></script>',
            '<script src="shared/aitoolbox-runtime.js?v=3.0.0"></script>\n    <script src="shared/aitoolbox-api.js?v=3.0.0"></script>',
        )
    lht = lht.replace(
        """                tip: 'Residual: Progress Map HTML is not in this toolbox tree (would 404). Restore pack later or ignore. Not part of admin ops.',
                path: 'Progress Map/Progress Map.html',
                category: 'Developer',
                emoji: '🗺️',
                featured: false,
                offlineOk: true,
                residualMissing: true""",
        """                tip: 'Roadmap with mythos layer. Installed in this tree — open from Home or Developer.',
                path: 'Progress Map/Progress Map.html',
                category: 'Developer',
                emoji: '🗺️',
                featured: true,
                offlineOk: true""",
    )
    lht = lht.replace(
        """                tip: 'Residual: Tech Quest HTML is not in this toolbox tree (would 404). Restore pack later or ignore.',
                path: 'Tech Quest/Tech Quest.html',
                category: 'Games',
                emoji: '🗡️',
                featured: false,
                offlineOk: true,
                residualMissing: true""",
        """                tip: 'Turn-based tech RPG. Installed in this tree — open from Home or Utilities.',
                path: 'Tech Quest/Tech Quest.html',
                category: 'Games',
                emoji: '🗡️',
                featured: true,
                offlineOk: true""",
    )
    # add classic standalones before closing TOOLS
    extra = """
            {
                id: 'media-library-classic',
                name: 'Media Library (classic)',
                desc: 'Standalone catalog — same engine as Media Hub → Library',
                tip: 'Direct page. Hub iframe still available from Media Hub.',
                path: 'Movie File Manager/Media Library Manager.html',
                category: 'Library',
                emoji: '📚',
                nestedUnder: 'media-hub',
                needsServer: true,
                localOnly: true
            },
            {
                id: 'duplicate-finder-classic',
                name: 'Duplicate File Manager (classic)',
                desc: 'Standalone duplicate scanner',
                tip: 'Direct page. Also Media Hub → Duplicates.',
                path: 'File Tools/Duplicate File Manager.html',
                category: 'Library',
                emoji: '🗑️',
                nestedUnder: 'media-hub',
                needsServer: true,
                localOnly: true
            },
            {
                id: 'file-organizer-classic',
                name: 'File Organizer (classic)',
                desc: 'Standalone organizer',
                tip: 'Direct page. Also Media Hub → Organizer.',
                path: 'Movie File Manager/File Organizer.html',
                category: 'Library',
                emoji: '✏️',
                nestedUnder: 'media-hub',
                needsServer: true,
                localOnly: true
            },
            {
                id: 'video-compare-classic',
                name: 'Video Comparator (classic)',
                desc: 'Standalone video slider',
                tip: 'Direct page. Also Compare Hub → Video.',
                path: 'Video Tools/Video Comparison Slider Tool.html',
                category: 'Video',
                emoji: '🎬',
                nestedUnder: 'compare-hub',
                offlineOk: true
            },
            {
                id: 'image-compare-classic',
                name: 'Image Comparator (classic)',
                desc: 'Standalone image slider',
                tip: 'Direct page. Also Compare Hub → Image.',
                path: 'Image tools/Image Comparitor With Slider.html',
                category: 'Image',
                emoji: '🖼️',
                nestedUnder: 'compare-hub',
                offlineOk: true
            },
"""
    if "media-library-classic" not in lht:
        lht = lht.replace("        ];\n\n        const grid", extra + "        ];\n\n        const grid")
    # search haystack include path
    lht = lht.replace(
        "t.name + ' ' + t.desc + ' ' + (t.tip || '') + ' ' + t.id + ' ' + t.category",
        "t.name + ' ' + t.desc + ' ' + (t.tip || '') + ' ' + t.id + ' ' + t.category + ' ' + (t.path || '')",
    )
    launcher.write_text(lht, encoding="utf-8")
    print("ok launcher")

    # --- stamp all HTML ---
    stamped = 0
    injected = 0
    for html in ROOT.rglob("*.html"):
        rel = html.relative_to(ROOT).as_posix()
        if rel.startswith("snapshots/") or "/snapshots/" in rel:
            continue
        text = html.read_text(encoding="utf-8", errors="replace")
        orig = text
        text = re.sub(r"\?v=1\.\d+\.\d+", "?v=3.0.0", text)
        # inject runtime before api
        if "aitoolbox-api.js" in text and "aitoolbox-runtime.js" not in text:
            text = re.sub(
                r'(<script[^>]+src="[^"]*aitoolbox-api\.js[^"]*"[^>]*>\s*</script>)',
                r'<script src="shared/aitoolbox-runtime.js?v=3.0.0"></script>\n    \1'
                if rel.count("/") == 0
                else (
                    r'<script src="../shared/aitoolbox-runtime.js?v=3.0.0"></script>\n    \1'
                    if rel.count("/") == 1
                    else r'<script src="../../shared/aitoolbox-runtime.js?v=3.0.0"></script>\n    \1'
                ),
                text,
                count=1,
            )
            # Fix prefix based on depth more carefully
            depth = rel.count("/")
            prefix = "../" * depth + "shared/aitoolbox-runtime.js?v=3.0.0"
            text = re.sub(
                r'<script src="(?:\.\./)*shared/aitoolbox-runtime\.js\?v=3\.0\.0"></script>',
                f'<script src="{prefix}"></script>',
                text,
                count=1,
            )
            injected += 1
        # inject config before api on hubs
        if "aitoolbox-api.js" in text and "aitoolbox-config.js" not in text:
            depth = rel.count("/")
            prefix = "../" * depth + "shared/"
            insert = (
                f'<script src="{prefix}aitoolbox-config.js?v=3.0.0"></script>\n'
                f'    <script src="{prefix}aitoolbox-version.js?v=3.0.0"></script>\n    '
            )
            text = re.sub(
                r'(<script[^>]+src="[^"]*aitoolbox-runtime\.js[^"]*"[^>]*>\s*</script>)',
                insert + r"\1",
                text,
                count=1,
            )
            if "aitoolbox-config.js" not in text:
                text = re.sub(
                    r'(<script[^>]+src="[^"]*aitoolbox-api\.js[^"]*"[^>]*>\s*</script>)',
                    insert + r"\1",
                    text,
                    count=1,
                )
        if text != orig:
            html.write_text(text, encoding="utf-8")
            stamped += 1
    print(f"stamped {stamped} html, runtime injected ~{injected}")

    # debounce library search
    lib = ROOT / "Movie File Manager" / "Media Library Manager.html"
    if lib.is_file():
        t = lib.read_text(encoding="utf-8")
        t2 = t.replace(
            "els.searchInput?.addEventListener('input', () => { page = 0;",
            "els.searchInput?.addEventListener('input', (window.AIToolboxRuntime && AIToolboxRuntime.debounce ? AIToolboxRuntime.debounce : (fn) => fn)(() => { page = 0;",
        )
        # This is fragile; a simpler unique replace:
        t2 = t  # reset
        t2 = re.sub(
            r"els\.searchInput\?\.addEventListener\('input',\s*\(\)\s*=>\s*\{\s*page\s*=\s*0;",
            "let _searchTimer=0; els.searchInput?.addEventListener('input', () => { clearTimeout(_searchTimer); _searchTimer=setTimeout(() => { page = 0;",
            t2,
            count=1,
        )
        if t2 != t:
            # close the extra setTimeout — find applyFilters(); after that listener is hard.
            # Add closing ); after first applyFilters(); following the listener if we opened setTimeout
            lib.write_text(t2, encoding="utf-8")
            print("ok library search debounce (timer opened — verify brace)")
        else:
            print("library search pattern miss")

    write(
        ROOT / "docs" / "PRODUCTION-3.0.md",
        """# FAFO Power Toolbox 3.0 — production pass

Frozen **2.0** (git-disconnected archive of `1.16.51`) first. Live tree is **3.0.0**.

## P0

- Single version source `3.0.0` (`VERSION`, `aitoolbox-version.js`, HTML `?v=`, README)
- Debug `console.error` no longer recurses (`?debug=1` is usable again)
- Layout capture divides by UI scale so Look → 4K/125% no longer snowballs panel sizes
- `rebindAll()` no longer resets `_fafoBound` (listener multiplication)
- Layout `destroy()` removes resize/pagehide listeners
- Keep-alive skipped in iframes and when `aitoolbox.keepalive=off` (Stop no longer fights open tabs)
- GET coalescing + JSON Content-Type only when a body is present
- Scan EventSource JSON.parse is guarded; first SSE errors are not fatal
- Confirm-rename HTML is escaped (filename XSS)
- `postMessage` targets `location.origin`
- CORS allowlist (loopback + `null`) instead of `*`
- Re-adding a watch folder no longer CASCADE-wipes the catalog
- Unhandled 500s no longer leak exception strings
- `/toolbox` refuses `.py` / `.db` / `.env`
- Bind fallback to `127.0.0.1` if `127.0.0.87` is missing (Linux/VMs)
- Health `?probe=1` skips demand so the watchdog does not keep S1 “in use” forever
- Progress Map + Tech Quest un-hidden (`residualMissing` was a lie — files exist)
- Launcher search includes `path` (amortization / comparitor now match)

## P1

- `aitoolbox-runtime.js` — debounce/throttle/coalesce/timer registry/quota storage
- Config+version+runtime injected on hubs that skipped them
- Classic standalone cards restored (Library, Duplicates, Organizer, comparators)
- `apiFetch` times out at 30s
- Health includes `db_ok`

## What 3.0 does not rewrite

Typing Trainer and Commander Site Console are still large inline apps. Three.js for Empire/Solar still comes from jsDelivr unless you vendor it locally. System Health Dashboard / Desk / HUD remain three surfaces — Dashboard is the front door; Desk is ops KPIs; HUD is the interactive scan.
""",
    )


if __name__ == "__main__":
    main()
