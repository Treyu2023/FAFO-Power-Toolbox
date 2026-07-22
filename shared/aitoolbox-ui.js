/**
 * AI Toolbox UI — tooltips, confirm+trust, tutorial walkthrough, toasts.
 */
(function (global) {
    'use strict';

    const TRUST_PREFIX = 'aitoolbox_trust_';

    /** Rename trust scopes — video and image are independent for single vs batch. */
    const RENAME_TRUST_KEYS = {
        singleVideo: 'rename_single_video',
        singleImage: 'rename_single_image',
        batchVideo: 'rename_batch_video',
        batchImage: 'rename_batch_image',
        vsrStage1: 'vsr_stage1',
        vsrStage2: 'vsr_stage2',
    };

    function isTrusted(key) {
        return localStorage.getItem(TRUST_PREFIX + key) === '1';
    }

    function setTrusted(key, val = true) {
        if (val) localStorage.setItem(TRUST_PREFIX + key, '1');
        else localStorage.removeItem(TRUST_PREFIX + key);
    }

    function resetAllRenameTrust() {
        Object.values(RENAME_TRUST_KEYS).forEach(k => setTrusted(k, false));
    }

    function migrateLegacyTrustKeys() {
        const legacy = [
            ['media_single_rename', [RENAME_TRUST_KEYS.singleVideo, RENAME_TRUST_KEYS.singleImage]],
            ['media_batch_rename', [RENAME_TRUST_KEYS.batchVideo, RENAME_TRUST_KEYS.batchImage]],
        ];
        legacy.forEach(([oldKey, newKeys]) => {
            if (!isTrusted(oldKey)) return;
            newKeys.forEach(k => { if (!isTrusted(k)) setTrusted(k); });
            setTrusted(oldKey, false);
        });
    }

    function isTutorialDone(key) {
        return localStorage.getItem('aitoolbox_tutorial_' + key) === '1';
    }

    function setTutorialDone(key) {
        localStorage.setItem('aitoolbox_tutorial_' + key, '1');
    }

    let tooltipEl = null;
    let tooltipTimer = null;

    function initTooltips(root = document) {
        if (!tooltipEl) {
            tooltipEl = document.createElement('div');
            tooltipEl.className = 'ui-tooltip';
            document.body.appendChild(tooltipEl);
        }

        root.querySelectorAll('[data-tip]').forEach(el => {
            if (el._tipBound) return;
            el._tipBound = true;
            const title = el.dataset.tipTitle || '';
            const text = el.dataset.tip || el.getAttribute('data-tip');

            el.addEventListener('mouseenter', e => {
                clearTimeout(tooltipTimer);
                tooltipTimer = setTimeout(() => {
                    tooltipEl.innerHTML = (title ? `<strong>${title}</strong>` : '') + text;
                    tooltipEl.classList.add('visible');
                    positionTooltip(e.target);
                }, 280);
            });
            el.addEventListener('mousemove', () => positionTooltip(el));
            el.addEventListener('mouseleave', () => {
                clearTimeout(tooltipTimer);
                tooltipEl.classList.remove('visible');
            });
        });
    }

    function positionTooltip(target) {
        const r = target.getBoundingClientRect();
        const tw = tooltipEl.offsetWidth;
        const th = tooltipEl.offsetHeight;
        let left = r.left + r.width / 2 - tw / 2;
        let top = r.bottom + 10;
        if (top + th > window.innerHeight - 8) top = r.top - th - 10;
        left = Math.max(8, Math.min(left, window.innerWidth - tw - 8));
        tooltipEl.style.left = left + 'px';
        tooltipEl.style.top = top + 'px';
    }

    function toast(msg, type = '') {
        let t = document.getElementById('ui-toast-global');
        if (!t) {
            t = document.createElement('div');
            t.id = 'ui-toast-global';
            t.className = 'ui-toast';
            document.body.appendChild(t);
        }
        t.className = 'ui-toast' + (type ? ' ' + type : '');
        t.textContent = msg;
        requestAnimationFrame(() => t.classList.add('show'));
        clearTimeout(t._hide);
        t._hide = setTimeout(() => t.classList.remove('show'), 2800);
    }

    function confirmAction(opts) {
        const {
            title = 'Confirm',
            body = '',
            preview = [],
            trustKey = null,
            trustLabel = "Don't ask again — I trust this action",
            trustDefaultChecked = false,
            showSafetyNote = false,
            confirmText = 'Confirm',
            cancelText = 'Cancel',
        } = opts;

        if (trustKey && isTrusted(trustKey)) {
            return Promise.resolve({ confirmed: true, trusted: true, skipped: true });
        }

        const safetyHtml = showSafetyNote
            ? '<p class="trust-safety">⚠ Files are renamed on disk. Wrong names cannot be auto-undone — review the preview carefully before confirming.</p>'
            : '';

        return new Promise(resolve => {
            const bg = document.createElement('div');
            bg.className = 'ui-modal-bg';
            const previewHtml = preview.length
                ? `<div class="preview-list">${preview.slice(0, 8).map(p =>
                    `<div><span style="color:#888">${p.from}</span> → <span style="color:var(--ui-accent)">${p.to}</span></div>`
                ).join('')}${preview.length > 8 ? `<div style="color:#666">…and ${preview.length - 8} more</div>` : ''}</div>`
                : '';

            const trustChecked = trustDefaultChecked ? ' checked' : '';
            bg.innerHTML = `
                <div class="ui-modal">
                    <h3>${title}</h3>
                    <div class="ui-modal-body">${body}${safetyHtml}</div>
                    ${previewHtml}
                    ${trustKey ? `<label class="trust-row"><input type="checkbox" id="ui-trust-cb"${trustChecked}> ${trustLabel}</label>` : ''}
                    <div class="ui-modal-actions">
                        <button class="ui-btn ghost" id="ui-cancel">${cancelText}</button>
                        <button class="ui-btn primary" id="ui-confirm">${confirmText}</button>
                    </div>
                </div>`;
            document.body.appendChild(bg);
            requestAnimationFrame(() => bg.classList.add('open'));

            const close = (result) => {
                bg.classList.remove('open');
                setTimeout(() => bg.remove(), 250);
                resolve(result);
            };

            bg.querySelector('#ui-cancel').onclick = () => close({ confirmed: false });
            bg.querySelector('#ui-confirm').onclick = () => {
                const cb = bg.querySelector('#ui-trust-cb');
                if (trustKey && cb?.checked) setTrusted(trustKey);
                close({ confirmed: true, trusted: !!(trustKey && cb?.checked) });
            };
            bg.addEventListener('click', e => { if (e.target === bg) close({ confirmed: false }); });
        });
    }

    let tutorialState = null;

    function startTutorial(steps, storageKey, onStep, opts) {
        const force = opts === true || (opts && opts.force);
        if (!force && storageKey && isTutorialDone(storageKey)) return;
        tutorialState = { steps, index: 0, storageKey, onStep };
        showTutorialStep();
    }

    function showTutorialStep() {
        if (!tutorialState) return;
        const { steps, index, onStep } = tutorialState;
        if (index >= steps.length) {
            endTutorial();
            return;
        }

        document.querySelectorAll('.ui-tutorial-bg').forEach(e => e.remove());

        const step = steps[index];
        if (onStep) onStep(step, index);

        const bg = document.createElement('div');
        bg.className = 'ui-tutorial-bg';
        bg.innerHTML = `<div class="ui-tutorial-dim"></div><div class="ui-tutorial-spotlight" id="ui-spot"></div><div class="ui-tutorial-card" id="ui-tut-card"></div>`;
        document.body.appendChild(bg);

        const card = bg.querySelector('#ui-tut-card');
        const spot = bg.querySelector('#ui-spot');
        const dots = steps.map((_, i) =>
            `<span class="ui-tutorial-dot ${i < index ? 'done' : ''} ${i === index ? 'active' : ''}"></span>`
        ).join('');

        card.innerHTML = `
            <div class="ui-tutorial-progress">${dots}</div>
            <h4>${step.title}</h4>
            <p>${step.body}</p>
            <div class="ui-tutorial-actions">
                <button class="ui-btn ghost" id="tut-skip">Skip tour</button>
                <div style="display:flex;gap:8px">
                    ${index > 0 ? '<button class="ui-btn ghost" id="tut-back">Back</button>' : ''}
                    <button class="ui-btn" id="tut-next">${index === steps.length - 1 ? 'Finish ✓' : 'Next →'}</button>
                </div>
            </div>`;

        const positionSpotlight = () => {
            const target = step.target ? document.querySelector(step.target) : null;
            if (target) {
                target.scrollIntoView({ behavior: 'smooth', block: 'center' });
                setTimeout(() => {
                    const r = target.getBoundingClientRect();
                    const pad = 8;
                    spot.style.left = (r.left - pad) + 'px';
                    spot.style.top = (r.top - pad) + 'px';
                    spot.style.width = (r.width + pad * 2) + 'px';
                    spot.style.height = (r.height + pad * 2) + 'px';
                    spot.style.display = 'block';
                    let cardTop = r.bottom + 16;
                    if (cardTop + 200 > window.innerHeight) cardTop = r.top - 200;
                    card.style.left = Math.min(Math.max(16, r.left), window.innerWidth - 380) + 'px';
                    card.style.top = Math.max(16, cardTop) + 'px';
                }, 350);
            } else {
                spot.style.display = 'none';
                card.style.left = '50%';
                card.style.top = '50%';
                card.style.transform = 'translate(-50%, -50%)';
            }
        };

        positionSpotlight();
        window.addEventListener('resize', positionSpotlight);

        bg.querySelector('#tut-skip').onclick = endTutorial;
        bg.querySelector('#tut-next').onclick = () => {
            tutorialState.index++;
            showTutorialStep();
        };
        const backBtn = bg.querySelector('#tut-back');
        if (backBtn) backBtn.onclick = () => { tutorialState.index--; showTutorialStep(); };
    }

    function endTutorial() {
        if (tutorialState?.storageKey) setTutorialDone(tutorialState.storageKey);
        document.querySelectorAll('.ui-tutorial-bg').forEach(e => e.remove());
        tutorialState = null;
        toast('Tutorial complete — explore freely!', 'ok');
    }

    function resetTutorial(storageKey) {
        localStorage.removeItem('aitoolbox_tutorial_' + storageKey);
    }

    function scoreClass(pct) {
        if (pct >= 75) return 'high';
        if (pct >= 55) return 'mid';
        return 'low';
    }

    /**
     * Render workflow stepper. states: pending | active | done | error
     * steps: [{ id, label }]
     * getStates(): { [id]: 'active', ... }
     */
    function renderWorkflow(container, steps, states) {
        if (typeof container === 'string') container = document.querySelector(container);
        if (!container) return;
        container.className = 'ui-workflow';
        container.innerHTML = steps.map((s, i) => {
            const st = states[s.id] || 'pending';
            const conn = i < steps.length - 1
                ? `<span class="ui-workflow-conn ${states[steps[i + 1].id] !== 'pending' || st === 'done' ? 'lit' : ''}"></span>`
                : '';
            return `<div class="ui-workflow-step ${st}" data-step="${s.id}">
                <span class="ui-workflow-num">${i + 1}</span>
                <span class="ui-workflow-label">${s.label}</span>
            </div>${conn}`;
        }).join('');
    }

    /**
     * Shared server pill + Start Server controls for any tool page.
     * opts: {
     *   statusEl, startBtn, hintEl?,
     *   onlineText?, offlineText?, startingText?,
     *   pollMs?, onOnline?, onOffline?
     * }
     */
    function bindServerControls(opts = {}) {
        const API = () => global.AIToolboxAPI;
        const statusEl = typeof opts.statusEl === 'string'
            ? document.querySelector(opts.statusEl) : opts.statusEl;
        const startBtn = typeof opts.startBtn === 'string'
            ? document.querySelector(opts.startBtn) : opts.startBtn;
        const hintEl = typeof opts.hintEl === 'string'
            ? document.querySelector(opts.hintEl) : opts.hintEl;
        const endpoint = () => {
            if (API()?.getEndpointLabel) return API().getEndpointLabel();
            return global.AITOOLBOX_CONFIG?.ENDPOINT_LABEL || '127.0.0.87:18765';
        };
        let starting = false;
        let pollTimer = null;

        async function refresh(force = false) {
            if (starting) return false;
            if (!API()?.isOnline) {
                if (statusEl) {
                    statusEl.textContent = opts.offlineText || ('○ Offline — ' + endpoint());
                    statusEl.className = (statusEl.className || '').replace(/\b(ok|online|warn|wait|offline|bad)\b/g, '').trim() + ' warn offline';
                }
                if (startBtn) startBtn.style.display = '';
                return false;
            }
            const on = await API().isOnline(!!force, starting ? 3000 : 2000);
            if (statusEl) {
                if (on) {
                    statusEl.textContent = opts.onlineText || ('● Online @ ' + endpoint());
                    statusEl.className = (statusEl.className || '').replace(/\b(ok|online|warn|wait|offline|bad)\b/g, '').trim() + ' ok online';
                    statusEl.title = 'Toolbox backend ' + endpoint();
                } else {
                    statusEl.textContent = opts.offlineText || ('○ Offline — click or ▶ Start');
                    statusEl.className = (statusEl.className || '').replace(/\b(ok|online|warn|wait|offline|bad)\b/g, '').trim() + ' warn offline';
                    statusEl.title = 'Start server on ' + endpoint();
                }
            }
            if (startBtn) {
                startBtn.style.display = on ? 'none' : '';
                startBtn.disabled = false;
                if (!on) startBtn.textContent = startBtn.dataset.label || '▶ Start Server';
            }
            if (hintEl && !starting) {
                hintEl.textContent = on
                    ? ('Connected · ' + endpoint())
                    : ('Backend: ' + endpoint() + ' (unique — not FAFO :8765)');
                hintEl.className = (hintEl.className || '').replace(/\b(ok|warn)\b/g, '').trim() + (on ? ' ok' : '');
            }
            if (on) opts.onOnline?.(await API().health().catch(() => ({})));
            else opts.onOffline?.();
            return on;
        }

        async function start(mode) {
            if (starting || API()?.isServerLaunching?.()) return;
            if (await API()?.isOnline(true, 2000)) {
                toast('Server already online', 'ok');
                await refresh(true);
                return;
            }
            starting = true;
            if (statusEl) {
                statusEl.textContent = opts.startingText || '◌ Starting…';
                statusEl.className = (statusEl.className || '').replace(/\b(ok|online|warn|wait|offline|bad)\b/g, '').trim() + ' wait warn';
            }
            if (startBtn) {
                startBtn.disabled = true;
                startBtn.textContent = 'Starting…';
            }
            if (hintEl) {
                hintEl.textContent = 'Launching backend on ' + endpoint() + '…';
                hintEl.className = (hintEl.className || '').replace(/\b(ok|warn)\b/g, '').trim() + ' warn';
            }
            try {
                const result = await API().startServer({
                    mode: mode === 'console' ? 'console' : 'tray',
                    waitMs: opts.waitMs || 90000,
                    onStatus: (msg) => {
                        if (statusEl) statusEl.textContent = '◌ ' + msg;
                        if (hintEl) hintEl.textContent = msg;
                    },
                });
                starting = false;
                if (result.ok) {
                    toast('Server online — ' + endpoint(), 'ok');
                    await refresh(true);
                } else {
                    if (statusEl) {
                        statusEl.textContent = '○ Start failed';
                        statusEl.className = (statusEl.className || '').replace(/\b(ok|online|warn|wait|offline|bad)\b/g, '').trim() + ' warn offline';
                    }
                    if (startBtn) {
                        startBtn.disabled = false;
                        startBtn.textContent = startBtn.dataset.label || '▶ Start Server';
                    }
                    if (hintEl) {
                        hintEl.textContent = 'Browser may have blocked launch — use Console / START SERVER.bat';
                        hintEl.className = (hintEl.className || '').replace(/\b(ok|warn)\b/g, '').trim() + ' warn';
                    }
                    toast('Start blocked — try Console or START SERVER.bat', 'warn');
                }
            } catch (e) {
                starting = false;
                if (startBtn) {
                    startBtn.disabled = false;
                    startBtn.textContent = startBtn.dataset.label || '▶ Start Server';
                }
                toast('Start failed: ' + (e.message || e), 'warn');
                await refresh(true);
            }
        }

        if (startBtn && !startBtn._serverBound) {
            startBtn._serverBound = true;
            startBtn.dataset.label = startBtn.textContent || '▶ Start Server';
            startBtn.addEventListener('click', () => start('tray'));
        }
        if (statusEl && !statusEl._serverBound) {
            statusEl._serverBound = true;
            statusEl.style.cursor = 'pointer';
            statusEl.addEventListener('click', () => start('tray'));
            statusEl.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); start('tray'); }
            });
            if (!statusEl.hasAttribute('tabindex')) statusEl.setAttribute('tabindex', '0');
            if (!statusEl.getAttribute('role')) statusEl.setAttribute('role', 'button');
        }

        const pollMs = opts.pollMs != null ? opts.pollMs : 8000;
        if (pollMs > 0) {
            pollTimer = setInterval(() => {
                // Skip background-tab polling (many tool pages mount this bar)
                if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return;
                refresh(false);
            }, pollMs);
        }
        refresh(true);

        return { refresh, start, stop: () => { if (pollTimer) clearInterval(pollTimer); } };
    }

    /**
     * Escape text for safe HTML insertion (text nodes only — not attributes with quotes).
     */
    function escapeHtml(s) {
        if (s == null) return '';
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    /**
     * Format byte counts for UI (B / KB / MB / GB / TB).
     */
    function formatBytes(n, digits = 1) {
        const num = Number(n) || 0;
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        let v = Math.abs(num);
        let i = 0;
        while (v >= 1024 && i < units.length - 1) {
            v /= 1024;
            i++;
        }
        const shown = i === 0 ? String(Math.round(v)) : v.toFixed(digits);
        return (num < 0 ? '-' : '') + shown + ' ' + units[i];
    }

    /**
     * Inject a shared server status bar under nav/header (or at top of body).
     * Replaces the duplicated IIFE copied into many thin system tools.
     * @param {{ insertAfter?: string|Element, pollMs?: number, onOnline?: Function, onOffline?: Function }} opts
     */
    function mountServerBar(opts = {}) {
        if (document.getElementById('tbSharedServerBar')) {
            return bindServerControls({
                statusEl: '#tbServerPill',
                startBtn: '#tbBtnStartServer',
                hintEl: '#tbServerHint',
                pollMs: opts.pollMs,
                onOnline: opts.onOnline,
                onOffline: opts.onOffline,
            });
        }

        const endpoint = () => {
            if (global.AIToolboxAPI?.getEndpointLabel) return global.AIToolboxAPI.getEndpointLabel();
            return global.AITOOLBOX_CONFIG?.ENDPOINT_LABEL || '127.0.0.87:18765';
        };

        const bar = document.createElement('div');
        bar.id = 'tbSharedServerBar';
        bar.setAttribute('role', 'status');
        bar.style.cssText = 'display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:8px 16px;'
            + 'border-bottom:1px solid rgba(0,243,255,.15);background:rgba(0,0,0,.35);font-size:12px;';
        bar.innerHTML =
            '<span id="tbServerPill" style="padding:3px 10px;border-radius:999px;border:1px solid rgba(255,255,255,.15);cursor:pointer" '
            + 'data-tip-title="Backend" data-tip="Green = toolbox server online. Click to start if offline.">Server …</span>'
            + '<button type="button" id="tbBtnStartServer" style="padding:5px 12px;border-radius:8px;border:1px solid #00f3ff;'
            + 'background:rgba(0,243,255,.12);color:#00f3ff;cursor:pointer;font-weight:600" '
            + 'data-tip-title="Start Server" data-tip="Uses aitoolbox:// protocol (no .hta Save prompts). Run Setup Once if nothing happens.">▶ Start Server</button>'
            + '<button type="button" id="tbBtnServerConsole" style="padding:5px 10px;border-radius:8px;border:1px solid rgba(255,255,255,.2);'
            + 'background:transparent;color:#aaa;cursor:pointer;font-size:11px" '
            + 'data-tip="Start via aitoolbox://console (visible window)">🖥 Console</button>'
            + '<span id="tbServerHint" style="color:#888;font-size:11px"></span>'
            + '<span style="margin-left:auto;opacity:.55;font-size:11px" id="tbVer"></span>';

        let anchor = null;
        if (opts.insertAfter) {
            anchor = typeof opts.insertAfter === 'string'
                ? document.querySelector(opts.insertAfter)
                : opts.insertAfter;
        }
        if (!anchor) {
            anchor = document.querySelector('nav, .nav, .nav-bar, header, .toolbox-nav');
        }
        if (anchor && anchor.parentNode) {
            anchor.parentNode.insertBefore(bar, anchor.nextSibling);
        } else {
            document.body.insertBefore(bar, document.body.firstChild);
        }

        if (global.AITOOLBOX_VERSION) {
            const ver = document.getElementById('tbVer');
            if (ver) ver.textContent = 'v' + global.AITOOLBOX_VERSION;
        }

        const controls = bindServerControls({
            statusEl: '#tbServerPill',
            startBtn: '#tbBtnStartServer',
            hintEl: '#tbServerHint',
            pollMs: opts.pollMs,
            onOnline: opts.onOnline,
            onOffline: opts.onOffline,
        });

        const consoleBtn = document.getElementById('tbBtnServerConsole');
        if (consoleBtn && !consoleBtn._serverBound) {
            consoleBtn._serverBound = true;
            consoleBtn.addEventListener('click', async () => {
                if (!global.AIToolboxAPI?.startServer) return;
                consoleBtn.disabled = true;
                try {
                    await global.AIToolboxAPI.startServer({ mode: 'console', waitMs: 90000 });
                    await controls.refresh(true);
                } finally {
                    consoleBtn.disabled = false;
                }
            });
        }

        try { initTooltips(bar); } catch { /* ignore */ }
        bar.dataset.endpoint = endpoint();
        return controls;
    }

    /**
     * Resolve API base consistently (config → AIToolboxAPI → bind default).
     */
    function getApiBase() {
        if (global.AIToolboxAPI?.getApiBase) return global.AIToolboxAPI.getApiBase();
        if (global.AITOOLBOX_CONFIG?.API_BASE) return global.AITOOLBOX_CONFIG.API_BASE;
        if (global.AITOOLBOX_API_BASE) return global.AITOOLBOX_API_BASE;
        return 'http://127.0.0.87:18765/api';
    }

    /**
     * Fetch JSON from toolbox API with clearer offline errors.
     */
    async function apiFetch(path, opts = {}) {
        const base = getApiBase();
        const url = path.startsWith('http') ? path : base + path;
        let r;
        try {
            r = await fetch(url, {
                headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
                ...opts,
            });
        } catch (e) {
            const err = new Error('Server offline — use ▶ Start Server (backend ' + (
                global.AIToolboxAPI?.getEndpointLabel?.() || '127.0.0.87:18765'
            ) + ')');
            err.cause = e;
            err.offline = true;
            throw err;
        }
        if (!r.ok) {
            const body = await r.json().catch(() => ({}));
            throw new Error(body.detail || r.statusText || ('HTTP ' + r.status));
        }
        const ct = r.headers.get('content-type') || '';
        if (ct.includes('json')) return r.json();
        return r;
    }

    global.AIToolboxUI = {
        initTooltips,
        toast,
        confirmAction,
        isTrusted,
        setTrusted,
        resetAllRenameTrust,
        migrateLegacyTrustKeys,
        RENAME_TRUST_KEYS,
        startTutorial,
        endTutorial,
        resetTutorial,
        isTutorialDone,
        setTutorialDone,
        scoreClass,
        renderWorkflow,
        bindServerControls,
        mountServerBar,
        escapeHtml,
        formatBytes,
        getApiBase,
        apiFetch,
    };
})(typeof window !== 'undefined' ? window : globalThis);