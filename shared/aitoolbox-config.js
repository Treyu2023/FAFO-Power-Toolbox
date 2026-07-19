/**
 * AI HTML Toolbox — network bind config (single source for the browser).
 * Keep defaults in sync with shared/aitoolbox-bind.json (Python reads that file).
 *
 * Why 127.0.0.87:18765 instead of 127.0.0.1:8765?
 * - Port 8765 is shared with FAFO's optional companion — only one process can own it.
 * - A dedicated loopback IP (still 127/8, never leaves this PC) + unique port
 *   prevents collisions with other local tools on standard 127.0.0.1 ports.
 * Override at runtime: window.AITOOLBOX_BIND = { host, port } before this script.
 */
(function (g) {
    'use strict';

    const DEFAULTS = { host: '127.0.0.87', port: 18765 };
    const ov = g.AITOOLBOX_BIND || {};
    const host = String(ov.host || DEFAULTS.host).trim() || DEFAULTS.host;
    const port = Number(ov.port || DEFAULTS.port) || DEFAULTS.port;
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
    };

    g.AITOOLBOX_CONFIG = cfg;
    /** Convenience alias used by older inline scripts */
    g.AITOOLBOX_API_BASE = apiBase;
})(typeof window !== 'undefined' ? window : globalThis);
