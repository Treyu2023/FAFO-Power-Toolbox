/**
 * Media-desk production helpers.
 *
 * Load after aitoolbox-runtime.js. Auto-installs:
 *   - pause <video>/<audio> while the tab is hidden, resume what was playing
 *   - IntersectionObserver: pause clips that scroll off-screen
 *   - pagehide: pause media
 *
 * window.AIToolboxMedia:
 *   watchServer(fn, opts)  visibility-aware poll (iframe/offline backoff)
 *   bindSearch(fn, ms)     debounce wrapper
 *   safeJson(raw, fallback)
 *   rafify(fn)             coalesce to one rAF
 *   observeVideos(root)
 */
(function (global) {
    'use strict';

    const RT = function () { return global.AIToolboxRuntime || null; };

    function isIframe() {
        try { return global.self !== global.top; } catch (_) { return true; }
    }

    function watchServer(fn, opts) {
        opts = opts || {};
        const rt = RT();
        let timer = null;
        let inflight = false;
        let stopped = false;
        let unbind = null;

        function delay() {
            if (typeof document !== 'undefined' && document.hidden) return 0;
            if (isIframe()) return opts.iframeMs || 30000;
            return opts.onlineMs || 12000;
        }

        function clearTimer() {
            if (timer == null) return;
            if (rt && rt.clearTimeout) rt.clearTimeout(timer);
            else clearTimeout(timer);
            timer = null;
        }

        function schedule() {
            if (stopped) return;
            clearTimer();
            const ms = delay();
            if (!ms) return;
            const fire = function () { timer = null; tick(); };
            timer = rt && rt.setTimeout ? rt.setTimeout(fire, ms) : setTimeout(fire, ms);
        }

        async function tick() {
            if (stopped || inflight) return;
            if (typeof document !== 'undefined' && document.hidden) return;
            inflight = true;
            try { await fn(); } catch (_) { /* badge/poll failures are non-fatal */ }
            inflight = false;
            schedule();
        }

        if (rt && typeof rt.whenHidden === 'function') {
            unbind = rt.whenHidden(clearTimer, function () { if (!stopped) tick(); });
        } else if (typeof document !== 'undefined') {
            document.addEventListener('visibilitychange', function () {
                if (document.hidden) clearTimer();
                else if (!stopped) tick();
            });
        }

        tick();
        return function stop() {
            stopped = true;
            clearTimer();
            if (typeof unbind === 'function') try { unbind(); } catch (_) {}
        };
    }

    function bindSearch(fn, ms) {
        const rt = RT();
        if (rt && typeof rt.debounce === 'function') return rt.debounce(fn, ms || 280);
        let t = 0;
        return function () {
            const ctx = this, args = arguments;
            clearTimeout(t);
            t = setTimeout(function () { fn.apply(ctx, args); }, ms || 280);
        };
    }

    function safeJson(raw, fallback) {
        if (raw == null || raw === '') return fallback;
        try {
            const v = typeof raw === 'string' ? JSON.parse(raw) : raw;
            return v == null ? fallback : v;
        } catch (_) {
            return fallback;
        }
    }

    function rafify(fn) {
        const rt = RT();
        if (rt && typeof rt.rafBatch === 'function') {
            return function () {
                const ctx = this, args = arguments;
                rt.rafBatch(function () { fn.apply(ctx, args); });
            };
        }
        let q = null;
        return function () {
            const ctx = this, args = arguments;
            if (q != null) return;
            q = requestAnimationFrame(function () {
                q = null;
                fn.apply(ctx, args);
            });
        };
    }

    function observeVideos(root) {
        if (typeof IntersectionObserver !== 'function') return null;
        const io = new IntersectionObserver(function (entries) {
            entries.forEach(function (en) {
                const v = en.target;
                if (!v || v.nodeName !== 'VIDEO') return;
                if (v.hasAttribute('data-keep-playing')) return;
                const on = en.isIntersecting && en.intersectionRatio >= 0.18;
                if (on) {
                    if (v.dataset.fafoWantPlay === '1') {
                        v.play().catch(function () {});
                    }
                } else if (!v.paused && !v.ended) {
                    v.dataset.fafoWantPlay = '1';
                    try { v.pause(); } catch (_) {}
                }
            });
        }, { threshold: [0, 0.18, 0.5] });

        function scan() {
            const scope = root || document;
            if (!scope || !scope.querySelectorAll) return;
            scope.querySelectorAll('video').forEach(function (v) {
                try { io.observe(v); } catch (_) {}
            });
        }
        scan();
        if (typeof MutationObserver === 'function' && (root || document.body)) {
            const mo = new MutationObserver(scan);
            try { mo.observe(root || document.body, { childList: true, subtree: true }); } catch (_) {}
        }
        return io;
    }

    function installAuto() {
        const playing = [];
        function pauseAll() {
            playing.length = 0;
            if (typeof document === 'undefined') return;
            document.querySelectorAll('video, audio').forEach(function (el) {
                if (!el.paused && !el.ended) {
                    playing.push(el);
                    try { el.pause(); } catch (_) {}
                }
            });
        }
        function resumeAll() {
            playing.forEach(function (el) {
                try { el.play(); } catch (_) {}
            });
            playing.length = 0;
        }
        const rt = RT();
        if (rt && typeof rt.whenHidden === 'function') rt.whenHidden(pauseAll, resumeAll);
        else if (typeof document !== 'undefined') {
            document.addEventListener('visibilitychange', function () {
                if (document.hidden) pauseAll();
                else resumeAll();
            });
        }
        if (typeof window !== 'undefined') {
            window.addEventListener('pagehide', pauseAll);
        }
        if (typeof document !== 'undefined') {
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', function () { observeVideos(document.body); });
            } else {
                observeVideos(document.body);
            }
        }
    }

    try { installAuto(); } catch (_) { /* never break a desk */ }

    global.AIToolboxMedia = {
        watchServer: watchServer,
        bindSearch: bindSearch,
        safeJson: safeJson,
        rafify: rafify,
        observeVideos: observeVideos,
        isIframe: isIframe,
        // aliases once aitoolbox-dom.js is present
        get el() { return (global.AIToolboxDom && AIToolboxDom.el) || null; },
        get bind() { return (global.AIToolboxDom && AIToolboxDom.bind) || null; },
        get escapeHtml() { return (global.AIToolboxDom && AIToolboxDom.escapeHtml) || null; },
        get withBusy() { return (global.AIToolboxDom && AIToolboxDom.withBusy) || null; },
        get recentFolders() { return (global.AIToolboxDom && AIToolboxDom.recentFolders) || (function () { return []; }); },
        get pushRecentFolder() { return (global.AIToolboxDom && AIToolboxDom.pushRecentFolder) || (function () { return []; }); },
    };
})(typeof window !== 'undefined' ? window : globalThis);
