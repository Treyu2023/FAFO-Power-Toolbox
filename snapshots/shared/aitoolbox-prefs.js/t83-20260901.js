/**
 * FAFO Toolbox — shell Look prefs
 * --------------------------------
 * Layout   — phone vs desktop (how the chrome is arranged)
 * Lighting — glow, accents, brightness of the neon
 * Colors   — surfaces, text, severity, server pills, borders
 * Type     — title / body / mono fonts
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
    custom: { accent: '#00f3ff', accent2: '#ff6b35', accent3: '#7c5cff', rgb: '0,243,255' },
  };

  const FONTS = [
    { v: 'segoe', l: 'Segoe UI', stack: '"Segoe UI", system-ui, sans-serif' },
    { v: 'system', l: 'System UI', stack: 'system-ui, "Segoe UI", sans-serif' },
    { v: 'tahoma', l: 'Tahoma', stack: 'Tahoma, Geneva, sans-serif' },
    { v: 'verdana', l: 'Verdana', stack: 'Verdana, Geneva, sans-serif' },
    { v: 'trebuchet', l: 'Trebuchet', stack: '"Trebuchet MS", "Segoe UI", sans-serif' },
    { v: 'arial', l: 'Arial', stack: 'Arial, Helvetica, sans-serif' },
    { v: 'georgia', l: 'Georgia', stack: 'Georgia, "Times New Roman", serif' },
    { v: 'garamond', l: 'Garamond', stack: 'Garamond, Georgia, serif' },
    { v: 'palatino', l: 'Palatino', stack: '"Palatino Linotype", Palatino, serif' },
    { v: 'times', l: 'Times', stack: '"Times New Roman", Times, serif' },
    { v: 'consolas', l: 'Consolas', stack: 'Consolas, "Cascadia Mono", monospace' },
    { v: 'cascadia', l: 'Cascadia Mono', stack: '"Cascadia Mono", Consolas, monospace' },
    { v: 'courier', l: 'Courier New', stack: '"Courier New", Courier, monospace' },
    { v: 'lucida', l: 'Lucida Console', stack: '"Lucida Console", Monaco, monospace' },
    { v: 'impact', l: 'Impact', stack: 'Impact, Haettenschweiler, sans-serif' },
    { v: 'comic', l: 'Comic Sans', stack: '"Comic Sans MS", "Segoe Print", cursive' },
    { v: 'custom', l: 'Custom name', stack: '' },
  ];

  const COLOR_FIELDS = [
    { k: 'colorBg', l: 'Page background', aliases: ['--bg', '--atx-bg'] },
    { k: 'colorPanel', l: 'Panel', aliases: ['--panel', '--atx-panel'] },
    { k: 'colorPanel2', l: 'Panel (inset)', aliases: ['--panel2', '--atx-panel2'] },
    { k: 'colorText', l: 'Body text', aliases: ['--text', '--atx-text'] },
    { k: 'colorMuted', l: 'Muted text', aliases: ['--muted', '--atx-muted'] },
    { k: 'colorBorder', l: 'Borders', aliases: ['--border', '--atx-border'] },
    { k: 'colorOk', l: 'OK / success', aliases: ['--ok', '--ui-ok', '--atx-ok'] },
    { k: 'colorWarn', l: 'Warning', aliases: ['--warn', '--atx-warn'] },
    { k: 'colorDanger', l: 'Danger / error', aliases: ['--danger', '--ui-danger', '--atx-danger'] },
    { k: 'colorInfo', l: 'Info', aliases: ['--info', '--atx-info'] },
    { k: 'colorServerOnline', l: 'Server online', aliases: ['--atx-server-online'] },
    { k: 'colorServerOffline', l: 'Server offline', aliases: ['--atx-server-offline'] },
  ];


  const DEFAULTS = {
    // Layout — arrangement, not color
    layout: 'auto',          // auto | phone | desktop
    density: 'comfortable',  // comfortable | compact
    uiScale: 100,            // % whole UI (panels, chrome, assets)
    textScale: 100,          // % extra text in panels / main UI
    scaleChrome: true,       // docks / S1-S2 / Look chip follow UI scale (4K TV)
    // Lighting — glow / accents / neon, not arrangement
    accent: 'cyan',
    glow: 55,                // 0–100
    lighting: 'full',        // full | soft | dim | flat
    halo: true,
    ambient: true,
    fxTheme: 'off',          // off | sparkysparks | paintonsalought  (lighting FX, not layout)
    // Colors — empty string means "leave the page default"
    accentCustom: '',
    colorBg: '',
    colorPanel: '',
    colorPanel2: '',
    colorText: '',
    colorMuted: '',
    colorBorder: '',
    colorOk: '',
    colorWarn: '',
    colorDanger: '',
    colorInfo: '',
    colorServerOnline: '',
    colorServerOffline: '',
    // Type
    fontTitle: 'segoe',
    fontBody: 'segoe',
    fontMono: 'consolas',
    fontTitleCustom: '',
    fontBodyCustom: '',
    fontMonoCustom: '',
  };

  function clamp(n, lo, hi) {
    n = Number(n);
    if (!Number.isFinite(n)) return lo;
    return Math.max(lo, Math.min(hi, n));
  }

  function isHex(v) {
    return typeof v === 'string' && /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/.test(v.trim());
  }
  function normHex(v) {
    if (!isHex(v)) return '';
    let h = v.trim();
    if (h.length === 4) {
      h = '#' + h[1] + h[1] + h[2] + h[2] + h[3] + h[3];
    }
    return h.toLowerCase();
  }
  function hexToRgb(hex) {
    const h = normHex(hex).replace('#', '');
    if (h.length < 6) return '';
    return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)).join(',');
  }
  function fontStack(key, custom) {
    if (key === 'custom') {
      const name = String(custom || '').trim().replace(/["<>;]/g, '');
      if (name) return '"' + name + '", system-ui, sans-serif';
    }
    const f = FONTS.find((x) => x.v === key);
    return (f && f.stack) || FONTS[0].stack;
  }
  function fontOk(key) {
    return FONTS.some((f) => f.v === key);
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
    out.uiScale = clamp(out.uiScale != null ? out.uiScale : 100, UI_SCALE_MIN, UI_SCALE_MAX);
    out.textScale = clamp(out.textScale != null ? out.textScale : 100, 25, 800);
    if (out.accent !== 'custom' && !ACCENTS[out.accent]) out.accent = 'cyan';
    out.accentCustom = normHex(out.accentCustom);
    out.glow = clamp(out.glow, 0, 100);
    if (!['full', 'soft', 'dim', 'flat'].includes(out.lighting)) out.lighting = 'full';
    out.halo = out.halo !== false;
    out.ambient = out.ambient !== false;
    if (!['off', 'sparkysparks', 'paintonsalought'].includes(out.fxTheme)) out.fxTheme = 'off';
    COLOR_FIELDS.forEach(function (f) {
      out[f.k] = normHex(out[f.k]);
    });
    if (!fontOk(out.fontTitle)) out.fontTitle = 'segoe';
    if (!fontOk(out.fontBody)) out.fontBody = 'segoe';
    if (!fontOk(out.fontMono)) out.fontMono = 'consolas';
    out.fontTitleCustom = String(out.fontTitleCustom || '').slice(0, 64);
    out.fontBodyCustom = String(out.fontBodyCustom || '').slice(0, 64);
    out.fontMonoCustom = String(out.fontMonoCustom || '').slice(0, 64);
    return out;
  }

  let prefs = load();

  function save(patch) {
    prefs = { ...prefs, ...patch };
    safeSet(LS, JSON.stringify(prefs));
    apply();
    try {
      const ev = new CustomEvent(EVT, { detail: get() });
      global.dispatchEvent(ev);
      document.dispatchEvent(ev);
    } catch (_) { /* ignore */ }
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
    let pal = ACCENTS[p.accent] || ACCENTS.cyan;
    if (p.accent === 'custom' && isHex(p.accentCustom)) {
      const rgb = hexToRgb(p.accentCustom);
      pal = {
        accent: p.accentCustom,
        accent2: pal.accent2,
        accent3: pal.accent3,
        rgb: rgb || pal.rgb,
      };
    }
    const layout = resolvedLayout(p);
    const glowMul = clamp(p.glow, 0, 100) / 50; // 1.0 at 50

    html.setAttribute('data-atx-layout', layout);
    html.setAttribute('data-atx-lighting', p.lighting);
    html.setAttribute('data-atx-accent', p.accent);
    html.setAttribute('data-atx-fx', p.fxTheme === 'sparkysparks' || p.fxTheme === 'paintonsalought' ? p.fxTheme : 'off');
    html.style.setProperty('--atx-accent', pal.accent);
    html.style.setProperty('--atx-accent2', pal.accent2);
    html.style.setProperty('--atx-accent3', pal.accent3);
    html.style.setProperty('--atx-accent-rgb', pal.rgb);
    html.style.setProperty('--atx-glow-mul', String(glowMul));
    const ui = clamp(p.uiScale != null ? p.uiScale : 100, 25, 800) / 100;
    const tx = clamp(p.textScale != null ? p.textScale : 100, 25, 800) / 100;
    html.style.setProperty('--atx-ui-scale', String(ui));
    html.style.setProperty('--atx-text-scale', String(tx));
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

    COLOR_FIELDS.forEach(function (f) {
      const val = p[f.k];
      f.aliases.forEach(function (name) {
        if (isHex(val)) html.style.setProperty(name, val);
        else html.style.removeProperty(name);
      });
    });
    if (isHex(p.colorBorder)) {
      const rgb = hexToRgb(p.colorBorder);
      if (rgb) html.style.setProperty('--atx-border-rgb', rgb);
    } else {
      html.style.removeProperty('--atx-border-rgb');
    }

    const titleStack = fontStack(p.fontTitle, p.fontTitleCustom);
    const bodyStack = fontStack(p.fontBody, p.fontBodyCustom);
    const monoStack = fontStack(p.fontMono, p.fontMonoCustom);
    html.style.setProperty('--atx-font-title', titleStack);
    html.style.setProperty('--atx-font-body', bodyStack);
    html.style.setProperty('--atx-font-mono', monoStack);
    if (body) {
      body.style.fontFamily = bodyStack;
      if (isHex(p.colorText)) body.style.color = p.colorText;
      else body.style.removeProperty('color');
      if (isHex(p.colorBg)) body.style.backgroundColor = p.colorBg;
      else body.style.removeProperty('background-color');
    }
    markScaleRoots();
    return p;
  }

  const OVERLAY_SEL = [
    '#atx-look', '#atx-look-chip', '#atx-pro-bar', '#atx-pro-help', '#atx-pro-toast',
    '#atx-theme-fx', '#ui-toast-global',
    '.fafo-layout-float-dock', '.ui-modal-bg', '.ui-tutorial-bg', '.ui-toast', '.ui-tooltip',
    '.dbg-panel', '.compare-panel', '.cine-root', '.cmdk-backdrop',
    '.tile-modal-backdrop', '.vis-modal-backdrop',
    '#tbSharedServerBar', '#tbCompanionBar', '#settingsModal',
  ].join(',');

  function inIframe() {
    try { return window.self !== window.top; } catch (_) { return true; }
  }

  function isOverlayNode(el) {
    if (!el || el.nodeType !== 1) return true;
    const tag = el.tagName;
    if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'LINK' || tag === 'META' || tag === 'NOSCRIPT') return true;
    try { return el.matches(OVERLAY_SEL); } catch (_) { return false; }
  }

  function markScaleRoots() {
    const html = document.documentElement;
    const body = document.body;
    if (inIframe()) {
      html.setAttribute('data-atx-iframe', '1');
      html.style.setProperty('--atx-ui-scale', '1');
      if (body) body.querySelectorAll('.fafo-scale-root').forEach(function (n) { n.classList.remove('fafo-scale-root'); });
      return;
    }
    html.removeAttribute('data-atx-iframe');
    if (!body) return;
    Array.prototype.forEach.call(body.children, function (el) {
      if (isOverlayNode(el)) el.classList.remove('fafo-scale-root');
      else el.classList.add('fafo-scale-root');
    });
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
html[data-atx-layout="phone"] .fafo-chrome-btn{
  min-width:32px; min-height:32px; width:auto; height:auto;
}
html[data-atx-layout="desktop"] #atx-pro-bar{
  flex-direction:row;
}

/* Scale the app shell only. Overlays (Look, pro bar, modals) stay 1:1 with the viewport. */
.fafo-scale-root {
  zoom: var(--atx-ui-scale, 1);
}
html[data-atx-iframe="1"] .fafo-scale-root {
  zoom: 1 !important;
}
body.run-active .fafo-scale-root,
body.tat-stage .fafo-scale-root,
html:fullscreen .fafo-scale-root,
html:-webkit-full-screen .fafo-scale-root {
  zoom: 1;
}
.fafo-panel-body, .panel, .ui-card,
.hs-list, .history-list, .tips, .section-title, .section-label {
  font-size: calc(1em * var(--atx-text-scale, 1));
}

/* Lighting (glow + accents) — color / neon only */
html[data-atx-lighting="soft"] .panel, html[data-atx-lighting="soft"] .ui-card{
  box-shadow:0 8px 28px rgba(0,0,0,.28) !important;
}
html[data-atx-lighting="dim"] .fafo-scale-root{
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
  position:fixed; inset:0; z-index:100000; display:none; place-items:center;
  background:rgba(0,0,0,.58); backdrop-filter:blur(5px);
}
#atx-look.open{display:grid}
#atx-look .atx-look-panel{
  width:min(640px,96vw); max-height:min(90vh,860px); overflow:auto;
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
  display:grid; grid-template-columns:110px 1fr auto; gap:8px; align-items:center;
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

/* Colors & type — applied globally so every tool can be uniquely theirs */
html, body{
  font-family: var(--atx-font-body, "Segoe UI", system-ui, sans-serif);
}
h1, h2, h3, h4, h5, h6,
.fafo-panel-title, .fafo-section-title, .fafo-section-chrome h3,
.nav-bar h1, .atx-brand, .ui-card h2, .ui-modal h3, .ui-tutorial-card h4,
.dup-group h4, .detail-head h2, .compare-top h3{
  font-family: var(--atx-font-title, inherit);
}
code, pre, kbd, .mono, .file-path, .dup-folder, .dbg-panel, .preview-list{
  font-family: var(--atx-font-mono, Consolas, "Cascadia Mono", monospace);
}
.server-pill.online{
  color: var(--atx-server-online, var(--ok, var(--ui-ok, #00ff88))) !important;
  border-color: var(--atx-server-online, var(--ok, var(--ui-ok, #00ff88))) !important;
}
.server-pill.offline{
  color: var(--atx-server-offline, var(--danger, var(--ui-danger, #ff4466))) !important;
  border-color: var(--atx-server-offline, var(--danger, var(--ui-danger, #ff4466))) !important;
}
.ui-score.high, .persist-pill{ color: var(--ok, var(--ui-ok)); }
.ui-score.low{ color: var(--danger, var(--ui-danger)); }
.ui-score.mid{ color: var(--warn, #ffc800); }

#atx-look .atx-look-panel{width:min(640px,96vw); max-height:min(90vh,860px)}
#atx-look .color-pair{display:flex;align-items:center;gap:8px;min-width:0}
#atx-look input[type="color"]{
  width:36px;height:28px;padding:0;border:1px solid rgba(255,255,255,.2);
  background:#10141c;border-radius:6px;cursor:pointer;
}
#atx-look input[type="text"].hex, #atx-look input.hex{
  width:92px;background:#10141c;color:#e8eef6;border:1px solid #445;
  border-radius:6px;padding:4px 6px;font:600 11px/1 ui-monospace,Consolas,monospace;
}
#atx-look select.atx-font{
  width:100%;background:#10141c;color:#e8eef6;border:1px solid #445;
  border-radius:6px;padding:6px 8px;font:600 11px/1.3 "Segoe UI",system-ui,sans-serif;
}
#atx-look .row-btns button.mini, #atx-look button.mini{
  padding:4px 8px;font-size:10px;border-radius:6px;
  border:1px solid rgba(255,255,255,.16);background:transparent;color:#9aa8b8;cursor:pointer;
}
#atx-look .swatch-preview{
  display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 0;
}
#atx-look .swatch-preview span{
  font:700 10px/1 "Segoe UI",system-ui,sans-serif;padding:6px 10px;border-radius:999px;
  border:1px solid currentColor;
}
`;
    (document.head || document.documentElement).appendChild(css);
  }

  function colorRowsHtml(p) {
    const fallbacks = {
      colorBg: '#0a0e14', colorPanel: '#121820', colorPanel2: '#0d1218',
      colorText: '#e8eef6', colorMuted: '#8b9bb0', colorBorder: '#1a3a44',
      colorOk: '#4ade80', colorWarn: '#fbbf24', colorDanger: '#f87171', colorInfo: '#67e8f9',
      colorServerOnline: '#4ade80', colorServerOffline: '#f87171',
    };
    return COLOR_FIELDS.map(function (f) {
      const cur = isHex(p[f.k]) ? p[f.k] : '';
      const shown = cur || fallbacks[f.k] || '#00f3ff';
      return '<label class="row"><span>' + f.l + '</span>' +
        '<span class="color-pair">' +
          '<input type="color" id="atx_' + f.k + '" value="' + shown + '">' +
          '<input type="text" class="hex" id="atx_' + f.k + 'Hex" value="' + cur + '" placeholder="' + (fallbacks[f.k] || '') + '" maxlength="9">' +
        '</span>' +
        '<button type="button" class="mini" data-clear="' + f.k + '">Default</button></label>';
    }).join('');
  }

  function fontRowHtml(key, label, current, custom) {
    const opts = FONTS.map(function (f) {
      return '<option value="' + f.v + '"' + (current === f.v ? ' selected' : '') + '>' + f.l + '</option>';
    }).join('');
    const customShow = current === 'custom' || String(custom || '').trim();
    return '<label class="row"><span>' + label + '</span>' +
      '<select class="atx-font" id="atx_' + key + '">' + opts + '</select>' +
      '<span></span></label>' +
      (customShow
        ? '<label class="row"><span>Custom ' + label.toLowerCase() + '</span>' +
          '<input type="text" id="atx_' + key + 'Custom" value="' + String(custom || '').replace(/"/g, '"') + '" placeholder="Font name on this PC" style="width:100%;background:#10141c;color:#e8eef6;border:1px solid #445;border-radius:6px;padding:6px 8px">' +
          '<span></span></label>'
        : '');
  }

  function bindColorPair(colorId, hexId, key, extra) {
    const panel = document.getElementById('atx-look');
    if (!panel) return;
    const c = panel.querySelector('#' + colorId);
    const h = panel.querySelector('#' + hexId);
    function commit(v, rerender) {
      v = normHex(v);
      if (!v) return;
      const patch = {};
      patch[key] = v;
      save(patch);
      if (typeof extra === 'function') extra(v);
      else if (rerender) renderPanel();
    }
    c && c.addEventListener('input', function () { if (h) h.value = c.value; commit(c.value, false); });
    c && c.addEventListener('change', function () { commit(c.value, true); });
    h && h.addEventListener('change', function () {
      const v = normHex(h.value);
      if (!v) { const patch = {}; patch[key] = ''; save(patch); renderPanel(); return; }
      if (c) c.value = v;
      commit(v, true);
    });
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
    const palLive = ACCENTS[p.accent] || ACCENTS.cyan;
    const panel = el.querySelector('.atx-look-panel');
    panel.innerHTML =
      '<h2 id="atxLookTitle">Look</h2>' +
      '<p class="atx-look-sub">Make this toolbox yours. Layout is phone vs desktop. Lighting is glow. Colors, severity, server pills, and fonts are yours to mix.</p>' +

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
        '<label class="row"><span>UI scale</span><input type="range" min="25" max="800" step="5" id="atxUiScale" value="' + p.uiScale + '"><input type="number" min="25" max="800" step="5" id="atxUiScaleN" value="' + p.uiScale + '" style="width:64px;background:#10141c;color:#e8eef6;border:1px solid #445;border-radius:6px;padding:4px"></label>' +
        '<label class="row"><span>Text scale</span><input type="range" min="25" max="800" step="5" id="atxTextScale" value="' + p.textScale + '"><input type="number" min="25" max="800" step="5" id="atxTextScaleN" value="' + p.textScale + '" style="width:64px;background:#10141c;color:#e8eef6;border:1px solid #445;border-radius:6px;padding:4px"></label>' +
        '<p class="atx-look-hint">UI scale resizes chrome, panels, and assets. Text scale is extra for copy inside panels. Drag panel edges as large as you want — no window-size cap. Ctrl+mouse-wheel also changes UI scale. Type up to 800% in the box.</p>' +
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
          { v: 'custom', l: 'Custom', color: (isHex(p.accentCustom) ? p.accentCustom : '#ffffff') },
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
        '<label class="row"><span>Custom accent</span>' +
          '<span class="color-pair"><input type="color" id="atxAccentCustom" value="' + (isHex(p.accentCustom) ? p.accentCustom : (palLive && palLive.accent) || '#00f3ff') + '">' +
          '<input type="text" class="hex" id="atxAccentCustomHex" value="' + (p.accentCustom || '') + '" placeholder="#00f3ff" maxlength="9"></span>' +
          '<button type="button" class="mini" data-clear="accentCustom">Default</button></label>' +
      '</div>' +

      '<div class="atx-look-sec">' +
        '<h3>Colors</h3>' +
        colorRowsHtml(p) +
        '<div class="swatch-preview" aria-hidden="true">' +
          '<span style="color:var(--ok,#4ade80);border-color:currentColor">OK</span>' +
          '<span style="color:var(--warn,#fbbf24);border-color:currentColor">Warn</span>' +
          '<span style="color:var(--danger,#f87171);border-color:currentColor">Danger</span>' +
          '<span style="color:var(--info,#67e8f9);border-color:currentColor">Info</span>' +
          '<span class="server-pill online" style="text-transform:uppercase">● Online</span>' +
          '<span class="server-pill offline" style="text-transform:uppercase">○ Offline</span>' +
        '</div>' +
        '<p class="atx-look-hint">Empty hex = that tool keeps its own default. Pick a color or type any #hex. Export/import saves the whole skin.</p>' +
      '</div>' +

      '<div class="atx-look-sec">' +
        '<h3>Type</h3>' +
        fontRowHtml('fontTitle', 'Titles', p.fontTitle, p.fontTitleCustom) +
        fontRowHtml('fontBody', 'Body', p.fontBody, p.fontBodyCustom) +
        fontRowHtml('fontMono', 'Mono / paths', p.fontMono, p.fontMonoCustom) +
        '<p class="atx-look-hint">Titles cover headings and panel chrome. Body is everything else. Mono is paths, code, and hashes. Custom name uses a font already installed on this PC.</p>' +
      '</div>' +

      '<div class="atx-look-sec">' +
        '<h3>Theme FX</h3>' +
        segHtml('fxTheme', [
          { v: 'off', l: 'Off' },
          { v: 'sparkysparks', l: 'SparkySparks' },
          { v: 'paintonsalought', l: 'PAINTONSaLOUGHT' },
        ], p.fxTheme || 'off') +
        '<p class="atx-look-hint">SparkySparks: click fireworks, move to shower bloom sparks that pile at the bottom, scroll blows piles away, borders lightning-flash in burst colors. PAINTONSaLOUGHT: same motion with neon / blacklight paint specks that swell when you get near them. Lighting, not layout.</p>' +
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
        if (k === 'fxTheme' && v === 'sparkysparks') patch.accent = 'gold';
        if (k === 'fxTheme' && v === 'paintonsalought') patch.accent = 'violet';
        if (k === 'accent' && v === 'custom' && !prefs.accentCustom) {
          patch.accentCustom = (ACCENTS.cyan && ACCENTS.cyan.accent) || '#00f3ff';
        }
        save(patch);
        renderPanel();
        toast(k === 'layout' || k === 'density' ? 'Layout: ' + (k === 'layout' ? v : prefs.density)
          : (k === 'fxTheme' ? (v === 'off' ? 'Theme FX off' : 'Theme: ' + v) : 'Lighting updated'));
      });
    });
    const glow = panel.querySelector('#atxGlow');
    if (glow) {
      glow.addEventListener('input', function () {
        panel.querySelector('#atxGlowVal').textContent = glow.value;
        save({ glow: clamp(glow.value, 0, 100) });
      });
    }
    function bindScale(rangeId, numId, key) {
      const r = panel.querySelector('#' + rangeId);
      const n = panel.querySelector('#' + numId);
      function setBoth(v) {
        v = clamp(v, 25, 800);
        if (r) r.value = String(v);
        if (n) n.value = String(v);
        const patch = {};
        patch[key] = v;
        save(patch);
      }
      r && r.addEventListener('input', function () { setBoth(r.value); if (n) n.value = r.value; });
      n && n.addEventListener('change', function () { setBoth(n.value); });
    }
    bindScale('atxUiScale', 'atxUiScaleN', 'uiScale');
    bindScale('atxTextScale', 'atxTextScaleN', 'textScale');
    bindColorPair('atxAccentCustom', 'atxAccentCustomHex', 'accentCustom', function (hex) {
      save({ accent: 'custom', accentCustom: hex });
      renderPanel();
    });
    COLOR_FIELDS.forEach(function (f) {
      bindColorPair('atx_' + f.k, 'atx_' + f.k + 'Hex', f.k);
    });
    panel.querySelectorAll('[data-clear]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        const k = btn.getAttribute('data-clear');
        const patch = {};
        patch[k] = '';
        if (k === 'accentCustom') patch.accent = 'cyan';
        save(patch);
        renderPanel();
        toast('Reverted to default');
      });
    });
    ['fontTitle', 'fontBody', 'fontMono'].forEach(function (k) {
      const sel = panel.querySelector('#atx_' + k);
      const custom = panel.querySelector('#atx_' + k + 'Custom');
      sel && sel.addEventListener('change', function () {
        const patch = {};
        patch[k] = sel.value;
        save(patch);
        renderPanel();
        toast('Font updated');
      });
      custom && custom.addEventListener('change', function () {
        const patch = {};
        patch[k + 'Custom'] = custom.value;
        patch[k] = 'custom';
        save(patch);
        renderPanel();
      });
    });
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

  function loadThemeFx() {
    if (global.AIToolboxThemeFx) {
      try { global.AIToolboxThemeFx.sync(); } catch (_) { /* ignore */ }
      return;
    }
    try {
      const nodes = document.querySelectorAll('script[src]');
      let url = '';
      for (let i = nodes.length - 1; i >= 0; i--) {
        const src = nodes[i].getAttribute('src') || '';
        if (/aitoolbox-prefs\.js/i.test(src)) { url = src.replace(/aitoolbox-prefs\.js(\?.*)?$/i, 'aitoolbox-theme-fx.js'); break; }
        if (/aitoolbox-pro\.js/i.test(src)) { url = src.replace(/aitoolbox-pro\.js(\?.*)?$/i, 'aitoolbox-theme-fx.js'); break; }
      }
      if (!url) url = 'shared/aitoolbox-theme-fx.js';
      const s = document.createElement('script');
      s.src = url;
      s.async = true;
      s.onload = function () { try { global.AIToolboxThemeFx && global.AIToolboxThemeFx.sync(); } catch (_) { /* ignore */ } };
      (document.head || document.documentElement).appendChild(s);
    } catch (_) { /* optional */ }
  }

  function boot() {
    injectCss();
    apply();
    markScaleRoots();
    if (document.body && !document.body._fafoScaleObs) {
      document.body._fafoScaleObs = true;
      try {
        new MutationObserver(function () { markScaleRoots(); }).observe(document.body, { childList: true });
      } catch (_) { /* ignore */ }
    }
    loadThemeFx();
    if (!document.getElementById('atx-pro-bar') && !document.getElementById('atx-look-chip') && document.body && !inIframe()) {
      const chip = document.createElement('button');
      chip.id = 'atx-look-chip';
      chip.type = 'button';
      chip.textContent = 'Look';
      chip.title = 'Look — layout, lighting, colors, fonts. Shortcut O';
      chip.addEventListener('click', openPanel);
      document.body.appendChild(chip);
    }
    document.addEventListener('wheel', function (e) {
      if (!e.ctrlKey) return;
      if (inIframe()) return;
      const body = document.body;
      if (body && (body.classList.contains('run-active') || body.classList.contains('tat-stage'))) return;
      const tag = (e.target && e.target.tagName) || '';
      if (tag === 'INPUT' && e.target.type === 'number') return;
      if (/^(VIDEO|CANVAS|IMG|IFRAME)$/.test(tag)) return;
      if (e.target && e.target.closest && e.target.closest('video, canvas, .video-deck, .compare-content, .prompt-wrap, .prompt')) return;
      e.preventDefault();
      const step = e.deltaY < 0 ? 5 : -5;
      save({ uiScale: clamp(prefs.uiScale + step, 25, 800) });
      if (document.getElementById('atx-look')?.classList.contains('open')) renderPanel();
    }, { passive: false });
    try {
      window.matchMedia('(max-width: 720px)').addEventListener('change', onResize);
    } catch (_) {
      window.addEventListener('resize', onResize);
    }
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        const box = document.getElementById('atx-look');
        if (box && box.classList.contains('open')) {
          e.preventDefault();
          e.stopPropagation();
          closePanel();
        }
        return;
      }
      const tag = (e.target && e.target.tagName) || '';
      const typing = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target?.isContentEditable;
      if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
      const body = document.body;
      if (body && (body.classList.contains('run-active') || body.classList.contains('tat-stage'))) return;
      if (e.key === 'o' || e.key === 'O') {
        e.preventDefault();
        const box = document.getElementById('atx-look');
        if (box && box.classList.contains('open')) closePanel();
        else openPanel();
      }
    }, true);
  }

  global.AIToolboxPrefs = {
    ACCENTS,
    FONTS,
    COLOR_FIELDS,
    DEFAULTS,
    load,
    get,
    save,
    apply,
    open: openPanel,
    close: closePanel,
    inIframe: inIframe,
    markScaleRoots: markScaleRoots,
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
