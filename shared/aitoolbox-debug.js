/**
 * Debug mode — captures errors & runtime events in a ring buffer + optional panel.
 * Enable: Settings, toolbar button, or ?debug=1
 */
(function (global) {
    'use strict';

    const STORAGE_KEY = 'aitoolbox_debug';
    const MAX_LOCAL = 400;
    const buffer = [];
    let panelEl = null;
    let listEl = null;
    let pollTimer = null;
    let paused = false;

    function enabled() {
        if (new URLSearchParams(location.search).has('debug')) return true;
        return localStorage.getItem(STORAGE_KEY) === '1';
    }

    function setEnabled(on) {
        if (on) localStorage.setItem(STORAGE_KEY, '1');
        else localStorage.removeItem(STORAGE_KEY);
        if (on) boot(); else shutdown();
    }

    function fmtEntry(e) {
        const lv = (e.level || 'info').toUpperCase().padEnd(5);
        return `[${e.ts || ''}] ${lv} ${e.source || '?'}: ${e.message}`;
    }

    function push(entry) {
        if (paused) return;
        buffer.unshift(entry);
        if (buffer.length > MAX_LOCAL) buffer.length = MAX_LOCAL;
        if (listEl) appendLine(entry);
        try {
            localStorage.setItem('aitoolbox_debug_buffer', JSON.stringify(buffer.slice(0, 80)));
        } catch (_) {}
    }

    function log(source, level, message, extra) {
        const entry = {
            ts: new Date().toISOString(),
            source,
            level,
            message: String(message),
            extra: extra ?? null,
        };
        push(entry);
        if (level === 'error') console.error(`[${source}]`, message, extra || '');
        else if (level === 'warn') console.warn(`[${source}]`, message);
        flushToServer(entry);
        return entry;
    }

    function apiBase() {
        const cfg = global.AITOOLBOX_CONFIG;
        if (cfg && cfg.API_BASE) return cfg.API_BASE;
        if (global.AITOOLBOX_API_BASE) return global.AITOOLBOX_API_BASE;
        return 'http://127.0.0.87:18765/api';
    }

    async function flushToServer(entry) {
        if (!enabled()) return;
        try {
            await fetch(apiBase() + '/debug/log', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(entry),
                signal: AbortSignal.timeout(1200),
            });
        } catch (_) {}
    }

    function appendLine(entry) {
        if (!listEl) return;
        const div = document.createElement('div');
        div.className = 'dbg-line dbg-' + (entry.level || 'info');
        div.textContent = fmtEntry(entry);
        if (entry.extra) div.title = JSON.stringify(entry.extra, null, 2);
        listEl.prepend(div);
        while (listEl.children.length > 200) listEl.lastChild.remove();
    }

    function renderPanel() {
        if (panelEl) return;
        panelEl = document.createElement('div');
        panelEl.id = 'aitoolbox-debug-panel';
        panelEl.className = 'dbg-panel';
        panelEl.innerHTML = `
            <div class="dbg-header">
                <span>🐛 Debug — runtime echo</span>
                <div class="dbg-actions">
                    <button type="button" id="dbg-pause" title="Pause capture">⏸</button>
                    <button type="button" id="dbg-copy" title="Copy log">📋</button>
                    <button type="button" id="dbg-clear" title="Clear">🗑</button>
                    <button type="button" id="dbg-min" title="Minimize">—</button>
                </div>
            </div>
            <div class="dbg-list" id="dbg-list"></div>`;
        document.body.appendChild(panelEl);
        listEl = panelEl.querySelector('#dbg-list');
        buffer.forEach(e => appendLine(e));

        panelEl.querySelector('#dbg-min').onclick = () => {
            panelEl.classList.toggle('minimized');
        };
        panelEl.querySelector('#dbg-pause').onclick = (e) => {
            paused = !paused;
            e.target.textContent = paused ? '▶' : '⏸';
        };
        panelEl.querySelector('#dbg-clear').onclick = async () => {
            buffer.length = 0;
            listEl.innerHTML = '';
            try {
                await fetch(apiBase() + '/debug/clear', { method: 'POST', signal: AbortSignal.timeout(1500) });
            } catch (_) {}
            log('debug', 'info', 'Log cleared');
        };
        panelEl.querySelector('#dbg-copy').onclick = () => {
            const text = buffer.map(fmtEntry).join('\n');
            navigator.clipboard?.writeText(text).then(() => log('debug', 'info', 'Copied to clipboard'));
        };
    }

    function installGlobalHandlers() {
        if (global._dbgHandlers) return;
        global._dbgHandlers = true;
        global.addEventListener('error', e => {
            log('window', 'error', e.message || 'Script error', { file: e.filename, line: e.lineno });
        });
        global.addEventListener('unhandledrejection', e => {
            log('promise', 'error', e.reason?.message || String(e.reason), e.reason);
        });
        const orig = console.error;
        console.error = function (...args) {
            log('console', 'error', args.map(a => (a?.message || String(a))).join(' '));
            orig.apply(console, args);
        };
    }

    async function pollServerLogs() {
        if (!enabled()) return;
        try {
            const r = await fetch(apiBase() + '/debug/logs?limit=40', { signal: AbortSignal.timeout(2000) });
            if (!r.ok) return;
            const data = await r.json();
            (data.logs || []).forEach(e => {
                if (e.source?.startsWith('server') && !buffer.find(b => b.ts === e.ts && b.message === e.message)) {
                    push(e);
                }
            });
        } catch (_) {}
    }

    function boot() {
        installGlobalHandlers();
        renderPanel();
        log('debug', 'info', 'Debug mode ON — ' + (location.pathname.split('/').pop() || 'app'));
        try {
            const saved = JSON.parse(localStorage.getItem('aitoolbox_debug_buffer') || '[]');
            saved.reverse().forEach(e => { if (!buffer.find(b => b.ts === e.ts)) push(e); });
        } catch (_) {}
        clearInterval(pollTimer);
        pollTimer = setInterval(pollServerLogs, 4000);
        pollServerLogs();
    }

    function shutdown() {
        clearInterval(pollTimer);
        panelEl?.remove();
        panelEl = null;
        listEl = null;
    }

    global.AIToolboxDebug = {
        enabled,
        setEnabled,
        log,
        boot,
        shutdown,
        getBuffer: () => [...buffer],
    };

    if (enabled()) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', boot);
        } else {
            boot();
        }
    }
})(typeof window !== 'undefined' ? window : globalThis);