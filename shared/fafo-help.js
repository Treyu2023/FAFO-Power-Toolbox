/**
 * FAFO Help — location-aware summoner.
 *
 * F1 or Shift+? opens the Guide filtered to the screen you are on.
 * Other menus/apps can call:
 *   FAFOHelp.summon()
 *   FAFOHelp.summon({ context: 'options.tag-themes' })
 *   FAFOHelp.summon({ from: element })
 *   FAFOHelp.setContext('newtab.tags')  // sticky override for a view
 *
 * Requires fafo-knowledge.bundle.js (FAFOKnowledge) loaded first.
 */
(function (global) {
  'use strict';

  let stickyContext = null;
  let lastPointerEl = null;
  let lastContextId = 'global';

  function K() {
    return global.FAFOKnowledge || null;
  }

  function contexts() {
    const d = K()?.data;
    return (d && d.contexts) || {};
  }

  function pathHay() {
    try {
      return String(location.href || '') + ' ' + String(location.pathname || '') + ' ' + String(document.title || '');
    } catch {
      return '';
    }
  }

  function isVisible(el) {
    if (!el || !el.getBoundingClientRect) return false;
    const st = global.getComputedStyle?.(el);
    if (st && (st.display === 'none' || st.visibility === 'hidden' || st.opacity === '0')) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  function matchDetect(ctxId, def) {
    const det = def.detect || {};
    let score = def.priority || 0;
    let hits = 0;

    const hay = pathHay().toLowerCase();
    (det.pathIncludes || []).forEach((p) => {
      if (hay.includes(String(p).toLowerCase())) {
        hits += 1;
        score += 20;
      }
    });

    (det.bodyClassAny || []).forEach((c) => {
      if (document.body?.classList?.contains(c)) {
        hits += 1;
        score += 25;
      }
    });

    (det.selectorsAny || []).forEach((sel) => {
      try {
        const el = document.querySelector(sel);
        if (el && isVisible(el)) {
          hits += 1;
          score += 30;
        }
      } catch (_) {}
    });

    if (det.dataView) {
      const view = document.querySelector('.view-section.active, .view-section[style*="display: block"]');
      // Options uses tab data-target / sections shown
      const activeTab = document.querySelector(`.tab.active[data-target="${det.dataView}"]`);
      const section = document.getElementById(det.dataView);
      if (activeTab || (section && isVisible(section))) {
        hits += 1;
        score += 40;
      }
    }

    // Need at least one positive signal unless it's global
    if (ctxId === 'global') return { id: ctxId, score: 1, hits: 1 };
    if (hits === 0 && !(det.pathIncludes || det.selectorsAny || det.bodyClassAny || det.dataView)) {
      return null;
    }
    if (hits === 0) return null;
    return { id: ctxId, score, hits, def };
  }

  /**
   * Walk from an element up for data-fafo-help-context.
   */
  function contextFromElement(el) {
    let n = el;
    while (n && n !== document && n !== document.documentElement) {
      if (n.getAttribute) {
        const c = n.getAttribute('data-fafo-help-context');
        if (c && contexts()[c]) return c;
        const tip = n.getAttribute('data-fafo-tip');
        if (tip) return { tipId: tip };
      }
      n = n.parentNode;
    }
    return null;
  }

  function detectContext(opts) {
    opts = opts || {};
    if (opts.context && contexts()[opts.context]) {
      return { id: opts.context, score: 999, def: contexts()[opts.context], source: 'explicit' };
    }
    if (stickyContext && contexts()[stickyContext]) {
      return { id: stickyContext, score: 500, def: contexts()[stickyContext], source: 'sticky' };
    }

    const fromEl = opts.from || lastPointerEl || document.activeElement;
    const walked = contextFromElement(fromEl);
    if (typeof walked === 'string') {
      return { id: walked, score: 400, def: contexts()[walked], source: 'data-attr' };
    }
    if (walked && walked.tipId) {
      // Map tip → best context that lists this item
      const tipId = walked.tipId;
      let best = null;
      Object.keys(contexts()).forEach((id) => {
        const def = contexts()[id];
        if ((def.items || []).includes(tipId) || (def.sections || []).some((sec) => {
          const section = (K()?.data?.sections || []).find((s) => s.id === sec);
          return (section?.items || []).some((it) => it.id === tipId);
        })) {
          const m = { id, score: (def.priority || 0) + 100, def, source: 'tip-map' };
          if (!best || m.score > best.score) best = m;
        }
      });
      if (best) return best;
    }

    let best = null;
    Object.keys(contexts()).forEach((id) => {
      const m = matchDetect(id, contexts()[id]);
      if (!m) return;
      if (!best || m.score > best.score) best = m;
    });
    if (best) {
      best.source = 'detect';
      return best;
    }
    return { id: 'global', score: 0, def: contexts().global || { label: 'General', items: [] }, source: 'fallback' };
  }

  function itemsForContext(ctx) {
    const def = (ctx && ctx.def) || contexts()[ctx?.id] || {};
    const out = [];
    const seen = new Set();
    const pushItem = (it, reason) => {
      if (!it || !it.id || seen.has(it.id)) return;
      seen.add(it.id);
      out.push(Object.assign({ _reason: reason }, it));
    };

    (def.items || []).forEach((id) => {
      const it = K()?.byId?.(id);
      if (it) pushItem(it, 'context-item');
    });

    (def.sections || []).forEach((secId) => {
      const sec = (K()?.data?.sections || []).find((s) => s.id === secId);
      (sec?.items || []).forEach((it) => pushItem(it, 'context-section'));
    });

    // Always append a few global essentials if empty
    if (!out.length) {
      (contexts().global?.items || []).forEach((id) => {
        const it = K()?.byId?.(id);
        if (it) pushItem(it, 'global');
      });
    }
    return out;
  }

  function ensureUi() {
    return K()?.ensureGuide?.() || document.getElementById('fafo-knowledge-guide');
  }

  function renderContextual(ctx, filterQ) {
    const kn = K();
    if (!kn) return;
    const el = kn.ensureGuide ? kn.ensureGuide() : ensureUi();
    if (!el) return;

    // Context bar
    let bar = el.querySelector('.fkg-context-bar');
    if (!bar) {
      const head = el.querySelector('.fkg-head');
      bar = document.createElement('div');
      bar.className = 'fkg-context-bar';
      if (head && head.nextSibling) head.parentNode.insertBefore(bar, head.nextSibling);
      else el.querySelector('.fkg-panel')?.insertBefore(bar, el.querySelector('.fkg-meta'));
    }
    const label = ctx?.def?.label || ctx?.id || 'General';
    bar.innerHTML =
      '<span class="fkg-ctx-label">Help for:</span> ' +
      '<strong class="fkg-ctx-name">' +
      esc(label) +
      '</strong> ' +
      '<button type="button" class="fkg-ctx-all" type="button">Show all</button> ' +
      '<span class="fkg-ctx-src">' +
      esc(ctx?.source || '') +
      '</span>';
    bar.querySelector('.fkg-ctx-all')?.addEventListener('click', () => {
      stickyContext = null;
      kn.openGuide?.('');
      // full guide without filter
      renderAll(filterQ);
    });

    const meta = el.querySelector('.fkg-meta');
    if (meta) {
      meta.textContent =
        'Context · ' +
        label +
        ' · v' +
        (kn.data?.version || '') +
        ' · F1 anywhere to re-summon';
    }

    const items = itemsForContext(ctx);
    const q = (filterQ || '').trim().toLowerCase();
    const filtered = !q
      ? items
      : items.filter((it) => {
          const hay = [it.id, it.title, it.tip, it.body, (it.keywords || []).join(' ')].join(' ').toLowerCase();
          return hay.includes(q);
        });

    // Group by section
    const bySec = new Map();
    filtered.forEach((it) => {
      const secId = it.section || guessSection(it.id);
      if (!bySec.has(secId)) bySec.set(secId, []);
      bySec.get(secId).push(it);
    });

    const body = el.querySelector('.fkg-body');
    if (!body) return;
    let html = '';
    if (!filtered.length) {
      html = '<p class="fkg-empty">No tips for this location. Try “Show all” or clear search.</p>';
    } else {
      bySec.forEach((list, secId) => {
        const secTitle =
          (kn.data?.sections || []).find((s) => s.id === secId)?.title || secId;
        html += '<section class="fkg-sec"><h3>' + esc(secTitle) + '</h3>';
        list.forEach((it) => {
          html +=
            '<article class="fkg-item" data-id="' +
            esc(it.id) +
            '">' +
            '<h4>' +
            esc(it.title || it.id) +
            '</h4>' +
            '<p class="fkg-tip">' +
            esc(it.tip || '') +
            '</p>' +
            (it.body ? '<p class="fkg-body-text">' + esc(it.body) + '</p>' : '') +
            (it.keys && it.keys.length
              ? '<p class="fkg-keys">' +
                it.keys.map((k) => '<kbd>' + esc(k) + '</kbd>').join(' ') +
                '</p>'
              : '') +
            '<code class="fkg-id">' +
            esc(it.id) +
            '</code></article>';
        });
        html += '</section>';
      });
    }
    body.innerHTML = html;
  }

  function guessSection(id) {
    if (!id) return 'general';
    const p = String(id).split('.')[0];
    return p || 'general';
  }

  function renderAll(q) {
    const kn = K();
    if (!kn?.renderGuide) return;
    kn.renderGuide(q || '');
    const bar = document.querySelector('.fkg-context-bar');
    if (bar) {
      bar.innerHTML =
        '<span class="fkg-ctx-label">Help for:</span> <strong>All topics</strong>';
    }
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /**
   * Open contextual help.
   * @param {object} [opts]
   * @param {string} [opts.context] force context id
   * @param {Element} [opts.from] element that summoned help
   * @param {string} [opts.q] search filter
   * @param {boolean} [opts.all] show full guide
   */
  function summon(opts) {
    opts = opts || {};
    const kn = K();
    if (!kn) {
      console.warn('FAFOHelp: FAFOKnowledge not loaded');
      return null;
    }
    const ctx = opts.all ? { id: 'global', def: { label: 'All topics' }, source: 'all' } : detectContext(opts);
    lastContextId = ctx.id;

    // Open shell
    if (typeof kn.openGuide === 'function') {
      // openGuide originally takes search string; call with empty then replace body
      kn.openGuide(opts.q || '');
    } else {
      const el = document.getElementById('fafo-knowledge-guide');
      el?.classList.remove('hidden');
      document.body.classList.add('fafo-guide-open');
    }

    if (opts.all) {
      renderAll(opts.q || '');
    } else {
      renderContextual(ctx, opts.q || '');
    }

    // Wire search to stay contextual
    const el = document.getElementById('fafo-knowledge-guide');
    const search = el?.querySelector('.fkg-search');
    if (search && !search.dataset.ctxWired) {
      search.dataset.ctxWired = '1';
      search.addEventListener('input', () => {
        if (stickyContext === null && lastContextId && lastContextId !== 'global') {
          renderContextual(detectContext({ context: lastContextId }), search.value);
        } else if (document.body.classList.contains('fafo-guide-open')) {
          // if user chose show all, keep all
          const bar = el.querySelector('.fkg-ctx-name');
          if (bar && bar.textContent === 'All topics') renderAll(search.value);
          else renderContextual(detectContext({ context: lastContextId }), search.value);
        }
      });
    }

    try {
      global.dispatchEvent(
        new CustomEvent('fafo:help', { detail: { context: ctx.id, source: ctx.source } })
      );
    } catch (_) {}
    return ctx;
  }

  function setContext(id) {
    stickyContext = id || null;
    try {
      document.body.dataset.fafoHelpContext = id || '';
    } catch (_) {}
  }

  function clearContext() {
    stickyContext = null;
    try {
      delete document.body.dataset.fafoHelpContext;
    } catch (_) {}
  }

  function onPointer(e) {
    lastPointerEl = e.target;
  }

  function onKey(e) {
    // F1 or Shift+/
    if (e.key === 'F1' || (e.shiftKey && e.key === '?')) {
      // Allow in inputs for F1; Shift+? skip when typing
      if (e.key !== 'F1') {
        const t = e.target;
        if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
      }
      e.preventDefault();
      summon({ from: lastPointerEl || document.activeElement });
      return;
    }
    if (e.key === 'Escape' && document.body.classList.contains('fafo-guide-open')) {
      K()?.closeGuide?.();
    }
  }

  function init() {
    document.addEventListener('pointerdown', onPointer, true);
    document.addEventListener('focusin', onPointer, true);
    document.addEventListener('keydown', onKey, true);

    // Options tabs: set sticky context from data-target
    document.querySelectorAll('.tab[data-target]').forEach((tab) => {
      tab.addEventListener('click', () => {
        const target = tab.getAttribute('data-target');
        if (!target) return;
        const map = {
          'view-library': 'options.library',
          'view-tag-themes': 'options.tag-themes',
          'view-session': 'options.session',
          'view-intro-promos': 'options.intro-promos',
          'view-chrome-art': 'options.chrome-art',
          'view-knowledge': 'options.knowledge',
        };
        if (map[target]) setContext(map[target]);
        else if (pathHay().toLowerCase().includes('options')) setContext('options');
      });
    });

    // New tab: tags panel open → context
    const obs = new MutationObserver(() => {
      if (document.body.classList.contains('fafo-sprint-mode')) {
        /* keep detect for sprint */
      }
    });
    try {
      obs.observe(document.body, { attributes: true, attributeFilter: ['class'] });
    } catch (_) {}
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  global.FAFOHelp = {
    summon,
    detectContext,
    setContext,
    clearContext,
    itemsForContext,
    getLastContext: () => lastContextId,
  };

  // Bridge: openGuide(context) convenience
  if (K()) {
    const orig = K().openGuide?.bind(K());
    K().openGuideFrom = function (ctx, q) {
      return summon({ context: ctx, q: q });
    };
    K().summonHelp = summon;
  }
})(typeof window !== 'undefined' ? window : globalThis);
