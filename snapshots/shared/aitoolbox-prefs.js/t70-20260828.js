/**
 * FAFO Toolbox — shell Look prefs
 * --------------------------------
 * Two separate controls:
 *   Layout   — phone vs desktop (how the chrome is arranged)
 *   Lighting — glow, accents, brightness of the neon
 *
 * Storage: localStorage aitoolbox.shell.prefs.v1
 * API:     window.AIToolboxPrefs
 *
 * Snapshots: snapshots/shared/aitoolbox-prefs.js/ (newest 5).
 */
(function (global) {
  'use strict';

  const LS = 'aitoolbox.shell.prefs.v1';
  const EVT = 'fafo-shell-prefs';

  const ACCENTS = {
    cyan:   { accent: '#00f3ff', accent2: '#ff6b35', accent3: '#7c5cff', rgb: '0,243,255' },
    violet: { accent: '#a78bfa', accent2: '#00f3ff', accent3: '#f472b6', rgb: '167,139,250' },
    ember:  { accent: '#ff6b1a', accent2: '#ffc800', accent3: '#ff4d6a', rgb: '255,107,26' },
    ice:    { accent: '#7dd3fc', accent2: '#38bdf8', accent3: '#e0f2fe', rgb: '125,211,252' },
    gold:   { accent: '#ffc800', accent2: '#ff9f43', accent3: '#ffe8b0', rgb: '255,200,0' },
    matrix: { accent: '#00ff88', accent2: '#00f3ff', accent3: '#14532d', rgb: '0,255,136' },
    rose:   { accent: '#fb7185', accent2: '#f472b6', accent3: '#00f3ff', rgb: '251,113,133' },
  };

  const DEFAULTS = {
    // Layout — arrangement, not color
    layout: 'auto',          // auto | phone | desktop
    density: 'comfortable',  // comfortable | compact
    // Lighting — glow / accents / neon, not arrangement
    accent: 'cyan',
    glow: 55,                // 0–100
    lighting: 'full',        // full | soft | dim | flat
    halo: true,
    ambient: true,
  };

  function clamp(n, lo, hi) {
    n = Number(n);
    if (!Number.isFinite(n)) return lo;
    return Math.max(lo, Math.min(hi, n));
  }

  function safeGet(key) {
    try { return localStorage.getItem(key); } catch (_) { return null; }
  }
  function safeSet(key, val) {
    try {
      localStorage.setItem(key, val);
      return true;
    } catch (err) {
      if (err && (err.name === 'QuotaExceededError' || err.code === 22)) {
        try { localStorage.removeItem('aitoolbox.pro.recents'); } catch (_) { /* ignore */ }
        try { localStorage.setItem(key, val); return true; } catch (_) { return false; }
      }
      return false;
    }
  }

  function load() {
    let raw = {};
    try { raw = JSON.parse(safeGet(LS) || '{}') || {}; } catch (_) { raw = {}; }
    const out = { ...DEFAULTS, ...raw };
    if (!['auto', 'phone', 'desktop'].includes(out.layout)) out.layout = 'auto';
    if (!['comfortable', 'compact'].includes(out.density)) out.density = 'comfortable';
    if (!ACCENTS[out.accent]) out.accent = 'cyan';
    out.glow = clamp(out.glow, 0, 100);
    if (!['full', 'soft', 'dim', 'flat'].includes(out.lighting)) out.lighting = 'full';
    out.halo = out.halo !== false;
    out.ambient = out.ambient !== false;
    return out;
  }

  let prefs = load();

  function save(patch) {
    prefs = { ...prefs, ...patch };
    safeSet(LS, JSON.stringify(prefs));
    apply();
    try { global.dispatchEvent(new CustomEvent(EVT, { detail: get() })); } catch (_) { /* ignore */ }
    return prefs;
  }

  function get() { return { ...prefs }; }

  function wantsPhone(p) {
    if (p.layout === 'phone') return true;
    if (p.layout === 'desktop') return false;
    try {
      const narrow = window.matchMedia('(max-width: 720px)').matches;
      const coarse = window.matchMedia('(pointer: coarse)').matches && window.innerWidth <= 900;
      return !!(narrow || coarse);
    } catch (_) {
      return (window.innerWidth || 1200) <= 720;
    }
  }

  function resolvedLayout(p) {
    return wantsPhone(p) ? 'phone' : 'desktop';
  }

  function apply(p) {
    p = p || prefs;
    const html = document.documentElement;
    const body = document.body;
    const pal = ACCENTS[p.accent] || ACCENTS.cyan;
    const layout = resolvedLayout(p);
    const glowMul = clamp(p.glow, 0, 100) / 50; // 1.0 at 50

    html.setAttribute('data-atx-layout', layout);
    html.setAttribute('data-atx-lighting', p.lighting);
    html.setAttribute('data-atx-accent', p.accent);
    html.style.setProperty('--atx-accent', pal.accent);
    html.style.setProperty('--atx-accent2', pal.accent2);
    html.style.setProperty('--atx-accent3', pal.accent3);
    html.style.setProperty('--atx-accent-rgb', pal.rgb);
    html.style.setProperty('--atx-glow-mul', String(glowMul));
    html.style.setProperty('--ui-accent', pal.accent);
    html.style.setProperty('--ui-accent2', pal.accent2);
    html.style.setProperty('--ui-accent3', pal.accent3);
    html.style.setProperty('--accent', pal.accent);
    html.style.setProperty('--accent2', pal.accent3);
    const a = 0.45 * glowMul * (p.lighting === 'flat' ? 0 : p.lighting === 'dim' ? 0.35 : p.lighting === 'soft' ? 0.7 : 1);
    const blur = Math.round(16 * glowMul);
    html.style.setProperty('--ui-glow', p.lighting === 'flat' || glowMul <= 0.02
      ? 'none'
      : '0 0 ' + blur + 'px rgba(' + pal.rgb + ',' + a.toFixed(3) + ')');

    if (body) {
      body.classList.toggle('atx-layout-phone', layout === 'phone');
      body.classList.toggle('atx-layout-desktop', layout === 'desktop');
      body.classList.toggle('atx-dense', p.density === 'compact');
      body.classList.toggle('atx-halo-off', !p.halo);
      body.classList.toggle('atx-ambient-off', !p.ambient);
      body.classList.toggle('atx-lit-full', p.lighting === 'full');
      body.classList.toggle('atx-lit-soft', p.lighting === 'soft');
      body.classList.toggle('atx-lit-dim', p.lighting === 'dim');
      body.classList.toggle('atx-lit-flat', p.lighting === 'flat');
      try { localStorage.setItem('aitoolbox.pro.dense', p.density === 'compact' ? '1' : '0'); } catch (_) { /* ignore */ }
    }
    return p;
  }

  function injectCss() {
    if (document.getElementById('aitoolbox-prefs-css')) return;
    const css = document.createElement('style');
    css.id = 'aitoolbox-prefs-css';
    css.textContent = `
/* Layout (phone vs desktop) — arrangement only */
html[data-atx-layout="phone"] .fafo-layout-root.fafo-layout-columns{
  flex-direction:column !important;
}
html[data-atx-layout="phone"] .fafo-layout-columns > .fafo-layout-panel{
  width:100% !important; max-width:100% !important; min-width:0 !important;
  flex:1 1 auto !important;
}
html[data-atx-layout="phone"] .fafo-split-handle{
  cursor:ns-resize;
}
html[data-atx-layout="phone"] #atx-pro-bar{
  flex-direction:column; align-items:stretch; gap:8px;
  padding:8px 10px calc(10px + env(safe-area-inset-bottom,0px));
}
html[data-atx-layout="phone"] #atx-pro-bar .atx-chips,
html[data-atx-layout="phone"] #atx-pro-bar .atx-actions{
  width:100%;
}
html[data-atx-layout="phone"] #atx-pro-bar a.atx-chip,
html[data-atx-layout="phone"] #atx-pro-bar button.atx-chip,
html[data-atx-layout="phone"] .btn, html[data-atx-layout="phone"] button.pill{
  min-height:44px; padding:8px 14px;
}
html[data-atx-layout="phone"] body, html[data-atx-layout="phone"]{
  font-size:16px;
}
html[data-atx-layout="desktop"] #atx-pro-bar{
  flex-direction:row;
}

/* Lighting (glow + accents) — color / neon only */
html[data-atx-lighting="soft"] .panel, html[data-atx-lighting="soft"] .ui-card{
  box-shadow:0 8px 28px rgba(0,0,0,.28) !important;
}
html[data-atx-lighting="dim"]{
  filter:saturate(.88) brightness(.94);
}
html[data-atx-lighting="dim"] .panel::before,
html[data-atx-lighting="dim"] .panel::after,
html[data-atx-lighting="flat"] .panel::before,
html[data-atx-lighting="flat"] .panel::after{
  opacity:.15 !important; animation:none !important;
}
html[data-atx-lighting="flat"]{
  --ui-glow:none !important;
}
html[data-atx-lighting="flat"] .panel, html[data-atx-lighting="flat"] .ui-card,
html[data-atx-lighting="flat"] .atx-chip, html[data-atx-lighting="flat"] .btn.primary{
  box-shadow:none !important;
}
body.atx-halo-off .ui-btn.primary, body.atx-halo-off .atx-chip.primary,
body.atx-halo-off #atx-pro-bar{
  box-shadow:none !important;
}
body.atx-ambient-off #ambient, body.atx-ambient-off #lxRoot,
body.atx-ambient-off .amb-blob, body.atx-ambient-off .amb-sweep,
body.atx-ambient-off .amb-wash, body.atx-ambient-off .lx-wash{
  opacity:0 !important; visibility:hidden !important; animation:none !important;
}

/* Look panel */
#atx-look{
  position:fixed; inset:0; z-index:99992; display:none; place-items:center;
  background:rgba(0,0,0,.58); backdrop-filter:blur(5px);
}
#atx-look.open{display:grid}
#atx-look .atx-look-panel{
  width:min(560px,94vw); max-height:min(86vh,720px); overflow:auto;
  background:linear-gradient(165deg,#10161f,#0a0e14 70%);
  border:1px solid rgba(var(--atx-accent-rgb,0,243,255),.4);
  border-radius:16px; padding:16px 16px 14px; color:#e8eef6;
  box-shadow:var(--ui-glow), 0 24px 70px rgba(0,0,0,.55);
  font:600 12px/1.45 "Segoe UI",system-ui,sans-serif;
}
#atx-look h2{margin:0 0 4px;font-size:15px;letter-spacing:.06em;color:var(--atx-accent,#00f3ff)}
#atx-look .atx-look-sub{color:#9aa8b8;font-size:11px;margin:0 0 14px;font-weight:500}
#atx-look .atx-look-sec{
  border:1px solid rgba(255,255,255,.08); border-radius:12px;
  padding:12px; margin:0 0 12px; background:rgba(0,0,0,.22);
}
#atx-look .atx-look-sec h3{
  margin:0 0 8px; font-size:10px; letter-spacing:.14em; text-transform:uppercase;
  color:var(--atx-accent,#00f3ff);
}
#atx-look .atx-look-hint{color:#8b98a8;font-size:10px;font-weight:500;margin:6px 0 0}
#atx-look .atx-seg{display:flex;flex-wrap:wrap;gap:6px}
#atx-look .atx-seg button{
  appearance:none; border:1px solid rgba(255,255,255,.16);
  background:#121820; color:#e8eef6; border-radius:999px;
  padding:7px 12px; cursor:pointer; font:700 11px/1 "Segoe UI",system-ui,sans-serif;
}
#atx-look .atx-seg button[aria-pressed="true"]{
  border-color:var(--atx-accent,#00f3ff); color:#fff;
  box-shadow:0 0 0 1px var(--atx-accent,#00f3ff);
  background:rgba(var(--atx-accent-rgb,0,243,255),.16);
}
#atx-look label.row{
  display:grid; grid-template-columns:110px 1fr 42px; gap:8px; align-items:center;
  margin:8px 0; font-size:11px; color:#c5d0dc;
}
#atx-look input[type="range"]{width:100%; accent-color:var(--atx-accent,#00f3ff)}
#atx-look .swatch{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:middle;box-shadow:0 0 8px currentColor}
#atx-look .toggles{display:flex;flex-wrap:wrap;gap:10px 14px;margin-top:8px}
#atx-look .toggles label{display:flex;align-items:center;gap:6px;cursor:pointer;font-size:11px;color:#c5d0dc}
#atx-look .row-btns{display:flex;flex-wrap:wrap;gap:8px;justify-content:flex-end;margin-top:10px}
#atx-look .row-btns button{
  border:1px solid rgba(var(--atx-accent-rgb,0,243,255),.4);
  background:rgba(var(--atx-accent-rgb,0,243,255),.1); color:#c8fbff;
  border-radius:8px; padding:7px 12px; cursor:pointer; font-weight:700; font-size:11px;
}
#atx-look .row-btns button.ghost{background:transparent;color:#9aa8b8;border-color:rgba(255,255,255,.16)}
@media (max-width:520px){
  #atx-look label.row{grid-template-columns:1fr; gap:4px}
}
#atx-look-chip{
  position:fixed; right:12px; bottom:58px; z-index:99981;
  appearance:none; border:1px solid rgba(var(--atx-accent-rgb,0,243,255),.45);
  background:rgba(8,14,20,.92); color:var(--atx-accent,#00f3ff);
  border-radius:999px; padding:8px 14px; cursor:pointer;
  font:700 11px/1 "Segoe UI",system-ui,sans-serif; letter-spacing:.06em;
  text-transform:uppercase;
  box-shadow:var(--ui-glow);
}
#atx-look-chip:hover{background:rgba(var(--atx-accent-rgb,0,243,255),.16);color:#fff}
body.atx-pro-pad #atx-look-chip{display:none} /* pro bar already has Look */
`;
    (document.head || document.documentElement).appendChild(css);
  }

  function segHtml(name, options, current) {
    return '<div class="atx-seg" role="radiogroup" aria-label="' + name + '">' +
      options.map(function (o) {
        const on = String(current) === String(o.v) ? 'true' : 'false';
        const sw = o.color
          ? '<span class="swatch" style="background:' + o.color + ';color:' + o.color + '"></span>'
          : '';
        return '<button type="button" data-k="' + name + '" data-v="' + o.v + '" aria-pressed="' + on + '">' +
          sw + o.l + '</button>';
      }).join('') + '</div>';
  }

  function openPanel() {
    injectCss();
    let el = document.getElementById('atx-look');
    if (!el) {
      el = document.createElement('div');
      el.id = 'atx-look';
      el.innerHTML = '<div class="atx-look-panel" role="dialog" aria-modal="true" aria-labelledby="atxLookTitle"></div>';
      el.addEventListener('click', function (e) { if (e.target === el) closePanel(); });
      document.body.appendChild(el);
    }
    renderPanel();
    el.classList.add('open');
    const closeBtn = el.querySelector('[data-act="close"]');
    if (closeBtn) closeBtn.focus();
  }

  function closePanel() {
    document.getElementById('atx-look')?.classList.remove('open');
  }

  function renderPanel() {
    const el = document.getElementById('atx-look');
    if (!el) return;
    const p = prefs;
    const live = resolvedLayout(p);
    const panel = el.querySelector('.atx-look-panel');
    panel.innerHTML =
      '<h2 id="atxLookTitle">Look</h2>' +
      '<p class="atx-look-sub">Layout is phone vs desktop. Lighting is glow and accents. They do not replace each other.</p>' +

      '<div class="atx-look-sec">' +
        '<h3>Layout</h3>' +
        segHtml('layout', [
          { v: 'auto', l: 'Auto' },
          { v: 'phone', l: 'Phone' },
          { v: 'desktop', l: 'Desktop' },
        ], p.layout) +
        '<p class="atx-look-hint">Now using <strong>' + live + '</strong> layout' +
          (p.layout === 'auto' ? ' (from this screen).' : '.') +
          ' Phone stacks columns and enlarges tap targets. Desktop keeps side-by-side panels.</p>' +
        '<div style="margin-top:10px"></div>' +
        segHtml('density', [
          { v: 'comfortable', l: 'Comfortable' },
          { v: 'compact', l: 'Compact' },
        ], p.density) +
      '</div>' +

      '<div class="atx-look-sec">' +
        '<h3>Lighting</h3>' +
        segHtml('accent', [
          { v: 'cyan', l: 'Cyan', color: ACCENTS.cyan.accent },
          { v: 'violet', l: 'Violet', color: ACCENTS.violet.accent },
          { v: 'ember', l: 'Ember', color: ACCENTS.ember.accent },
          { v: 'ice', l: 'Ice', color: ACCENTS.ice.accent },
          { v: 'gold', l: 'Gold', color: ACCENTS.gold.accent },
          { v: 'matrix', l: 'Matrix', color: ACCENTS.matrix.accent },
          { v: 'rose', l: 'Rose', color: ACCENTS.rose.accent },
        ], p.accent) +
        '<label class="row"><span>Glow</span><input type="range" min="0" max="100" step="1" id="atxGlow" value="' + p.glow + '"><span id="atxGlowVal">' + p.glow + '</span></label>' +
        segHtml('lighting', [
          { v: 'full', l: 'Full neon' },
          { v: 'soft', l: 'Soft' },
          { v: 'dim', l: 'Dim' },
          { v: 'flat', l: 'Flat (no glow)' },
        ], p.lighting) +
        '<div class="toggles">' +
          '<label><input type="checkbox" id="atxHalo"' + (p.halo ? ' checked' : '') + '> Halo / pulse</label>' +
          '<label><input type="checkbox" id="atxAmbient"' + (p.ambient ? ' checked' : '') + '> Ambient wash</label>' +
        '</div>' +
        '<p class="atx-look-hint">Glow strength and accent color never change phone vs desktop layout.</p>' +
      '</div>' +

      '<div class="row-btns">' +
        '<button type="button" class="ghost" data-act="export">Export</button>' +
        '<button type="button" class="ghost" data-act="import">Import</button>' +
        '<button type="button" class="ghost" data-act="reset-look">Reset look</button>' +
        '<button type="button" class="ghost" data-act="reset-layouts">Reset panel layouts</button>' +
        '<button type="button" data-act="close">Close</button>' +
      '</div>';

    panel.querySelectorAll('[data-k]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        const k = btn.getAttribute('data-k');
        const v = btn.getAttribute('data-v');
        const patch = {};
        patch[k] = v;
        save(patch);
        renderPanel();
        toast(k === 'layout' || k === 'density' ? 'Layout: ' + (k === 'layout' ? v : prefs.density) : 'Lighting updated');
      });
    });
    const glow = panel.querySelector('#atxGlow');
    if (glow) {
      glow.addEventListener('input', function () {
        panel.querySelector('#atxGlowVal').textContent = glow.value;
        save({ glow: clamp(glow.value, 0, 100) });
      });
    }
    panel.querySelector('#atxHalo')?.addEventListener('change', function (e) {
      save({ halo: !!e.target.checked });
    });
    panel.querySelector('#atxAmbient')?.addEventListener('change', function (e) {
      save({ ambient: !!e.target.checked });
    });
    panel.querySelector('[data-act="close"]')?.addEventListener('click', closePanel);
    panel.querySelector('[data-act="reset-look"]')?.addEventListener('click', function () {
      prefs = { ...DEFAULTS };
      save(prefs);
      renderPanel();
      toast('Look reset');
    });
    panel.querySelector('[data-act="reset-layouts"]')?.addEventListener('click', function () {
      try {
        if (global.AIToolboxLayout && typeof global.AIToolboxLayout.resetAll === 'function') {
          global.AIToolboxLayout.resetAll();
          toast('Panel layouts cleared');
        } else {
          toast('Layout engine not on this page');
        }
      } catch (_) { toast('Could not reset panel layouts'); }
    });
    panel.querySelector('[data-act="export"]')?.addEventListener('click', exportPrefs);
    panel.querySelector('[data-act="import"]')?.addEventListener('click', importPrefs);
  }

  function toast(msg) {
    try {
      if (global.AIToolboxPro && typeof global.AIToolboxPro.toast === 'function') {
        global.AIToolboxPro.toast(msg);
        return;
      }
      if (global.AIToolboxUI && typeof global.AIToolboxUI.toast === 'function') {
        global.AIToolboxUI.toast(msg, 'ok');
      }
    } catch (_) { /* ignore */ }
  }

  function exportPrefs() {
    const blob = JSON.stringify({ v: 1, prefs: get(), at: new Date().toISOString() }, null, 2);
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(blob).then(function () { toast('Look JSON copied'); }).catch(downloadJson);
      } else downloadJson();
    } catch (_) { downloadJson(); }
    function downloadJson() {
      try {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob([blob], { type: 'application/json' }));
        a.download = 'fafo-toolbox-look.json';
        a.click();
        toast('Look JSON downloaded');
      } catch (_) { toast('Export failed'); }
    }
  }

  function importPrefs() {
    const raw = window.prompt('Paste Look JSON');
    if (!raw) return;
    try {
      const data = JSON.parse(raw);
      const incoming = data.prefs && typeof data.prefs === 'object' ? data.prefs : data;
      save(incoming);
      renderPanel();
      toast('Look imported');
    } catch (_) {
      toast('Invalid JSON');
    }
  }

  function onResize() {
    if (prefs.layout !== 'auto') return;
    apply();
  }

  function boot() {
    injectCss();
    apply();
    if (!document.getElementById('atx-pro-bar') && !document.getElementById('atx-look-chip') && document.body) {
      const chip = document.createElement('button');
      chip.id = 'atx-look-chip';
      chip.type = 'button';
      chip.textContent = 'Look';
      chip.title = 'Layout is phone vs desktop. Lighting is glow and accents. Shortcut O';
      chip.addEventListener('click', openPanel);
      document.body.appendChild(chip);
    }
    try {
      window.matchMedia('(max-width: 720px)').addEventListener('change', onResize);
    } catch (_) {
      window.addEventListener('resize', onResize);
    }
    document.addEventListener('keydown', function (e) {
      const tag = (e.target && e.target.tagName) || '';
      const typing = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target?.isContentEditable;
      if (e.key === 'Escape') {
        closePanel();
        return;
      }
      if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === 'o' || e.key === 'O') {
        e.preventDefault();
        const box = document.getElementById('atx-look');
        if (box && box.classList.contains('open')) closePanel();
        else openPanel();
      }
    });
  }

  global.AIToolboxPrefs = {
    ACCENTS,
    DEFAULTS,
    load,
    get,
    save,
    apply,
    open: openPanel,
    close: closePanel,
    resolvedLayout: function () { return resolvedLayout(prefs); },
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
    // Apply variables as early as we can so the first paint is close
    try { apply(); } catch (_) { /* ignore */ }
  } else {
    boot();
  }
})(typeof window !== 'undefined' ? window : globalThis);
