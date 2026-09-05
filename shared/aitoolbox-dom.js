/**
 * Shared DOM kit for media desks.
 * One copy of el / bind / withBusy / escapeHtml instead of 10 inline clones.
 *
 * window.AIToolboxDom
 */
(function (global) {
    'use strict';

    function el(id) {
        if (id == null || id === '') return null;
        if (typeof id !== 'string') return id.nodeType ? id : null;
        try { return document.getElementById(id); } catch (_) { return null; }
    }

    function qs(sel, root) {
        try { return (root || document).querySelector(sel); } catch (_) { return null; }
    }

    function setText(node, text) {
        const n = typeof node === 'string' ? el(node) : node;
        if (!n) return null;
        try { n.textContent = text == null ? '' : String(text); } catch (_) {}
        return n;
    }

    function bind(node, ev, fn) {
        const n = typeof node === 'string' ? el(node) : node;
        if (!n || !ev || typeof fn !== 'function') return null;
        try { n.addEventListener(ev, fn); } catch (_) { return null; }
        return n;
    }

    function lsGet(key, fallback) {
        try {
            const v = localStorage.getItem(key);
            return v == null ? fallback : v;
        } catch (_) { return fallback; }
    }

    function lsSet(key, val) {
        try { localStorage.setItem(key, val); return true; } catch (_) { return false; }
    }

    function lsGetJson(key, fallback) {
        try {
            const raw = localStorage.getItem(key);
            if (raw == null || raw === '') return fallback;
            const v = JSON.parse(raw);
            return v == null ? fallback : v;
        } catch (_) { return fallback; }
    }

    function lsSetJson(key, val) {
        try { localStorage.setItem(key, JSON.stringify(val)); return true; } catch (_) { return false; }
    }

    function escapeHtml(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function cssEscape(s) {
        const v = String(s == null ? '' : s);
        if (global.CSS && typeof CSS.escape === 'function') return CSS.escape(v);
        return v.replace(/[^a-zA-Z0-9_\-]/g, '\\$&');
    }

    function isTypingTarget(t) {
        if (!t) return false;
        const tag = t.tagName || '';
        if (/INPUT|TEXTAREA|SELECT/.test(tag)) return true;
        if (t.isContentEditable) return true;
        return false;
    }

    const busyFlags = Object.create(null);
    async function withBusy(key, fn, btn) {
        if (!key || busyFlags[key]) return;
        busyFlags[key] = true;
        const b = typeof btn === 'string' ? el(btn) : btn;
        if (b) {
            b.disabled = true;
            try { b.setAttribute('aria-busy', 'true'); } catch (_) {}
        }
        try { return await fn(); }
        finally {
            delete busyFlags[key];
            if (b) {
                b.disabled = false;
                try { b.removeAttribute('aria-busy'); } catch (_) {}
            }
        }
    }

    function revokeBlobUrl(url) {
        try {
            if (url && String(url).indexOf('blob:') === 0) URL.revokeObjectURL(url);
        } catch (_) {}
    }

    function launcherHref() {
        try {
            if (global.AIToolboxUI && typeof AIToolboxUI.launcherHref === 'function') {
                return AIToolboxUI.launcherHref();
            }
        } catch (_) {}
        return '../Toolbox Launcher.html';
    }

    function toast(msg, kind) {
        try {
            if (global.AIToolboxUI && typeof AIToolboxUI.toast === 'function') {
                AIToolboxUI.toast(msg, kind || 'ok');
                return;
            }
        } catch (_) {}
        try { console.log('[fafo]', kind || 'ok', msg); } catch (_) {}
    }

    const RECENT_KEY = 'fafo_recent_folders_v1';

    function recentFolders() {
        const arr = lsGetJson(RECENT_KEY, []);
        return Array.isArray(arr) ? arr.filter(Boolean).slice(0, 12) : [];
    }

    function pushRecentFolder(path, label) {
        const p = String(path || '').trim();
        if (!p) return recentFolders();
        const entry = { path: p, label: label || p.split(/[/\\]/).pop() || p, at: Date.now() };
        const next = [entry].concat(recentFolders().filter((x) => String(x.path).toLowerCase() !== p.toLowerCase()));
        lsSetJson(RECENT_KEY, next.slice(0, 12));
        return next.slice(0, 12);
    }

    global.AIToolboxDom = {
        el: el,
        qs: qs,
        setText: setText,
        bind: bind,
        lsGet: lsGet,
        lsSet: lsSet,
        lsGetJson: lsGetJson,
        lsSetJson: lsSetJson,
        escapeHtml: escapeHtml,
        cssEscape: cssEscape,
        isTypingTarget: isTypingTarget,
        withBusy: withBusy,
        revokeBlobUrl: revokeBlobUrl,
        launcherHref: launcherHref,
        toast: toast,
        recentFolders: recentFolders,
        pushRecentFolder: pushRecentFolder,
    };
})(typeof window !== 'undefined' ? window : globalThis);
