/**
 * Catalog picker for Video / Image comparators.
 * Search the toolbox catalog, show both filenames, and highlight a slice of
 * the first name to live-refine the second-file search.
 *
 * AIToolboxCatalogPick.attach({ beforeZone, afterZone, type, onPick })
 */
(function (global) {
    'use strict';

    let lastUi = null;
    let stylesOnce = false;

    function esc(s) {
        const d = global.AIToolboxDom;
        if (d && d.escapeHtml) return d.escapeHtml(s);
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function qs(sel, root) {
        if (!sel) return null;
        if (typeof sel !== 'string') return sel;
        try { return (root || document).querySelector(sel); } catch (_) { return null; }
    }

    function injectStyles() {
        if (stylesOnce) return;
        stylesOnce = true;
        const css = document.createElement('style');
        css.setAttribute('data-atx', 'catalog-pick');
        css.textContent = [
            '.atx-pick{margin-top:8px;text-align:left}',
            '.atx-pick input{width:100%;box-sizing:border-box;background:#000;color:#e8eef6;border:1px solid rgba(0,243,255,.35);border-radius:6px;padding:6px 8px;font-size:11px}',
            '.atx-pick input:focus{outline:none;border-color:#00f3ff;box-shadow:0 0 8px rgba(0,243,255,.25)}',
            '.atx-pick-list{max-height:148px;overflow:auto;margin-top:4px;border:1px solid rgba(255,255,255,.08);border-radius:6px;background:rgba(0,0,0,.45)}',
            '.atx-pick-list:empty{display:none}',
            '.atx-pick-item{display:block;width:100%;text-align:left;background:transparent;border:0;border-bottom:1px solid rgba(255,255,255,.05);color:#e8eef6;padding:6px 8px;cursor:pointer;font-size:11px;line-height:1.35}',
            '.atx-pick-item:hover,.atx-pick-item:focus{background:rgba(0,243,255,.12)}',
            '.atx-pick-item .n{font-weight:700;display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
            '.atx-pick-item .p{color:#8b9bb0;font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
            '.atx-pick-empty{padding:8px;color:#8b9bb0;font-size:10px}',
            '.atx-cmp-names{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:10px 0 4px;text-align:left}',
            '.atx-cmp-names .lab{font-size:9px;letter-spacing:.08em;text-transform:uppercase;color:#8b9bb0;margin-bottom:3px}',
            '.atx-cmp-name{font-size:12px;font-weight:700;color:#f2f4f8;user-select:text;-webkit-user-select:text;cursor:text;padding:6px 8px;border-radius:6px;border:1px dashed rgba(0,243,255,.28);background:rgba(0,0,0,.35);word-break:break-all;min-height:2.2em}',
            '.atx-cmp-name.src{border-color:rgba(245,197,66,.55)}',
            '.atx-cmp-hint{grid-column:1/-1;font-size:10px;color:#8b9bb0;line-height:1.4}',
            '.atx-cmp-hint kbd{font:10px Consolas,monospace;color:#f5c542;padding:1px 4px;border:1px solid rgba(245,197,66,.4);border-radius:3px}',
            '.atx-pick-restore{margin-top:6px;font-size:10px;padding:4px 8px;border-radius:999px;border:1px solid rgba(0,243,255,.35);background:transparent;color:#00f3ff;cursor:pointer}',
        ].join('');
        document.head.appendChild(css);
    }

    function debounce(fn, ms) {
        let t = null;
        return function () {
            const args = arguments;
            const self = this;
            if (t) clearTimeout(t);
            t = setTimeout(function () { fn.apply(self, args); }, ms);
        };
    }

    function api() {
        return global.AIToolboxAPI || null;
    }

    function mountSlot(zone, opts) {
        const wrap = document.createElement('div');
        wrap.className = 'atx-pick';
        wrap.dataset.slot = opts.slot;
        const input = document.createElement('input');
        input.type = 'search';
        input.autocomplete = 'off';
        input.placeholder = opts.slot === 'before'
            ? 'Search catalog — original / before'
            : 'Search catalog — upscaled / after';
        input.setAttribute('aria-label', input.placeholder);
        const list = document.createElement('div');
        list.className = 'atx-pick-list';
        list.setAttribute('role', 'listbox');
        wrap.appendChild(input);
        wrap.appendChild(list);
        zone.appendChild(wrap);

        let gen = 0;
        async function search(q) {
            const needle = String(q == null ? input.value : q).trim();
            if (q != null && q !== input.value) input.value = needle;
            const g = ++gen;
            if (needle.length < 2) {
                list.innerHTML = '';
                return;
            }
            const A = api();
            if (!A || typeof A.queryMedia !== 'function') {
                list.innerHTML = '<div class="atx-pick-empty">Start the toolbox server to search the catalog.</div>';
                return;
            }
            list.innerHTML = '<div class="atx-pick-empty">Searching…</div>';
            try {
                const res = await A.queryMedia({
                    search: needle,
                    type: opts.type || undefined,
                    limit: 24,
                    sort: 'name',
                });
                if (g !== gen) return;
                const items = (res && res.items) || [];
                if (!items.length) {
                    list.innerHTML = '<div class="atx-pick-empty">No catalog hits for “' + esc(needle) + '”</div>';
                    return;
                }
                list.innerHTML = '';
                items.forEach(function (item) {
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'atx-pick-item';
                    btn.setAttribute('role', 'option');
                    const path = item.path || item.rel_path || item.relPath || '';
                    btn.innerHTML = '<span class="n">' + esc(item.name || 'file') + '</span>'
                        + (path ? '<span class="p">' + esc(path) + '</span>' : '');
                    btn.addEventListener('click', function () {
                        if (typeof opts.onPick === 'function') opts.onPick(opts.slot, item);
                        list.innerHTML = '';
                    });
                    list.appendChild(btn);
                });
            } catch (e) {
                if (g !== gen) return;
                list.innerHTML = '<div class="atx-pick-empty">' + esc((e && e.message) || 'Search failed') + '</div>';
            }
        }

        const run = debounce(function () { search(input.value); }, 160);
        input.addEventListener('input', run);
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                const first = list.querySelector('.atx-pick-item');
                if (first) first.click();
            }
            if (e.key === 'Escape') list.innerHTML = '';
        });

        return { input: input, list: list, search: search, wrap: wrap };
    }

    function attach(opts) {
        opts = opts || {};
        const beforeZone = qs(opts.beforeZone);
        const afterZone = qs(opts.afterZone);
        if (!beforeZone || !afterZone) return null;
        injectStyles();

        const type = opts.type || '';
        const lastKey = 'fafo_catalog_pick_last_' + (type || 'any');

        const host = beforeZone.parentNode;
        let strip = host && host.querySelector('.atx-cmp-names');
        if (!strip) {
            strip = document.createElement('div');
            strip.className = 'atx-cmp-names';
            strip.innerHTML = ''
                + '<div><div class="lab">Before filename</div><div class="atx-cmp-name src" id="atxNameBefore" tabindex="0">—</div></div>'
                + '<div><div class="lab">After filename</div><div class="atx-cmp-name" id="atxNameAfter">—</div></div>'
                + '<div class="atx-cmp-hint">Highlight a slice of the <strong>before</strong> name — the after search follows it live. Click a hit to load from the catalog.</div>';
            if (host) host.insertBefore(strip, afterZone.nextSibling);
        }
        const nameBefore = strip.querySelector('.src') || strip.querySelector('#atxNameBefore');
        const nameAfter = strip.querySelector('#atxNameAfter') || strip.querySelectorAll('.atx-cmp-name')[1];

        function setNames(b, a) {
            if (nameBefore) nameBefore.textContent = b || '—';
            if (nameAfter) nameAfter.textContent = a || '—';
        }

        const beforePick = mountSlot(beforeZone, {
            slot: 'before',
            type: type,
            onPick: function (slot, item) { opts.onPick && opts.onPick(slot, item); },
        });
        const afterPick = mountSlot(afterZone, {
            slot: 'after',
            type: type,
            onPick: function (slot, item) { opts.onPick && opts.onPick(slot, item); },
        });

        let selTimer = null;
        document.addEventListener('selectionchange', function () {
            if (!nameBefore) return;
            const sel = global.getSelection && global.getSelection();
            if (!sel || sel.isCollapsed) return;
            const anchor = sel.anchorNode;
            if (!anchor || !nameBefore.contains(anchor)) return;
            const text = String(sel.toString() || '').trim();
            if (text.length < 2) return;
            if (selTimer) clearTimeout(selTimer);
            selTimer = setTimeout(function () {
                afterPick.search(text);
            }, 90);
        });

        try {
            const raw = localStorage.getItem(lastKey);
            if (raw) {
                const last = JSON.parse(raw);
                if (last && last.before && last.after) {
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'atx-pick-restore';
                    btn.textContent = 'Restore last pair · ' + (last.before.name || 'before') + ' ↔ ' + (last.after.name || 'after');
                    btn.addEventListener('click', function () {
                        if (opts.onPick) {
                            opts.onPick('before', last.before);
                            opts.onPick('after', last.after);
                        }
                    });
                    strip.appendChild(btn);
                }
            }
        } catch (_) { /* ignore */ }

        const ui = {
            setNames: setNames,
            beforePick: beforePick,
            afterPick: afterPick,
            remember: function (before, after) {
                if (!before || !after) return;
                try {
                    localStorage.setItem(lastKey, JSON.stringify({
                        before: { id: before.id, name: before.name, path: before.path, size: before.size },
                        after: { id: after.id, name: after.name, path: after.path, size: after.size },
                    }));
                } catch (_) { /* quota */ }
            },
        };
        lastUi = ui;
        return ui;
    }

    function syncNames(b, a) {
        if (lastUi && lastUi.setNames) lastUi.setNames(b, a);
    }

    global.AIToolboxCatalogPick = {
        attach: attach,
        syncNames: syncNames,
    };
})(typeof window !== 'undefined' ? window : globalThis);
