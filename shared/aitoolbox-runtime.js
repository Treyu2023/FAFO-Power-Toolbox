/**
 * AI Toolbox production runtime helpers.
 *
 * Load order: after aitoolbox-config.js + aitoolbox-version.js, before aitoolbox-api.js.
 *
 * Exposes window.AIToolboxRuntime:
 *   debounce, throttle, rafBatch,
 *   setTimeout / setInterval (auto-cleared on pagehide),
 *   storage.set/get (try/catch + quota fallback),
 *   prefersReducedMotion, whenHidden, coalesce
 */
(function (global) {
    'use strict';

    const timeoutIds = new Set();
    const intervalIds = new Set();
    const inFlight = new Map();
    const hiddenCbs = new Set();
    const rafQueue = [];
    let rafQueued = null;
    const memFallback = Object.create(null);

    function debounce(fn, ms) {
        let t = null;
        const wait = Math.max(0, Number(ms) || 0);
        return function debounced() {
            const ctx = this;
            const args = arguments;
            if (t) clearTimeout(t);
            t = setTimeout(function () {
                t = null;
                fn.apply(ctx, args);
            }, wait);
        };
    }

    function throttle(fn, ms) {
        let last = 0;
        let t = null;
        let savedCtx;
        let savedArgs;
        const wait = Math.max(0, Number(ms) || 0);
        return function throttled() {
            const now = Date.now();
            const remaining = wait - (now - last);
            savedCtx = this;
            savedArgs = arguments;
            if (remaining <= 0) {
                if (t) { clearTimeout(t); t = null; }
                last = now;
                return fn.apply(savedCtx, savedArgs);
            }
            if (!t) {
                t = setTimeout(function () {
                    t = null;
                    last = Date.now();
                    fn.apply(savedCtx, savedArgs);
                }, remaining);
            }
        };
    }

    function rafBatch(fn) {
        if (typeof fn === 'function') rafQueue.push(fn);
        if (rafQueued != null) return;
        if (typeof requestAnimationFrame !== 'function') {
            const batch = rafQueue.splice(0, rafQueue.length);
            for (let i = 0; i < batch.length; i++) {
                try { batch[i](); } catch (_) { /* ignore */ }
            }
            return;
        }
        rafQueued = requestAnimationFrame(function () {
            rafQueued = null;
            const batch = rafQueue.splice(0, rafQueue.length);
            for (let i = 0; i < batch.length; i++) {
                try { batch[i](); } catch (_) { /* ignore */ }
            }
        });
    }

    function trackedTimeout(fn, ms) {
        const id = setTimeout(function () {
            timeoutIds.delete(id);
            try { fn(); } catch (_) { /* ignore */ }
        }, ms);
        timeoutIds.add(id);
        return id;
    }

    function trackedInterval(fn, ms) {
        const id = setInterval(fn, ms);
        intervalIds.add(id);
        return id;
    }

    function trackedClearTimeout(id) {
        timeoutIds.delete(id);
        return clearTimeout(id);
    }

    function trackedClearInterval(id) {
        intervalIds.delete(id);
        return clearInterval(id);
    }

    function clearAllTimers() {
        timeoutIds.forEach(function (id) {
            try { clearTimeout(id); } catch (_) { /* ignore */ }
        });
        intervalIds.forEach(function (id) {
            try { clearInterval(id); } catch (_) { /* ignore */ }
        });
        timeoutIds.clear();
        intervalIds.clear();
        if (rafQueued != null && typeof cancelAnimationFrame === 'function') {
            try { cancelAnimationFrame(rafQueued); } catch (_) { /* ignore */ }
        }
        rafQueued = null;
        rafQueue.length = 0;
    }

    const storage = {
        set: function (key, value) {
            const k = String(key);
            let raw;
            try {
                raw = typeof value === 'string' ? value : JSON.stringify(value);
            } catch (_) {
                raw = String(value);
            }
            try {
                localStorage.setItem(k, raw);
                return true;
            } catch (err) {
                try {
                    if (err && (err.name === 'QuotaExceededError' || err.code === 22 || err.code === 1014)) {
                        localStorage.removeItem(k);
                        try {
                            localStorage.setItem(k, raw);
                            return true;
                        } catch (_) { /* fall through */ }
                    }
                } catch (_) { /* ignore */ }
                memFallback[k] = raw;
                return false;
            }
        },
        get: function (key, fallback) {
            const k = String(key);
            try {
                const v = localStorage.getItem(k);
                if (v != null) return v;
            } catch (_) { /* ignore */ }
            if (Object.prototype.hasOwnProperty.call(memFallback, k)) return memFallback[k];
            return fallback === undefined ? null : fallback;
        },
    };

    function prefersReducedMotion() {
        try {
            return !!(global.matchMedia && global.matchMedia('(prefers-reduced-motion: reduce)').matches);
        } catch (_) {
            return false;
        }
    }

    function whenHidden(pauseFn, resumeFn) {
        const rec = { pause: pauseFn, resume: resumeFn };
        hiddenCbs.add(rec);
        return function unbind() { hiddenCbs.delete(rec); };
    }

    function coalesce(key, fn) {
        const k = String(key);
        if (inFlight.has(k)) return inFlight.get(k);
        let p;
        try {
            p = Promise.resolve(typeof fn === 'function' ? fn() : fn);
        } catch (e) {
            return Promise.reject(e);
        }
        inFlight.set(k, p);
        const clear = function () {
            if (inFlight.get(k) === p) inFlight.delete(k);
        };
        if (typeof p.finally === 'function') p.finally(clear);
        else p.then(clear, clear);
        return p;
    }

    function onPageHide() {
        clearAllTimers();
    }

    function onVisibility() {
        const hidden = typeof document !== 'undefined' && document.hidden;
        hiddenCbs.forEach(function (rec) {
            try {
                if (hidden) {
                    if (typeof rec.pause === 'function') rec.pause();
                } else if (typeof rec.resume === 'function') {
                    rec.resume();
                }
            } catch (_) { /* ignore */ }
        });
    }

    if (typeof window !== 'undefined') {
        window.addEventListener('pagehide', onPageHide);
        if (typeof document !== 'undefined') {
            document.addEventListener('visibilitychange', onVisibility);
        }
    }

    global.AIToolboxRuntime = {
        debounce: debounce,
        throttle: throttle,
        rafBatch: rafBatch,
        setTimeout: trackedTimeout,
        setInterval: trackedInterval,
        clearTimeout: trackedClearTimeout,
        clearInterval: trackedClearInterval,
        storage: storage,
        prefersReducedMotion: prefersReducedMotion,
        whenHidden: whenHidden,
        coalesce: coalesce,
    };
})(typeof window !== 'undefined' ? window : globalThis);
