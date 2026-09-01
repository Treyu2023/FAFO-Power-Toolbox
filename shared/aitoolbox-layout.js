/**
 * FAFO modular layout engine
 * --------------------------
 * Resize columns/rows, reorder panels & sections, auto-save per app.
 *
 * Adopt in any tool HTML:
 *
 *   <link rel="stylesheet" href="../shared/aitoolbox-layout.css">
 *   <script src="../shared/aitoolbox-layout.js"></script>
 *
 *   <div class="main"
 *        data-fafo-layout-root
 *        data-fafo-layout-app="my-app-id"
 *        data-fafo-layout-type="columns">
 *     <aside data-fafo-panel="sidebar" data-fafo-panel-title="Scan"
 *            data-fafo-panel-min="200" data-fafo-panel-default="280">
 *       <div data-fafo-section="scan" data-fafo-section-title="Scan folder">…</div>
 *       <div data-fafo-section="options" data-fafo-section-title="Options"
 *            data-fafo-resizable="1" data-fafo-section-min="100" data-fafo-section-default="180">…</div>
 *     </aside>
 *     <section data-fafo-panel="center" data-fafo-panel-title="Results"
 *              data-fafo-flex="1">…</section>
 *     <aside data-fafo-panel="detail" data-fafo-panel-title="Detail"
 *            data-fafo-panel-min="260" data-fafo-panel-default="360">…</aside>
 *   </div>
 *
 * Optional toolbar host:  <div data-fafo-layout-toolbar></div>
 * Or pass { toolbar: '#nav' } to init.
 *
 * API:
 *   AIToolboxLayout.init({ appId, root })
 *   AIToolboxLayout.reset(appId)
 *   AIToolboxLayout.resetAll()
 *   AIToolboxLayout.listApps()
 */
(function (global) {
  'use strict';

  // v2 prefix: one-time break from corrupt "slim banner" saves in v1 (tiny fixed row heights).
  // Old v1 keys are left in place but ignored so first open heals to a full window.

  function readUiScale() {
    try {
      if (document.documentElement.getAttribute('data-atx-iframe') === '1') return 1;
      const v = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--atx-ui-scale'));
      return Number.isFinite(v) && v > 0.05 ? v : 1;
    } catch (_) { return 1; }
  }
  const STORAGE_PREFIX = 'fafo_layout_v2_';
  const INDEX_KEY = 'fafo_layout_v2__index';
  const instances = new Map();

  function storageKey(appId) {
    return STORAGE_PREFIX + String(appId || 'app').replace(/[^\w.\-]+/g, '_');
  }

  function readStore(appId) {
    try {
      const raw = localStorage.getItem(storageKey(appId));
      if (!raw) return null;
      const data = JSON.parse(raw);
      return data && typeof data === 'object' ? data : null;
    } catch (_) {
      return null;
    }
  }

  function writeStore(appId, data) {
    try {
      const payload = {
        v: 1,
        appId,
        updatedAt: new Date().toISOString(),
        ...data,
      };
      try {
        localStorage.setItem(storageKey(appId), JSON.stringify(payload));
      } catch (err) {
        if (err && (err.name === 'QuotaExceededError' || err.code === 22)) {
          try { localStorage.removeItem(storageKey(appId)); } catch (_) { /* ignore */ }
        }
        return false;
      }
      // Index for "reset all apps"
      let idx = [];
      try {
        idx = JSON.parse(localStorage.getItem(INDEX_KEY) || '[]') || [];
      } catch (_) {
        idx = [];
      }
      if (!idx.includes(appId)) {
        idx.push(appId);
        localStorage.setItem(INDEX_KEY, JSON.stringify(idx));
      }
      return true;
    } catch (_) {
      return false;
    }
  }

  function clearStore(appId) {
    try {
      localStorage.removeItem(storageKey(appId));
    } catch (_) { /* ignore */ }
  }

  function listApps() {
    try {
      return JSON.parse(localStorage.getItem(INDEX_KEY) || '[]') || [];
    } catch (_) {
      return [];
    }
  }

  function debounce(fn, ms) {
    let t = null;
    return function debounced() {
      const ctx = this;
      const args = arguments;
      clearTimeout(t);
      t = setTimeout(() => fn.apply(ctx, args), ms);
    };
  }

  function el(tag, cls, attrs) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (attrs) {
      Object.keys(attrs).forEach((k) => {
        if (k === 'text') node.textContent = attrs[k];
        else if (k === 'html') node.innerHTML = attrs[k];
        else node.setAttribute(k, attrs[k]);
      });
    }
    return node;
  }

  function panelEls(root, { visibleOnly } = {}) {
    const all = Array.from(root.querySelectorAll(':scope > [data-fafo-panel]'));
    if (!visibleOnly) return all;
    return all.filter((p) => {
      try {
        return getComputedStyle(p).display !== 'none' && !p.hasAttribute('hidden');
      } catch (_) {
        return true;
      }
    });
  }

  function sectionEls(panel) {
    const body = panel.querySelector(':scope > .fafo-panel-body') || panel;
    return Array.from(body.querySelectorAll(':scope > [data-fafo-section]'));
  }

  function defaultStateFromDom(root) {
    const type = (root && root.getAttribute('data-fafo-layout-type')) || 'columns';
    const panels = panelEls(root);
    const order = panels.map((p) => p.getAttribute('data-fafo-panel'));
    const sizes = {};
    const flex = {};
    panels.forEach((p) => {
      const id = p.getAttribute('data-fafo-panel');
      const def = parseInt(p.getAttribute('data-fafo-panel-default') || '', 10);
      const isFlex = p.getAttribute('data-fafo-flex') === '1';
      flex[id] = isFlex;
      // Columns: a default width is useful (content doesn't define it).
      // Rows: never seed a 120–140px cage — height comes from content until
      // the user drags. Seeding defaults was the "one grows, neighbor shrinks" bug.
      if (type === 'columns' && !isFlex && Number.isFinite(def) && def > 0) sizes[id] = def;
    });
    const sections = {};
    panels.forEach((p) => {
      const id = p.getAttribute('data-fafo-panel');
      const secs = sectionEls(p).map((s) => s.getAttribute('data-fafo-section'));
      if (secs.length) sections[id] = secs;
    });
    const sectionHeights = {};
    const collapsed = {};
    // Do not seed sectionHeights from data-fafo-section-default.
    return { order, sizes, flex, sections, sectionHeights, collapsed };
  }

  function ensureChrome(panel) {
    if (!panel) return;
    // Hub iframe shells and other full-bleed workspaces: a title chrome
    // sits on top of position:absolute children and steals toolbar clicks.
    if (panel.getAttribute('data-fafo-chrome') === '0') {
      const existing = panel.querySelector(':scope > .fafo-panel-chrome');
      if (existing) existing.remove();
      panel.classList.add('fafo-layout-panel');
      return;
    }
    if (panel.querySelector(':scope > .fafo-panel-chrome')) {
      panel.classList.add('fafo-layout-panel');
      return;
    }
    const id = panel.getAttribute('data-fafo-panel') || 'panel';
    const title =
      panel.getAttribute('data-fafo-panel-title') ||
      panel.getAttribute('data-fafo-title') ||
      id;

    // Wrap existing children into body
    const body = el('div', 'fafo-panel-body');
    while (panel.firstChild) body.appendChild(panel.firstChild);

    const chrome = el('div', 'fafo-panel-chrome', {
      draggable: 'true',
      title: 'Drag to reorder panels · use ↺ to reset this panel',
    });
    chrome.innerHTML =
      '<span class="fafo-grip" aria-hidden="true">⠿</span>' +
      `<span class="fafo-panel-title">${escapeHtml(title)}</span>` +
      '<span class="fafo-panel-actions"></span>';

    panel.appendChild(chrome);
    panel.appendChild(body);
    panel.classList.add('fafo-layout-panel');
  }

  function ensureSectionChrome(section) {
    if (section.querySelector(':scope > .fafo-section-chrome')) {
      // Still ensure resize handle exists for resizable sections
      if (
        section.getAttribute('data-fafo-resizable') === '1' &&
        !section.querySelector(':scope > .fafo-section-resize')
      ) {
        section.appendChild(
          el('div', 'fafo-section-resize', { title: 'Drag to resize section height' })
        );
      }
      return;
    }
    const title =
      section.getAttribute('data-fafo-section-title') ||
      (section.querySelector('h3') && section.querySelector('h3').textContent) ||
      section.getAttribute('data-fafo-section') ||
      'Section';

    const chrome = el('div', 'fafo-section-chrome', {
      draggable: 'true',
      title: 'Drag to reorder sections · use ↺ to reset this section size/order slot',
    });
    const grip = el('span', 'fafo-grip', { text: '⠿', 'aria-hidden': 'true' });
    chrome.appendChild(grip);

    // Wrap remaining content in body for resizable sections
    const body = el('div', 'fafo-section-body');
    while (section.firstChild) body.appendChild(section.firstChild);
    // Move h3 into chrome if it was wrapped
    const h3 = body.querySelector(':scope > h3');
    if (h3) chrome.appendChild(h3);
    else chrome.appendChild(el('span', 'fafo-section-title', { text: title }));

    // Actions host for per-section reset
    const actions = el('span', 'fafo-section-actions');
    chrome.appendChild(actions);

    section.appendChild(chrome);
    section.appendChild(body);

    if (section.getAttribute('data-fafo-resizable') === '1') {
      const handle = el('div', 'fafo-section-resize', {
        title: 'Drag to resize section height',
      });
      section.appendChild(handle);
    }
  }

  /**
   * Viewport span for clamp math.
   * IMPORTANT: root.getBoundingClientRect() is often ~content height on first paint
   * (or after a corrupt save of 120px panels). Using that as the clamp ceiling
   * re-saves the "slim banner" forever. Prefer the real window size when root is collapsed.
   */
  function layoutSpan(root, type) {
    const vw = Math.max(320, window.innerWidth || document.documentElement.clientWidth || 1200);
    const vh = Math.max(240, window.innerHeight || document.documentElement.clientHeight || 800);
    let rootW = 0;
    let rootH = 0;
    try {
      const r = root.getBoundingClientRect();
      rootW = r.width || 0;
      rootH = r.height || 0;
    } catch (_) { /* ignore */ }
    const scale = readUiScale();
    if (type === 'columns') {
      // Trust root width only when it looks like a real shell (CSS px, not zoomed paint)
      const cssW = rootW / scale;
      return cssW >= 280 ? cssW : vw;
    }
    // rows: if root is shorter than ~half the viewport, treat as collapsed / corrupt
    const cssH = rootH / scale;
    return cssH >= Math.min(320, vh * 0.4) ? cssH : vh;
  }

  /**
   * Fix "whole page stuck in a slim banner" layouts.
   * Happens when every row panel is fixed ~56–140px and none flex, or flex was lost.
   */
  function healBannerStripState(root, state, opts) {
    const type = (opts && opts.type) || 'columns';
    const panels = panelEls(root);
    if (!panels.length) return state;
    const out = state;
    out.flex = out.flex || {};
    out.sizes = out.sizes || {};

    // 1) DOM says flex → always honor (never pin main work area to 120px)
    panels.forEach((p) => {
      const id = p.getAttribute('data-fafo-panel');
      if (!id) return;
      if (p.getAttribute('data-fafo-flex') === '1') {
        out.flex[id] = true;
        delete out.sizes[id];
      }
    });

    const visible = panels.filter((p) => {
      try {
        return getComputedStyle(p).display !== 'none' && !p.hasAttribute('hidden') && !p.classList.contains('hidden');
      } catch (_) {
        return true;
      }
    });
    if (!visible.length) return out;

    function pickFlexCandidate() {
      const prefer = ['main', 'center', 'content', 'workspace', 'video', 'library', 'primary'];
      for (const key of prefer) {
        const hit = visible.find((p) => {
          const id = (p.getAttribute('data-fafo-panel') || '').toLowerCase();
          return id === key || id.includes(key);
        });
        if (hit) return hit.getAttribute('data-fafo-panel');
      }
      // Prefer largest min/default, else last visible
      let best = visible[visible.length - 1];
      let bestScore = -1;
      visible.forEach((p) => {
        const def = parseInt(p.getAttribute('data-fafo-panel-default') || '0', 10) || 0;
        const min = parseInt(p.getAttribute('data-fafo-panel-min') || '0', 10) || 0;
        const score = Math.max(def, min);
        if (score >= bestScore) {
          bestScore = score;
          best = p;
        }
      });
      return best.getAttribute('data-fafo-panel');
    }

    if (type === 'rows') {
      const vh = window.innerHeight || 800;
      // Classic bug: no flex survivor → every panel is a fixed strip (often 56–140px) = banner viewport
      let anyFlex = visible.some((p) => out.flex[p.getAttribute('data-fafo-panel')]);
      if (!anyFlex && vh > 360) {
        const id = pickFlexCandidate();
        if (id) {
          out.flex[id] = true;
          delete out.sizes[id];
          try {
            const elp = visible.find((p) => p.getAttribute('data-fafo-panel') === id);
            if (elp) elp.setAttribute('data-fafo-flex', '1');
          } catch (_) { /* ignore */ }
        }
      }
      // Corrupt sizes: a "main" panel was saved at toolbar height — drop so it can flex
      visible.forEach((p) => {
        const id = p.getAttribute('data-fafo-panel');
        if (!id || out.flex[id]) return;
        const s = out.sizes[id];
        const looksNav = /nav|toolbar|header|tabs|status|chrome/i.test(id);
        if (!looksNav && Number.isFinite(s) && s > 0 && s <= 160 && vh > 400) {
          // Prefer promoting to flex over leaving a 120px content cage
          if (!anyFlex) {
            out.flex[id] = true;
            delete out.sizes[id];
            anyFlex = true;
          } else {
            delete out.sizes[id];
          }
        }
      });
    }

    if (type === 'columns') {
      const vw = window.innerWidth || 1200;
      const fixedWidths = visible
        .filter((p) => !out.flex[p.getAttribute('data-fafo-panel')])
        .map((p) => {
          const id = p.getAttribute('data-fafo-panel');
          const s = out.sizes[id];
          if (Number.isFinite(s) && s > 0) return s;
          return parseInt(p.getAttribute('data-fafo-panel-default') || '240', 10) || 240;
        });
      const anyFlex = visible.some((p) => out.flex[p.getAttribute('data-fafo-panel')]);
      // Slim vertical strip: main content not flex and everything ≤200px wide
      if (!anyFlex && vw > 600) {
        const id = pickFlexCandidate();
        if (id) {
          out.flex[id] = true;
          delete out.sizes[id];
        }
      } else if (
        anyFlex &&
        fixedWidths.length &&
        fixedWidths.every((w) => w <= 100) &&
        vw > 600
      ) {
        // leave flex; drop absurdly tiny sidebars toward defaults later
      }
    }

    return out;
  }

  /** Clamp saved sizes so panels never sit at 0px / off-screen / larger than viewport. */
  function sanitizeState(root, state, opts) {
    const type = (opts && opts.type) || 'columns';
    const span = layoutSpan(root, type);
    let out = {
      order: Array.isArray(state.order) ? state.order.slice() : [],
      sizes: { ...(state.sizes || {}) },
      flex: { ...(state.flex || {}) },
      sections: { ...(state.sections || {}) },
      sectionHeights: { ...(state.sectionHeights || {}) },
      collapsed: { ...(state.collapsed || {}) },
    };
    out = healBannerStripState(root, out, opts);

    // No viewport ceiling — the user may drag a panel larger than the window
    // and scroll. Tiny sizes still get healed so we never freeze a slim banner.
    const minContent =
      type === 'rows'
        ? Math.min(280, Math.max(160, Math.floor(span * 0.25)))
        : Math.min(240, Math.max(160, Math.floor(span * 0.15)));

    Object.keys(out.sizes).forEach((id) => {
      if (out.flex[id]) {
        delete out.sizes[id];
        return;
      }
      let w = out.sizes[id];
      if (!Number.isFinite(w) || w <= 0) {
        delete out.sizes[id];
        return;
      }
      if (w < 40) w = 40;
      const looksNav = /^(nav|header|toolbar|tabs|chrome|status)$/i.test(id) || /nav|toolbar|header|tabs/i.test(id);
      if (type === 'rows') {
        // Drop auto-saved default cages (exact or near data-fafo-panel-default)
        try {
          const p = root.querySelector('[data-fafo-panel="' + id.replace(/"/g, '') + '"]');
          const def = parseInt(p && p.getAttribute('data-fafo-panel-default') || '', 10);
          if (Number.isFinite(def) && def > 0 && Math.abs(w - def) <= 12) {
            delete out.sizes[id];
            return;
          }
        } catch (_) { /* keep */ }
        if (!looksNav && w < minContent && span > 400) {
          delete out.sizes[id];
          return;
        }
      } else if (!looksNav && w < minContent && span > 400) {
        delete out.sizes[id];
        return;
      }
      out.sizes[id] = Math.round(w);
    });
    Object.keys(out.sectionHeights).forEach((id) => {
      let h = out.sectionHeights[id];
      if (!Number.isFinite(h) || h <= 0) {
        delete out.sectionHeights[id];
        return;
      }
      // Drop auto-saved defaults (exact or near data-fafo-section-default).
      // Those were never a real user choice and crush list panes.
      try {
        const sec = root.querySelector('[data-fafo-section="' + id.replace(/"/g, '') + '"]');
        const def = parseInt(sec && sec.getAttribute('data-fafo-section-default') || '160', 10) || 160;
        if (Math.abs(h - def) <= 12) {
          delete out.sectionHeights[id];
          return;
        }
      } catch (_) { /* keep */ }
      let minH = 60;
      try {
        const sec2 = root.querySelector('[data-fafo-section="' + id.replace(/"/g, '') + '"]');
        const attrMin = parseInt(sec2 && sec2.getAttribute('data-fafo-section-min') || '', 10);
        if (Number.isFinite(attrMin) && attrMin > 0) minH = Math.max(24, attrMin);
      } catch (_) { /* keep */ }
      if (h < minH) h = minH;
      out.sectionHeights[id] = Math.round(h);
    });
    Object.keys(out.collapsed || {}).forEach((id) => {
      if (!out.collapsed[id]) delete out.collapsed[id];
    });
    return out;
  }

  /** True if capturing now would freeze a slim-banner layout into localStorage. */
  function looksLikeCollapsedCapture(root, opts) {
    const type = (opts && opts.type) || 'columns';
    try {
      const r = root.getBoundingClientRect();
      const vh = window.innerHeight || 800;
      const vw = window.innerWidth || 1200;
      if (type === 'rows' && r.height > 0 && r.height < Math.min(200, vh * 0.22) && vh > 400) return true;
      if (type === 'columns' && r.width > 0 && r.width < Math.min(200, vw * 0.15) && vw > 600) return true;
    } catch (_) { /* ignore */ }
    return false;
  }

  function escapeHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function applyState(root, state, opts) {
    const type = opts.type || 'columns';
    const panels = panelEls(root);
    const byId = {};
    panels.forEach((p) => {
      byId[p.getAttribute('data-fafo-panel')] = p;
    });

    // Reorder panels according to state.order
    const order = (state.order || []).filter((id) => byId[id]);
    panels.forEach((p) => {
      const id = p.getAttribute('data-fafo-panel');
      if (!order.includes(id)) order.push(id);
    });

    // Clear split handles
    Array.from(root.querySelectorAll(':scope > .fafo-split-handle')).forEach((h) => h.remove());

    function isVisiblePanel(p) {
      if (!p) return false;
      try {
        return getComputedStyle(p).display !== 'none' && !p.hasAttribute('hidden');
      } catch (_) {
        return true;
      }
    }

    // Size every panel first. Growing one panel must NOT shrink its neighbors:
    // flex-shrink stays 0. Rows without a user size are height:auto (content).
    order.forEach((id) => {
      const panel = byId[id];
      if (!panel) return;
      const isFlex = panel.getAttribute('data-fafo-flex') === '1' || (state.flex && state.flex[id]);
      const min = parseInt(panel.getAttribute('data-fafo-panel-min') || '160', 10) || 160;
      const max = parseInt(panel.getAttribute('data-fafo-panel-max') || '0', 10) || 0;
      if (isFlex) {
        panel.style.flex = '1 0 auto';
        panel.style.flexShrink = '0';
        panel.style.minHeight = type === 'rows' ? Math.max(min, 200) + 'px' : '';
        panel.style.minWidth = type === 'columns' ? min + 'px' : '';
        panel.style.width = '';
        panel.style.height = '';
        panel.style.maxHeight = '';
        panel.style.maxWidth = '';
        panel.removeAttribute('data-fafo-sized');
        panel.setAttribute('data-fafo-flex', '1');
        if (state.flex) state.flex[id] = true;
        if (state.sizes) delete state.sizes[id];
      } else {
        let w = state.sizes && state.sizes[id];
        if (type === 'rows') {
          if (!Number.isFinite(w) || w <= 0) {
            panel.style.flex = '0 0 auto';
            panel.style.flexShrink = '0';
            panel.style.height = 'auto';
            panel.style.maxHeight = 'none';
            panel.style.minHeight = Math.min(min, 80) + 'px';
            panel.style.width = '';
            panel.style.maxWidth = '';
            panel.removeAttribute('data-fafo-sized');
            delete panel.dataset.fafoSize;
            if (state.sizes) delete state.sizes[id];
          } else {
            w = Math.max(min, w);
            if (max > 0) w = Math.min(max, w);
            panel.style.flex = '0 0 auto';
            panel.style.flexShrink = '0';
            panel.style.height = w + 'px';
            panel.style.minHeight = min + 'px';
            panel.style.maxHeight = 'none';
            panel.style.width = '';
            panel.style.maxWidth = '';
            panel.setAttribute('data-fafo-sized', '1');
            panel.dataset.fafoSize = String(w);
            if (state.sizes) state.sizes[id] = w;
          }
        } else {
          if (!Number.isFinite(w) || w <= 0) {
            w = parseInt(panel.getAttribute('data-fafo-panel-default') || String(min), 10) || min;
          }
          w = Math.max(min, w);
          if (max > 0) w = Math.min(max, w);
          panel.style.flex = '0 0 auto';
          panel.style.flexShrink = '0';
          panel.style.width = w + 'px';
          panel.style.minWidth = min + 'px';
          panel.style.height = '';
          panel.style.maxHeight = '';
          panel.setAttribute('data-fafo-sized', '1');
          panel.dataset.fafoSize = String(w);
          if (state.sizes) state.sizes[id] = w;
        }
      }
    });

    // Rebuild root children: panels in order + handles only between visible ones
    const frag = document.createDocumentFragment();
    const visibleOrder = order.filter((id) => isVisiblePanel(byId[id]));
    order.forEach((id) => {
      const panel = byId[id];
      if (!panel) return;
      frag.appendChild(panel);
      if (isVisiblePanel(panel)) {
        const vi = visibleOrder.indexOf(id);
        if (vi >= 0 && vi < visibleOrder.length - 1) {
          frag.appendChild(
            el('div', 'fafo-split-handle', {
              'data-fafo-split-after': id,
              title: type === 'columns' ? 'Drag to resize columns' : 'Drag to resize rows',
            })
          );
        }
      }
    });
    root.appendChild(frag);

    // Section order + heights per panel
    order.forEach((pid) => {
      const panel = byId[pid];
      if (!panel) return;
      const body = panel.querySelector(':scope > .fafo-panel-body') || panel;
      const secs = sectionEls(panel);
      const bySid = {};
      secs.forEach((s) => {
        bySid[s.getAttribute('data-fafo-section')] = s;
      });
      let secOrder = (state.sections && state.sections[pid]) || [];
      secOrder = secOrder.filter((id) => bySid[id]);
      secs.forEach((s) => {
        const id = s.getAttribute('data-fafo-section');
        if (!secOrder.includes(id)) secOrder.push(id);
      });
      secOrder.forEach((sid) => {
        const s = bySid[sid];
        if (s) body.appendChild(s);
        if (s && s.getAttribute('data-fafo-resizable') === '1') {
          let h = state.sectionHeights && state.sectionHeights[sid];
          const minH = parseInt(s.getAttribute('data-fafo-section-min') || '80', 10) || 80;
          if (!Number.isFinite(h) || h <= 0) {
            // No user size — CSS flex (list fills leftover; others size to content)
            s.style.flex = '';
            s.style.height = '';
            s.style.maxHeight = '';
            delete s.dataset.fafoHeight;
            s.removeAttribute('data-fafo-user-sized');
            if (state.sectionHeights) delete state.sectionHeights[sid];
          } else {
            h = Math.max(minH, h);
            s.style.flex = '0 0 auto';
            s.style.flexShrink = '0';
            s.style.height = h + 'px';
            s.style.maxHeight = 'none';
            s.dataset.fafoHeight = String(h);
            s.setAttribute('data-fafo-user-sized', '1');
            if (state.sectionHeights) state.sectionHeights[sid] = h;
          }
        }
        applyCollapsedClass(s, !!(state.collapsed && state.collapsed[sid]));
      });
    });
  }

  function applyCollapsedClass(section, on) {
    if (!section) return;
    if (on) {
      section.classList.add('fafo-section-collapsed');
      section.setAttribute('data-fafo-collapsed', '1');
      section.style.height = '';
      section.style.flex = '0 0 auto';
      section.style.flexShrink = '0';
      section.style.maxHeight = 'none';
    } else {
      section.classList.remove('fafo-section-collapsed');
      section.removeAttribute('data-fafo-collapsed');
    }
  }

  function captureState(root, opts) {
    const type = opts.type || 'columns';
    const panels = panelEls(root);
    const order = panels.map((p) => p.getAttribute('data-fafo-panel'));
    const sizes = {};
    const flex = {};
    panels.forEach((p) => {
      const id = p.getAttribute('data-fafo-panel');
      const isFlex = p.getAttribute('data-fafo-flex') === '1';
      flex[id] = isFlex;
      if (isFlex) return;
      // Rows: only persist a height the user actually dragged. Capturing
      // content height on every save froze panels and made neighbors shrink.
      if (type === 'rows' && p.getAttribute('data-fafo-sized') !== '1') return;
      const rect = p.getBoundingClientRect();
      const px = type === 'columns' ? rect.width : rect.height;
      if (px > 0) sizes[id] = Math.round(px);
    });
    const sections = {};
    const sectionHeights = {};
    const collapsed = {};
    panels.forEach((p) => {
      const id = p.getAttribute('data-fafo-panel');
      const secs = sectionEls(p);
      sections[id] = secs.map((s) => s.getAttribute('data-fafo-section'));
      secs.forEach((s) => {
        const sid = s.getAttribute('data-fafo-section');
        if (sid && (s.getAttribute('data-fafo-collapsed') === '1' || s.classList.contains('fafo-section-collapsed'))) {
          collapsed[sid] = true;
        }
        if (s.getAttribute('data-fafo-resizable') !== '1') return;
        if (s.getAttribute('data-fafo-user-sized') !== '1') return;
        if (s.getAttribute('data-fafo-collapsed') === '1') return;
        const h = Math.round(s.getBoundingClientRect().height);
        if (sid && h > 0) sectionHeights[sid] = h;
      });
    });
    return { order, sizes, flex, sections, sectionHeights, collapsed };
  }

  /**
   * Clear global resize/drag cursor state.
   * If pointerup is missed (leave window, alt-tab, capture lost), body can stick on
   * grabbing/col-resize and the normal pointer never returns.
   */
  function clearLayoutPointerState(root) {
    try {
      document.body.classList.remove(
        'fafo-layout-resizing',
        'fafo-layout-resizing-row',
        'fafo-layout-dragging'
      );
      document.body.style.cursor = '';
      document.documentElement.style.cursor = '';
      const scope = root || document;
      scope.querySelectorAll?.('.fafo-split-handle.is-active, .fafo-section-resize.is-active')
        .forEach?.((el) => el.classList.remove('is-active'));
      scope.querySelectorAll?.('.fafo-layout-panel.is-dragging, [data-fafo-section].is-section-dragging')
        .forEach?.((el) => {
          el.classList.remove('is-dragging', 'is-section-dragging', 'is-drop-target', 'is-section-drop');
        });
    } catch (_) { /* ignore */ }
  }

  // One-time global safety net for stuck cursors (all layout apps)
  if (!global.__fafoLayoutCursorGuard) {
    global.__fafoLayoutCursorGuard = true;
    const bail = () => clearLayoutPointerState(document);
    window.addEventListener('pointercancel', bail, true);
    window.addEventListener('blur', bail);
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) bail();
    });
    window.addEventListener(
      'keydown',
      (e) => {
        if (e.key === 'Escape') bail();
      },
      true
    );
    // Lost capture / mouse up outside iframe
    window.addEventListener('pointerup', bail, true);
  }

  function bindSplitResize(root, opts, save) {
    const type = opts.type || 'columns';
    root.querySelectorAll(':scope > .fafo-split-handle').forEach((handle) => {
      if (handle._fafoBound) return;
      handle._fafoBound = true;
      handle.addEventListener('pointerdown', (ev) => {
        if (ev.button !== 0) return;
        ev.preventDefault();
        const afterId = handle.getAttribute('data-fafo-split-after');
        const panels = panelEls(root);
        const left = panels.find((p) => p.getAttribute('data-fafo-panel') === afterId);
        // next panel after handle
        let right = handle.nextElementSibling;
        while (right && !right.hasAttribute('data-fafo-panel')) {
          right = right.nextElementSibling;
        }
        if (!left || !right) return;
        // Prefer resizing the non-flex neighbor; if both fixed, resize left.
        const leftFlex = left.getAttribute('data-fafo-flex') === '1';
        const rightFlex = right.getAttribute('data-fafo-flex') === '1';
        const target = leftFlex && !rightFlex ? right : left;
        const min = parseInt(target.getAttribute('data-fafo-panel-min') || '160', 10) || 160;
        const maxAttr = parseInt(target.getAttribute('data-fafo-panel-max') || '0', 10) || 0;
        const scale = readUiScale();
        const start = type === 'columns' ? ev.clientX : ev.clientY;
        const startSize =
          ((type === 'columns'
            ? target.getBoundingClientRect().width
            : target.getBoundingClientRect().height) / scale);
        const sign = target === left ? 1 : -1;

        handle.classList.add('is-active');
        document.body.classList.add(
          type === 'columns' ? 'fafo-layout-resizing' : 'fafo-layout-resizing-row'
        );
        try {
          handle.setPointerCapture?.(ev.pointerId);
        } catch (_) { /* ignore */ }
        // Don't convert a flex survivor into a fixed pixel width — that
        // is how "resize once, layout stuck forever" happens.
        if (target.getAttribute('data-fafo-flex') === '1') {
          target.style.flex = '0 0 auto';
        }

        let finished = false;
        function onMove(e) {
          if (finished) return;
          const cur = type === 'columns' ? e.clientX : e.clientY;
          let next = startSize + sign * ((cur - start) / scale);
          next = Math.max(min, next);
          if (maxAttr > 0) next = Math.min(maxAttr, next);
          // Independent sizes: do NOT clamp to leftover so the neighbor
          // would have to shrink. The page/root grows instead.

          target.style.flex = '0 0 auto';
          target.style.flexShrink = '0';
          target.setAttribute('data-fafo-sized', '1');
          if (type === 'columns') {
            target.style.width = next + 'px';
            target.style.minWidth = min + 'px';
          } else {
            target.style.height = next + 'px';
            target.style.minHeight = min + 'px';
            target.style.maxHeight = 'none';
          }
          target.dataset.fafoSize = String(Math.round(next));
        }
        function onUp() {
          if (finished) return;
          finished = true;
          handle.classList.remove('is-active');
          if (target.getAttribute('data-fafo-flex') === '1') {
            target.style.flex = '1 1 auto';
            if (type === 'columns') {
              target.style.width = '';
              target.style.maxWidth = '';
            } else {
              target.style.height = '';
              target.style.maxHeight = '';
            }
          }
          clearLayoutPointerState(root);
          try {
            handle.releasePointerCapture?.(ev.pointerId);
          } catch (_) { /* ignore */ }
          window.removeEventListener('pointermove', onMove);
          window.removeEventListener('pointerup', onUp);
          window.removeEventListener('pointercancel', onUp);
          save();
        }
        window.addEventListener('pointermove', onMove);
        window.addEventListener('pointerup', onUp);
        window.addEventListener('pointercancel', onUp);
      });
    });
  }

  function bindSectionResize(root, save) {
    root.querySelectorAll('.fafo-section-resize').forEach((handle) => {
      if (handle._fafoBound) return;
      handle._fafoBound = true;
      handle.addEventListener('pointerdown', (ev) => {
        if (ev.button !== 0) return;
        ev.preventDefault();
        const section = handle.closest('[data-fafo-section]');
        if (!section) return;
        const minH = parseInt(section.getAttribute('data-fafo-section-min') || '80', 10) || 80;
        const scale = readUiScale();
        const startY = ev.clientY;
        const startH = section.getBoundingClientRect().height / scale;
        handle.classList.add('is-active');
        document.body.classList.add('fafo-layout-resizing-row');
        try {
          handle.setPointerCapture?.(ev.pointerId);
        } catch (_) { /* ignore */ }
        let finished = false;
        function onMove(e) {
          if (finished) return;
          let h = startH + ((e.clientY - startY) / scale);
          h = Math.max(minH, h);
          section.style.flex = '0 0 auto';
          section.style.flexShrink = '0';
          section.style.height = h + 'px';
          section.style.maxHeight = 'none';
          section.dataset.fafoHeight = String(Math.round(h));
          section.setAttribute('data-fafo-user-sized', '1');
        }
        function onUp() {
          if (finished) return;
          finished = true;
          handle.classList.remove('is-active');
          clearLayoutPointerState(root);
          try {
            handle.releasePointerCapture?.(ev.pointerId);
          } catch (_) { /* ignore */ }
          window.removeEventListener('pointermove', onMove);
          window.removeEventListener('pointerup', onUp);
          window.removeEventListener('pointercancel', onUp);
          save();
        }
        window.addEventListener('pointermove', onMove);
        window.addEventListener('pointerup', onUp);
        window.addEventListener('pointercancel', onUp);
      });
    });
  }

  function bindPanelDrag(root, opts, save, rebindAll) {
    const panels = panelEls(root);
    panels.forEach((panel) => {
      const chrome = panel.querySelector(':scope > .fafo-panel-chrome');
      if (!chrome || chrome._fafoDrag) return;
      chrome._fafoDrag = true;
      if (!chrome._fafoMaxBound) {
        chrome._fafoMaxBound = true;
        chrome.addEventListener('dblclick', (ev) => {
          if (ev.target && ev.target.closest && ev.target.closest('button, a, input, select, textarea, .fafo-chrome-btn')) {
            return;
          }
          ev.preventDefault();
          const turningOn = !panel.classList.contains('fafo-max-panel');
          panelEls(root).forEach((p) => p.classList.remove('fafo-max-panel'));
          root.classList.toggle('fafo-maxed', turningOn);
          if (turningOn) panel.classList.add('fafo-max-panel');
          toast(turningOn ? 'Panel maximized — double-click header to restore' : 'Layout restored');
        });
      }
      // Only the grip starts a drag — buttons/reset must not steal the hand cursor forever
      chrome.addEventListener('dragstart', (ev) => {
        if (ev.target && ev.target.closest && ev.target.closest('button, a, input, select, textarea, .fafo-chrome-btn')) {
          ev.preventDefault();
          return;
        }
        const id = panel.getAttribute('data-fafo-panel');
        ev.dataTransfer.setData('text/fafo-panel', id);
        ev.dataTransfer.effectAllowed = 'move';
        panel.classList.add('is-dragging');
        document.body.classList.add('fafo-layout-dragging');
        root._fafoDragPanel = id;
      });
      chrome.addEventListener('dragend', () => {
        panel.classList.remove('is-dragging');
        panels.forEach((p) => p.classList.remove('is-drop-target'));
        root._fafoDragPanel = null;
        clearLayoutPointerState(root);
      });
      panel.addEventListener('dragover', (ev) => {
        if (!root._fafoDragPanel) return;
        ev.preventDefault();
        panel.classList.add('is-drop-target');
      });
      panel.addEventListener('dragleave', () => panel.classList.remove('is-drop-target'));
      panel.addEventListener('drop', (ev) => {
        ev.preventDefault();
        panel.classList.remove('is-drop-target');
        const fromId = ev.dataTransfer.getData('text/fafo-panel') || root._fafoDragPanel;
        const toId = panel.getAttribute('data-fafo-panel');
        if (!fromId || !toId || fromId === toId) return;
        const state = captureState(root, opts);
        const order = state.order.slice();
        const from = order.indexOf(fromId);
        const to = order.indexOf(toId);
        if (from < 0 || to < 0) return;
        order.splice(from, 1);
        order.splice(to, 0, fromId);
        state.order = order;
        applyState(root, state, opts);
        rebindAll();
        save();
      });
    });
  }

  function bindSectionDrag(root, opts, save, rebindAll) {
    panelEls(root).forEach((panel) => {
      const pid = panel.getAttribute('data-fafo-panel');
      sectionEls(panel).forEach((section) => {
        const chrome = section.querySelector(':scope > .fafo-section-chrome');
        if (!chrome || chrome._fafoDrag) return;
        chrome._fafoDrag = true;
        chrome.addEventListener('dragstart', (ev) => {
          // Don't let panel chrome capture
          ev.stopPropagation();
          if (ev.target && ev.target.closest && ev.target.closest('button, a, input, select, textarea, .fafo-chrome-btn')) {
            ev.preventDefault();
            return;
          }
          const sid = section.getAttribute('data-fafo-section');
          ev.dataTransfer.setData('text/fafo-section', sid);
          ev.dataTransfer.setData('text/fafo-section-panel', pid);
          ev.dataTransfer.effectAllowed = 'move';
          section.classList.add('is-section-dragging');
          document.body.classList.add('fafo-layout-dragging');
          root._fafoDragSection = { sid, pid };
        });
        chrome.addEventListener('dragend', () => {
          section.classList.remove('is-section-dragging');
          root.querySelectorAll('.is-section-drop').forEach((n) => n.classList.remove('is-section-drop'));
          root._fafoDragSection = null;
          clearLayoutPointerState(root);
        });
        section.addEventListener('dragover', (ev) => {
          if (!root._fafoDragSection) return;
          if (root._fafoDragSection.pid !== pid) return; // same panel only
          ev.preventDefault();
          ev.stopPropagation();
          section.classList.add('is-section-drop');
        });
        section.addEventListener('dragleave', () => section.classList.remove('is-section-drop'));
        section.addEventListener('drop', (ev) => {
          ev.preventDefault();
          ev.stopPropagation();
          section.classList.remove('is-section-drop');
          const drag = root._fafoDragSection;
          if (!drag || drag.pid !== pid) return;
          const fromId = drag.sid;
          const toId = section.getAttribute('data-fafo-section');
          if (!fromId || !toId || fromId === toId) return;
          const state = captureState(root, opts);
          const order = (state.sections[pid] || []).slice();
          const from = order.indexOf(fromId);
          const to = order.indexOf(toId);
          if (from < 0 || to < 0) return;
          order.splice(from, 1);
          order.splice(to, 0, fromId);
          state.sections[pid] = order;
          applyState(root, state, opts);
          rebindAll();
          save();
        });
      });
    });
  }

  function mountToolbar(host, appId, instance) {
    if (!host) return;
    if (host.querySelector('.fafo-layout-bar')) return;
    const bar = el('div', 'fafo-layout-bar');
    bar.innerHTML = `
      <button type="button" class="fafo-layout-btn" data-act="save" title="Save layout now (also auto-saves)">Save layout</button>
      <button type="button" class="fafo-layout-btn" data-act="reset" title="Reset this app's panel layout to defaults (fixes off-screen / skewed panels)">Reset layout</button>
      <button type="button" class="fafo-layout-btn danger" data-act="reset-all" title="Reset saved layouts for every toolbox app on this PC">Reset all apps</button>
      <span class="fafo-layout-hint" title="Drag panel headers to reorder · drag edges to resize · ▾ collapses a section · ↺ resets just that piece · layout always remembers last position">Layout remembers · auto-saves</span>
    `;
    bar.querySelector('[data-act="save"]').addEventListener('click', () => {
      try {
        instance.save(true);
        toast('Layout saved');
      } catch (_) {
        toast('Layout save failed');
      }
    });
    bar.querySelector('[data-act="reset"]').addEventListener('click', () => {
      if (confirm('Reset this app layout to defaults?\n\nFixes panels stuck tiny, huge, or off-screen. Your last layout will be replaced.')) {
        instance.reset();
        toast('Layout reset for ' + appId);
      }
    });
    bar.querySelector('[data-act="reset-all"]').addEventListener('click', () => {
      if (confirm('Reset saved layouts for ALL toolbox apps on this PC?')) {
        AIToolboxLayout.resetAll();
        instance.reset();
        toast('All app layouts reset');
      }
    });
    host.appendChild(bar);
  }

  /** Always-visible floating dock when a page has no toolbar host. */
  function ensureFloatingToolbar(appId, instance) {
    try {
      if (window.self !== window.top) return;
    } catch (_) { return; }
    const root = document.querySelector('[data-fafo-layout-root]');
    if (root && root.getAttribute('data-fafo-layout-dock') === '0') return;
    if (document.body && document.body.getAttribute('data-fafo-layout-dock') === '0') return;
    let dock = document.getElementById('fafo-layout-float-dock');
    if (!dock) {
      dock = el('div', 'fafo-layout-float-dock');
      dock.id = 'fafo-layout-float-dock';
      document.body.appendChild(dock);
    }
    if (!dock.querySelector('[data-fafo-dock-toggle]')) {
      const tog = el('button', 'fafo-layout-dock-toggle', {
        type: 'button',
        title: 'Show or hide layout controls (also: double-click a panel header to maximize it)',
        'data-fafo-dock-toggle': '1',
        text: 'Layout',
      });
      tog.addEventListener('click', () => {
        dock.classList.toggle('collapsed');
        tog.textContent = dock.classList.contains('collapsed') ? 'Layout' : 'Layout ▾';
        try {
          localStorage.setItem(
            'fafo_layout_dock_collapsed',
            dock.classList.contains('collapsed') ? '1' : '0'
          );
        } catch (_) { /* ignore */ }
      });
      dock.insertBefore(tog, dock.firstChild);
      let collapsed = true;
      try {
        collapsed = localStorage.getItem('fafo_layout_dock_collapsed') !== '0';
      } catch (_) { /* ignore */ }
      dock.classList.toggle('collapsed', collapsed);
      tog.textContent = collapsed ? 'Layout' : 'Layout ▾';
    }
    // One bar per app id inside the dock
    const safeId = String(appId || 'app').replace(/[^\w.\-]+/g, '_');
    let host = dock.querySelector('[data-fafo-layout-float="' + safeId + '"]');
    if (!host) {
      host = el('div', 'fafo-layout-float-host');
      host.setAttribute('data-fafo-layout-float', safeId);
      const label = el('span', 'fafo-layout-float-label', { text: 'Layout' });
      host.appendChild(label);
      dock.appendChild(host);
      restoreDockSize(host);
      watchDockSize(host);
    }
    mountToolbar(host, appId, instance);
  }

  function restoreDockSize(host) {
    try {
      const saved = JSON.parse(localStorage.getItem('fafo_layout_dock_size') || 'null');
      if (!saved || !saved.w || !saved.h) return;
      host.style.width = Math.max(160, saved.w) + 'px';
      host.style.height = Math.max(36, saved.h) + 'px';
    } catch (_) { /* ignore */ }
  }

  function watchDockSize(host) {
    if (host.dataset.sizeWatch === '1' || typeof ResizeObserver !== 'function') return;
    host.dataset.sizeWatch = '1';
    let t = 0;
    new ResizeObserver(() => {
      clearTimeout(t);
      t = setTimeout(() => {
        const r = host.getBoundingClientRect();
        if (r.width < 80 || r.height < 24) return;
        try {
          localStorage.setItem('fafo_layout_dock_size', JSON.stringify({
            w: Math.round(r.width),
            h: Math.round(r.height),
          }));
        } catch (_) { /* ignore */ }
      }, 180);
    }).observe(host);
  }

  function wirePanelReset(panel, instance) {
    const actions = panel.querySelector(':scope > .fafo-panel-chrome .fafo-panel-actions');
    if (!actions || actions.querySelector('[data-fafo-reset-panel]')) return;
    const id = panel.getAttribute('data-fafo-panel');
    const btn = el('button', 'fafo-chrome-btn', {
      type: 'button',
      title: 'Reset this panel size/order slot to default',
      'data-fafo-reset-panel': id || '1',
      text: '↺',
    });
    btn.addEventListener('click', (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      if (instance && typeof instance.resetPanel === 'function') {
        instance.resetPanel(id);
        toast('Panel reset');
      }
    });
    // Don't start panel drag from the button
    btn.addEventListener('pointerdown', (ev) => ev.stopPropagation());
    btn.draggable = false;
    actions.appendChild(btn);
  }

  function wireSectionReset(section, panel, instance) {
    let actions = section.querySelector(':scope > .fafo-section-chrome .fafo-section-actions');
    if (!actions) {
      const chrome = section.querySelector(':scope > .fafo-section-chrome');
      if (!chrome) return;
      actions = el('span', 'fafo-section-actions');
      chrome.appendChild(actions);
    }
    const sid = section.getAttribute('data-fafo-section');
    const pid = panel.getAttribute('data-fafo-panel');
    if (!actions.querySelector('[data-fafo-collapse-section]')) {
      const collapsed = section.getAttribute('data-fafo-collapsed') === '1' ||
        section.classList.contains('fafo-section-collapsed');
      const fold = el('button', 'fafo-chrome-btn', {
        type: 'button',
        title: collapsed ? 'Expand this section' : 'Collapse this section to its header',
        'data-fafo-collapse-section': sid || '1',
        'aria-pressed': collapsed ? 'true' : 'false',
        text: collapsed ? '▸' : '▾',
      });
      fold.addEventListener('click', (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        if (instance && typeof instance.toggleSection === 'function') {
          instance.toggleSection(pid, sid);
        }
      });
      fold.addEventListener('pointerdown', (ev) => ev.stopPropagation());
      fold.draggable = false;
      actions.appendChild(fold);
    } else {
      const fold = actions.querySelector('[data-fafo-collapse-section]');
      const collapsed = section.getAttribute('data-fafo-collapsed') === '1' ||
        section.classList.contains('fafo-section-collapsed');
      fold.textContent = collapsed ? '▸' : '▾';
      fold.setAttribute('aria-pressed', collapsed ? 'true' : 'false');
      fold.title = collapsed ? 'Expand this section' : 'Collapse this section to its header';
    }
    if (actions.querySelector('[data-fafo-reset-section]')) return;
    const btn = el('button', 'fafo-chrome-btn', {
      type: 'button',
      title: 'Reset this section height to default',
      'data-fafo-reset-section': sid || '1',
      text: '↺',
    });
    btn.addEventListener('click', (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      if (instance && typeof instance.resetSection === 'function') {
        instance.resetSection(pid, sid);
        toast('Section reset');
      }
    });
    btn.addEventListener('pointerdown', (ev) => ev.stopPropagation());
    btn.draggable = false;
    actions.appendChild(btn);
  }

  function toast(msg) {
    try {
      if (global.AIToolboxUI && global.AIToolboxUI.toast) {
        global.AIToolboxUI.toast(msg, 'ok');
        return;
      }
    } catch (_) { /* ignore */ }
    try {
      if (global.AIToolboxPro && global.AIToolboxPro.toast) {
        global.AIToolboxPro.toast(msg);
        return;
      }
    } catch (_) { /* ignore */ }
  }

  const SETTINGS_RE = /option|setting|control|scan|filter|config|pref|keep|action|sidebar|intro|assist/i;
  const COMPACT_RE = /summary|stat|footer|hint|toolbar|action|head|nav|status|tally/i;
  const LIST_RE = /list|result|group|file|preview|library|grid|log|queue|detail-list|timeline|tile|catalog/i;
  const LIST_CHILD_SEL =
    '.groups-wrap, .list, .results, .file-list, .item-list, .grid-wrap, .table-wrap, .detail-list, .detail-list-inner, .log, .timeline, #groupsWrap, #fileGrid, #toolGrid, [data-fafo-scroll]';

  function isSettingsSection(s) {
    const id =
      (s.getAttribute('data-fafo-section') || '') +
      ' ' +
      (s.getAttribute('data-fafo-section-title') || '');
    return SETTINGS_RE.test(id);
  }
  function isListSection(s) {
    const id =
      (s.getAttribute('data-fafo-section') || '') +
      ' ' +
      (s.getAttribute('data-fafo-section-title') || '');
    return LIST_RE.test(id);
  }
  function isCompactSection(s) {
    if (!s) return false;
    const flag = s.getAttribute('data-fafo-compact');
    if (flag === '1') return true;
    if (flag === '0') return false;
    const id =
      (s.getAttribute('data-fafo-section') || '') +
      ' ' +
      (s.getAttribute('data-fafo-section-title') || '');
    return SETTINGS_RE.test(id) || COMPACT_RE.test(id);
  }
  function isCollapsedSection(s) {
    return !!(s && (s.getAttribute('data-fafo-collapsed') === '1' || s.classList.contains('fafo-section-collapsed')));
  }

  /**
   * Pin is OPT-IN (`data-fafo-layout-pin="1"`). Default is document scroll so
   * enlarging one panel grows the page instead of stealing height from siblings.
   */
  function wantsViewportPin(root) {
    if (!root) return false;
    if (root.getAttribute('data-fafo-layout-page-scroll') === '1') return false;
    return root.getAttribute('data-fafo-layout-pin') === '1';
  }

  function unpinViewport(root) {
    try {
      document.documentElement.classList.remove('fafo-layout-locked');
      document.body.classList.remove('fafo-layout-locked');
      if (root) root.classList.remove('fafo-viewport-pin');
    } catch (_) { /* ignore */ }
  }

  function pinViewport(root) {
    if (!wantsViewportPin(root)) {
      unpinViewport(root);
      return;
    }
    const html = document.documentElement;
    html.classList.add('fafo-layout-locked');
    document.body.classList.add('fafo-layout-locked');
    root.classList.add('fafo-viewport-pin');

    function measure() {
      let top = 0;
      try {
        const r = root.getBoundingClientRect();
        top = Math.max(0, Math.round(r.top));
      } catch (_) { /* ignore */ }
      let bottom = 0;
      // Only the fixed bottom pro bar reserves layout space. The LAYOUT dock
      // and S1/S2 companion bar are overlays / top chrome — counting them here
      // was eating a third of the viewport on every tool page.
      const pro = document.getElementById('atx-pro-bar');
      if (pro && pro.style.display !== 'none' && !document.body.classList.contains('atx-pro-min')) {
        try {
          const br = pro.getBoundingClientRect();
          if (br.height > 0) bottom = Math.min(56, Math.max(0, Math.round(br.height)));
        } catch (_) { /* ignore */ }
      } else if (document.body.classList.contains('atx-pro-min')) {
        bottom = 8;
      }
      html.style.setProperty('--fafo-chrome-top', top + 'px');
      html.style.setProperty('--fafo-chrome-bottom', bottom + 'px');
    }
    measure();
    requestAnimationFrame(measure);
    if (!root._fafoPinBound) {
      root._fafoPinBound = true;
      window.addEventListener('resize', debounce(measure, 80));
    }
    return measure;
  }

  /**
   * Split a panel's sections into independently scrolling panes.
   * Settings/options stay compact at the top of the panel; lists flex and
   * scroll so selecting a row never yanks the options off-screen.
   */
  function markScrollPanes(root) {
    panelEls(root).forEach((panel) => {
      const body = panel.querySelector(':scope > .fafo-panel-body') || panel;
      const secs = sectionEls(panel);
      body.classList.remove('fafo-body-split');
      secs.forEach((s) => {
        s.classList.remove('fafo-section-compact', 'fafo-section-flex');
      });
      if (secs.length >= 2) {
        body.classList.add('fafo-body-split');
        let flexed = false;
        secs.forEach((s) => {
          const userSized = s.getAttribute('data-fafo-user-sized') === '1';
          if (isCompactSection(s) || isCollapsedSection(s)) {
            s.classList.add('fafo-section-compact');
            s.classList.remove('fafo-section-flex');
            s.style.flexShrink = '0';
            return;
          }
          if (userSized) return;
          if (!flexed && isListSection(s)) {
            s.classList.add('fafo-section-flex');
            s.style.flexShrink = '0';
            flexed = true;
          } else {
            s.classList.add('fafo-section-compact');
            s.style.flexShrink = '0';
          }
        });
        // Never dump leftover height into a compact footer/summary/actions pane.
        // If no list is present, leftover stays as empty panel background.
      }
      try {
        body.querySelectorAll(LIST_CHILD_SEL).forEach((el) => {
          if (el.closest('[data-fafo-section]')) return;
          el.classList.add('fafo-scroll-pane');
        });
      } catch (_) { /* ignore */ }
    });
  }

  /**
   * Scroll `el` only inside its nearest panel/section/tile pane.
   * Never moves the window, so a sibling settings panel stays put.
   */
  function scrollInsidePane(el, opts) {
    if (!el || !el.getBoundingClientRect) return;
    const pane = el.closest(
      '.fafo-section-body, .fafo-scroll-pane, .lx-tile-scroll, .fafo-panel-body'
    );
    const behavior = (opts && opts.behavior) || 'auto';
    if (!pane) {
      try {
        el.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior });
      } catch (_) { /* ignore */ }
      return;
    }
    const pad = (opts && opts.padding) || 12;
    const elRect = el.getBoundingClientRect();
    const paneRect = pane.getBoundingClientRect();
    let dy = 0;
    if (elRect.top < paneRect.top + pad) dy = elRect.top - paneRect.top - pad;
    else if (elRect.bottom > paneRect.bottom - pad) dy = elRect.bottom - paneRect.bottom + pad;
    let dx = 0;
    if (elRect.left < paneRect.left + pad) dx = elRect.left - paneRect.left - pad;
    else if (elRect.right > paneRect.right - pad) dx = elRect.right - paneRect.right + pad;
    if (!dy && !dx) return;
    if (behavior === 'smooth' && typeof pane.scrollTo === 'function') {
      pane.scrollTo({
        top: pane.scrollTop + dy,
        left: pane.scrollLeft + dx,
        behavior: 'smooth',
      });
    } else {
      pane.scrollTop += dy;
      pane.scrollLeft += dx;
    }
  }

  /** One-time: make scrollIntoView stay inside independent panes. */
  function installScrollContainment() {
    if (global.__fafoScrollContain) return;
    global.__fafoScrollContain = true;
    const proto = typeof Element !== 'undefined' ? Element.prototype : null;
    if (!proto || !proto.scrollIntoView) return;
    const orig = proto.scrollIntoView;
    proto.scrollIntoView = function fafoContainedScrollIntoView(arg) {
      try {
        if (document.querySelector('.ui-tutorial-bg')) {
          return orig.apply(this, arguments);
        }
        const locked =
          document.documentElement.classList.contains('fafo-layout-locked');
        const pane = this.closest &&
          this.closest('.fafo-layout-root, .lx-tile-scroll, .fafo-panel-body, .fafo-scroll-pane, .fafo-section-body');
        let paneScrolls = false;
        try {
          if (pane) {
            const oy = getComputedStyle(pane).overflowY;
            paneScrolls =
              pane.scrollHeight > pane.clientHeight + 2 &&
              (oy === 'auto' || oy === 'scroll');
          }
        } catch (_) { /* ignore */ }
        if (paneScrolls || (locked && pane)) {
          const opts = typeof arg === 'object' && arg ? arg : {};
          scrollInsidePane(this, {
            behavior: opts.behavior || (arg === true ? 'smooth' : 'auto'),
          });
          return;
        }
      } catch (_) { /* fall through */ }
      return orig.apply(this, arguments);
    };
  }

  /**
   * When a root has no explicit data-fafo-panel children, invent panels/sections
   * from common toolbox markup (sidebar/main/detail, cards, panels, etc.).
   */
  function scaffoldIfNeeded(root) {
    if (root.querySelector(':scope > [data-fafo-panel]')) return;

    const kids = Array.from(root.children).filter((el) => {
      if (el.nodeType !== 1) return false;
      const tag = el.tagName.toLowerCase();
      if (tag === 'script' || tag === 'style' || tag === 'link') return false;
      if (el.classList.contains('fafo-split-handle')) return false;
      if (el.classList.contains('fafo-layout-bar')) return false;
      // skip pure toast/modal overlays
      if (el.classList.contains('toast') || el.classList.contains('modal-bg') || el.id === 'toast')
        return false;
      return true;
    });

    // Classic two/three column shells
    const sidebar = kids.find(
      (el) =>
        el.matches('aside.sidebar, .sidebar, nav.sidebar') ||
        /sidebar|nav-rail|side-nav/i.test(el.className || '')
    );
    const detail = kids.find(
      (el) =>
        el !== sidebar &&
        (el.matches('aside.detail, .detail-panel, .detail, aside.tags-panel') ||
          /detail|preview-panel|tags-panel/i.test(el.className || ''))
    );
    const main = kids.find(
      (el) =>
        el !== sidebar &&
        el !== detail &&
        (el.matches('main, .main, .center, section.main, .content') ||
          /main|center|content|workspace/i.test(el.className || ''))
    );

    if (sidebar || main || detail) {
      root.setAttribute('data-fafo-layout-type', root.getAttribute('data-fafo-layout-type') || 'columns');
      let n = 0;
      function markPanel(el, id, title, extra) {
        if (!el || el.hasAttribute('data-fafo-panel')) return;
        el.setAttribute('data-fafo-panel', id);
        el.setAttribute('data-fafo-panel-title', title);
        if (extra) {
          Object.keys(extra).forEach((k) => el.setAttribute(k, extra[k]));
        }
        // Sections inside: direct .panel / .card / .section / .side-card / h2 blocks
        scaffoldSections(el);
        n++;
      }
      markPanel(sidebar, 'sidebar', 'Sidebar', {
        'data-fafo-panel-min': '160',
        'data-fafo-panel-default': '240',
      });
      markPanel(main, 'main', 'Main', { 'data-fafo-flex': '1' });
      markPanel(detail, 'detail', 'Detail', {
        'data-fafo-panel-min': '220',
        'data-fafo-panel-default': '320',
      });
      // Any leftover direct children become extra panels
      kids.forEach((el, i) => {
        if (el.hasAttribute('data-fafo-panel')) return;
        markPanel(el, 'panel-' + i, el.getAttribute('aria-label') || el.tagName.toLowerCase(), {
          'data-fafo-panel-min': '120',
          'data-fafo-panel-default': '200',
        });
      });
      if (n) return;
    }

    // Card / panel stack → vertical modular rows
    const cards = kids.filter((el) =>
      el.matches(
        '.panel, .card, .ui-card, .side-card, .block, .section, section, .stat-card, .hero, .toolbar, .vitals'
      )
    );
    if (cards.length >= 2) {
      root.setAttribute('data-fafo-layout-type', root.getAttribute('data-fafo-layout-type') || 'rows');
      cards.forEach((el, i) => {
        if (el.hasAttribute('data-fafo-panel')) return;
        const title =
          el.querySelector('h1,h2,h3,.ph,.panel-head')?.textContent?.trim()?.slice(0, 40) ||
          'Block ' + (i + 1);
        el.setAttribute('data-fafo-panel', 'block-' + i);
        el.setAttribute('data-fafo-panel-title', title);
        el.setAttribute('data-fafo-panel-min', i === cards.length - 1 ? '120' : '60');
        if (i === cards.length - 1) el.setAttribute('data-fafo-flex', '1');
        else el.setAttribute('data-fafo-panel-default', String(Math.max(80, Math.min(280, el.offsetHeight || 140))));
      });
      return;
    }

    // Fallback: one flex main panel wrapping all children
    if (kids.length) {
      root.setAttribute('data-fafo-layout-type', root.getAttribute('data-fafo-layout-type') || 'rows');
      const wrap = document.createElement('div');
      wrap.setAttribute('data-fafo-panel', 'main');
      wrap.setAttribute('data-fafo-panel-title', 'Main');
      wrap.setAttribute('data-fafo-flex', '1');
      kids.forEach((el) => wrap.appendChild(el));
      root.appendChild(wrap);
      scaffoldSections(wrap);
    }
  }

  function scaffoldSections(panel) {
    if (panel.querySelector(':scope > [data-fafo-section], :scope > .fafo-panel-body > [data-fafo-section]'))
      return;
    const candidates = Array.from(panel.children).filter((el) => {
      if (el.nodeType !== 1) return false;
      return el.matches(
        '.panel, .card, .ui-card, .side-card, .sidebar-section, .section, .block, [class*="section"]'
      );
    });
    if (candidates.length < 2) return;
    candidates.forEach((el, i) => {
      if (el.hasAttribute('data-fafo-section')) return;
      const title =
        el.querySelector('h2,h3,.ph,.side-card-h')?.textContent?.trim()?.slice(0, 40) ||
        'Section ' + (i + 1);
      el.setAttribute('data-fafo-section', 'sec-' + i);
      el.setAttribute('data-fafo-section-title', title);
    });
  }

  function createInstance(root, options) {
    const appId =
      options.appId ||
      root.getAttribute('data-fafo-layout-app') ||
      root.getAttribute('data-fafo-app') ||
      'app';
    const type =
      options.type ||
      root.getAttribute('data-fafo-layout-type') ||
      'columns';
    const opts = { type, appId };

    // Auto-mark panels/sections when author only set the root
    try {
      scaffoldIfNeeded(root);
    } catch (e) {
      console.warn('[AIToolboxLayout] scaffold failed', appId, e);
    }
    // Re-read type if scaffold changed it
    opts.type =
      options.type ||
      root.getAttribute('data-fafo-layout-type') ||
      type ||
      'columns';

    root.classList.add('fafo-layout-root');
    root.classList.add(opts.type === 'rows' ? 'fafo-layout-rows' : 'fafo-layout-columns');

    // Prepare chrome for panels + sections
    let panelsNow = panelEls(root);
    if (!panelsNow.length) {
      // Last-resort scaffold so init never no-ops into a broken flex shell
      try {
        scaffoldIfNeeded(root);
      } catch (_) { /* ignore */ }
      panelsNow = panelEls(root);
    }
    if (!panelsNow.length) {
      console.warn('[AIToolboxLayout] no panels for', appId, '— layout inactive');
      return {
        appId,
        root,
        save() {},
        refresh() {},
        reset() {},
        getState() {
          return null;
        },
        destroy() {
          instances.delete(appId);
        },
      };
    }

    panelsNow.forEach((panel) => {
      ensureChrome(panel);
      sectionEls(panel).forEach((s) => ensureSectionChrome(s));
    });

    const defaults = defaultStateFromDom(root);
    let state = readStore(appId) || defaults;
    // Merge any new panels/sections added in later app versions
    state = mergeState(defaults, state);
    state = sanitizeState(root, state, opts);

    function saveNow() {
      try {
        // Never freeze a collapsed shell into localStorage (slim banner death spiral)
        if (looksLikeCollapsedCapture(root, opts)) {
          return null;
        }
        const snap = sanitizeState(root, captureState(root, opts), opts);
        writeStore(appId, snap);
        root.dispatchEvent(
          new CustomEvent('fafo-layout-saved', { detail: { appId, state: snap } })
        );
        return snap;
      } catch (e) {
        console.warn('[AIToolboxLayout] save failed', appId, e);
        return null;
      }
    }
    const save = debounce(saveNow, 180);

    const api = {
      appId,
      root,
      save: (immediate) => {
        if (immediate) return saveNow();
        save();
        return null;
      },
      /** Re-apply after CSS show/hide of panels (e.g. tags collapsed). */
      refresh() {
        const snap = sanitizeState(root, captureState(root, opts), opts);
        applyState(root, snap, opts);
        rebindAll();
        wireResets();
        markScrollPanes(root);
      },
      reset() {
        clearStore(appId);
        const fresh = sanitizeState(root, defaultStateFromDom(root), opts);
        applyState(root, fresh, opts);
        rebindAll();
        wireResets();
        markScrollPanes(root);
        saveNow();
      },
      /** Reset one panel to default size (keeps others). */
      resetPanel(panelId) {
        if (!panelId) return;
        const fresh = defaultStateFromDom(root);
        const cur = captureState(root, opts);
        if (fresh.sizes && fresh.sizes[panelId] != null) cur.sizes[panelId] = fresh.sizes[panelId];
        else delete cur.sizes[panelId];
        // Restore DOM default flex flag
        const panel = panelEls(root).find((p) => p.getAttribute('data-fafo-panel') === panelId);
        if (panel) {
          if (fresh.flex && fresh.flex[panelId]) {
            panel.setAttribute('data-fafo-flex', '1');
            cur.flex[panelId] = true;
            delete cur.sizes[panelId];
          } else {
            panel.removeAttribute('data-fafo-flex');
            cur.flex[panelId] = false;
            const def = parseInt(panel.getAttribute('data-fafo-panel-default') || '', 10);
            if (Number.isFinite(def) && def > 0) cur.sizes[panelId] = def;
          }
        }
        // Put panel back to default order index if present
        if (Array.isArray(fresh.order) && fresh.order.includes(panelId)) {
          const order = (cur.order || []).filter((id) => id !== panelId);
          const idx = fresh.order.indexOf(panelId);
          order.splice(Math.min(idx, order.length), 0, panelId);
          cur.order = order;
        }
        const next = sanitizeState(root, cur, opts);
        applyState(root, next, opts);
        rebindAll();
        wireResets();
        markScrollPanes(root);
        saveNow();
      },
      /** Reset one section height to its data-fafo-section-default. */
      resetSection(panelId, sectionId) {
        if (!sectionId) return;
        const cur = captureState(root, opts);
        const panel = panelEls(root).find((p) => p.getAttribute('data-fafo-panel') === panelId);
        const sec =
          panel &&
          sectionEls(panel).find((s) => s.getAttribute('data-fafo-section') === sectionId);
        if (sec) {
          sec.style.height = '';
          sec.style.flex = '';
          sec.style.maxHeight = '';
          delete sec.dataset.fafoHeight;
          sec.removeAttribute('data-fafo-user-sized');
          applyCollapsedClass(sec, false);
        }
        if (cur.sectionHeights) delete cur.sectionHeights[sectionId];
        if (cur.collapsed) delete cur.collapsed[sectionId];
        // Restore section order slot to default for that panel
        if (panelId && cur.sections && defaults.sections && defaults.sections[panelId]) {
          cur.sections[panelId] = defaults.sections[panelId].slice();
        }
        const next = sanitizeState(root, cur, opts);
        applyState(root, next, opts);
        rebindAll();
        wireResets();
        markScrollPanes(root);
        saveNow();
      },
      getState() {
        return captureState(root, opts);
      },
      /** Collapse or expand one section to chrome-only height. */
      toggleSection(panelId, sectionId) {
        if (!sectionId) return;
        const panel = panelEls(root).find((p) => p.getAttribute('data-fafo-panel') === panelId);
        const sec =
          panel &&
          sectionEls(panel).find((s) => s.getAttribute('data-fafo-section') === sectionId);
        if (!sec) return;
        const on = sec.getAttribute('data-fafo-collapsed') !== '1';
        applyCollapsedClass(sec, on);
        const cur = captureState(root, opts);
        cur.collapsed = cur.collapsed || {};
        if (on) cur.collapsed[sectionId] = true;
        else delete cur.collapsed[sectionId];
        const next = sanitizeState(root, cur, opts);
        applyState(root, next, opts);
        rebindAll();
        wireResets();
        markScrollPanes(root);
        saveNow();
        toast(on ? 'Section collapsed' : 'Section expanded');
      },
      destroy() {
        instances.delete(appId);
      },
    };

    function rebindAll() {
      // re-query handles after DOM reorder
      root.querySelectorAll('.fafo-split-handle').forEach((h) => {
        h._fafoBound = false;
      });
      root.querySelectorAll('.fafo-section-resize').forEach((h) => {
        h._fafoBound = false;
      });
      panelEls(root).forEach((p) => {
        const c = p.querySelector(':scope > .fafo-panel-chrome');
        if (c) c._fafoDrag = false;
        sectionEls(p).forEach((s) => {
          const sc = s.querySelector(':scope > .fafo-section-chrome');
          if (sc) sc._fafoDrag = false;
        });
      });
      bindSplitResize(root, opts, save);
      bindSectionResize(root, save);
      bindPanelDrag(root, opts, save, rebindAll);
      bindSectionDrag(root, opts, save, rebindAll);
    }

    function wireResets() {
      panelEls(root).forEach((p) => {
        wirePanelReset(p, api);
        sectionEls(p).forEach((s) => wireSectionReset(s, p, api));
      });
    }

    applyState(root, state, opts);
    rebindAll();
    wireResets();
    pinViewport(root);
    markScrollPanes(root);
    installScrollContainment();
    // Never inherit a stuck grab/resize cursor from a previous session/tab
    clearLayoutPointerState(root);
    // Second pass after paint: root has real height; heal any remaining banner strip
    requestAnimationFrame(() => {
      try {
        pinViewport(root);
        let healed = sanitizeState(root, captureState(root, opts), opts);
        healed = healBannerStripState(root, healed, opts);
        applyState(root, healed, opts);
        rebindAll();
        wireResets();
        markScrollPanes(root);
        // Only persist once layout looks like a real window
        if (!looksLikeCollapsedCapture(root, opts)) saveNow();
      } catch (e) {
        console.warn('[AIToolboxLayout] post-paint heal failed', appId, e);
      }
    });

    // Toolbar host: explicit slot → nav/header → always-on floating dock
    let toolbar =
      (options.toolbar &&
        (typeof options.toolbar === 'string'
          ? document.querySelector(options.toolbar)
          : options.toolbar)) ||
      root.closest('body')?.querySelector('[data-fafo-layout-toolbar]') ||
      document.querySelector('[data-fafo-layout-toolbar]') ||
      null;
    if (!toolbar) {
      toolbar =
        document.querySelector('.nav-bar') ||
        document.querySelector('nav.nav') ||
        document.querySelector('header.topbar') ||
        document.querySelector('header');
    }
    if (toolbar) mountToolbar(toolbar, appId, api);
    // Always also expose floating controls so reset is never lost off-screen
    ensureFloatingToolbar(appId, api);

    // Persist when window resizes (flex panels change absolute sizes)
    window.addEventListener(
      'resize',
      debounce(() => {
        // Re-clamp if viewport shrank under a huge saved panel
        pinViewport(root);
        const cur = sanitizeState(root, captureState(root, opts), opts);
        applyState(root, cur, opts);
        rebindAll();
        wireResets();
        markScrollPanes(root);
        saveNow();
      }, 400)
    );

    // Always remember last position — flush on leave / hide
    const flush = () => {
      try {
        saveNow();
      } catch (_) { /* ignore */ }
    };
    window.addEventListener('pagehide', flush);
    window.addEventListener('beforeunload', flush);
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) flush();
    });

    instances.set(appId, api);
    return api;
  }

  function mergeState(defaults, saved) {
    const out = {
      order: Array.isArray(saved.order) ? saved.order.slice() : defaults.order.slice(),
      sizes: { ...(defaults.sizes || {}), ...(saved.sizes || {}) },
      flex: { ...(defaults.flex || {}), ...(saved.flex || {}) },
      sections: { ...(defaults.sections || {}) },
      sectionHeights: { ...(defaults.sectionHeights || {}), ...(saved.sectionHeights || {}) },
      collapsed: { ...(defaults.collapsed || {}), ...(saved.collapsed || {}) },
    };
    // append any new default panels not in saved order
    (defaults.order || []).forEach((id) => {
      if (!out.order.includes(id)) out.order.push(id);
    });
    // sections per panel
    Object.keys(defaults.sections || {}).forEach((pid) => {
      const base = (defaults.sections[pid] || []).slice();
      const prev = (saved.sections && saved.sections[pid]) || [];
      const merged = prev.filter((id) => base.includes(id));
      base.forEach((id) => {
        if (!merged.includes(id)) merged.push(id);
      });
      out.sections[pid] = merged;
    });
    return out;
  }

  function init(options) {
    options = options || {};
    let root = options.root;
    if (typeof root === 'string') root = document.querySelector(root);
    if (!root) root = document.querySelector('[data-fafo-layout-root]');
    if (!root) return null;
    const appId =
      options.appId ||
      root.getAttribute('data-fafo-layout-app') ||
      'app';
    if (instances.has(appId)) return instances.get(appId);
    return createInstance(root, options);
  }

  function autoInit() {
    document.querySelectorAll('[data-fafo-layout-root]').forEach((root) => {
      const appId = root.getAttribute('data-fafo-layout-app') || 'app';
      if (instances.has(appId)) return;
      try {
        createInstance(root, {
          appId,
          type: root.getAttribute('data-fafo-layout-type') || 'columns',
        });
      } catch (e) {
        console.warn('[AIToolboxLayout] init failed', appId, e);
      }
    });
  }

  const AIToolboxLayout = {
    init,
    autoInit,
    reset(appId) {
      if (appId && instances.has(appId)) {
        instances.get(appId).reset();
        return true;
      }
      if (appId) {
        clearStore(appId);
        return true;
      }
      return false;
    },
    resetAll() {
      listApps().forEach((id) => clearStore(id));
      try {
        localStorage.removeItem(INDEX_KEY);
      } catch (_) { /* ignore */ }
      // Live instances re-default
      instances.forEach((inst) => {
        try {
          inst.reset();
        } catch (_) { /* ignore */ }
      });
    },
    listApps,
    get(appId) {
      return instances.get(appId) || null;
    },
    scrollInsidePane,
    pinViewport,
    STORAGE_PREFIX,
  };

  global.AIToolboxLayout = AIToolboxLayout;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      installScrollContainment();
      if (!global.AITOOLBOX_LAYOUT_NO_AUTO) autoInit();
    });
  } else {
    installScrollContainment();
    if (!global.AITOOLBOX_LAYOUT_NO_AUTO) autoInit();
  }
})(typeof window !== 'undefined' ? window : globalThis);
