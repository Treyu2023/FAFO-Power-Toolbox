/**
 * Shared iframe hub controller for Media Hub + Compare Hub.
 * One showTab / ping / load-fail / abort-on-switch implementation.
 *
 * AIToolboxHub.mount({ tabs, order, aliases, defaultTab, lsKey, ... })
 */
(function (global) {
    'use strict';

    function D() { return global.AIToolboxDom || null; }

    function el(id) {
        const d = D();
        if (d && d.el) return d.el(id);
        try { return typeof id === 'string' ? document.getElementById(id) : id; } catch (_) { return null; }
    }
    function setText(n, t) {
        const d = D();
        if (d && d.setText) return d.setText(n, t);
        const node = typeof n === 'string' ? el(n) : n;
        if (node) try { node.textContent = t == null ? '' : String(t); } catch (_) {}
        return node;
    }
    function bind(n, ev, fn) {
        const d = D();
        if (d && d.bind) return d.bind(n, ev, fn);
        const node = typeof n === 'string' ? el(n) : n;
        if (node && ev && typeof fn === 'function') node.addEventListener(ev, fn);
        return node;
    }
    function lsGet(k, fb) {
        const d = D();
        if (d && d.lsGet) return d.lsGet(k, fb);
        try { const v = localStorage.getItem(k); return v == null ? fb : v; } catch (_) { return fb; }
    }
    function lsSet(k, v) {
        const d = D();
        if (d && d.lsSet) return d.lsSet(k, v);
        try { localStorage.setItem(k, v); return true; } catch (_) { return false; }
    }
    function escHtml(s) {
        const d = D();
        if (d && d.escapeHtml) return d.escapeHtml(s);
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }
    function withBusy(key, fn, btn) {
        const d = D();
        if (d && d.withBusy) return d.withBusy(key, fn, btn);
        return Promise.resolve().then(fn);
    }
    function isTypingTarget(t) {
        const d = D();
        if (d && d.isTypingTarget) return d.isTypingTarget(t);
        if (!t) return false;
        return /INPUT|TEXTAREA|SELECT/.test(t.tagName || '') || !!t.isContentEditable;
    }
    function launcherHref() {
        const d = D();
        if (d && d.launcherHref) return d.launcherHref();
        try {
            if (global.AIToolboxUI && AIToolboxUI.launcherHref) return AIToolboxUI.launcherHref();
        } catch (_) {}
        return '../Toolbox Launcher.html';
    }
    function toast(msg, kind) {
        const d = D();
        if (d && d.toast) return d.toast(msg, kind);
        try { global.AIToolboxUI && AIToolboxUI.toast && AIToolboxUI.toast(msg, kind || 'ok'); } catch (_) {}
    }

    function abortFrame(frame) {
        if (!frame) return;
        try { frame.contentWindow && frame.contentWindow.stop && frame.contentWindow.stop(); } catch (_) {}
        try {
            const prev = frame.getAttribute('src');
            if (prev && prev.indexOf('blob:') === 0) URL.revokeObjectURL(prev);
        } catch (_) {}
        try { frame.removeAttribute('src'); } catch (_) {}
        try { frame.src = 'about:blank'; } catch (_) {}
    }

    function mount(opts) {
        opts = opts || {};
        const TABS = opts.tabs || {};
        const ORDER = opts.order || Object.keys(TABS);
        const ALIASES = opts.aliases || {};
        const defaultTab = opts.defaultTab || ORDER[0];
        const LS_TAB = opts.lsKey || 'fafo_hub_last_tab';
        const frame = el(opts.frameId || 'hubFrame');
        const loading = el(opts.loadingId || 'loading');
        const meta = el(opts.metaId || 'hubMeta');
        const badgeId = opts.badgeId || 'serverBadge';
        const pairHealthId = opts.pairHealthId || '';
        const forwardSearchOnTab = opts.forwardSearchOnTab || '';
        const messageType = opts.messageType || 'fafo-hub-tab';
        const keyMap = opts.keyMap || {};
        const reportTitle = opts.reportTitle || 'FAFO Hub';
        const reportLines = opts.reportLines || [];
        const loadTimeoutMs = opts.loadTimeoutMs || 25000;

        try {
            if (global.parent !== global) {
                document.documentElement.classList.add('hub-embedded');
            }
        } catch (_) {
            document.documentElement.classList.add('hub-embedded');
        }

        let current = defaultTab;
        let loadTimer = null;
        let loadGen = 0;
        let lastSrc = '';

        function normalizeTab(raw) {
            let h = String(raw || '').replace(/^#/, '').toLowerCase();
            h = h.split('?')[0].split('/')[0].trim();
            if (ALIASES[h]) return ALIASES[h];
            if (TABS[h]) return h;
            return '';
        }

        function tabFromHash() {
            let h = (location.hash || '').replace(/^#/, '');
            if (!h) {
                try {
                    const m = /#([^#]*)$/.exec(location.href || '');
                    if (m) h = decodeURIComponent(m[1]);
                } catch (_) {}
            }
            const tab = normalizeTab(h);
            if (tab) return tab;
            const last = lsGet(LS_TAB, '');
            if (last && TABS[last]) return last;
            return defaultTab;
        }

        function syncTabChrome(id) {
            document.querySelectorAll('.hub-tab').forEach((b) => {
                const on = b.dataset.tab === id;
                b.classList.toggle('active', on);
                b.setAttribute('aria-selected', on ? 'true' : 'false');
                b.tabIndex = on ? 0 : -1;
            });
        }

        async function pingPairHealth() {
            const badge = pairHealthId ? el(pairHealthId) : null;
            if (!badge || !global.AIToolboxAPI || !AIToolboxAPI.pairHealth) return;
            try {
                const h = await AIToolboxAPI.pairHealth(false);
                const s = h.summary || {};
                const c = s.complete || 0;
                const b = s.broken || 0;
                const p = s.partial || 0;
                const d = s.duplicate_occupancy || 0;
                badge.textContent = 'Pairs ' + c
                    + (b ? ' · ' + b + ' broken' : p ? ' · ' + p + ' partial' : ' ok')
                    + (d ? ' · ' + d + ' overlap' : '');
                badge.className = 'server-badge ' + (b || d ? 'bad' : 'ok');
                badge.title = c + ' complete · ' + p + ' partial · ' + b + ' broken'
                    + (d ? ' · ' + d + ' media in two pairs' : '');
            } catch (_) {
                badge.textContent = 'Pairs —';
            }
        }

        async function pingServer() {
            if (pairHealthId) pingPairHealth();
            const badge = el(badgeId);
            if (!badge) return;
            try {
                const on = await (global.AIToolboxAPI && AIToolboxAPI.isOnline
                    ? AIToolboxAPI.isOnline(false, 1500).catch(() => false)
                    : false);
                setText(badge, on ? '● Online' : '○ Offline — click ▶ Start');
                badge.className = 'server-badge ' + (on ? 'ok' : 'bad');
                badge.title = on ? 'Toolbox server online' : 'Server offline — click to start from this page';
            } catch (_) {
                setText(badge, '○ Offline');
                badge.className = 'server-badge bad';
            }
        }

        async function startServerFromHub() {
            await withBusy('startServer', async () => {
                const btn = el(opts.startBtnId || 'btnStartServer');
                if (btn) btn.disabled = true;
                try {
                    toast('Starting toolbox server…', 'ok');
                    if (global.AIToolboxAPI && AIToolboxAPI.startServer) {
                        await AIToolboxAPI.startServer({ mode: 'tray', waitMs: 90000 });
                    } else {
                        location.href = launcherHref();
                        return;
                    }
                    await pingServer();
                    toast('Server ready — reloading workspace', 'ok');
                    showTab(current, false);
                } catch (e) {
                    toast((e && e.message) || 'Start failed — open Launcher', 'warn');
                } finally {
                    if (btn) btn.disabled = false;
                }
            });
        }

        async function resolveSrc(tabId) {
            const t = TABS[tabId] || TABS[defaultTab] || {};
            const path = t.path || '';
            let toolboxPath = t.toolboxPath;
            if (!toolboxPath) {
                toolboxPath = path.indexOf('../') === 0
                    ? path.replace(/^\.\.\//, '')
                    : 'Movie File Manager/' + path;
            }
            let src = path;
            try {
                if (global.AIToolboxAPI && AIToolboxAPI.isOnline && AIToolboxAPI.toolPageUrl) {
                    const on = await AIToolboxAPI.isOnline(false, 1500).catch(() => false);
                    if (on) src = AIToolboxAPI.toolPageUrl(toolboxPath) || src;
                }
            } catch (_) { /* ignore */ }
            if (forwardSearchOnTab && tabId === forwardSearchOnTab && location.search) {
                src += (String(src).indexOf('?') >= 0 ? '&' : '?') + location.search.replace(/^\?/, '');
            }
            return src || path;
        }

        function showLoadFail(title, src) {
            if (!loading) return;
            loading.classList.remove('hide');
            loading.classList.add('fail');
            const safeTitle = escHtml(title);
            const safeSrc = escHtml(src);
            const safeLaunch = escHtml(launcherHref());
            loading.innerHTML =
                '<div><strong style="color:#fff">' + safeTitle + ' didn’t load</strong></div>' +
                '<div style="max-width:420px;color:var(--muted);font-size:12px;line-height:1.45">' +
                'The workspace tab timed out or failed. Retry, open it full-window, or return to the Launcher.</div>' +
                '<div class="actions">' +
                '<button type="button" id="hubRetry">↻ Retry</button>' +
                '<a href="' + safeSrc + '" target="_blank" rel="noopener">↗ Open full window</a>' +
                '<a class="ghost" href="' + safeLaunch + '">← Launcher</a>' +
                '<button type="button" class="ghost" id="hubStartFromFail">▶ Start Server</button>' +
                '</div>';
            bind(el('hubRetry'), 'click', () => showTab(current, false));
            bind(el('hubStartFromFail'), 'click', startServerFromHub);
        }

        async function showTab(id, pushHash) {
            if (!TABS[id]) id = defaultTab;
            current = id;
            syncTabChrome(id);
            const t = TABS[id] || {};
            document.title = (t.title || 'Hub') + ' — ' + (opts.hubName || 'Hub');
            if (meta) meta.innerHTML = t.meta || '';
            lsSet(LS_TAB, id);
            if (pushHash !== false) {
                const hash = id;
                if ((location.hash || '').replace(/^#/, '') !== hash) {
                    try { history.replaceState(null, '', '#' + hash); } catch (_) {}
                }
            }
            if (!frame || !loading) return;
            const gen = ++loadGen;
            if (loadTimer) clearTimeout(loadTimer);
            loading.classList.remove('hide', 'fail');
            setText(loading, 'Loading ' + (t.title || 'workspace') + '…');
            const src = await resolveSrc(id);
            if (gen !== loadGen) return;
            frame.onload = () => {
                if (gen !== loadGen) return;
                if (loadTimer) clearTimeout(loadTimer);
                loading.classList.add('hide');
                loading.classList.remove('fail');
            };
            frame.onerror = () => {
                if (gen !== loadGen) return;
                if (loadTimer) clearTimeout(loadTimer);
                showLoadFail(t.title, src);
            };
            loadTimer = setTimeout(() => {
                if (gen !== loadGen) return;
                if (loading.classList.contains('hide')) return;
                try {
                    const doc = frame.contentDocument;
                    if (doc && (doc.readyState === 'complete' || doc.readyState === 'interactive')) {
                        loading.classList.add('hide');
                        return;
                    }
                } catch (_) {
                    showLoadFail(t.title, src);
                    return;
                }
                showLoadFail(t.title, src);
            }, loadTimeoutMs);
            abortFrame(frame);
            lastSrc = src || '';
            frame.src = src || 'about:blank';
        }

        async function copyHubReport() {
            await withBusy('copyReport', async () => {
                const t = TABS[current] || {};
                const lines = [
                    reportTitle + ' — session report',
                    'Time: ' + new Date().toISOString(),
                    'Active tab: ' + (t.title || current),
                    'Hash: ' + (location.hash || ''),
                    'URL: ' + location.href,
                    'Server: ' + (el(badgeId) && el(badgeId).textContent || 'unknown'),
                    '',
                ].concat(reportLines);
                const text = lines.join('\n');
                try {
                    await navigator.clipboard.writeText(text);
                    toast('Hub report copied', 'ok');
                } catch (_) {
                    try { prompt('Copy report:', text); } catch (__) {}
                }
            }, opts.reportId || 'btnCopyReport');
        }

        function focusTabByOffset(delta) {
            const i = Math.max(0, ORDER.indexOf(current));
            let n = i + delta;
            if (n < 0) n = ORDER.length - 1;
            if (n >= ORDER.length) n = 0;
            const next = ORDER[n];
            showTab(next, true);
            const btn = document.querySelector('.hub-tab[data-tab="' + next + '"]');
            try { btn && btn.focus && btn.focus(); } catch (_) {}
        }

        bind(el(opts.tabsId || 'hubTabs'), 'click', (e) => {
            const btn = e.target && e.target.closest ? e.target.closest('.hub-tab') : null;
            if (!btn || !btn.dataset.tab) return;
            showTab(btn.dataset.tab, true);
        });
        bind(el(opts.tabsId || 'hubTabs'), 'keydown', (e) => {
            if (!e) return;
            if (e.key === 'ArrowRight' || e.key === 'ArrowDown') { e.preventDefault(); focusTabByOffset(1); }
            else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') { e.preventDefault(); focusTabByOffset(-1); }
            else if (e.key === 'Home') { e.preventDefault(); showTab(ORDER[0], true); }
            else if (e.key === 'End') { e.preventDefault(); showTab(ORDER[ORDER.length - 1], true); }
        });

        bind(el(opts.popoutId || 'btnPopout'), 'click', () => {
            withBusy('popout', async () => {
                const src = await resolveSrc(current);
                try { window.open(src, '_blank', 'noopener'); } catch (_) {}
            });
        });
        bind(el(opts.reportId || 'btnCopyReport'), 'click', copyHubReport);
        bind(el(opts.startBtnId || 'btnStartServer'), 'click', startServerFromHub);
        bind(el(badgeId), 'click', () => {
            const badge = el(badgeId);
            if (badge && badge.classList.contains('bad')) startServerFromHub();
            else pingServer();
        });

        window.addEventListener('hashchange', () => showTab(tabFromHash(), false));
        window.addEventListener('pageshow', (e) => {
            if (e.persisted) showTab(tabFromHash(), false);
        });
        document.addEventListener('keydown', function hubTabKeys(e) {
            if (isTypingTarget(e.target)) return;
            if (keyMap[e.key]) { e.preventDefault(); showTab(keyMap[e.key], true); }
            if (e.key === 'r' || e.key === 'R') { e.preventDefault(); copyHubReport(); }
        });
        window.addEventListener('message', function (ev) {
            if (ev.origin !== location.origin) return;
            const data = ev && ev.data;
            if (!data || typeof data !== 'object') return;
            if (data.type === messageType) {
                const tab = normalizeTab(data.tab);
                if (!tab) return;
                if (data.search && String(data.search).indexOf('?') === 0) {
                    try { history.replaceState(null, '', data.search + '#' + tab); } catch (_) {}
                }
                showTab(tab, true);
                return;
            }
            if (data.type === 'fafo-escape') {
                try {
                    location.href = launcherHref() || data.href || '../Toolbox Launcher.html';
                } catch (_) {
                    location.href = '../Toolbox Launcher.html';
                }
            }
        });

        showTab(tabFromHash(), true);
        if (global.AIToolboxMedia && AIToolboxMedia.watchServer) {
            AIToolboxMedia.watchServer(pingServer, { onlineMs: 20000, offlineMs: 8000, iframeMs: 30000 });
        } else {
            pingServer();
            setInterval(pingServer, 20000);
        }

        return {
            showTab: showTab,
            pingServer: pingServer,
            current: function () { return current; },
            resolveSrc: resolveSrc,
        };
    }

    /**
     * Path-first pair save used by both comparators.
     * Avoids locking the wrong catalog row when two files share a name.
     */
    async function saveComparatorPair(api, opts) {
        opts = opts || {};
        if (!api) throw new Error('API missing');
        const name = opts.name || '';
        const kind = opts.kind || 'video';
        const pinned = opts.pinned !== false;
        if (opts.beforePath && opts.afterPath && typeof api.savePairFromPaths === 'function') {
            return api.savePairFromPaths({
                beforePath: opts.beforePath,
                afterPath: opts.afterPath,
                name: name,
                kind: kind,
                pinned: pinned,
                notes: opts.notes || '',
            });
        }
        const bName = opts.beforeName;
        const aName = opts.afterName;
        if (bName && aName && typeof api.queryMedia === 'function' && typeof api.savePair === 'function') {
            const bq = await api.queryMedia({ search: bName, limit: 20 });
            const aq = await api.queryMedia({ search: aName, limit: 20 });
            const sizeMatch = function (items, name, size) {
                const list = items || [];
                if (size != null) {
                    const hit = list.find((m) => m.name === name && Number(m.size) === Number(size));
                    if (hit) return hit;
                }
                const named = list.filter((m) => m.name === name);
                return named.length === 1 ? named[0] : null;
            };
            const bm = sizeMatch(bq.items, bName, opts.beforeSize);
            const am = sizeMatch(aq.items, aName, opts.afterSize);
            if (bm && am) {
                return api.savePair({
                    name: name, kind: kind, beforeMediaId: bm.id, afterMediaId: am.id, pinned: pinned,
                });
            }
        }
        throw new Error('Add files to Media Library first, or load a server pair to save by path.');
    }


    const MEDIA_WORKSPACE_ORDER = ['library', 'duplicates', 'organizer', 'match', 'pairs', 'video', 'image', 'companion'];
    const MEDIA_WORKSPACE_ALIASES = {
        dupes: 'duplicates', duplicate: 'duplicates', org: 'organizer', organize: 'organizer', lib: 'library',
        guided: 'match', elim: 'match', studio: 'match', pair: 'pairs', review: 'pairs', queue: 'pairs',
        vid: 'video', vc: 'video', img: 'image', ic: 'image',
        name: 'companion', vsr: 'companion', mismatch: 'companion',
    };
    function mediaWorkspaceTabs() {
        return {
            library: {
                path: 'Media Library Manager.html',
                toolboxPath: 'Movie File Manager/Media Library Manager.html',
                title: 'Media Library',
                meta: 'Catalog, preview, pair and search. Stay on these tabs — no trip back to Home.'
            },
            duplicates: {
                path: '../File Tools/Duplicate File Manager.html',
                toolboxPath: 'File Tools/Duplicate File Manager.html',
                title: 'Duplicates',
                meta: 'Scan, compare, merge and recycle exact/near duplicates. Results persist across tab switches.'
            },
            organizer: {
                path: 'File Organizer.html',
                toolboxPath: 'Movie File Manager/File Organizer.html',
                title: 'File Organizer',
                meta: 'Rename, tag, rank, merge same-named folders — metadata-first (no grid).'
            },
            match: {
                path: 'Guided Pair Match.html',
                toolboxPath: 'Movie File Manager/Guided Pair Match.html',
                title: 'Guided Pair Match',
                meta: 'One unpaired file at a time · up to 10 candidates · Y match / N next.'
            },
            pairs: {
                path: 'Pair Review Queue.html',
                toolboxPath: 'Movie File Manager/Pair Review Queue.html',
                title: 'Pair Review',
                meta: 'Review before/after pairs, accept or reject, then jump to a comparator.'
            },
            video: {
                path: '../Video Tools/Video Comparison Slider Tool.html',
                toolboxPath: 'Video Tools/Video Comparison Slider Tool.html',
                title: 'Video Comparator',
                meta: 'Search the catalog, highlight a slice of the before name, load the after match.'
            },
            image: {
                path: '../Image tools/Image Comparitor With Slider.html',
                toolboxPath: 'Image tools/Image Comparitor With Slider.html',
                title: 'Image Comparator',
                meta: 'Before/after image slider with catalog search and highlight-to-match.'
            },
            companion: {
                path: 'Mismatched Source Companion.html',
                toolboxPath: 'Movie File Manager/Mismatched Source Companion.html',
                title: 'Name match',
                meta: 'Match and rename dumps whose names no longer match the originals. Not FlashVSR.'
            }
        };
    }
    function mediaWorkspaceKeyMap() {
        const o = {};
        MEDIA_WORKSPACE_ORDER.forEach(function (id, i) { o[String(i + 1)] = id; });
        return o;
    }

    global.AIToolboxHub = {
        mount: mount,
        abortFrame: abortFrame,
        saveComparatorPair: saveComparatorPair,
        mediaWorkspaceTabs: mediaWorkspaceTabs,
        mediaWorkspaceKeyMap: mediaWorkspaceKeyMap,
        MEDIA_WORKSPACE_ORDER: MEDIA_WORKSPACE_ORDER,
        MEDIA_WORKSPACE_ALIASES: MEDIA_WORKSPACE_ALIASES,
    };
})(typeof window !== 'undefined' ? window : globalThis);
