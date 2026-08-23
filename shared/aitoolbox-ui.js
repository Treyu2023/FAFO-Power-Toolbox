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

        // Include multi-level tip attributes + title fallbacks
        root.querySelectorAll('[data-tip], [data-tip-basic], [data-tip-pro], [data-tip-mid]').forEach(el => {
            if (el._tipBound) return;
            el._tipBound = true;

            el.addEventListener('mouseenter', e => {
                clearTimeout(tooltipTimer);
                // Slightly snappy so users can skim cards before clicking
                tooltipTimer = setTimeout(() => {
                    let title = el.dataset.tipTitle || el.getAttribute('data-tip-title') || '';
                    let text = el.dataset.tip || el.getAttribute('data-tip') || '';
                    // Skill-aware resolution (FAFOGuidance)
                    try {
                        if (global.FAFOGuidance?.resolveTip) {
                            const r = global.FAFOGuidance.resolveTip(el);
                            if (r.title) title = r.title;
                            if (r.text) text = r.text;
                        }
                    } catch (_) { /* ignore */ }
                    if (!title && !text) return;
                    // Escape HTML so tool names/descriptions cannot inject markup
                    const esc = (s) => String(s || '')
                        .replace(/&/g, '&amp;')
                        .replace(/</g, '&lt;')
                        .replace(/>/g, '&gt;')
                        .replace(/"/g, '&quot;');
                    // Allow simple newlines in tip text as <br>
                    const body = esc(text).replace(/\n/g, '<br>');
                    tooltipEl.innerHTML = (title ? `<strong>${esc(title)}</strong>` : '') + body;
                    tooltipEl.classList.add('visible');
                    positionTooltip(e.target);
                }, 160);
            });
            el.addEventListener('mousemove', () => {
                if (tooltipEl && tooltipEl.classList.contains('visible')) positionTooltip(el);
            });
            el.addEventListener('mouseleave', () => {
                clearTimeout(tooltipTimer);
                tooltipEl.classList.remove('visible');
            });
            // Keyboard focus also shows tip (accessibility)
            el.addEventListener('focus', () => {
                el.dispatchEvent(new Event('mouseenter'));
            });
            el.addEventListener('blur', () => {
                clearTimeout(tooltipTimer);
                tooltipEl.classList.remove('visible');
            });
        });
    }

    function positionTooltip(target) {
        if (!tooltipEl || !target) return;
        const r = target.getBoundingClientRect();
        const tw = tooltipEl.offsetWidth || 320;
        const th = tooltipEl.offsetHeight || 80;
        let left = r.left + r.width / 2 - tw / 2;
        let top = r.bottom + 10;
        if (top + th > window.innerHeight - 8) top = r.top - th - 10;
        if (top < 8) top = 8;
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
                        <button type="button" class="ui-btn ghost" id="ui-cancel">${cancelText}</button>
                        <button type="button" class="ui-btn primary" id="ui-confirm">${confirmText}</button>
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
        let lastUiOnline = null;

        async function refresh(force = false) {
            // While starting, keep waiting UI — never paint offline mid-launch
            if (starting) {
                if (statusEl) {
                    statusEl.textContent = opts.waitText || ('Starting S1 @ ' + endpoint() + '…');
                    statusEl.className = (statusEl.className || '').replace(/\b(ok|online|warn|wait|offline|bad)\b/g, '').trim() + ' warn wait';
                }
                return false;
            }
            if (!API()?.isOnline) {
                if (statusEl) {
                    statusEl.textContent = opts.offlineText || ('○ Offline — load shared/aitoolbox-api.js');
                    statusEl.className = (statusEl.className || '').replace(/\b(ok|online|warn|wait|offline|bad)\b/g, '').trim() + ' warn offline';
                }
                if (startBtn) startBtn.style.display = '';
                return false;
            }
            let on = await API().isOnline(!!force, 2800);
            // Soft recheck before painting red (stops home=up / tool-page=offline flicker)
            if (!force && lastUiOnline === true && on === false) {
                on = await API().isOnline(true, 3500);
            }
            lastUiOnline = on;
            if (statusEl) {
                if (on) {
                    statusEl.textContent = opts.onlineText || ('● Online @ ' + endpoint());
                    statusEl.className = (statusEl.className || '').replace(/\b(ok|online|warn|wait|offline|bad)\b/g, '').trim() + ' ok online';
                    statusEl.title = 'Toolbox backend S1 ' + endpoint() + ' (not FAFO :8765)';
                } else {
                    statusEl.textContent = opts.offlineText || ('○ Offline — ▶ Start S1 @ ' + endpoint());
                    statusEl.className = (statusEl.className || '').replace(/\b(ok|online|warn|wait|offline|bad)\b/g, '').trim() + ' warn offline';
                    statusEl.title = 'Start HTML Toolbox Server on ' + endpoint();
                }
            }
            if (startBtn) {
                startBtn.style.display = on ? 'none' : '';
                startBtn.disabled = false;
                if (!on) startBtn.textContent = startBtn.dataset.label || '▶ Start Server';
            }
            if (hintEl && !starting) {
                hintEl.textContent = on
                    ? ('Connected · S1 ' + endpoint())
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
                        hintEl.textContent = 'Browser blocked launch — use Desktop “Start Servers” or tray icon';
                        hintEl.className = (hintEl.className || '').replace(/\b(ok|warn)\b/g, '').trim() + ' warn';
                    }
                    toast('Start blocked — Desktop “Start Servers” or tray', 'warn');
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
     * Inject a consistent multi-server status bar (S1 HTML Toolbox + S2 FAFO Tagger)
     * with ← Toolbox escape hatch. OLED black + teal/neon accents.
     * @param {{ insertAfter?: string|Element, pollMs?: number, onOnline?: Function, onOffline?: Function, skipOnLauncher?: boolean }} opts
     */
    function mountServerBar(opts = {}) {
        // Don't put a second bar on the launcher (it has its own full panel)
        const isLauncher = /Toolbox Launcher\.html/i.test(location.pathname || location.href || '');
        if (opts.skipOnLauncher !== false && isLauncher) {
            return null;
        }

        if (document.getElementById('tbSharedServerBar')) {
            return _wireCompanionBar(opts);
        }

        const bar = document.createElement('div');
        bar.id = 'tbSharedServerBar';
        bar.className = 'tb-companion-bar';
        bar.setAttribute('role', 'navigation');
        bar.setAttribute('aria-label', 'Toolbox servers and navigation');
        bar.innerHTML = `
            <a class="tb-bar-back toolbox-back" id="tbBtnToolbox" href="#"
               data-tip-title="Toolbox" data-tip="Return to Toolbox Launcher without closing servers.">← Toolbox</a>
            <div class="tb-bar-servers">
                <span class="tb-pill off" id="tbPillS1" tabindex="0" role="button"
                      data-tip-title="S1 HTML Toolbox" data-tip="127.0.0.87:18765 — media, Verifone, system tools. Click to start if offline.">
                    <i class="tb-dot"></i> S1 Toolbox <em>…</em>
                </span>
                <span class="tb-pill off" id="tbPillS2" tabindex="0" role="button"
                      data-tip-title="S2 FAFO Tagger" data-tip="127.0.0.1:8765 — FAFO Local Media tags/ratings. Click to start if offline.">
                    <i class="tb-dot"></i> S2 Tagger <em>…</em>
                </span>
            </div>
            <div class="tb-bar-actions">
                <button type="button" class="tb-btn primary" id="tbBtnStartServer"
                        data-tip-title="Start All" data-tip="Start S1 + S2 in the background (tray).">▶ Start</button>
                <button type="button" class="tb-btn" id="tbBtnRelaunchServers"
                        data-tip-title="Relaunch" data-tip="Force restart S1 + S2.">↺</button>
                <button type="button" class="tb-btn ghost" id="tbBtnServerConsole"
                        data-tip="S1 console window (debug)">🖥</button>
            </div>
            <span class="tb-bar-hint" id="tbServerHint"></span>
            <span class="tb-bar-ver" id="tbVer"></span>
        `;

        // Inject OLED/teal styles once
        if (!document.getElementById('tbCompanionBarCss')) {
            const style = document.createElement('style');
            style.id = 'tbCompanionBarCss';
            style.textContent = `
                .tb-companion-bar{
                    display:flex;flex-wrap:wrap;gap:10px;align-items:center;
                    padding:8px 14px;font:600 12px/1.3 system-ui,Segoe UI,sans-serif;
                    background:linear-gradient(180deg,#050508 0%,#0a0a10 100%);
                    border-bottom:1px solid rgba(0,243,255,.22);
                    box-shadow:0 0 24px rgba(0,243,255,.06), inset 0 1px 0 rgba(0,243,255,.08);
                    color:#c8d0d8;position:sticky;top:0;z-index:9990;
                }
                .tb-bar-back{
                    color:#00e5ff;text-decoration:none;padding:5px 10px;border-radius:8px;
                    border:1px solid rgba(0,229,255,.28);background:rgba(0,229,255,.08);
                    white-space:nowrap;transition:box-shadow .2s,border-color .2s;
                }
                .tb-bar-back:hover{border-color:#00f3ff;box-shadow:0 0 12px rgba(0,243,255,.35);color:#fff}
                .tb-bar-servers{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
                .tb-pill{
                    display:inline-flex;align-items:center;gap:6px;padding:4px 10px;
                    border-radius:999px;border:1px solid rgba(255,255,255,.12);
                    background:rgba(0,0,0,.45);cursor:pointer;user-select:none;
                    color:#9aa3ad;transition:border-color .2s,box-shadow .2s,color .2s;
                }
                .tb-pill em{font-style:normal;opacity:.75;font-weight:500;font-size:11px}
                .tb-pill .tb-dot{
                    width:8px;height:8px;border-radius:50%;background:#ff4466;
                    box-shadow:0 0 6px #ff4466;flex-shrink:0;
                }
                .tb-pill.on{border-color:rgba(0,255,136,.45);color:#d8ffe8}
                .tb-pill.on .tb-dot{background:#00ff88;box-shadow:0 0 8px #00ff88}
                .tb-pill.wait{border-color:rgba(45,212,191,.5);color:#99f6e4}
                .tb-pill.wait .tb-dot{background:#2dd4bf;box-shadow:0 0 8px #2dd4bf;animation:ui-pulse-glow 1.2s ease infinite}
                .tb-pill.warn{border-color:rgba(255,159,26,.55);color:#ffd8a8}
                .tb-pill.warn .tb-dot{background:#ff9f1a;box-shadow:0 0 8px #ff9f1a}
                .tb-pill.attention{border-color:rgba(255,68,102,.55);color:#ffd0d8}
                .tb-pill.attention .tb-dot{
                    animation:tb-attn-flash .85s ease infinite;
                }
                @keyframes tb-attn-flash{
                    0%,100%{background:#00ff88;box-shadow:0 0 8px #00ff88}
                    50%{background:#ff4466;box-shadow:0 0 10px #ff4466}
                }
                .tb-pill.off{border-color:rgba(255,68,102,.35)}
                .tb-bar-actions{display:flex;gap:6px;align-items:center}
                .tb-btn{
                    padding:5px 11px;border-radius:8px;border:1px solid rgba(0,243,255,.35);
                    background:rgba(0,243,255,.1);color:#00f3ff;cursor:pointer;font:600 11px system-ui,sans-serif;
                }
                .tb-btn.primary{background:rgba(0,243,255,.18);border-color:#00f3ff}
                .tb-btn.primary.state-online{background:rgba(0,255,136,.2);border-color:#00ff88;color:#b7ffd9}
                .tb-btn.primary.state-starting{background:rgba(45,212,191,.22);border-color:#2dd4bf;color:#99f6e4}
                .tb-btn.primary.state-warn{background:rgba(255,159,26,.2);border-color:#ff9f1a;color:#ffd8a8}
                .tb-btn.ghost{background:transparent;border-color:rgba(255,255,255,.18);color:#888}
                .tb-btn:hover{box-shadow:0 0 12px rgba(0,243,255,.3)}
                .tb-btn:disabled{opacity:.5;cursor:wait}
                .tb-bar-hint{color:#6a7380;font-size:11px;font-weight:500;min-width:0;flex:1}
                .tb-bar-ver{margin-left:auto;opacity:.45;font-size:11px;font-weight:500}
            `;
            document.head.appendChild(style);
        }

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
        } else if (document.body) {
            document.body.insertBefore(bar, document.body.firstChild);
        } else {
            document.addEventListener('DOMContentLoaded', () => {
                if (!document.getElementById('tbSharedServerBar')) {
                    document.body.insertBefore(bar, document.body.firstChild);
                }
            }, { once: true });
        }

        if (global.AITOOLBOX_VERSION) {
            const ver = document.getElementById('tbVer');
            if (ver) ver.textContent = 'v' + global.AITOOLBOX_VERSION;
        }

        // Mark body so pages can hide legacy duplicate S1/S2 / Start Server chrome
        try {
            document.body?.classList.add('tb-has-companion-bar');
            // Hide common page-local server pills when shared bar is present
            document.querySelectorAll(
                '#serverPill, #btnStartServer, #serverStatus, .server-pill.legacy-server, [data-legacy-server-chrome]'
            ).forEach((el) => {
                if (el.closest('#tbSharedServerBar')) return;
                el.classList.add('tb-legacy-server-hidden');
                el.style.display = 'none';
            });
            // Remove accidental second companion bars
            document.querySelectorAll('#tbSharedServerBar').forEach((el, i) => {
                if (i > 0) el.remove();
            });
        } catch (_) { /* ignore */ }

        return _wireCompanionBar(opts);
    }

    function _setPill(el, state, detail) {
        if (!el) return;
        el.classList.remove('on', 'off', 'wait', 'warn', 'attention');
        const cls = (
            state === 'on' ? 'on'
            : state === 'wait' ? 'wait'
            : state === 'warn' ? 'warn'
            : state === 'attention' ? 'attention'
            : 'off'
        );
        el.classList.add(cls);
        const em = el.querySelector('em');
        if (em) {
            em.textContent = detail || (
                state === 'on' ? 'online'
                : state === 'wait' ? '…'
                : state === 'warn' ? 'warn'
                : state === 'attention' ? 'attn'
                : 'offline'
            );
        }
    }

    function _wireCompanionBar(opts = {}) {
        const API = () => global.AIToolboxAPI;
        const back = document.getElementById('tbBtnToolbox');
        if (back && !back._tbBound) {
            back._tbBound = true;
            back.href = launcherHref();
            back.addEventListener('click', (e) => {
                // Always re-resolve in case scripts load late
                back.href = launcherHref();
            });
        }

        const pillS1 = document.getElementById('tbPillS1');
        const pillS2 = document.getElementById('tbPillS2');
        const startBtn = document.getElementById('tbBtnStartServer');
        const relaunchBtn = document.getElementById('tbBtnRelaunchServers');
        const consoleBtn = document.getElementById('tbBtnServerConsole');
        const hintEl = document.getElementById('tbServerHint');
        // Legacy alias used by bindServerControls callers
        const statusEl = pillS1;
        let starting = false;
        let pollTimer = null;

        async function probeS2(timeoutMs = 900) {
            try {
                const ctrl = new AbortController();
                const t = setTimeout(() => ctrl.abort(), timeoutMs);
                const r = await fetch('http://127.0.0.1:8765/api/health', {
                    signal: ctrl.signal,
                    cache: 'no-store',
                });
                clearTimeout(t);
                if (!r.ok) return { ok: false };
                const j = await r.json().catch(() => ({}));
                return { ok: true, body: j };
            } catch {
                return { ok: false };
            }
        }

        async function refresh(force = false) {
            if (starting) return false;
            const api = API();
            let s1 = false;
            let s1Label = 'offline';
            if (api?.isOnline) {
                s1 = await api.isOnline(!!force, 2000);
                if (s1) {
                    const h = await api.health().catch(() => ({}));
                    s1Label = h.version ? `v${h.version}` : 'online';
                }
            }
            _setPill(pillS1, s1 ? 'on' : 'off', s1Label);

            // Prefer launch status (includes S2) when S1 is up; else direct probe
            let s2 = false;
            let s2Label = 'offline';
            if (s1 && api?.getLaunchStatus) {
                try {
                    const st = await api.getLaunchStatus();
                    const meta = st?.fafoMeta || {};
                    s2 = !!(meta.healthy || meta.listening);
                    s2Label = s2 ? 'online' : (meta.root?.ok === false ? 'path?' : 'offline');
                } catch {
                    const p = await probeS2();
                    s2 = !!p.ok;
                    s2Label = s2 ? 'online' : 'offline';
                }
            } else {
                const p = await probeS2();
                s2 = !!p.ok;
                s2Label = s2 ? 'online' : 'offline';
            }
            _setPill(pillS2, s2 ? 'on' : 'off', s2Label);

            if (startBtn) {
                startBtn.style.display = (s1 && s2) ? 'none' : '';
                startBtn.disabled = false;
                startBtn.classList.remove('state-online', 'state-starting', 'state-warn', 'state-offline');
                if (s1 && s2) {
                    startBtn.classList.add('state-online');
                    startBtn.textContent = '✓ Online';
                } else if (s1 || s2) {
                    startBtn.classList.add('state-warn');
                    startBtn.textContent = startBtn.dataset.label || '▶ Start missing';
                } else {
                    startBtn.classList.add('state-offline');
                    startBtn.textContent = startBtn.dataset.label || '▶ Start';
                }
            }
            if (hintEl && !starting) {
                const parts = [];
                parts.push(s1 ? 'S1 on' : 'S1 off');
                parts.push(s2 ? 'S2 on' : 'S2 off');
                hintEl.textContent = parts.join(' · ') + ' · servers stay up when you leave this page';
            }
            if (s1) opts.onOnline?.(await api?.health?.().catch(() => ({})));
            else opts.onOffline?.();
            return s1;
        }

        async function startAll(mode) {
            if (starting || API()?.isServerLaunching?.()) return;
            starting = true;
            _setPill(pillS1, 'wait', '…');
            _setPill(pillS2, 'wait', '…');
            if (startBtn) { startBtn.disabled = true; startBtn.textContent = 'Starting…'; }
            if (hintEl) hintEl.textContent = 'Starting S1 + S2 in background…';
            try {
                const result = await API()?.startServer({
                    mode: mode === 'console' ? 'console' : 'tray',
                    waitMs: opts.waitMs || 90000,
                    companions: true,
                    onStatus: (msg) => { if (hintEl) hintEl.textContent = msg; },
                });
                starting = false;
                if (result?.ok) toast('Servers online (S1 + S2)', 'ok');
                else toast('If blocked: Desktop Start Servers or tray', 'warn');
                await refresh(true);
            } catch (e) {
                starting = false;
                toast('Start failed: ' + (e.message || e), 'warn');
                await refresh(true);
            } finally {
                if (startBtn) {
                    startBtn.disabled = false;
                    startBtn.textContent = startBtn.dataset.label || '▶ Start';
                }
            }
        }

        if (startBtn && !startBtn._serverBound) {
            startBtn._serverBound = true;
            startBtn.dataset.label = startBtn.textContent || '▶ Start';
            startBtn.addEventListener('click', () => startAll('tray'));
        }
        if (relaunchBtn && !relaunchBtn._serverBound) {
            relaunchBtn._serverBound = true;
            relaunchBtn.addEventListener('click', async () => {
                if (!API()?.relaunchServers) return startAll('tray');
                relaunchBtn.disabled = true;
                try {
                    await API().relaunchServers({ waitMs: 60000 });
                    await refresh(true);
                    toast('Servers relaunched', 'ok');
                } catch (e) {
                    toast(String(e.message || e), 'warn');
                } finally {
                    relaunchBtn.disabled = false;
                }
            });
        }
        if (consoleBtn && !consoleBtn._serverBound) {
            consoleBtn._serverBound = true;
            consoleBtn.addEventListener('click', () => startAll('console'));
        }
        const bindPillStart = (el) => {
            if (!el || el._serverBound) return;
            el._serverBound = true;
            el.addEventListener('click', () => startAll('tray'));
            el.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); startAll('tray'); }
            });
        };
        bindPillStart(pillS1);
        bindPillStart(pillS2);

        // Keep legacy single-server bind for pages that still pass custom els
        if (opts.statusEl || opts.startBtn) {
            bindServerControls(opts);
        }

        const pollMs = opts.pollMs != null ? opts.pollMs : 8000;
        if (pollMs > 0) {
            pollTimer = setInterval(() => {
                if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return;
                refresh(false);
            }, pollMs);
        }
        refresh(true);
        try { initTooltips(document.getElementById('tbSharedServerBar')); } catch { /* ignore */ }

        return {
            refresh,
            start: startAll,
            stop: () => { if (pollTimer) clearInterval(pollTimer); },
        };
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

    /**
     * Resolve path to Toolbox Launcher.html from any nested tool page.
     * Walks up from the current URL until a candidate works, falls back to ../ climbs.
     */
    function launcherHref() {
        // Prefer S1-served launcher so Back always lands on a page with live health
        try {
            const origin = global.AITOOLBOX_CONFIG?.ORIGIN
                || global.AIToolboxAPI?.getOrigin?.()
                || 'http://127.0.0.87:18765';
            if (location.protocol === 'http:' || location.protocol === 'https:') {
                // Same host as toolbox server → use absolute path on that origin
                if (location.hostname === '127.0.0.87' || location.port === '18765') {
                    return origin.replace(/\/$/, '') + '/toolbox/Toolbox%20Launcher.html';
                }
            }
            // file:// or other — still deep-link to live server when possible
            return origin.replace(/\/$/, '') + '/toolbox/Toolbox%20Launcher.html';
        } catch { /* fall through */ }
        try {
            const scripts = document.getElementsByTagName('script');
            for (let i = scripts.length - 1; i >= 0; i--) {
                const src = scripts[i].src || '';
                if (src.includes('aitoolbox-ui.js') || src.includes('aitoolbox-api.js') || src.includes('aitoolbox-config.js')) {
                    return new URL('../Toolbox Launcher.html', src).href;
                }
            }
        } catch { /* ignore */ }
        const depth = (location.pathname.match(/\//g) || []).length;
        const up = depth > 2 ? '../'.repeat(Math.min(depth - 1, 4)) : '../';
        return up + 'Toolbox Launcher.html';
    }

    /**
     * Ensure a sticky “← Toolbox” control exists (does not duplicate if page already has one).
     */
    function ensureToolboxBack(opts = {}) {
        if (document.querySelector('a.toolbox-back, a[href*="Toolbox Launcher"]')) return null;
        const a = document.createElement('a');
        a.className = 'toolbox-back';
        a.href = opts.href || launcherHref();
        a.textContent = opts.label || '← Toolbox';
        a.style.cssText = opts.style || [
            'position:fixed', 'top:10px', 'left:12px', 'z-index:9998',
            'color:#00e5ff', 'text-decoration:none', 'font:600 12px system-ui,sans-serif',
            'padding:6px 10px', 'border-radius:8px',
            'background:rgba(5,5,12,.85)', 'border:1px solid rgba(0,229,255,.25)',
            'backdrop-filter:blur(8px)',
        ].join(';');
        const mount = () => {
            if (!document.body) return;
            document.body.appendChild(a);
        };
        if (document.body) mount();
        else document.addEventListener('DOMContentLoaded', mount, { once: true });
        return a;
    }

    /**
     * Catch unhandled errors / rejections and surface a toast once (no spam).
     * Call from tool pages that load this script; safe to call multiple times.
     */
    let guardsInstalled = false;
    let lastErrToast = 0;
    function installStabilityGuards(opts = {}) {
        if (guardsInstalled || typeof window === 'undefined') return;
        guardsInstalled = true;
        const quiet = !!opts.quiet;

        window.addEventListener('error', (ev) => {
            const msg = ev?.error?.message || ev?.message || 'Script error';
            // Ignore noisy extension / third-party noise
            if (/ResizeObserver|Script error\.|chrome-extension:\/\//i.test(String(msg))) return;
            console.error('[AIToolbox]', ev.error || msg);
            const now = Date.now();
            if (!quiet && now - lastErrToast > 4000) {
                lastErrToast = now;
                try { toast('Error: ' + String(msg).slice(0, 140), 'warn'); } catch { /* ignore */ }
            }
        });

        window.addEventListener('unhandledrejection', (ev) => {
            const reason = ev?.reason;
            const msg = reason?.message || String(reason || 'Unhandled promise rejection');
            if (/ResizeObserver|chrome-extension:\/\//i.test(msg)) return;
            console.error('[AIToolbox] unhandledrejection', reason);
            const now = Date.now();
            if (!quiet && now - lastErrToast > 4000) {
                lastErrToast = now;
                try { toast(String(msg).slice(0, 160), 'warn'); } catch { /* ignore */ }
            }
        });
    }

    /**
     * Mount companion bar + toolbox back on every tool page that loads this kit.
     * Safe to call multiple times; skipped on Toolbox Launcher.
     */
    function mountToolChrome(opts = {}) {
        try { installStabilityGuards({ quiet: false }); } catch { /* ignore */ }
        try { mountServerBar(opts); } catch (e) { console.warn('[AIToolbox] mountServerBar', e); }
        // Back link is already in the bar; still ensure sticky if bar was skipped
        try {
            if (!document.getElementById('tbSharedServerBar')) ensureToolboxBack();
        } catch { /* ignore */ }
    }

    /**
     * Close transient UI before Esc→launcher (compare panes, menus, modals).
     * Returns true if something was closed (caller should NOT leave the page).
     */
    function tryCloseTransientUi() {
        try {
            // Explicit close targets (Dup Manager compare, etc.)
            const cmp = document.getElementById('comparePanel');
            if (cmp && cmp.classList.contains('open')) {
                const btn = document.getElementById('btnCloseCompare');
                if (btn) { btn.click(); return true; }
                cmp.classList.remove('open', 'active');
                return true;
            }
            // data-esc-close elements that are open/visible
            const escClose = document.querySelector(
                '[data-esc-close].open, [data-esc-close].active, [data-esc-close][aria-hidden="false"]'
            );
            if (escClose) {
                const b = escClose.querySelector('[data-close], .close, .btn-close, [aria-label="Close"]');
                if (b) b.click();
                else {
                    escClose.classList.remove('open', 'active');
                    escClose.setAttribute('aria-hidden', 'true');
                    if (escClose.style) escClose.style.display = 'none';
                }
                return true;
            }
            // Open dropdown menus (Media Library Pairs/Tools menus)
            const menus = document.querySelectorAll(
                '.menu-wrap.open, .dropdown.open, .menu.open, .nav-menu.open, details[open].menu-details'
            );
            if (menus.length) {
                menus.forEach((m) => {
                    m.classList.remove('open');
                    if (m.tagName === 'DETAILS') m.open = false;
                });
                return true;
            }
            // Visible modal overlays
            const modal = document.querySelector(
                '.modal.open, .ui-modal.open, .overlay.open, .overlay.visible, ' +
                '.modal.show, .ui-modal.show, dialog[open], ' +
                '[role="dialog"].open, [role="dialog"][aria-hidden="false"]'
            );
            if (modal) {
                const b = modal.querySelector(
                    '[data-close], .close, .btn-close, .modal-close, [aria-label="Close"], button.close'
                );
                if (b) { b.click(); return true; }
                if (modal.tagName === 'DIALOG' && typeof modal.close === 'function') {
                    modal.close();
                    return true;
                }
                modal.classList.remove('open', 'show', 'visible', 'active');
                modal.setAttribute('aria-hidden', 'true');
                return true;
            }
            // Tutorial / walkthrough
            const tut = document.querySelector('.tutorial-overlay, .cine-root, #tutorialRoot, [data-tutorial-open]');
            if (tut && (tut.classList.contains('open') || tut.classList.contains('active') || getComputedStyle(tut).display !== 'none')) {
                try { endTutorial?.(); } catch { /* ignore */ }
                tut.classList.remove('open', 'active');
                if (tut.style) tut.style.display = 'none';
                return true;
            }
        } catch { /* ignore */ }
        return false;
    }

    /**
     * Esc closes overlays first; second Esc (or Esc with nothing open) → Toolbox Launcher.
     * Pages can set body data-tb-esc="off" or cancel the `fafo:escape` event to keep control.
     * Inside iframes (Media Hub / Compare Hub), Esc posts to parent instead of hijacking frame.
     */
    function bindEscToLauncher() {
        if (typeof document === 'undefined' || document.documentElement.dataset.tbEsc === '1') return;
        document.documentElement.dataset.tbEsc = '1';
        document.addEventListener('keydown', (e) => {
            if (e.key !== 'Escape') return;
            if (document.body?.dataset?.tbEsc === 'off') return;
            // Don't steal Esc from typing fields, dialogs, or pointer-lock games
            const t = e.target;
            if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)) return;
            if (t?.closest?.('[role="dialog"], .modal, .overlay, .ui-modal, .cine-root, dialog[open]')) {
                // still try close helper, but don't navigate
                if (tryCloseTransientUi()) {
                    e.preventDefault();
                    e.stopPropagation();
                }
                return;
            }
            if (document.pointerLockElement) return;
            // Skip on launcher itself
            if (/Toolbox Launcher/i.test(document.title) || /Toolbox Launcher\.html/i.test(location.pathname || '')) return;

            // Layer 1: close open UI (compare panel, menus, modals)
            if (tryCloseTransientUi()) {
                e.preventDefault();
                e.stopPropagation();
                return;
            }

            // Layer 2: page-specific handler can cancel
            try {
                const ev = new CustomEvent('fafo:escape', { cancelable: true, bubbles: true });
                if (!document.dispatchEvent(ev) || ev.defaultPrevented) {
                    e.preventDefault();
                    e.stopPropagation();
                    return;
                }
            } catch { /* ignore */ }

            // Layer 3: embedded in hub iframe — don't dump user out of the hub shell
            try {
                if (window.self !== window.top) {
                    e.preventDefault();
                    e.stopPropagation();
                    window.parent.postMessage({ type: 'fafo-escape', href: launcherHref() }, '*');
                    return;
                }
            } catch { /* cross-origin — fall through to local leave */ }

            // Layer 4: leave tool → launcher
            e.preventDefault();
            e.stopPropagation();
            try {
                location.href = launcherHref();
            } catch { /* ignore */ }
        }, true);
    }

    /**
     * Parse Media Hub / Compare Hub deep-link from an href.
     * Returns { kind: 'media'|'compare'|'launcher'|null, tab, search, href }.
     */
    function parseToolboxDeepLink(href) {
        const raw = String(href || '');
        let abs = raw;
        try { abs = new URL(raw, location.href).href; } catch { /* keep raw */ }
        const media = /Media(?:%20| )Hub\.html([^#]*)#([^?#]*)/i.exec(abs) || /Media(?:%20| )Hub\.html([^#]*)#([^?#]*)/i.exec(raw);
        if (media) {
            return { kind: 'media', tab: decodeURIComponent(media[2] || '').split('?')[0].split('/')[0], search: media[1] || '', href: abs };
        }
        const compare = /Compare(?:%20| )Hub\.html([^#]*)#([^?#]*)/i.exec(abs) || /Compare(?:%20| )Hub\.html([^#]*)#([^?#]*)/i.exec(raw);
        if (compare) {
            return { kind: 'compare', tab: decodeURIComponent(compare[2] || '').split('?')[0].split('/')[0], search: compare[1] || '', href: abs };
        }
        if (/Toolbox(?:%20| )Launcher\.html/i.test(abs) || /Toolbox(?:%20| )Launcher\.html/i.test(raw)) {
            return { kind: 'launcher', tab: '', search: '', href: abs };
        }
        if (/Media(?:%20| )Hub\.html/i.test(abs) || /Media(?:%20| )Hub\.html/i.test(raw)) {
            return { kind: 'media', tab: '', search: '', href: abs };
        }
        if (/Compare(?:%20| )Hub\.html/i.test(abs) || /Compare(?:%20| )Hub\.html/i.test(raw)) {
            return { kind: 'compare', tab: '', search: '', href: abs };
        }
        return null;
    }

    /**
     * Navigate to a toolbox page. When this tool is framed by Media/Compare Hub,
     * switch the parent tab (or break out to top) instead of nesting a hub in the iframe.
     */
    function navigateToolbox(href) {
        const info = parseToolboxDeepLink(href);
        const fallback = () => { location.href = href; };
        if (!info) { fallback(); return; }
        try {
            if (window.self !== window.top) {
                if (info.kind === 'media' && info.tab) {
                    window.parent.postMessage({ type: 'fafo-hub-tab', tab: info.tab, search: info.search, href: info.href }, '*');
                    return;
                }
                if (info.kind === 'compare' && info.tab) {
                    window.parent.postMessage({ type: 'fafo-compare-tab', tab: info.tab, search: info.search, href: info.href }, '*');
                    return;
                }
                try { window.top.location.href = info.href; return; } catch { /* cross-origin */ }
                window.parent.postMessage({ type: 'fafo-escape', href: info.href }, '*');
                return;
            }
        } catch { /* ignore */ }
        location.href = info.href || href;
    }

    /** Intercept <a href="Media Hub.html#duplicates"> etc. so iframe children cannot nest a hub. */
    function bindFramedHubLinks() {
        if (typeof document === 'undefined' || document.documentElement.dataset.tbHubLinks === '1') return;
        document.documentElement.dataset.tbHubLinks = '1';
        document.addEventListener('click', (e) => {
            if (e.defaultPrevented) return;
            if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
            const a = e.target?.closest?.('a[href]');
            if (!a) return;
            const href = a.getAttribute('href') || '';
            if (!href || href.startsWith('javascript:') || href === '#') return;
            const info = parseToolboxDeepLink(href) || parseToolboxDeepLink(a.href);
            if (!info) return;
            try {
                if (window.self === window.top) return;
            } catch { return; }
            e.preventDefault();
            e.stopPropagation();
            navigateToolbox(a.href || href);
        }, true);
    }

    // Auto-install on every page that loads the UI kit (low cost, high value)
    if (typeof window !== 'undefined') {
        try { installStabilityGuards({ quiet: false }); } catch { /* ignore */ }
        const autoMount = () => {
            try {
                // Skip pure extension pages / about:blank noise
                if (!document.body) return;
                if (document.body.dataset.tbChrome === 'off') return;
                mountToolChrome({ pollMs: 8000 });
                bindEscToLauncher();
                bindFramedHubLinks();
                // Guidance (PC score + skill tooltips) — load once
                ensureGuidanceScript();
            } catch (e) {
                console.warn('[AIToolbox] auto chrome', e);
            }
        };

        function ensureGuidanceScript() {
            if (global.FAFOGuidance) {
                try { global.FAFOGuidance.installSkillControl?.(); } catch (_) { /* ignore */ }
                return;
            }
            if (document.getElementById('fafoGuidanceScript')) return;
            let src = 'shared/fafo-guidance.js';
            try {
                const scripts = document.getElementsByTagName('script');
                for (let i = scripts.length - 1; i >= 0; i--) {
                    const s = scripts[i].src || '';
                    if (s.includes('aitoolbox-ui.js')) {
                        src = s.replace(/aitoolbox-ui\.js.*$/i, 'fafo-guidance.js');
                        break;
                    }
                }
            } catch (_) { /* ignore */ }
            const el = document.createElement('script');
            el.id = 'fafoGuidanceScript';
            el.src = src;
            el.async = true;
            document.head.appendChild(el);
        }
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', autoMount, { once: true });
        } else {
            // Defer so page scripts can set data-tb-chrome=off if needed
            setTimeout(autoMount, 0);
        }
    }

    global.AIToolboxUI = {
        initTooltips,
        toast,
        launcherHref,
        ensureToolboxBack,
        bindEscToLauncher,
        mountToolChrome,
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
        mountToolChrome,
        escapeHtml,
        formatBytes,
        getApiBase,
        apiFetch,
        launcherHref,
        ensureToolboxBack,
        installStabilityGuards,
        tryCloseTransientUi,
        parseToolboxDeepLink,
        navigateToolbox,
        bindFramedHubLinks,
    };
})(typeof window !== 'undefined' ? window : globalThis);