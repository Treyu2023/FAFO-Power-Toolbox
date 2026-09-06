/**
 * Shared media pipeline: Inbox / Before / After workspace, leftover queue,
 * dry-run Trust, method badges, hub-embedded chrome hide.
 *
 * AIToolboxPipeline.boot({ beforeSelect, afterSelect, leftoverHost, onApply })
 */
(function (global) {
    'use strict';

    function D() { return global.AIToolboxDom || null; }
    function API() { return global.AIToolboxAPI || null; }
    function UI() { return global.AIToolboxUI || null; }

    function el(id) {
        const d = D();
        if (d && d.el) return d.el(id);
        try { return typeof id === 'string' ? document.getElementById(id) : id; } catch (_) { return null; }
    }
    function esc(s) {
        const d = D();
        if (d && d.escapeHtml) return d.escapeHtml(s);
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }
    function toast(msg, kind) {
        try { UI() && UI().toast && UI().toast(msg, kind || 'ok'); } catch (_) {}
    }
    function fmtBytes(n) {
        n = Number(n) || 0;
        if (n < 1024) return n + ' B';
        if (n < 1048576) return (n / 1024).toFixed(1) + ' KB';
        if (n < 1073741824) return (n / 1048576).toFixed(1) + ' MB';
        return (n / 1073741824).toFixed(2) + ' GB';
    }

    function isEmbedded() {
        try {
            const q = new URLSearchParams(location.search || '');
            if (q.get('embedded') === '1' || q.get('hub') === '1') return true;
        } catch (_) {}
        try { if (global.parent && global.parent !== global) return true; } catch (_) { return true; }
        return false;
    }

    function markEmbedded() {
        if (!isEmbedded()) return false;
        try {
            document.documentElement.classList.add('hub-embedded');
            document.body && document.body.classList.add('hub-embedded');
        } catch (_) {}
        return true;
    }

    function methodKind(reason) {
        const r = String(reason || '').toLowerCase();
        if (r.indexOf('pid') === 0 || r.indexOf('pid_') >= 0) return 'pid';
        if (r.indexOf('stem') >= 0 || r.indexOf('tail') >= 0 || r.indexOf('digit') >= 0) return 'stem';
        if (r.indexOf('folder') >= 0) return 'stem';
        return 'fuzzy';
    }

    function methodLabel(reason) {
        const k = methodKind(reason);
        if (k === 'pid') return 'PID';
        if (k === 'stem') return String(reason || 'stem').split('·')[0].trim() || 'stem';
        return String(reason || 'fuzzy').split('·')[0].trim() || 'fuzzy';
    }

    function paintMethodBadge(node, reason) {
        const n = typeof node === 'string' ? el(node) : node;
        if (!n) return;
        const k = methodKind(reason);
        n.className = 'fafo-method ' + k;
        n.textContent = methodLabel(reason);
        n.title = reason || '';
        n.hidden = !reason;
    }

    function selectByPath(selectEl, path) {
        const sel = typeof selectEl === 'string' ? el(selectEl) : selectEl;
        if (!sel || !path) return false;
        const want = String(path).replace(/\\/g, '/').toLowerCase();
        for (let i = 0; i < sel.options.length; i++) {
            const opt = sel.options[i];
            const hay = (opt.getAttribute('data-path') || opt.textContent || opt.value || '')
                .replace(/\\/g, '/').toLowerCase();
            if (opt.value && hay && (hay === want || hay.endsWith(want) || want.endsWith(hay))) {
                sel.value = opt.value;
                sel.dispatchEvent(new Event('change', { bubbles: true }));
                return true;
            }
        }
        return false;
    }

    function renderPipelineBar(host, pipe, opts) {
        const root = typeof host === 'string' ? el(host) : host;
        if (!root) return;
        opts = opts || {};
        pipe = pipe || {};
        const roles = [
            { key: 'inbox', label: 'Inbox', hint: 'New downloads / Imagine HAVE' },
            { key: 'before', label: 'Pre-scaled', hint: 'Source after processing' },
            { key: 'after', label: 'After', hint: '4K / 96fps result — matched by PID' },
        ];
        root.classList.add('fafo-pipe-bar');
        root.innerHTML = roles.map((r) => {
            const row = pipe[r.key] || {};
            const path = row.path || '';
            const miss = path && row.exists === false;
            const live = row.live || {};
            const delta = Number(live.delta);
            let liveBit = '';
            if (miss) liveBit = '';
            else if (live.scanned) liveBit = ' <span class="fafo-pipe-live">indexed ' + Number(live.indexed || live.catalog_count || 0) + '</span>';
            else if (delta > 0) liveBit = ' <span class="fafo-pipe-stale">+' + delta + ' new</span>';
            else if (delta < 0) liveBit = ' <span class="fafo-pipe-stale">' + delta + ' gone</span>';
            else if (live.catalog_count != null) liveBit = ' <span class="fafo-pipe-live">current</span>';
            return '<div class="fafo-pipe-slot" data-role="' + r.key + '">' +
                '<div class="fafo-pipe-k">' + esc(r.label) +
                (miss ? ' <span class="fafo-pipe-miss">missing</span>' : '') + liveBit + '</div>' +
                '<div class="fafo-pipe-p" title="' + esc(r.hint) + '">' + esc(path || '— not set —') + '</div>' +
                '</div>';
        }).join('') +
            '<div class="fafo-pipe-actions">' +
            (opts.hideApply ? '' : '<button type="button" class="ui-btn ghost" id="fafoPipeApply" style="padding:4px 8px;font-size:11px">Use on this desk</button>') +
            '<button type="button" class="ui-btn ghost" id="fafoPipeEdit" style="padding:4px 8px;font-size:11px">Set folders</button>' +
            '</div>';
        const apply = root.querySelector('#fafoPipeApply');
        if (apply) apply.onclick = () => { if (typeof opts.onApply === 'function') opts.onApply(pipe); };
        const edit = root.querySelector('#fafoPipeEdit');
        if (edit) edit.onclick = () => promptSetPipeline(pipe, opts);
    }

    async function promptSetPipeline(pipe, opts) {
        pipe = pipe || {};
        const inbox = prompt('Inbox folder (new downloads / Imagine HAVE):', (pipe.inbox && pipe.inbox.path) || '');
        if (inbox === null) return null;
        const before = prompt('Pre-scaled / Before folder:', (pipe.before && pipe.before.path) || '');
        if (before === null) return null;
        const after = prompt('After folder (4K / 96fps):', (pipe.after && pipe.after.path) || '');
        if (after === null) return null;
        try {
            const next = await API().setPipeline({ inbox: inbox.trim(), before: before.trim(), after: after.trim() });
            toast('Pipeline folders saved', 'ok');
            if (typeof opts.onApply === 'function') opts.onApply(next);
            return next;
        } catch (e) {
            toast(e.message || String(e), 'warn');
            return null;
        }
    }

    function leftoverSummary(data) {
        data = data || {};
        const u = Number(data.unique_trusted || data.unique_ready || 0);
        const a = (data.ambiguous || []).length;
        const f = (data.fuzzy_ids || []).length;
        const r = Number(data.rejected || 0);
        const bits = [];
        if (u) bits.push(u + ' unique');
        if (a) bits.push(a + ' ambiguous');
        if (f) bits.push(f + ' leftover');
        if (r) bits.push(r + ' never-again');
        return bits.join(' · ') || 'Queue empty';
    }

    function renderLeftover(host, data, opts) {
        const root = typeof host === 'string' ? el(host) : host;
        if (!root) return;
        opts = opts || {};
        data = data || {};
        root.classList.add('fafo-leftover');
        root.innerHTML =
            '<span class="fafo-leftover-k">Leftover</span>' +
            '<span class="fafo-leftover-s">' + esc(data.note || leftoverSummary(data)) + '</span>' +
            '<button type="button" class="ui-btn ghost" id="fafoLeftoverResume" style="padding:3px 8px;font-size:10px;margin-left:auto">Resume leftover</button>' +
            '<button type="button" class="ui-btn ghost" id="fafoLeftoverRebuild" style="padding:3px 8px;font-size:10px">Rebuild</button>';
        const resume = root.querySelector('#fafoLeftoverResume');
        if (resume) resume.onclick = () => { if (typeof opts.onResume === 'function') opts.onResume(data); };
        const rebuild = root.querySelector('#fafoLeftoverRebuild');
        if (rebuild) rebuild.onclick = () => { if (typeof opts.onRebuild === 'function') opts.onRebuild(data); };
    }

    function ensureModal() {
        let m = document.getElementById('fafoDryRunModal');
        if (m) return m;
        m = document.createElement('div');
        m.id = 'fafoDryRunModal';
        m.className = 'fafo-dryrun-bg';
        m.innerHTML =
            '<div class="fafo-dryrun" role="dialog" aria-modal="true">' +
            '<h2 id="fafoDryRunTitle">Trust unique PID matches?</h2>' +
            '<p class="fafo-dryrun-lead" id="fafoDryRunLead"></p>' +
            '<div class="fafo-dryrun-list" id="fafoDryRunList"></div>' +
            '<div class="fafo-dryrun-actions">' +
            '<button type="button" class="ui-btn ghost" id="fafoDryRunCancel">Cancel</button>' +
            '<button type="button" class="ui-btn primary" id="fafoDryRunGo">Trust selected</button>' +
            '</div></div>';
        document.body.appendChild(m);
        return m;
    }

    function dryRunTrust(rows, opts) {
        opts = opts || {};
        rows = (rows || []).filter((r) => r && r.pid);
        return new Promise((resolve) => {
            if (!rows.length) { resolve({ confirmed: false, pids: [] }); return; }
            const m = ensureModal();
            const title = el('fafoDryRunTitle');
            const lead = el('fafoDryRunLead');
            const list = el('fafoDryRunList');
            if (title) title.textContent = opts.title || ('Trust ' + rows.length + ' unique PID pair' + (rows.length === 1 ? '' : 's') + '?');
            if (lead) lead.innerHTML = opts.body ||
                'Uncheck any row you do not trust. Ambiguous 3+ groups are not in this list.';
            list.innerHTML = rows.map((r, i) => {
                const pid = esc(r.pid);
                const bs = fmtBytes(r.before_size);
                const as = fmtBytes(r.after_size);
                return '<label class="fafo-dryrun-row">' +
                    '<input type="checkbox" data-dry-pid="' + pid + '" checked>' +
                    '<span class="pid">' + pid + '</span>' +
                    '<span class="names"><b>' + esc(r.before_name || '') + '</b> → ' +
                    esc(r.after_name || '') + '</span>' +
                    '<span class="sz">' + bs + ' → ' + as + '</span>' +
                    '</label>';
            }).join('');
            m.classList.add('on');
            const finish = (ok) => {
                m.classList.remove('on');
                if (!ok) { resolve({ confirmed: false, pids: [] }); return; }
                const pids = Array.from(list.querySelectorAll('input[data-dry-pid]:checked'))
                    .map((n) => n.getAttribute('data-dry-pid'))
                    .filter(Boolean);
                resolve({ confirmed: true, pids });
            };
            el('fafoDryRunCancel').onclick = () => finish(false);
            el('fafoDryRunGo').onclick = () => finish(true);
            m.onclick = (e) => { if (e.target === m) finish(false); };
        });
    }

    function filmstripHtml(members, pid) {
        const list = members || [];
        if (!list.length) return '';
        return '<div class="fafo-filmstrip" data-pid="' + esc(pid || '') + '">' +
            list.map((m) => {
                const role = (m.role || '').toLowerCase();
                return '<button type="button" class="fafo-film-card' + (role ? ' ' + role : '') +
                    '" data-member-id="' + esc(m.id || '') + '" title="' + esc(m.name || '') + '">' +
                    '<span class="role">' + esc(role || 'file') + '</span>' +
                    '<span class="nm">' + esc(m.name || '') + '</span>' +
                    '<span class="sz">' + fmtBytes(m.size) + '</span>' +
                    '</button>';
            }).join('') + '</div>';
    }

    async function inheritFolders(opts) {
        opts = opts || {};
        const api = API();
        if (!api || !api.getPipeline) return null;
        try {
            if (!(await api.isOnline?.(false, 1500))) return null;
            const pipe = await api.getPipeline();
            if (opts.beforeSelect) selectByPath(opts.beforeSelect, pipe.before && pipe.before.path);
            if (opts.afterSelect) selectByPath(opts.afterSelect, pipe.after && pipe.after.path);
            if (opts.inboxInput) {
                const n = typeof opts.inboxInput === 'string' ? el(opts.inboxInput) : opts.inboxInput;
                if (n && pipe.inbox && pipe.inbox.path && !n.value) n.value = pipe.inbox.path;
            }
            if (opts.beforeInput) {
                const n = typeof opts.beforeInput === 'string' ? el(opts.beforeInput) : opts.beforeInput;
                if (n && pipe.before && pipe.before.path && !n.value) n.value = pipe.before.path;
            }
            if (opts.afterInput) {
                const n = typeof opts.afterInput === 'string' ? el(opts.afterInput) : opts.afterInput;
                if (n && pipe.after && pipe.after.path && !n.value) n.value = pipe.after.path;
            }
            if (opts.host) renderPipelineBar(opts.host, pipe, opts);
            return pipe;
        } catch (_) {
            return null;
        }
    }

    async function persistReject(anchorId, candidateId, extra) {
        const api = API();
        if (!api || !api.rejectCandidate || !anchorId || !candidateId) return;
        try { await api.rejectCandidate(anchorId, candidateId, extra || {}); } catch (_) {}
    }

    let lastLiveAt = 0;
    const LIVE_COOLDOWN_MS = 20000;

    function applyLiveToPipe(pipe, live) {
        if (!pipe || !live || !Array.isArray(live.roles)) return pipe;
        live.roles.forEach(function (r) {
            if (!r || !r.role || !pipe[r.role]) return;
            pipe[r.role].live = r;
            if (r.dir_id) pipe[r.role].dir_id = r.dir_id;
        });
        pipe.liveNote = live.note || '';
        return pipe;
    }

    async function refreshLive(opts) {
        opts = opts || {};
        const api = API();
        if (!api || !api.refreshLivePipeline) return null;
        const now = Date.now();
        if (!opts.force && lastLiveAt && (now - lastLiveAt) < LIVE_COOLDOWN_MS) return null;
        try {
            if (!(await api.isOnline?.(false, 1500))) return null;
            lastLiveAt = now;
            const live = await api.refreshLivePipeline(opts);
            lastLiveAt = Date.now();
            applyLiveToPipe(opts.pipe, live);
            const scanned = (live && live.roles || []).filter(function (r) { return r && r.scanned; });
            if (scanned.length && !opts.quiet) toast(live.note || 'Inbox / After catalog updated', 'ok');
            if (opts.host && opts.pipe) renderPipelineBar(opts.host, opts.pipe, opts);
            if (typeof opts.onLive === 'function') opts.onLive(live, opts.pipe);
            return live;
        } catch (_) {
            return null;
        }
    }

    async function boot(opts) {
        opts = opts || {};
        markEmbedded();
        const pipe = await inheritFolders(opts);
        opts.pipe = pipe;
        await refreshLive(opts);
        if (opts.leftoverHost) {
            try {
                const left = await API()?.getLeftover?.();
                if (left) renderLeftover(opts.leftoverHost, left, opts);
            } catch (_) {}
        }
        try {
            window.addEventListener('message', function (ev) {
                try {
                    if (ev.origin !== location.origin) return;
                    const data = ev.data;
                    if (!data || data.type !== 'fafo-hub-focus') return;
                    refreshLive(Object.assign({}, opts, { pipe: pipe, quiet: true }));
                } catch (_) {}
            });
        } catch (_) {}
        return pipe;
    }

    function goTab(tab) {
        tab = String(tab || '').replace(/^#/, '');
        if (!tab) tab = 'library';
        try {
            if (global.parent && global.parent !== global) {
                global.parent.postMessage({ type: 'fafo-hub-tab', tab: tab }, location.origin);
                return;
            }
        } catch (_) {}
        try {
            const here = String(location.pathname || '');
            if (/Media%20Hub\.html$/i.test(here) || /Media Hub\.html$/i.test(here)) {
                location.hash = tab;
                return;
            }
        } catch (_) {}
        location.href = 'Media Hub.html#' + tab;
    }

    global.AIToolboxPipeline = {
        boot, markEmbedded, isEmbedded, inheritFolders, refreshLive, goTab,
        renderPipelineBar, renderLeftover, leftoverSummary,
        dryRunTrust, filmstripHtml, paintMethodBadge, methodKind, methodLabel,
        persistReject, promptSetPipeline, fmtBytes, esc,
    };

    if (typeof document !== 'undefined') {
        const go = () => { try { markEmbedded(); } catch (_) {} };
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', go, { once: true });
        else go();
    }
})(typeof window !== 'undefined' ? window : globalThis);
