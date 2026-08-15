/**
 * AI HTML Toolbox — network bind config (single source for the browser).
 * Keep defaults in sync with shared/aitoolbox-bind.json (Python reads that file).
 *
 * Why 127.0.0.87:18765 instead of 127.0.0.1:8765?
 * - Port 8765 is shared with FAFO's optional companion — only one process can own it.
 * - A dedicated loopback IP (still 127/8, never leaves this PC) + unique port
 *   prevents collisions with other local tools on standard 127.0.0.1 ports.
 * Override at runtime: window.AITOOLBOX_BIND = { host, port } before this script.
 *
 * Also installs a tiny AbortSignal.timeout polyfill for older Chromium/WebView2
 * builds still found on field laptops.
 */
(function (g) {
    'use strict';

    // ── Platform polyfills (cheap, once) ──
    try {
        if (typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout !== 'function') {
            AbortSignal.timeout = function timeout(ms) {
                const c = new AbortController();
                const t = setTimeout(function () {
                    try { c.abort(new DOMException('TimeoutError', 'TimeoutError')); }
                    catch (_) { c.abort(); }
                }, Math.max(0, Number(ms) || 0));
                if (c.signal && typeof c.signal.addEventListener === 'function') {
                    c.signal.addEventListener('abort', function () { clearTimeout(t); }, { once: true });
                }
                return c.signal;
            };
        }
    } catch (_) { /* ignore */ }

    const DEFAULTS = { host: '127.0.0.87', port: 18765 };
    const ov = g.AITOOLBOX_BIND || {};
    const host = String(ov.host || DEFAULTS.host).trim() || DEFAULTS.host;
    let port = Number(ov.port != null ? ov.port : DEFAULTS.port);
    if (!Number.isFinite(port) || port < 1 || port > 65535) port = DEFAULTS.port;
    const origin = 'http://' + host + ':' + port;
    const apiBase = origin + '/api';

    const cfg = {
        HOST: host,
        PORT: port,
        ORIGIN: origin,
        API_BASE: apiBase,
        /** Human label for UI copy */
        ENDPOINT_LABEL: host + ':' + port,
        DEFAULTS: Object.assign({}, DEFAULTS),
        /** True when running under file:// (IndexedDB-only until S1 is up) */
        IS_FILE_PROTOCOL: (function () {
            try { return String(g.location && g.location.protocol || '') === 'file:'; }
            catch (_) { return false; }
        })(),
    };

    g.AITOOLBOX_CONFIG = cfg;
    /** Convenience alias used by older inline scripts */
    g.AITOOLBOX_API_BASE = apiBase;
})(typeof window !== 'undefined' ? window : globalThis);
