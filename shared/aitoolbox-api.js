/**
 * Hybrid API — uses Python server when available, falls back to browser IndexedDB.
 * Load shared/aitoolbox-config.js first (defines AITOOLBOX_CONFIG / AITOOLBOX_API_BASE).
 */
(function (global) {
    'use strict';

    function resolveApiBase() {
        const cfg = global.AITOOLBOX_CONFIG;
        if (cfg && cfg.API_BASE) return cfg.API_BASE;
        if (global.AITOOLBOX_API_BASE) return global.AITOOLBOX_API_BASE;
        // Fallback matches shared/aitoolbox-bind.json (unique loopback + port)
        return 'http://127.0.0.87:18765/api';
    }

    /** Live getter so overrides applied after load still work */
    function apiBase() {
        return resolveApiBase();
    }

    // Keep a mutable alias for any code that read the old const name via closure
    let API_BASE = resolveApiBase();
    function refreshApiBase() {
        API_BASE = resolveApiBase();
        return API_BASE;
    }
    refreshApiBase();

    let serverOnline = null;
    let lastCheck = 0;
    /** Consecutive failed probes — avoids single flaky fetch flipping UI to offline. */
    let failStreak = 0;

    // Page keepalive: while any toolbox HTML page is open, auto-recover offline backend
    let keepAliveTimer = null;
    let keepAliveHealing = false;
    let keepAliveLastHeal = 0;
    const KEEP_ALIVE_MS = 15000;
    const KEEP_ALIVE_COOLDOWN_MS = 25000;

    async function probeHealthOnce(timeoutMs) {
        refreshApiBase();
        const r = await fetch(`${apiBase()}/health`, {
            signal: AbortSignal.timeout(timeoutMs),
            cache: 'no-store',
            mode: 'cors',
            credentials: 'omit',
        });
        return !!r && r.ok;
    }

    /**
     * Probe S1 (HTML Toolbox Server @ 127.0.0.87:18765 by default).
     * - Caches "online" for ~4s, "offline" only ~1s (recover quickly)
     * - Retries once on failure
     * - Hysteresis: while previously online, need 2 fails (unless force) before flipping offline
     *   so navigation / brief busy periods don't flash Offline on every tool page.
     */
    async function checkServer(force = false, timeoutMs = 2500) {
        const now = Date.now();
        const ms = Math.max(800, Number(timeoutMs) || 2500);
        if (!force && serverOnline === true && now - lastCheck < 4000) return true;
        if (!force && serverOnline === false && now - lastCheck < 1000) return false;

        let ok = false;
        try {
            ok = await probeHealthOnce(ms);
        } catch {
            ok = false;
        }
        // One retry — first paint / navigation often races a single failed fetch
        if (!ok) {
            try {
                await new Promise((r) => setTimeout(r, 120));
                ok = await probeHealthOnce(Math.max(ms, 3000));
            } catch {
                ok = false;
            }
        }

        lastCheck = Date.now();
        if (ok) {
            failStreak = 0;
            serverOnline = true;
            return true;
        }

        failStreak += 1;
        // force=true (Recheck / Start Server wait) reports raw truth after retries
        if (force || serverOnline !== true || failStreak >= 2) {
            serverOnline = false;
            return false;
        }
        // Optimistic: keep "online" for one blip so tool pages don't lie after home said UP
        return true;
    }

    /** Absolute http URL for a tool page when served by S1 (preferred over file://). */
    function toolboxOrigin() {
        const c = global.AITOOLBOX_CONFIG;
        if (c && c.ORIGIN) return String(c.ORIGIN).replace(/\/$/, '');
        return 'http://127.0.0.87:18765';
    }

    /**
     * Build http://127.0.0.87:18765/toolbox/... URL for a relative tool path.
     * Using the S1 origin keeps shared scripts + health checks consistent across pages.
     */
    function toolPageUrl(relativePath) {
        const rel = String(relativePath || '')
            .replace(/\\/g, '/')
            .replace(/^\.\//, '')
            .replace(/^\//, '');
        const encoded = rel.split('/').map((seg) => encodeURIComponent(seg)).join('/');
        return toolboxOrigin() + '/toolbox/' + encoded;
    }

    async function waitForServer(maxMs = 90000, intervalMs = 1000) {
        const t0 = Date.now();
        while (Date.now() - t0 < maxMs) {
            if (await checkServer(true, 3000)) return true;
            await new Promise(r => setTimeout(r, intervalMs));
        }
        return false;
    }

    /** Resolve toolbox root from this script's URL (works from any nested tool page). */
    function getToolboxRoot() {
        try {
            const scripts = document.getElementsByTagName('script');
            for (let i = scripts.length - 1; i >= 0; i--) {
                const src = scripts[i].src || '';
                if (src.includes('aitoolbox-api.js')) {
                    return new URL('..', src).href.replace(/\/?$/, '/');
                }
            }
        } catch { /* ignore */ }
        try {
            return new URL('../', window.location.href).href;
        } catch {
            return '';
        }
    }

    function toolboxFileUrl(filename) {
        const root = getToolboxRoot();
        if (!root) return filename;
        return new URL(filename.replace(/^\//, ''), root).href;
    }

    /**
     * Fire a custom protocol once. Browsers may show "Open AI Toolbox?" — that is OK.
     * Do NOT window.open .hta/.bat files: Chrome/Edge download them and prompt Save As
     * (often twice if open + anchor fallback both fire).
     */
    function tryProtocolLaunch(action = 'start') {
        const allowed = {
            start: 'start',
            tray: 'tray',
            restart: 'restart',
            console: 'console',
            folder: 'folder',
            setup: 'setup',
            launch: 'launch',
            diagnostics: 'diagnostics',
            'pack-reports': 'pack-reports',
            packreports: 'pack-reports',
            pack: 'pack-reports',
            ghost: 'ghost',
            'ghost-cleaner': 'ghost',
            ghostcleaner: 'ghost',
            'ghost-device-cleaner': 'ghost',
            watchdog: 'watchdog',
            'watchdog-status': 'watchdog-status',
            'watchdog-install': 'watchdog-install',
            'watchdog-folder': 'watchdog-folder',
        };
        const key = String(action || 'start').toLowerCase();
        const act = allowed[key] || 'start';
        // act: start | restart | tray | console | folder | setup | launch | watchdog* …
        const url = 'aitoolbox://' + act;
        dbg()?.log('api', 'info', 'Protocol launch: ' + url);
        try {
            // Hidden iframe is enough for registered URL handlers; avoids navigation + double fire.
            const iframe = document.createElement('iframe');
            iframe.style.cssText = 'position:absolute;width:0;height:0;border:0;pointer-events:none;opacity:0';
            iframe.setAttribute('aria-hidden', 'true');
            iframe.src = url;
            document.body.appendChild(iframe);
            setTimeout(() => { try { iframe.remove(); } catch { /* ignore */ } }, 4000);
        } catch (e) {
            dbg()?.log('api', 'warn', 'Protocol launch failed: ' + (e.message || e));
        }
        try {
            localStorage.setItem('aitoolbox_protocol_used', '1');
        } catch { /* ignore */ }
        return url;
    }

    /**
     * Open a toolbox file URL. Prefer protocol for launch actions.
     * For legacy .hta/.bat, only used when opts.allowDownload is true (explicit user intent).
     * Default path for start/folder/setup is custom protocol — no Save dialogs.
     */
    function launchToolboxFile(filename, opts = {}) {
        const name = String(filename || '').replace(/^\.\//, '');
        const lower = name.toLowerCase();

        // Map common launchers to protocol so we never download them from the browser.
        if (/launch_server\.hta$/i.test(lower) || /^start server\.bat$/i.test(lower)) {
            return tryProtocolLaunch('start');
        }
        if (/start server \(console\)\.bat$/i.test(lower) || /start_console/i.test(lower)) {
            return tryProtocolLaunch('console');
        }
        if (/open_toolbox_folder\.hta$/i.test(lower)) {
            return tryProtocolLaunch('folder');
        }
        if (/setup \(run once\)\.bat$/i.test(lower) || /^setup.*\.bat$/i.test(lower)) {
            return tryProtocolLaunch('setup');
        }
        if (/start-server-watchdog\.bat$/i.test(lower)) {
            return tryProtocolLaunch('watchdog');
        }
        if (/open-server-watchdog-status\.bat$/i.test(lower)) {
            return tryProtocolLaunch('watchdog-status');
        }
        if (/install-server-watchdog\.bat$/i.test(lower)) {
            return tryProtocolLaunch('watchdog-install');
        }

        const url = toolboxFileUrl(name);
        dbg()?.log('api', 'info', 'Launch file: ' + url + (opts.allowDownload ? ' (download allowed)' : ''));

        // .hta / .bat / .cmd almost always become "Save As" in modern browsers — skip unless forced.
        if (/\.(hta|bat|cmd|ps1)$/i.test(lower) && !opts.allowDownload) {
            dbg()?.log('api', 'warn', 'Skipped browser open of ' + name + ' (would download). Use protocol or desktop shortcut.');
            return url;
        }

        try {
            // Single navigation attempt only (no open + click double-fire).
            const a = document.createElement('a');
            a.href = url;
            a.rel = 'noopener noreferrer';
            // Same-tab for file:// resources reduces download; leave default.
            document.body.appendChild(a);
            a.click();
            a.remove();
        } catch (e) {
            dbg()?.log('api', 'error', 'Launch file failed: ' + (e.message || e));
        }
        return url;
    }

    let serverLaunching = false;

    /**
     * Launch the Python server from any toolbox page (file:// or http://).
     * Uses registered custom protocol only (aitoolbox://start|console) after SETUP.
     * Does not open .hta/.bat in the browser (that caused Save As prompts, often twice).
     *
     * @param {{ mode?: 'tray'|'console', waitMs?: number, onStatus?: (msg:string)=>void, allowLegacyHta?: boolean }} opts
     * @returns {Promise<{ ok: boolean, alreadyOnline?: boolean, blocked?: boolean, needsSetup?: boolean }>}
     */
    /**
     * Start companions via S1 API when toolbox is up.
     * opts.toolbox / opts.fafoMeta: true|false to include/exclude (default true).
     */
    async function startCompanionServers(opts = {}) {
        try {
            if (!(await checkServer(true, 1500))) return null;
            const body = {
                toolbox: opts.toolbox !== false,
                fafoMeta: opts.fafoMeta !== false,
                waitSec: opts.waitSec != null ? opts.waitSec : 8,
            };
            return await api('/launch/companions/start', {
                method: 'POST',
                body: JSON.stringify(body),
                timeoutMs: 20000,
            });
        } catch {
            return null;
        }
    }

    /**
     * Manually stop S1 HTML Toolbox and/or S2 FAFO Local Media Tagger.
     * Requires S1 online unless only stopping meta (still needs S1 for API).
     * opts.toolbox / opts.fafoMeta default true (stop both).
     */
    async function stopCompanionServers(opts = {}) {
        if (!(await checkServer(true, 1500))) {
            throw new Error('S1 HTML Toolbox offline — use Stop-ALL-Servers.bat or tray');
        }
        const body = {
            toolbox: opts.toolbox !== false,
            fafoMeta: opts.fafoMeta !== false,
        };
        return api('/launch/companions/stop', {
            method: 'POST',
            body: JSON.stringify(body),
            timeoutMs: 15000,
        });
    }

    async function getLaunchStatus() {
        if (!(await checkServer(true, 1500))) return null;
        try {
            return await api('/launch/status', { timeoutMs: 8000 });
        } catch {
            return null;
        }
    }

    async function saveLaunchPrefs(prefs) {
        if (!(await checkServer(true, 1500))) throw new Error('Server offline — start toolbox first');
        return api('/launch/prefs', {
            method: 'PUT',
            body: JSON.stringify(prefs || {}),
            timeoutMs: 15000,
        });
    }

    async function setWindowsStartup(flags) {
        if (!(await checkServer(true, 1500))) throw new Error('Server offline — start toolbox first');
        return api('/launch/windows-startup', {
            method: 'POST',
            body: JSON.stringify(flags || {}),
            timeoutMs: 15000,
        });
    }

    /**
     * Server watchdog helpers. Prefer S1 API when online; fall back to aitoolbox:// protocol.
     */
    async function getWatchdogStatus() {
        if (await checkServer(true, 1500)) {
            try {
                return await api('/launch/watchdog/status', { timeoutMs: 8000 });
            } catch {
                return null;
            }
        }
        return null;
    }

    async function startWatchdog() {
        if (await checkServer(true, 1500)) {
            try {
                return await api('/launch/watchdog/start', { method: 'POST', timeoutMs: 20000 });
            } catch (e) {
                dbg()?.log('api', 'warn', 'watchdog API start failed: ' + (e && e.message || e));
            }
        }
        tryProtocolLaunch('watchdog');
        return { ok: true, via: 'protocol', action: 'watchdog' };
    }

    async function installWatchdog() {
        if (await checkServer(true, 1500)) {
            try {
                return await api('/launch/watchdog/install', { method: 'POST', timeoutMs: 60000 });
            } catch (e) {
                dbg()?.log('api', 'warn', 'watchdog API install failed: ' + (e && e.message || e));
            }
        }
        tryProtocolLaunch('watchdog-install');
        return { ok: true, via: 'protocol', action: 'watchdog-install' };
    }

    async function openWatchdogStatus() {
        if (await checkServer(true, 1500)) {
            try {
                return await api('/launch/watchdog/open-status', { method: 'POST', timeoutMs: 30000 });
            } catch (e) {
                dbg()?.log('api', 'warn', 'watchdog open-status API failed: ' + (e && e.message || e));
            }
        }
        tryProtocolLaunch('watchdog-status');
        return { ok: true, via: 'protocol', action: 'watchdog-status' };
    }

    async function openWatchdogBatsFolder() {
        if (await checkServer(true, 1500)) {
            try {
                return await api('/launch/watchdog/open-folder', { method: 'POST', timeoutMs: 10000 });
            } catch (e) {
                dbg()?.log('api', 'warn', 'watchdog open-folder API failed: ' + (e && e.message || e));
            }
        }
        tryProtocolLaunch('watchdog-folder');
        return { ok: true, via: 'protocol', action: 'watchdog-folder' };
    }

    /**
     * While this page is open: poll health and relaunch servers if they die.
     * Pairs with the tray watchdog — minimal effort, no folder hunting.
     */
    function startKeepAlive(opts = {}) {
        const intervalMs = opts.intervalMs != null ? opts.intervalMs : KEEP_ALIVE_MS;
        if (keepAliveTimer) return keepAliveTimer;
        keepAliveTimer = setInterval(async () => {
            if (serverLaunching || keepAliveHealing) return;
            if (typeof document !== 'undefined' && document.hidden) return;
            try {
                const on = await checkServer(true, 1500);
                if (on) return;
                const now = Date.now();
                if (now - keepAliveLastHeal < KEEP_ALIVE_COOLDOWN_MS) return;
                keepAliveHealing = true;
                keepAliveLastHeal = now;
                dbg()?.log('api', 'info', 'KeepAlive: backend offline — auto-relaunch');
                try {
                    await startServer({ mode: 'tray', waitMs: 25000, companions: true });
                } catch (e) {
                    dbg()?.log('api', 'warn', 'KeepAlive relaunch: ' + (e && e.message || e));
                } finally {
                    keepAliveHealing = false;
                }
            } catch { /* ignore poll errors */ }
        }, intervalMs);
        // First check soon after load (don't wait full interval)
        setTimeout(async () => {
            try {
                if (!(await checkServer(true, 1500)) && !serverLaunching) {
                    keepAliveLastHeal = Date.now();
                    await startServer({ mode: 'tray', waitMs: 20000, companions: true });
                }
            } catch { /* ignore */ }
        }, 2500);
        return keepAliveTimer;
    }

    function stopKeepAlive() {
        if (keepAliveTimer) {
            clearInterval(keepAliveTimer);
            keepAliveTimer = null;
        }
    }

    /**
     * Relaunch companions without browsing install folders.
     * Works offline via aitoolbox://restart|start (after SETUP once).
     */
    async function relaunchServers(opts = {}) {
        const waitMs = opts.waitMs != null ? opts.waitMs : 45000;
        const onStatus = typeof opts.onStatus === 'function' ? opts.onStatus : null;
        const hard = opts.restart !== false;

        onStatus?.(hard ? 'Relaunching servers…' : 'Starting servers…');
        tryProtocolLaunch(hard ? 'restart' : 'start');

        // If toolbox is already up, also use API restart (hidden, no UAC)
        if (hard && (await checkServer(true, 1200))) {
            try {
                await api('/launch/companions/restart', {
                    method: 'POST',
                    body: JSON.stringify({
                        toolbox: opts.toolbox !== false,
                        fafoMeta: opts.fafoMeta !== false,
                        waitSec: 12,
                    }),
                    timeoutMs: 25000,
                });
            } catch { /* protocol path may still succeed */ }
        }

        onStatus?.('Waiting for servers…');
        const ok = await waitForServer(waitMs, 800);
        if (ok) {
            onStatus?.('Servers online');
            try {
                await startCompanionServers({ toolbox: true, fafoMeta: true, waitSec: 6 });
            } catch { /* optional */ }
        }
        return { ok };
    }

    async function startServer(opts = {}) {
        const mode = opts.mode === 'console' ? 'console' : 'tray';
        const waitMs = opts.waitMs != null ? opts.waitMs : 90000;
        const onStatus = typeof opts.onStatus === 'function' ? opts.onStatus : null;
        const alsoCompanions = opts.companions !== false;

        if (await checkServer(true, 2000)) {
            onStatus?.('Server already online');
            if (alsoCompanions) {
                onStatus?.('Starting companion servers…');
                await startCompanionServers({ toolbox: true, fafoMeta: true, waitSec: 6 });
            }
            return { ok: true, alreadyOnline: true };
        }
        if (serverLaunching) {
            onStatus?.('Server launch already in progress…');
            const ok = await waitForServer(waitMs, 1000);
            return { ok, blocked: !ok };
        }

        serverLaunching = true;
        try {
            onStatus?.('Starting via aitoolbox:// protocol…');
            tryProtocolLaunch(mode === 'console' ? 'console' : 'start');

            // Brief wait — protocol handler is usually instant if registered.
            onStatus?.('Waiting for server…');
            let ok = await waitForServer(Math.min(12000, waitMs), 800);
            if (ok) {
                onStatus?.('Server online');
                try { localStorage.setItem('aitoolbox_protocol_ok', '1'); } catch { /* ignore */ }
                if (alsoCompanions) {
                    onStatus?.('Ensuring FAFO tagging companion…');
                    await startCompanionServers({ toolbox: true, fafoMeta: true, waitSec: 6 });
                }
                return { ok: true };
            }

            // One more protocol nudge (user may have dismissed the first "Open?" dialog)
            onStatus?.('Retrying protocol launch…');
            tryProtocolLaunch(mode === 'console' ? 'console' : 'start');
            ok = await waitForServer(Math.max(3000, waitMs - 12000), 1000);
            if (ok) {
                onStatus?.('Server online');
                try { localStorage.setItem('aitoolbox_protocol_ok', '1'); } catch { /* ignore */ }
                if (alsoCompanions) {
                    await startCompanionServers({ toolbox: true, fafoMeta: true, waitSec: 6 });
                }
                return { ok: true };
            }

            // Opt-in legacy only — still often causes Save As; not default.
            if (opts.allowLegacyHta) {
                onStatus?.('Trying legacy HTA (may prompt Save)…');
                launchToolboxFile('launch_server.hta', { allowDownload: true });
                ok = await waitForServer(Math.min(20000, waitMs), 1000);
                if (ok) {
                    onStatus?.('Server online');
                    if (alsoCompanions) {
                        await startCompanionServers({ toolbox: true, fafoMeta: true, waitSec: 6 });
                    }
                    return { ok: true };
                }
            }

            onStatus?.('Server did not start — run SETUP once, or double-click START SERVER.bat');
            return { ok: false, blocked: true, needsSetup: true };
        } finally {
            serverLaunching = false;
        }
    }

    function openToolboxFolder() {
        return tryProtocolLaunch('folder');
    }

    function runSetupOnce() {
        return tryProtocolLaunch('setup');
    }

    function isServerLaunching() {
        return serverLaunching;
    }

    function dbg() {
        return global.AIToolboxDebug;
    }

    function normalizeMedia(m) {
        if (!m) return m;
        return {
            ...m,
            relativePath: m.relativePath || m.rel_path || '',
            dirId: m.dirId || m.dir_id,
            rank: m.rank != null ? Number(m.rank) : 0,
            category: m.category || '',
            status: m.status || '',
            tags: m.tags || [],
            file_write: m.file_write || m.fileWrite || null,
            tagged_partner: m.tagged_partner != null ? m.tagged_partner : m.taggedPartner,
            partner_id: m.partner_id || m.partnerId || null,
        };
    }

    /**
     * Fetch toolbox API with timeout + clearer offline errors.
     * opts.timeoutMs — default 30000 (use 0 to disable).
     * opts.signal — optional AbortSignal (combined with timeout).
     */
    async function api(path, opts = {}) {
        const method = opts.method || 'GET';
        const t0 = Date.now();
        const timeoutMs = opts.timeoutMs != null ? opts.timeoutMs : 30000;
        dbg()?.log('api', 'info', `${method} ${path}`);

        // Don't send custom fields to fetch()
        const { timeoutMs: _tm, ...fetchOpts } = opts;
        const headers = { 'Content-Type': 'application/json', ...(fetchOpts.headers || {}) };

        let timeoutCtrl = null;
        let timeoutTimer = null;
        let combinedSignal = fetchOpts.signal || null;
        if (timeoutMs > 0) {
            timeoutCtrl = new AbortController();
            timeoutTimer = setTimeout(() => timeoutCtrl.abort(), timeoutMs);
            if (fetchOpts.signal) {
                if (fetchOpts.signal.aborted) {
                    timeoutCtrl.abort();
                } else {
                    fetchOpts.signal.addEventListener('abort', () => timeoutCtrl.abort(), { once: true });
                }
            }
            combinedSignal = timeoutCtrl.signal;
        }

        try {
            refreshApiBase();
            const r = await fetch(`${apiBase()}${path}`, {
                ...fetchOpts,
                headers,
                signal: combinedSignal,
            });
            if (timeoutTimer) clearTimeout(timeoutTimer);
            if (!r.ok) {
                const err = await r.json().catch(() => ({ detail: r.statusText }));
                const msg = typeof err.detail === 'string'
                    ? err.detail
                    : (err.detail ? JSON.stringify(err.detail) : r.statusText);
                dbg()?.log('api', 'error', `${method} ${path} → ${r.status}: ${msg}`);
                const e = new Error(msg || `HTTP ${r.status}`);
                e.status = r.status;
                e.path = path;
                throw e;
            }
            serverOnline = true;
            lastCheck = Date.now();
            const out = r.headers.get('content-type')?.includes('json') ? await r.json() : r;
            dbg()?.log('api', 'info', `${method} ${path} OK ${Date.now() - t0}ms`);
            return out;
        } catch (e) {
            if (timeoutTimer) clearTimeout(timeoutTimer);
            const name = e && e.name;
            const raw = String(e && e.message || e || '');
            const offlineLike = name === 'AbortError'
                || /Failed to fetch|NetworkError|Load failed|ERR_CONNECTION|ECONNREFUSED|timed out|aborted/i.test(raw);

            if (offlineLike) {
                serverOnline = false;
                lastCheck = Date.now();
            }

            let msg = raw;
            if (name === 'AbortError' || /aborted/i.test(raw)) {
                msg = timeoutMs > 0
                    ? `Request timed out after ${timeoutMs}ms (${method} ${path}). Is the toolbox server busy or offline?`
                    : `Request aborted (${method} ${path})`;
            } else if (/Failed to fetch|NetworkError|Load failed|ECONNREFUSED/i.test(raw)) {
                msg = `Server unreachable at ${apiBase()}. Click ▶ Start Server, then retry.`;
            }

            if (!String(msg).includes('→')) {
                dbg()?.log('api', 'error', `${method} ${path}: ${msg}`);
            }
            const err = new Error(msg);
            err.cause = e;
            err.offline = offlineLike;
            err.path = path;
            throw err;
        }
    }

    const API = {
        async isOnline(force, timeoutMs) { return checkServer(force, timeoutMs); },
        async waitForServer(maxMs, intervalMs) { return waitForServer(maxMs, intervalMs); },
        async health() { return api('/health'); },

        /** Current API base (http://host:port/api) — unique bind, not shared with FAFO :8765 */
        getApiBase() { return apiBase(); },
        /** Alias used by icon helpers */
        apiBase() { return apiBase(); },
        getEndpointLabel() {
            const c = global.AITOOLBOX_CONFIG;
            return (c && c.ENDPOINT_LABEL) || '127.0.0.87:18765';
        },
        getOrigin() { return toolboxOrigin(); },
        toolPageUrl,
        refreshBind() { return refreshApiBase(); },

        /**
         * Copy a tool icon into assets/tool-icons and update shared manifest (all users).
         * Accepts data URLs for png/gif/jpg/webp/ico/svg/bmp.
         */
        async publishToolIcon(toolId, dataUrl, opts = {}) {
            if (!(await checkServer(true, 2000))) {
                return { ok: false, offline: true, error: 'Server offline — icon saved in this browser only' };
            }
            return api('/icons', {
                method: 'POST',
                body: JSON.stringify({
                    toolId,
                    dataUrl,
                    filename: opts.filename || null,
                    asAppIcon: !!opts.asAppIcon,
                }),
            });
        },

        async getIconManifest() {
            if (await checkServer(false, 1200)) {
                return api('/icons/manifest');
            }
            return global.AIToolbox?.loadSharedIconManifest?.(true);
        },

        async deleteSharedToolIcon(toolId) {
            if (!(await checkServer(true, 2000))) {
                throw new Error('Server offline');
            }
            return api('/icons/' + encodeURIComponent(toolId), { method: 'DELETE' });
        },

        /** Publish every personal IndexedDB icon into the shared repo folder */
        async publishAllPersonalIcons() {
            const rows = await (global.AIToolbox?.listPersonalLauncherIcons?.() || []);
            const results = [];
            for (const row of rows) {
                try {
                    const r = await this.publishToolIcon(row.toolId, row.dataUrl);
                    results.push({ toolId: row.toolId, ...r });
                } catch (e) {
                    results.push({ toolId: row.toolId, ok: false, error: e.message || String(e) });
                }
            }
            try { await global.AIToolbox?.loadSharedIconManifest?.(true); } catch { /* ignore */ }
            return results;
        },

        /** Toolbox root URL (parent of shared/). */
        getToolboxRoot,
        toolboxFileUrl,
        /** Launch Python server from browser (protocol + HTA). Works from any tool page. */
        startServer,
        startCompanionServers,
        stopCompanionServers,
        relaunchServers,
        startKeepAlive,
        stopKeepAlive,
        getLaunchStatus,
        saveLaunchPrefs,
        setWindowsStartup,
        getWatchdogStatus,
        startWatchdog,
        installWatchdog,
        openWatchdogStatus,
        openWatchdogBatsFolder,
        launchToolboxFile,
        openToolboxFolder,
        runSetupOnce,
        tryProtocolLaunch,
        isServerLaunching,
        isLaunching: isServerLaunching,

        /**
         * Launch allowlisted desktop tools (e.g. elevated Ghost Device Cleaner).
         * Tries S1 API first, then aitoolbox:// protocol fallback.
         * @param {string} toolId e.g. 'ghost-device-cleaner'
         * @param {{ action?: string }} opts action: run | folder | ui
         */
        async launchLocalTool(toolId, opts = {}) {
            const id = String(toolId || '').trim();
            const action = opts.action || 'run';
            if (!id) throw new Error('tool id required');
            try {
                if (await checkServer(true, 1500)) {
                    const r = await api('/tools/launch', {
                        method: 'POST',
                        body: JSON.stringify({ id, action }),
                        timeoutMs: 8000,
                    });
                    if (r && r.ok !== false) return { ok: true, via: 'api', ...r };
                }
            } catch (e) {
                dbg()?.log('api', 'warn', 'launchLocalTool API failed: ' + (e.message || e));
            }
            // Protocol fallback (works offline if SETUP registered aitoolbox://)
            if (/ghost/i.test(id) || action === 'ghost') {
                tryProtocolLaunch('ghost');
                return { ok: true, via: 'protocol', id, action: 'ghost' };
            }
            throw new Error('Could not launch local tool (server offline and no protocol match)');
        },

        async listDirectories() {
            if (await checkServer()) return api('/directories');
            return (global.AIToolbox?.listDirectories() || []);
        },

        async addDirectory(path) {
            if (await checkServer()) return api('/directories', { method: 'POST', body: JSON.stringify({ path }) });
            if ('showDirectoryPicker' in window) {
                const h = await window.showDirectoryPicker({ mode: 'readwrite' });
                return global.AIToolbox.addDirectory(h);
            }
            throw new Error('Server offline — use ▶ Start Server in the app, or Chrome folder picker');
        },

        async pickDirectoryNative() {
            if (await checkServer()) return api('/directories/pick', { method: 'POST' });
            throw new Error('Start server first (▶ Start Server) for native folder picker');
        },

        async pickFolderOnly() {
            if (await checkServer()) return api('/pick-folder', { method: 'POST' });
            throw new Error('Start server first (▶ Start Server) for native folder picker');
        },

        async removeDirectory(id) {
            if (await checkServer()) return api(`/directories/${encodeURIComponent(id)}`, { method: 'DELETE' });
            return global.AIToolbox.removeDirectory(id);
        },

        async scanDirectory(dirId, onProgress) {
            if (await checkServer()) {
                if (onProgress) {
                    return new Promise((resolve, reject) => {
                        const es = new EventSource(`${apiBase()}/scan/${encodeURIComponent(dirId)}/stream`);
                        es.onmessage = e => {
                            const d = JSON.parse(e.data);
                            if (d.error) { es.close(); reject(new Error(d.error)); }
                            else if (d.done) { es.close(); resolve({ indexed: d.count }); }
                            else onProgress(d.count, d.file);
                        };
                        es.onerror = () => { es.close(); reject(new Error('Scan stream failed')); };
                    });
                }
                return api(`/scan/${encodeURIComponent(dirId)}`, { method: 'POST' });
            }
            const dirs = await global.AIToolbox.listDirectories();
            const entry = dirs.find(d => d.id === dirId);
            if (!entry) throw new Error('Directory not found');
            const n = await global.AIToolbox.scanDirectory(entry, onProgress, true);
            return { indexed: n };
        },

        async listFolderIndex(dirId, subpath = '') {
            if (await checkServer()) {
                const p = new URLSearchParams();
                if (subpath) p.set('path', subpath);
                return api(`/directories/${encodeURIComponent(dirId)}/folders?${p}`);
            }
            return { path: subpath, breadcrumb: [], subfolders: [], files_count: 0 };
        },

        async queryMedia(opts = {}) {
            if (await checkServer()) {
                const p = new URLSearchParams();
                if (opts.search) p.set('search', opts.search);
                if (opts.tags?.length) p.set('tags', opts.tags.join(','));
                if (opts.type) p.set('type', opts.type);
                if (opts.dirId) p.set('dir_id', opts.dirId);
                if (opts.pathPrefix != null && !opts.search) p.set('path_prefix', opts.pathPrefix);
                if (opts.folderOnly) p.set('folder_only', 'true');
                if (opts.virtualRoot) p.set('virtual_root', opts.virtualRoot);
                if (opts.category) p.set('category', opts.category);
                if (opts.status) p.set('status', opts.status);
                if (opts.rankMin != null) p.set('rank_min', opts.rankMin);
                if (opts.sort) p.set('sort', opts.sort);
                if (opts.page != null) p.set('page', opts.page);
                if (opts.limit) p.set('limit', opts.limit);
                const res = await api(`/media?${p}`);
                if (res.items) res.items = res.items.map(normalizeMedia);
                return res;
            }
            const items = await global.AIToolbox.queryMedia({
                search: opts.search, tags: opts.tags, type: opts.type,
                dirId: opts.dirId, sort: opts.sort,
            });
            const page = opts.page || 0;
            const limit = opts.limit || 80;
            const start = page * limit;
            return { items: items.slice(start, start + limit), total: items.length, page, limit };
        },

        async getMedia(id) {
            if (await checkServer()) {
                const m = await api(`/media/item?mid=${encodeURIComponent(id)}`);
                return normalizeMedia(m);
            }
            return global.AIToolbox.getMedia(id);
        },

        async updateMedia(id, patchOrTags, notes, writeFileTags = true) {
            let body;
            if (patchOrTags && typeof patchOrTags === 'object' && !Array.isArray(patchOrTags)) {
                body = { ...patchOrTags };
                if (body.writeFileTags != null) {
                    body.write_file_tags = body.writeFileTags;
                    delete body.writeFileTags;
                }
                // Default: always write Explorer-visible file metadata unless explicitly false
                if (body.write_file_tags == null) body.write_file_tags = true;
            } else {
                body = { tags: patchOrTags, notes, write_file_tags: writeFileTags !== false };
            }
            if (await checkServer()) {
                const m = await api(`/media/patch?mid=${encodeURIComponent(id)}`, {
                    method: 'PATCH',
                    body: JSON.stringify(body),
                });
                return normalizeMedia(m);
            }
            const m = await global.AIToolbox.getMedia(id);
            if (body.tags) m.tags = body.tags;
            if (body.notes != null) m.notes = body.notes;
            if (body.rank != null) m.rank = body.rank;
            if (body.category != null) m.category = body.category;
            if (body.status != null) m.status = body.status;
            return global.AIToolbox.updateMedia(m);
        },

        async batchUpdateMeta(ids, patch) {
            if (await checkServer()) {
                return api('/media/batch-meta', { method: 'POST', body: JSON.stringify({ ids, ...patch }) });
            }
            throw new Error('Batch metadata requires server');
        },

        async getMetaFacets() {
            if (await checkServer()) return api('/meta/facets');
            return { categories: [], statuses: [] };
        },

        async listVirtualFolders() {
            if (await checkServer()) return api('/virtual-folders');
            return [];
        },

        async listVirtualFolderIndex(name, subpath = '') {
            if (await checkServer()) {
                const p = new URLSearchParams();
                if (subpath) p.set('path', subpath);
                return api(`/virtual-folders/${encodeURIComponent(name)}/folders?${p}`);
            }
            return { virtual_root: name, path: subpath, subfolders: [], files_count: 0, sources: [] };
        },

        async renameMedia(id, newName) {
            if (await checkServer()) {
                return api(`/media/rename?mid=${encodeURIComponent(id)}`, {
                    method: 'POST', body: JSON.stringify({ new_name: newName }),
                });
            }
            const m = await global.AIToolbox.getMedia(id);
            return global.AIToolbox.renameMedia(m, newName);
        },

        async batchRename(ids, pattern) {
            if (await checkServer()) {
                return api('/media/batch-rename', { method: 'POST', body: JSON.stringify({ ids, pattern }) });
            }
            const recs = [];
            for (const id of ids) {
                const m = await global.AIToolbox.getMedia(id);
                if (m) recs.push(m);
            }
            return { results: await global.AIToolbox.applyBatchRename(recs, pattern) };
        },

        async batchAddTags(ids, tags) {
            if (await checkServer()) {
                return api('/media/batch-tags', { method: 'POST', body: JSON.stringify({ ids, tags }) });
            }
            const recs = [];
            for (const id of ids) {
                const m = await global.AIToolbox.getMedia(id);
                if (m) recs.push(m);
            }
            await global.AIToolbox.batchAddTags(recs, tags);
            return { updated: recs.length };
        },

        async deleteMedia(ids, { toTrash = true } = {}) {
            const idList = Array.isArray(ids) ? ids : [ids];
            if (await checkServer()) {
                return api('/media/delete', {
                    method: 'POST',
                    body: JSON.stringify({ ids: idList, to_trash: toTrash }),
                });
            }
            throw new Error('Start server first (▶ Start Server) to delete files from disk');
        },

        async getAllTags() {
            if (await checkServer()) return api('/tags');
            return global.AIToolbox.getAllTags();
        },

        /** Write tags/rating into the real file (Windows Explorer System.Keywords / Rating). */
        async writeFileMetadata({ path, name, size, mtime, tags, rating, updateCatalog = true } = {}) {
            if (!(await checkServer())) {
                throw new Error('AI Toolbox server required to write file metadata');
            }
            return api('/fs/write-metadata', {
                method: 'POST',
                body: JSON.stringify({
                    path: path || null,
                    name: name || null,
                    size: size != null ? size : null,
                    mtime: mtime != null ? mtime : null,
                    tags: tags != null ? tags : null,
                    rating: rating != null ? rating : null,
                    update_catalog: updateCatalog,
                }),
            });
        },

        /**
         * Push catalog tags + star rating (rank) onto the real file for Explorer.
         * Used when "Update files on next" is on and the user advances pairs/videos.
         * @param {string|object} idOrMedia media id or media row
         * @param {{ tags?: string[], rank?: number, notes?: string }} [override]
         */
        async flushMediaTagsToFile(idOrMedia, override = {}) {
            if (!(await checkServer())) {
                throw new Error('Server offline — cannot write file tags/rating');
            }
            const id = typeof idOrMedia === 'string'
                ? idOrMedia
                : (idOrMedia && (idOrMedia.id || idOrMedia.mediaId));
            if (!id) throw new Error('No media id');
            let tags = override.tags;
            let rank = override.rank;
            let notes = override.notes;
            if (tags == null || rank == null || notes === undefined) {
                const m = typeof idOrMedia === 'object' && idOrMedia && (idOrMedia.tags != null || idOrMedia.rank != null)
                    ? idOrMedia
                    : await this.getMedia(id);
                if (!m) throw new Error('Media not found');
                if (tags == null) tags = m.tags || [];
                if (rank == null) rank = m.rank != null ? m.rank : 0;
                if (notes === undefined) notes = m.notes;
            }
            return this.updateMedia(id, {
                tags: Array.isArray(tags) ? tags : [],
                rank: Math.max(0, Math.min(5, parseInt(rank, 10) || 0)),
                notes: notes != null ? notes : undefined,
                write_file_tags: true,
            });
        },

        /** Flush both sides of a pair (before + after) to disk metadata. */
        async flushPairMediaToFiles(beforeId, afterId, opts = {}) {
            const out = { ok: true, before: null, after: null, errors: [] };
            if (beforeId) {
                try { out.before = await this.flushMediaTagsToFile(beforeId, opts.before || {}); }
                catch (e) { out.ok = false; out.errors.push('before: ' + (e.message || e)); }
            }
            if (afterId) {
                try { out.after = await this.flushMediaTagsToFile(afterId, opts.after || {}); }
                catch (e) { out.ok = false; out.errors.push('after: ' + (e.message || e)); }
            }
            return out;
        },

        async readFileMetadata(path) {
            if (!(await checkServer())) {
                throw new Error('AI Toolbox server required');
            }
            return api(`/fs/read-metadata?path=${encodeURIComponent(path)}`);
        },

        async getRenameHistory() {
            if (await checkServer()) return api('/rename-history');
            return global.AIToolbox.getRenameHistory();
        },

        normalizePair(p) {
            if (!p) return p;
            return {
                ...p,
                beforeMediaId: p.beforeMediaId || p.before_media_id,
                afterMediaId: p.afterMediaId || p.after_media_id,
                beforeName: p.beforeName || p.before_name || '',
                afterName: p.afterName || p.after_name || '',
                beforePath: p.beforePath || p.before_path || '',
                afterPath: p.afterPath || p.after_path || '',
                pairCode: p.pairCode || p.pair_code || '',
                pinned: !!(p.pinned),
            };
        },

        async listPairs(kind, { pinnedOnly = false } = {}) {
            if (await checkServer()) {
                const p = new URLSearchParams();
                if (kind) p.set('kind', kind);
                if (pinnedOnly) p.set('pinned', 'true');
                const q = p.toString();
                const rows = await api(`/pairs${q ? `?${q}` : ''}`);
                return (rows || []).map(r => this.normalizePair(r));
            }
            return global.AIToolbox.listPairs();
        },

        async savePair(data) {
            if (await checkServer() && data.beforeMediaId && data.afterMediaId) {
                const r = await api('/pairs', {
                    method: 'POST',
                    body: JSON.stringify({
                        name: data.name || '',
                        before_media_id: data.beforeMediaId,
                        after_media_id: data.afterMediaId,
                        kind: data.kind || 'video',
                        pinned: !!data.pinned,
                        notes: data.notes || '',
                    }),
                });
                return this.normalizePair(r);
            }
            return global.AIToolbox.savePair(data);
        },

        async savePairFromPaths(data) {
            const r = await api('/pairs/from-paths', {
                method: 'POST',
                body: JSON.stringify({
                    before_path: data.beforePath,
                    after_path: data.afterPath,
                    name: data.name || '',
                    kind: data.kind || 'video',
                    pinned: data.pinned !== false,
                    notes: data.notes || '',
                }),
            });
            return this.normalizePair(r);
        },

        async updatePair(id, patch) {
            const body = {};
            if (patch.name != null) body.name = patch.name;
            if (patch.pinned != null) body.pinned = patch.pinned;
            if (patch.notes != null) body.notes = patch.notes;
            const r = await api(`/pairs/${encodeURIComponent(id)}`, {
                method: 'PATCH',
                body: JSON.stringify(body),
            });
            return this.normalizePair(r);
        },

        /** Apply shared tags (and optional rank) to BOTH files in a before/after pair. */
        async tagPairBoth(pairId, { tags, rank, writeFileTags = true, sharedOnly = true } = {}) {
            if (!(await checkServer())) throw new Error('Start server first (▶ Start Server) to tag pairs');
            return api(`/pairs/${encodeURIComponent(pairId)}/tags`, {
                method: 'POST',
                body: JSON.stringify({
                    tags: tags || [],
                    rank: rank != null ? rank : null,
                    write_file_tags: writeFileTags !== false,
                    shared_only: sharedOnly !== false,
                }),
            });
        },

        /** Rebuild pair links from UP-#### tags after files were moved between folders. */
        async relinkPairsFromMetadata() {
            if (!(await checkServer())) throw new Error('Start server first (▶ Start Server)');
            return api('/pairs/relink', { method: 'POST', body: '{}' });
        },

        async pairHealth(relink = false) {
            if (!(await checkServer())) throw new Error('Start server first (▶ Start Server)');
            return api(`/pairs/health?relink=${relink ? 'true' : 'false'}`);
        },

        async verifyTags({ ids = null, limit = 500, fix = false } = {}) {
            if (!(await checkServer())) throw new Error('Start server first (▶ Start Server)');
            return api('/media/verify-tags', {
                method: 'POST',
                body: JSON.stringify({ ids, limit, fix }),
            });
        },

        async exportPairMap() {
            if (!(await checkServer())) throw new Error('Start server first (▶ Start Server)');
            return api('/pairs/export-map');
        },

        async importPairMap(data, writeFiles = true) {
            if (!(await checkServer())) throw new Error('Start server first (▶ Start Server)');
            return api('/pairs/import-map', {
                method: 'POST',
                body: JSON.stringify({ data, write_files: writeFiles }),
            });
        },

        async archivePair(pairId, dest) {
            if (!(await checkServer())) throw new Error('Start server first (▶ Start Server)');
            return api(`/pairs/${encodeURIComponent(pairId)}/archive`, {
                method: 'POST',
                body: JSON.stringify({ dest, pair_id: pairId }),
            });
        },

        async listSmartSearches() {
            if (!(await checkServer())) return [];
            return api('/smart-searches');
        },

        async addSmartSearch(name, query) {
            if (!(await checkServer())) throw new Error('Start server first (▶ Start Server)');
            return api('/smart-searches', {
                method: 'POST',
                body: JSON.stringify({ name, query }),
            });
        },

        async deleteSmartSearch(id) {
            if (!(await checkServer())) throw new Error('Start server first (▶ Start Server)');
            return api(`/smart-searches/${encodeURIComponent(id)}`, { method: 'DELETE' });
        },

        async runSmartSearch(query, page = 0, limit = 80) {
            if (!(await checkServer())) throw new Error('Start server first (▶ Start Server)');
            return api('/smart-searches/run', {
                method: 'POST',
                body: JSON.stringify({ query, page, limit }),
            });
        },

        async autoPairUpscaled(opts = {}) {
            return api('/pairs/auto-upscale', {
                method: 'POST',
                body: JSON.stringify({
                    min_confidence: opts.minConfidence ?? 0.7,
                    limit: opts.limit ?? 200,
                    dry_run: !!opts.dryRun,
                    pin: opts.pin !== false,
                    before_dir_id: opts.beforeDirId || opts.before_dir_id || null,
                    after_dir_id: opts.afterDirId || opts.after_dir_id || null,
                    require_upscale_name: opts.requireUpscaleName ?? opts.require_upscale_name ?? null,
                }),
            });
        },

        async getPair(id) {
            if (await checkServer()) return this.normalizePair(await api(`/pairs/${encodeURIComponent(id)}`));
            return global.AIToolbox.getPair(id);
        },

        async deletePair(id) {
            if (await checkServer()) return api(`/pairs/${encodeURIComponent(id)}`, { method: 'DELETE' });
            return global.AIToolbox.deletePair(id);
        },

        /**
         * Guided match: top candidates for one media id (process-of-elimination).
         * @param {string} mediaId
         * @param {{ limit?: number, minRatio?: number, excludeIds?: string[], afterDirId?: string }} [opts]
         */
        async pairCandidates(mediaId, opts = {}) {
            if (!(await checkServer())) throw new Error('Start server first (▶ Start Server)');
            const exclude = opts.excludeIds || opts.exclude_ids || [];
            return api('/pairs/candidates', {
                method: 'POST',
                body: JSON.stringify({
                    media_id: mediaId,
                    limit: opts.limit ?? 10,
                    min_ratio: opts.minRatio ?? opts.min_ratio ?? 0.35,
                    exclude_ids: exclude,
                    unpaired_only: opts.unpairedOnly !== false,
                    tail_len: opts.tailLen ?? opts.tail_len ?? 5,
                    after_dir_id: opts.afterDirId || opts.after_dir_id || null,
                    before_dir_id: opts.beforeDirId || opts.before_dir_id || null,
                }),
            });
        },

        /** Unpaired queue for guided match (sources first). */
        async pairAnchors(opts = {}) {
            if (!(await checkServer())) return { anchors: [] };
            const p = new URLSearchParams();
            if (opts.limit) p.set('limit', opts.limit);
            if (opts.kind) p.set('kind', opts.kind);
            if (opts.dirId || opts.dir_id) p.set('dir_id', opts.dirId || opts.dir_id);
            if (opts.preferSources === false) p.set('prefer_sources', 'false');
            return api(`/pairs/anchors?${p}`);
        },

        async suggestPairs(limit = 30, opts = {}) {
            if (!(await checkServer())) return [];
            const beforeDirId = opts.beforeDirId || opts.before_dir_id || null;
            const afterDirId = opts.afterDirId || opts.after_dir_id || null;
            const body = {
                limit: limit ?? 50,
                min_ratio: opts.minRatio ?? opts.min_ratio ?? 0.5,
                before_dir_id: beforeDirId,
                after_dir_id: afterDirId,
                unpaired_only: opts.unpairedOnly !== false,
                kind: opts.kind || null,
                tail_len: opts.tailLen ?? opts.tail_len ?? 5,
                use_tail: opts.useTail !== false && opts.use_tail !== false,
                use_digits: opts.useDigits !== false && opts.use_digits !== false,
                use_fuzzy: opts.useFuzzy !== false && opts.use_fuzzy !== false,
                use_folder: opts.useFolder !== false && opts.use_folder !== false,
            };
            // Prefer POST so multi-signal knobs always apply
            if (beforeDirId || afterDirId || opts.minRatio != null || opts.tailLen != null
                || opts.useTail != null || opts.useDigits != null || opts.useFuzzy != null
                || opts.forcePost) {
                const r = await api('/pairs/suggest', {
                    method: 'POST',
                    body: JSON.stringify(body),
                });
                return Array.isArray(r) ? r : (r.suggestions || []);
            }
            const q = new URLSearchParams({
                limit: String(limit ?? 40),
                min_ratio: String(body.min_ratio),
                tail_len: String(body.tail_len),
            });
            return api(`/pairs/suggest?${q}`);
        },

        async captureThumbnail(mediaId, timestamp = 0) {
            if (await checkServer()) {
                return api(`/media/thumbnail?mid=${encodeURIComponent(mediaId)}`, {
                    method: 'POST',
                    body: JSON.stringify({ timestamp, sidecar: true }),
                });
            }
            throw new Error('ffmpeg capture requires server');
        },

        mediaFileUrl(mediaId) {
            return `${apiBase()}/media/file?mid=${encodeURIComponent(mediaId)}`;
        },

        thumbUrl(mediaId) {
            return `${apiBase()}/thumb?mid=${encodeURIComponent(mediaId)}`;
        },

        async resolvePaths(ids) {
            if (await checkServer()) {
                return api('/media/paths', { method: 'POST', body: JSON.stringify({ ids }) });
            }
            throw new Error('Start server first (▶ Start Server) to resolve disk paths');
        },

        async listPlaylists() {
            if (await checkServer()) return api('/playlists');
            return [];
        },

        async createPlaylist(name, description = '', kind = 'mixed') {
            if (await checkServer()) {
                return api('/playlists', {
                    method: 'POST',
                    body: JSON.stringify({ name, description, kind }),
                });
            }
            throw new Error('Playlists require server');
        },

        async getPlaylist(id) {
            if (await checkServer()) return api(`/playlists/${encodeURIComponent(id)}`);
            throw new Error('Playlists require server');
        },

        async updatePlaylist(id, patch) {
            if (await checkServer()) {
                return api(`/playlists/${encodeURIComponent(id)}`, {
                    method: 'PATCH',
                    body: JSON.stringify(patch),
                });
            }
            throw new Error('Playlists require server');
        },

        async deletePlaylist(id) {
            if (await checkServer()) {
                return api(`/playlists/${encodeURIComponent(id)}`, { method: 'DELETE' });
            }
            throw new Error('Playlists require server');
        },

        async addToPlaylist(playlistId, ids) {
            if (await checkServer()) {
                return api(`/playlists/${encodeURIComponent(playlistId)}/items`, {
                    method: 'POST',
                    body: JSON.stringify({ ids }),
                });
            }
            throw new Error('Playlists require server');
        },

        async removeFromPlaylist(playlistId, mediaId) {
            if (await checkServer()) {
                return api(`/playlists/${encodeURIComponent(playlistId)}/items?mid=${encodeURIComponent(mediaId)}`, {
                    method: 'DELETE',
                });
            }
            throw new Error('Playlists require server');
        },

        async getPlaylistPaths(playlistId) {
            if (await checkServer()) return api(`/playlists/${encodeURIComponent(playlistId)}/paths`);
            throw new Error('Playlists require server');
        },

        async getSettings() {
            if (await checkServer()) return api('/settings');
            return global.AIToolbox?.getSettings() || {};
        },

        async saveSettings(data) {
            if (await checkServer()) return api('/settings', { method: 'PATCH', body: JSON.stringify(data) });
            return global.AIToolbox.saveSettings(data);
        },

        comparatorUrl(pair, settings) {
            const base = pair.kind === 'image'
                ? (settings?.comparator_image || '../Image tools/Image Comparitor With Slider.html')
                : (settings?.comparator_video || '../Video Tools/Video Comparison Slider Tool.html');
            return `${base}?pair=${pair.id}&server=1`;
        },

        async vsrGetConfig() { return api('/vsr/config'); },
        async vsrSaveConfig(config) { return api('/vsr/config', { method: 'PATCH', body: JSON.stringify({ config }) }); },
        async vsrPreview() { return api('/vsr/preview'); },
        async vsrLearn(pairs) { return api('/vsr/learn', { method: 'POST', body: JSON.stringify({ pairs }) }); },
        async vsrApply(stage, dryRun = false) {
            return api('/vsr/apply', { method: 'POST', body: JSON.stringify({ stage: String(stage), dry_run: dryRun }) });
        },
        /**
         * Apply only selected renames (pair review queue).
         * @param {{path:string,new_name:string}[]} renames
         * @param {boolean} [dryRun]
         */
        async vsrApplySelected(renames, dryRun = false) {
            return api('/vsr/apply-selected', {
                method: 'POST',
                body: JSON.stringify({ renames: renames || [], dry_run: !!dryRun }),
            });
        },
        /** Stream a local file path through the toolbox server (for dual preview). */
        fileServeUrl(path) {
            if (!path) return '';
            return `${apiBase()}/files/serve?path=${encodeURIComponent(path)}`;
        },
        async getPairPaths(pairId) {
            return api(`/pairs/${encodeURIComponent(pairId)}/paths`);
        },
        async scanDuplicates(folder, deep = false, opts = {}) {
            const p = new URLSearchParams({
                folder,
                deep: String(!!deep),
                match_mode: opts.matchMode || 'quick',
                file_types: opts.fileTypes || 'video',
            });
            return api(`/duplicates/scan?${p}`);
        },

        scanDuplicatesStream(folder, opts = {}, onProgress) {
            const p = new URLSearchParams({
                folder,
                deep: String(!!opts.deep),
                match_mode: opts.matchMode || 'quick',
                file_types: opts.fileTypes || 'all',
            });
            return new Promise((resolve, reject) => {
                const es = new EventSource(`${apiBase()}/duplicates/scan/stream?${p}`);
                es.onmessage = e => {
                    const d = JSON.parse(e.data);
                    if (d.error) { es.close(); reject(new Error(d.error)); }
                    else if (d.done) { es.close(); resolve(d.result); }
                    else if (onProgress) onProgress(d.count, d.file);
                };
                es.onerror = () => { es.close(); reject(new Error('Duplicate scan stream failed')); };
            });
        },

        async deleteDuplicateFiles({ keepPath, deletePaths, toTrash = true, dryRun = false }) {
            return api('/duplicates/delete', {
                method: 'POST',
                body: JSON.stringify({
                    keep_path: keepPath || null,
                    delete_paths: deletePaths,
                    to_trash: toTrash,
                    dry_run: dryRun,
                }),
            });
        },

        async mergeDuplicateGroup({ keepPath, groupPaths, toTrash = true, dryRun = false }) {
            return api('/duplicates/merge', {
                method: 'POST',
                body: JSON.stringify({
                    keep_path: keepPath,
                    group_paths: groupPaths,
                    to_trash: toTrash,
                    dry_run: dryRun,
                }),
            });
        },

        async getFileInfo(path) {
            return api(`/files/info?path=${encodeURIComponent(path)}`);
        },

        /** PC Report Library / system diagnostics (this machine only). */
        async diagnosticsStatus() {
            return api('/diagnostics/status');
        },
        async diagnosticsCatalog() {
            return api('/diagnostics/catalog');
        },
        async diagnosticsPack() {
            return api('/diagnostics/pack', { method: 'POST', body: '{}' });
        },
        async diagnosticsRun(openViewer = false) {
            return api('/diagnostics/run', {
                method: 'POST',
                body: JSON.stringify({ open_viewer: !!openViewer }),
            });
        },

        async getFileText(path, maxBytes = 65536) {
            return api(`/files/text?path=${encodeURIComponent(path)}&max_bytes=${maxBytes}`);
        },
        async getTagRules() { return api('/tag-rules'); },
        async saveTagRules(rules) { return api('/tag-rules', { method: 'PATCH', body: JSON.stringify(rules) }); },
        async applyTagRules(dirId) {
            const q = dirId ? `?dir_id=${encodeURIComponent(dirId)}` : '';
            return api(`/tag-rules/apply${q}`, { method: 'POST' });
        },

        /**
         * First-run / setup status from the server (marker + critical checks).
         * Returns null-ish offline fields when the backend is down.
         */
        async getSetupStatus() {
            // Browser cache: after a successful setup this origin hides first-run even offline
            if (API.isSetupCompleteCached()) {
                const online = await checkServer(false, 1200);
                if (!online) {
                    return {
                        complete: true,
                        readyToLaunch: true,
                        showFirstRun: false,
                        offline: true,
                        cached: true,
                        missing: [],
                        checks: {},
                    };
                }
            }
            if (!(await checkServer(false, 1200))) {
                return {
                    complete: false,
                    readyToLaunch: false,
                    showFirstRun: true,
                    offline: true,
                    missing: ['Server offline — use One-Click Launch or Complete Setup'],
                    checks: {},
                };
            }
            const status = await api('/setup/status', { timeoutMs: 5000 });
            if (status && status.complete) {
                API.markSetupCompleteCached(true);
            }
            return status;
        },

        /**
         * One-click launch helpers via custom protocol (Chrome shell + server).
         * Prefer Scripts/Launch-FAFOToolbox.ps1 from the desktop bat for true one-click.
         */
        launchToolboxShell() {
            return tryProtocolLaunch('launch');
        },

        /** true when machine-local setup marker + critical checks are complete (cached). */
        isSetupCompleteCached() {
            try {
                return localStorage.getItem('aitoolbox_setup_complete') === '1';
            } catch {
                return false;
            }
        },

        markSetupCompleteCached(complete = true) {
            try {
                if (complete) {
                    localStorage.setItem('aitoolbox_setup_complete', '1');
                    localStorage.setItem('aitoolbox_setup_completed_at', new Date().toISOString());
                } else {
                    localStorage.removeItem('aitoolbox_setup_complete');
                    localStorage.removeItem('aitoolbox_setup_completed_at');
                }
            } catch { /* ignore */ }
        },
    };

    global.AIToolboxAPI = API;

    // Auto-keep servers alive while any toolbox page is open (no user action needed)
    if (typeof document !== 'undefined') {
        const bootKeepAlive = () => {
            try { startKeepAlive(); } catch { /* ignore */ }
        };
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', bootKeepAlive, { once: true });
        } else {
            bootKeepAlive();
        }
    }
})(typeof window !== 'undefined' ? window : globalThis);