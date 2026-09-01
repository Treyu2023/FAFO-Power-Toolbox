/**
 * Font Foundry — outline-point editor + color pixels. Always exports a copy.
 * Depends on opentype + FAFO_FOUNDRY_LIB.
 */
(function (global) {
  'use strict';

  const LS = 'fafo_font_foundry_v2';
  const LS_OLD = 'fafo_font_foundry_v1';
  const $ = (id) => document.getElementById(id);
  const clamp = (n, a, b) => Math.max(a, Math.min(b, n));
  const INK_SWATCH = ['#1c1915', '#f4f4f5', '#e11d48', '#f97316', '#eab308', '#22c55e', '#14b8a6', '#3b82f6', '#8b5cf6', '#ec4899', '#a8a29e'];
  const ASCIINAMES = { 32: 'space', 33: 'exclam', 34: 'quotedbl', 35: 'numbersign', 36: 'dollar', 37: 'percent', 38: 'ampersand', 39: 'quotesingle', 40: 'parenleft', 41: 'parenright', 42: 'asterisk', 43: 'plus', 44: 'comma', 45: 'hyphen', 46: 'period', 47: 'slash', 48: 'zero', 49: 'one', 50: 'two', 51: 'three', 52: 'four', 53: 'five', 54: 'six', 55: 'seven', 56: 'eight', 57: 'nine', 58: 'colon', 59: 'semicolon', 60: 'less', 61: 'equal', 62: 'greater', 63: 'question', 64: 'at', 65: 'A', 91: 'bracketleft', 92: 'backslash', 93: 'bracketright', 94: 'asciicircum', 95: 'underscore', 96: 'grave', 97: 'a', 123: 'braceleft', 124: 'bar', 125: 'braceright', 126: 'asciitilde' };

  const FILTERS = [
    { id: 'all', label: 'All' }, { id: 'upper', label: 'A–Z' }, { id: 'lower', label: 'a–z' },
    { id: 'digit', label: '0–9' }, { id: 'punct', label: 'Punct' }, { id: 'sym', label: 'Symbols' },
    { id: 'emoji', label: 'Emoji' }, { id: 'pua', label: 'Icons' },
  ];

  const TOOLS = [
    { tool: 'pencil', title: 'Pencil (B)', svg: '<path d="M4 16l9-9 3 3-9 9H4z"/><path d="M12 8l2 2"/>' },
    { tool: 'eraser', title: 'Eraser (E)', svg: '<path d="M5 5l10 10M15 5L5 15"/>' },
    { tool: 'dropper', title: 'Eyedropper (I)', svg: '<path d="M6 14l8-8 2 2-8 8H6z"/>' },
    { tool: 'fill', title: 'Fill (G)', svg: '<path d="M4 11h12l-2 6H6z"/><path d="M7 11V7a3 3 0 016 0v4"/>' },
    { tool: 'line', title: 'Line', svg: '<path d="M4 16L16 4"/>' },
    { tool: 'rect', title: 'Rect outline', svg: '<rect x="4" y="5" width="12" height="10" rx="1"/>' },
    { tool: 'rectf', title: 'Rect fill', svg: '<rect x="4" y="5" width="12" height="10" rx="1" fill="currentColor" stroke="none"/>' },
    { tool: 'oval', title: 'Oval outline', svg: '<ellipse cx="10" cy="10" rx="6" ry="5"/>' },
    { tool: 'ovalf', title: 'Oval fill', svg: '<ellipse cx="10" cy="10" rx="6" ry="5" fill="currentColor" stroke="none"/>' },
    { tool: 'spray', title: 'Spray', svg: '<circle cx="7" cy="8" r="1"/><circle cx="12" cy="6" r="1"/><circle cx="10" cy="12" r="1"/><circle cx="14" cy="11" r="1"/>' },
    { tool: 'gradient', title: 'Gradient', svg: '<path d="M4 16L16 4"/><path d="M6 16h10M4 12h10"/>' },
    { tool: 'pen', title: 'Outline pen (P)', svg: '<path d="M4 16l8-12 4 3-8 12H4z"/>' },
    { tool: 'stamp', title: 'Stamp last library char', svg: '<path d="M8 4v12M4 8h12"/>' },
    { tool: 'image', title: 'Trace image (color)', svg: '<rect x="3" y="5" width="14" height="10" rx="1"/><circle cx="8" cy="9" r="1.3"/><path d="M7 15l3-3 2 2 3-4"/>' },
  ];

  let project = null;
  let currentU = 65;
  let tool = 'pencil';
  let brush = 1;
  let ink = '#1c1915';
  let paper = '#efece4';
  let filter = 'all';
  let libCat = 'punct';
  let libQuery = '';
  let side = 'font';
  let drawing = false;
  let panning = false;
  let spaceDown = false;
  let startCell = null;
  let hover = null;
  let undo = [];
  let stampChar = '★';
  let recent = [];
  let selectedPt = null;
  let view = { zoom: 1, panX: 0, panY: 0 };
  let pvMode = 'solo';
  let pvScale = 200;
  let editMode = 'auto';
  let previewTimer = 0;
  let previewUrl = null;
  let statusTimer = 0;
  let lastPan = null;

  const stage = $('stage');
  const ctx = stage.getContext('2d');
  const pv = $('pvCanvas');
  const pvx = pv.getContext('2d');

  function toast(msg) {
    const el = $('toast');
    el.textContent = msg;
    el.classList.add('on');
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove('on'), 2400);
  }
  function setStatus(msg) {
    $('status').textContent = msg;
    clearTimeout(statusTimer);
    statusTimer = setTimeout(() => {
      if ($('status').textContent === msg) $('status').textContent = glyphCount() + ' glyphs · ' + (cur().grid && cur().grid.length) + 'px';
    }, 2500);
  }
  function esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&', '<': '<', '>': '>', '"': '"', "'": '&#39;' }[c]));
  }
  function uid() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }
  function glyphName(u) {
    if (u === 0) return '.notdef';
    if (ASCIINAMES[u]) return ASCIINAMES[u];
    if (u >= 65 && u <= 90) return String.fromCharCode(u);
    if (u >= 97 && u <= 122) return String.fromCharCode(u);
    return 'uni' + u.toString(16).toUpperCase().padStart(4, '0');
  }
  function chOf(u) { try { return String.fromCodePoint(u); } catch (_) { return ''; } }
  function parseCode(raw) {
    const s = String(raw || '').trim();
    if (!s) return null;
    const hex = s.match(/^(?:U\+?|0x)?([0-9a-f]{2,6})$/i);
    if (hex && (/^U/i.test(s) || /^0x/i.test(s))) {
      const n = parseInt(hex[1], 16);
      if (n >= 0 && n <= 0x10ffff) return n;
    }
    const cps = Array.from(s);
    if (cps.length === 1) return cps[0].codePointAt(0);
    if (/^[0-9]{2,7}$/.test(s)) { const n = +s; if (n <= 0x10ffff) return n; }
    return cps[0].codePointAt(0);
  }
  function hexRgb(h) {
    const m = String(h || '#000').replace('#', '');
    const n = m.length === 3 ? m.split('').map((c) => c + c).join('') : m;
    return [parseInt(n.slice(0, 2), 16) || 0, parseInt(n.slice(2, 4), 16) || 0, parseInt(n.slice(4, 6), 16) || 0];
  }
  function rgbHex(r, g, b) {
    const h = (n) => clamp(n | 0, 0, 255).toString(16).padStart(2, '0');
    return '#' + h(r) + h(g) + h(b);
  }
  function lerpHex(a, b, t) {
    const A = hexRgb(a), B = hexRgb(b);
    return rgbHex(A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t, A[2] + (B[2] - A[2]) * t);
  }

  function emptyGrid(n) {
    n = clamp(n | 0, 8, 256);
    return Array.from({ length: n }, () => Array(n).fill(null));
  }
  function migrateGrid(grid, n) {
    if (grid && grid.n && Array.isArray(grid.cells)) {
      const g = emptyGrid(grid.n);
      for (let i = 0; i < grid.cells.length; i += 3) {
        const x = grid.cells[i], y = grid.cells[i + 1], v = grid.cells[i + 2];
        if (g[y] && x >= 0 && x < g.length) g[y][x] = v;
      }
      return g;
    }
    if (!grid || !grid.length) return emptyGrid(n || 48);
    if (Array.isArray(grid[0])) return grid;
    const rows = grid.length;
    const g = emptyGrid(rows);
    for (let y = 0; y < rows; y++) {
      const row = String(grid[y] || '');
      for (let x = 0; x < row.length; x++) if (row[x] === '1') g[y][x] = '#1c1915';
    }
    return g;
  }
  function packGrid(grid) {
    const n = grid.length;
    const cells = [];
    for (let y = 0; y < n; y++) {
      const row = grid[y];
      if (!row) continue;
      for (let x = 0; x < n; x++) if (row[x]) cells.push(x, y, row[x]);
    }
    return { n: n, cells: cells };
  }
  function gridN(g) { return (g && g.grid && g.grid.length) || (project && project.grid) || 48; }
  function cellVal(grid, x, y) {
    if (!grid || y < 0 || y >= grid.length) return null;
    const row = grid[y];
    if (!row) return null;
    if (Array.isArray(row)) return row[x] || null;
    return row[x] === '1' ? '#1c1915' : null;
  }
  function setCell(grid, x, y, v) {
    if (!grid || y < 0 || y >= grid.length || x < 0 || x >= grid.length) return;
    if (!Array.isArray(grid[y])) grid[y] = migrateGrid(grid)[y];
    grid[y][x] = v;
  }
  function paintDot(grid, x, y, v, size) {
    const r = Math.max(0, (size | 0) - 1);
    for (let yy = y - r; yy <= y + r; yy++) {
      for (let xx = x - r; xx <= x + r; xx++) {
        if ((xx - x) * (xx - x) + (yy - y) * (yy - y) <= r * r + 0.25) setCell(grid, xx, yy, v);
      }
    }
  }
  function lineOn(grid, x0, y0, x1, y1, v, size) {
    let dx = Math.abs(x1 - x0), sx = x0 < x1 ? 1 : -1;
    let dy = -Math.abs(y1 - y0), sy = y0 < y1 ? 1 : -1;
    let err = dx + dy;
    for (;;) {
      paintDot(grid, x0, y0, v, size);
      if (x0 === x1 && y0 === y1) break;
      const e2 = 2 * err;
      if (e2 >= dy) { err += dy; x0 += sx; }
      if (e2 <= dx) { err += dx; y0 += sy; }
    }
  }
  function rectOn(grid, x0, y0, x1, y1, v, fill) {
    const xa = Math.min(x0, x1), xb = Math.max(x0, x1);
    const ya = Math.min(y0, y1), yb = Math.max(y0, y1);
    for (let y = ya; y <= yb; y++) for (let x = xa; x <= xb; x++) {
      if (fill || y === ya || y === yb || x === xa || x === xb) setCell(grid, x, y, v);
    }
  }
  function ovalOn(grid, x0, y0, x1, y1, v, fill) {
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    const rx = Math.max(0.5, Math.abs(x1 - x0) / 2), ry = Math.max(0.5, Math.abs(y1 - y0) / 2);
    const xa = Math.floor(cx - rx), xb = Math.ceil(cx + rx);
    const ya = Math.floor(cy - ry), yb = Math.ceil(cy + ry);
    for (let y = ya; y <= yb; y++) for (let x = xa; x <= xb; x++) {
      const nx = (x - cx) / rx, ny = (y - cy) / ry;
      const d = nx * nx + ny * ny;
      if (fill ? d <= 1.05 : (d <= 1.08 && d >= 0.62)) setCell(grid, x, y, v);
    }
  }
  function fillOn(grid, x, y, v) {
    const from = cellVal(grid, x, y);
    if (from === v) return;
    const n = grid.length;
    const stack = [[x, y]];
    const seen = new Uint8Array(n * n);
    while (stack.length) {
      const [cx, cy] = stack.pop();
      if (cx < 0 || cy < 0 || cx >= n || cy >= n) continue;
      const i = cy * n + cx;
      if (seen[i]) continue;
      seen[i] = 1;
      if (cellVal(grid, cx, cy) !== from) continue;
      setCell(grid, cx, cy, v);
      stack.push([cx + 1, cy], [cx - 1, cy], [cx, cy + 1], [cx, cy - 1]);
    }
  }
  function sprayOn(grid, x, y, v, size) {
    const r = Math.max(2, size * 2);
    for (let i = 0; i < 8; i++) {
      const a = Math.random() * Math.PI * 2;
      const d = Math.random() * r;
      setCell(grid, Math.round(x + Math.cos(a) * d), Math.round(y + Math.sin(a) * d), v);
    }
  }
  function gradientOn(grid, x0, y0, x1, y1, a, b) {
    const xa = Math.min(x0, x1), xb = Math.max(x0, x1);
    const ya = Math.min(y0, y1), yb = Math.max(y0, y1);
    const dx = x1 - x0 || 1, dy = y1 - y0 || 1, len2 = dx * dx + dy * dy;
    for (let y = ya; y <= yb; y++) for (let x = xa; x <= xb; x++) {
      const t = clamp(((x - x0) * dx + (y - y0) * dy) / len2, 0, 1);
      setCell(grid, x, y, lerpHex(a, b, t));
    }
  }
  function glyphCount() { return project ? Object.keys(project.glyphs).length : 0; }

  function makeGlyph(u, n, extra) {
    return Object.assign({
      unicode: u, name: glyphName(u), advance: 600, source: 'pixel',
      grid: emptyGrid(n), commands: null, color: ink,
    }, extra || {});
  }
  function boxNotdef(g) {
    const n = g.grid.length, c = '#1c1915';
    for (let i = 2; i < n - 2; i++) {
      setCell(g.grid, 2, i, c); setCell(g.grid, n - 3, i, c);
      setCell(g.grid, i, 2, c); setCell(g.grid, i, n - 3, c);
    }
  }
  function newProject(opts) {
    const n = opts.size || 48;
    const p = {
      id: uid(), family: opts.family || 'Foundry Copy', style: opts.style || 'Regular',
      upm: 1000, ascender: 800, descender: -200, grid: n,
      source: opts.source || 'blank', sourceFile: opts.sourceFile || '', glyphs: {},
    };
    p.glyphs[0] = makeGlyph(0, n, { name: '.notdef' });
    boxNotdef(p.glyphs[0]);
    p.glyphs[32] = makeGlyph(32, n, { name: 'space', advance: Math.round(n * 12) });
    return p;
  }
  function migrateProject(p) {
    if (!p || !p.glyphs) return p;
    Object.keys(p.glyphs).forEach((k) => {
      const g = p.glyphs[k];
      g.grid = migrateGrid(g.grid, p.grid || 48);
      if (!g.color) g.color = '#1c1915';
    });
    return p;
  }
  function ensureGlyph(u) {
    if (!project.glyphs[u]) project.glyphs[u] = makeGlyph(u, project.grid);
    const g = project.glyphs[u];
    g.grid = migrateGrid(g.grid, project.grid);
    return g;
  }
  function cur() { return ensureGlyph(currentU); }
  function modeOf(g) {
    if (editMode === 'outline') return 'outline';
    if (editMode === 'pixels') return 'pixels';
    return (g.source === 'path' && g.commands && g.commands.length) ? 'outline' : 'pixels';
  }

  function snapshot() {
    undo.push(JSON.stringify({ u: currentU, g: cur() }));
    if (undo.length > 80) undo.shift();
  }
  function restore() {
    const s = undo.pop();
    if (!s) return;
    const { u, g } = JSON.parse(s);
    g.grid = migrateGrid(g.grid, project.grid);
    project.glyphs[u] = g;
    currentU = u;
    renderAll();
    schedulePreview();
  }

  /* ── color-aware trace ── */
  function traceChar(ch, cols, rows, family, weight, asColor) {
    const c = document.createElement('canvas');
    c.width = cols; c.height = rows;
    const x = c.getContext('2d', { willReadFrequently: true });
    x.clearRect(0, 0, cols, rows);
    const size = Math.floor(rows * 0.82);
    x.font = (weight || '600') + ' ' + size + 'px ' + (family || 'sans-serif');
    x.textAlign = 'center';
    x.textBaseline = 'alphabetic';
    x.fillStyle = ink;
    x.fillText(ch, cols / 2, Math.round(rows * 0.8));
    const img = x.getImageData(0, 0, cols, rows).data;
    const grid = emptyGrid(cols);
    for (let y = 0; y < rows; y++) {
      for (let xx = 0; xx < cols; xx++) {
        const i = (y * cols + xx) * 4;
        const a = img[i + 3];
        if (a < 28) continue;
        if (asColor) grid[y][xx] = rgbHex(img[i], img[i + 1], img[i + 2]);
        else if (a > 90) grid[y][xx] = ink;
      }
    }
    return grid;
  }
  function stampInto(g, ch, family) {
    const n = g.grid.length;
    const face = family || 'Segoe UI Emoji, Apple Color Emoji, Noto Color Emoji, Segoe UI Symbol, sans-serif';
    g.grid = traceChar(ch, n, n, face, '600', true);
    g.source = 'pixel';
    g.commands = null;
  }

  function asciiSet() { const o = []; for (let i = 33; i <= 126; i++) o.push(i); return o; }

  function bootBlank() {
    const n = +$('gridSize').value || 48;
    project = newProject({ family: 'Foundry Copy', size: n, source: 'blank' });
    for (const u of asciiSet()) ensureGlyph(u);
    currentU = 65;
    editMode = 'pixels';
    afterProject('Blank ' + n + '×' + n);
  }
  function bootTrace() {
    const family = $('traceFace').value;
    const n = Math.max(48, +$('gridSize').value || 64);
    $('gridSize').value = n;
    project = newProject({ family: 'Foundry Copy', size: n, source: 'trace:' + family });
    for (const u of [32].concat(asciiSet())) {
      const g = ensureGlyph(u);
      if (u === 32) continue;
      g.grid = traceChar(chOf(u), n, n, family, '600', false);
    }
    currentU = 65;
    editMode = 'pixels';
    afterProject('Traced ' + family.split(',')[0] + ' at ' + n + 'px');
  }
  function bootEmoji() {
    const n = Math.max(48, +$('gridSize').value || 64);
    $('gridSize').value = n;
    project = newProject({ family: 'Foundry Marks', size: n, source: 'emoji-kit' });
    const lib = global.FAFO_FOUNDRY_LIB || [];
    const pack = [];
    ['marks', 'arrows', 'geometric', 'smileys'].forEach((id) => {
      const cat = lib.find((c) => c.id === id);
      if (cat) pack.push(...Array.from(cat.glyphs).slice(0, 24));
    });
    Array.from(new Set(pack)).slice(0, 80).forEach((ch) => {
      const u = ch.codePointAt(0);
      stampInto(ensureGlyph(u), ch);
    });
    ['A', 'B', 'O', 'I', 'X'].forEach((ch) => {
      const g = ensureGlyph(ch.codePointAt(0));
      g.grid = traceChar(ch, n, n, 'Segoe UI, system-ui, sans-serif', '700', false);
    });
    currentU = '★'.codePointAt(0);
    afterProject('Emoji & symbols kit');
  }
  function afterProject(label) {
    $('boot').hidden = true;
    $('family').value = project.family;
    $('styleName').value = project.style;
    $('gridSize').value = project.grid;
    $('metaUpm').value = project.upm;
    $('metaAsc').value = project.ascender;
    $('metaDesc').value = project.descender;
    $('sourceLabel').textContent = label + (project.sourceFile ? ' — ' + project.sourceFile : '') + ' · Save copy never overwrites';
    persist();
    renderAll();
    schedulePreview();
    toast(label);
  }

  /* ── opentype ── */
  function loadFontBuffer(buf, filename) {
    if (!global.opentype) { toast('Font engine missing'); return; }
    let font;
    try { font = global.opentype.parse(buf); }
    catch (e) { toast('Could not read that font'); return; }
    const n = Math.max(64, +$('gridSize').value || 64);
    const fam = (font.names && font.names.fontFamily && (font.names.fontFamily.en || Object.values(font.names.fontFamily)[0])) || 'Imported';
    project = newProject({
      family: String(fam) + ' Copy',
      style: (font.names && font.names.fontSubfamily && (font.names.fontSubfamily.en || 'Regular')) || 'Regular',
      size: n, source: 'file', sourceFile: filename || '',
    });
    project.upm = font.unitsPerEm || 1000;
    project.ascender = font.ascender || 800;
    project.descender = font.descender || -200;
    const glyphs = font.glyphs;
    const count = glyphs.length || 0;
    let added = 0;
    for (let i = 0; i < count && added < 1200; i++) {
      const gl = glyphs.get ? glyphs.get(i) : glyphs.glyphs[i];
      if (!gl) continue;
      const u = (gl.unicode != null) ? gl.unicode : (gl.unicodes && gl.unicodes[0]);
      if (u == null || u === 0) {
        if (gl.name === '.notdef') { project.glyphs[0] = otToGlyph(gl, 0); added++; }
        continue;
      }
      project.glyphs[u] = otToGlyph(gl, u);
      added++;
    }
    if (!project.glyphs[32]) project.glyphs[32] = makeGlyph(32, n, { name: 'space', advance: Math.round(project.upm * 0.3) });
    currentU = project.glyphs[65] ? 65 : +Object.keys(project.glyphs).find((k) => +k > 32) || 0;
    editMode = 'outline';
    tool = 'pen';
    afterProject('Editing outlines of ' + (filename || fam));
  }
  function otToGlyph(gl, u) {
    const cmds = [];
    const path = gl.path;
    if (path && path.commands) {
      path.commands.forEach((c) => {
        if (c.type === 'M') cmds.push({ t: 'M', x: c.x, y: c.y });
        else if (c.type === 'L') cmds.push({ t: 'L', x: c.x, y: c.y });
        else if (c.type === 'C') cmds.push({ t: 'C', x1: c.x1, y1: c.y1, x2: c.x2, y2: c.y2, x: c.x, y: c.y });
        else if (c.type === 'Q') cmds.push({ t: 'Q', x1: c.x1, y1: c.y1, x: c.x, y: c.y });
        else if (c.type === 'Z' || c.type === 'z') cmds.push({ t: 'Z' });
      });
    }
    return {
      unicode: u, name: gl.name || glyphName(u),
      advance: Math.round(gl.advanceWidth || project.upm * 0.6),
      source: cmds.length ? 'path' : 'pixel',
      grid: emptyGrid(project.grid),
      commands: cmds.length ? cmds : null,
      color: '#1c1915',
    };
  }
  function isPainted(grid, x, y) { return !!cellVal(grid, x, y); }
  function gridToPath(grid, g) {
    const path = new global.opentype.Path();
    const rows = grid.length, cols = grid[0].length;
    const usable = project.ascender - project.descender;
    const cw = (g.advance || project.upm * 0.6) / cols;
    const ch = usable / rows;
    for (let y = 0; y < rows; y++) {
      let x = 0;
      while (x < cols) {
        while (x < cols && !isPainted(grid, x, y)) x++;
        if (x >= cols) break;
        let x2 = x;
        while (x2 < cols && isPainted(grid, x2, y)) x2++;
        const xL = Math.round(x * cw), xR = Math.round(x2 * cw);
        const yT = Math.round(project.ascender - y * ch);
        const yB = Math.round(project.ascender - (y + 1) * ch);
        path.moveTo(xL, yB); path.lineTo(xR, yB); path.lineTo(xR, yT); path.lineTo(xL, yT); path.close();
        x = x2;
      }
    }
    return path;
  }
  function commandsToPath(cmds) {
    const path = new global.opentype.Path();
    (cmds || []).forEach((c) => {
      if (c.t === 'M') path.moveTo(c.x, c.y);
      else if (c.t === 'L') path.lineTo(c.x, c.y);
      else if (c.t === 'C') path.curveTo(c.x1, c.y1, c.x2, c.y2, c.x, c.y);
      else if (c.t === 'Q') path.quadTo(c.x1, c.y1, c.x, c.y);
      else if (c.t === 'Z') path.close();
    });
    return path;
  }
  function buildFont() {
    const notdef = project.glyphs[0] || makeGlyph(0, project.grid, { name: '.notdef' });
    const list = [];
    const push = (g) => {
      g.grid = migrateGrid(g.grid, project.grid);
      const path = (g.source === 'path' && g.commands && g.commands.length)
        ? commandsToPath(g.commands)
        : gridToPath(g.grid, g);
      const opts = { name: g.name || glyphName(g.unicode), advanceWidth: Math.max(0, Math.round(g.advance || project.upm * 0.5)), path };
      if (g.unicode) opts.unicode = g.unicode;
      list.push(new global.opentype.Glyph(opts));
    };
    push(notdef);
    Object.keys(project.glyphs).map(Number).sort((a, b) => a - b).forEach((u) => { if (u) push(project.glyphs[u]); });
    return new global.opentype.Font({
      familyName: ($('family').value || project.family || 'Foundry Copy').trim() || 'Foundry Copy',
      styleName: ($('styleName').value || project.style || 'Regular').trim() || 'Regular',
      unitsPerEm: project.upm, ascender: project.ascender, descender: project.descender, glyphs: list,
    });
  }
  function saveCopy() {
    try {
      project.family = $('family').value.trim() || project.family;
      project.style = $('styleName').value.trim() || project.style;
      const font = buildFont();
      const safe = (project.family + '-' + project.style).replace(/[^\w\-]+/g, '-');
      font.download(safe + '.otf');
      persist();
      toast('Downloaded ' + safe + '.otf (original not changed)');
    } catch (e) {
      toast('Could not build font — ' + (e.message || e));
    }
  }
  function savePng() {
    const g = cur();
    const n = g.grid.length;
    const scale = 8;
    const c = document.createElement('canvas');
    c.width = n * scale; c.height = n * scale;
    const x = c.getContext('2d');
    x.fillStyle = paper; x.fillRect(0, 0, c.width, c.height);
    blitGlyph(x, g, 0, 0, n * scale);
    c.toBlob((blob) => {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = (project.family || 'glyph') + '-' + glyphName(currentU) + '.png';
      a.click();
    });
  }

  /* ── view / canvas ── */
  function layout() {
    const n = gridN(cur());
    const pad = 24;
    const base = Math.min(stage.width, stage.height) - pad * 2;
    const size = base * view.zoom;
    return {
      n, pad, size,
      ox: (stage.width - size) / 2 + view.panX,
      oy: (stage.height - size) / 2 + view.panY,
      cell: size / n,
      fontScale: size / project.upm,
    };
  }
  function fontToCanvas(x, y, L) {
    const span = project.ascender - project.descender;
    return { x: L.ox + x * L.fontScale, y: L.oy + (project.ascender - y) / span * L.size };
  }
  function canvasToFont(px, py, L) {
    const span = project.ascender - project.descender;
    return { x: (px - L.ox) / L.fontScale, y: project.ascender - (py - L.oy) / L.size * span };
  }
  function cellAt(ev) {
    const L = layout();
    const r = stage.getBoundingClientRect();
    const x = (ev.clientX - r.left) * (stage.width / r.width);
    const y = (ev.clientY - r.top) * (stage.height / r.height);
    return { x: Math.floor((x - L.ox) / L.cell), y: Math.floor((y - L.oy) / L.cell), px: x, py: y, L };
  }
  function resizeStage() {
    const wrap = document.querySelector('.stage-wrap');
    if (!wrap) return;
    const r = wrap.getBoundingClientRect();
    const size = Math.max(240, Math.floor(Math.min(r.width, r.height) - 2));
    if (size > 10 && (stage.width !== size || stage.height !== size)) {
      stage.width = size; stage.height = size;
    }
    if (project) drawStage();
  }

  function drawStage() {
    if (!project) return;
    const g = cur();
    g.grid = migrateGrid(g.grid, project.grid);
    const L = layout();
    const w = stage.width, h = stage.height;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#141416';
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = paper;
    ctx.fillRect(L.ox, L.oy, L.size, L.size);

    const n = L.n;
    if (n <= 64 && view.zoom >= 0.7) {
      ctx.strokeStyle = 'rgba(28,25,21,.12)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let i = 0; i <= n; i++) {
        ctx.moveTo(L.ox + i * L.cell, L.oy);
        ctx.lineTo(L.ox + i * L.cell, L.oy + L.size);
        ctx.moveTo(L.ox, L.oy + i * L.cell);
        ctx.lineTo(L.ox + L.size, L.oy + i * L.cell);
      }
      ctx.stroke();
    }
    const baseY = fontToCanvas(0, 0, L).y;
    const capY = fontToCanvas(0, project.ascender * 0.7, L).y;
    ctx.strokeStyle = 'rgba(180,40,40,.4)';
    ctx.beginPath(); ctx.moveTo(L.ox, baseY); ctx.lineTo(L.ox + L.size, baseY); ctx.stroke();
    ctx.strokeStyle = 'rgba(40,80,160,.3)';
    ctx.beginPath(); ctx.moveTo(L.ox, capY); ctx.lineTo(L.ox + L.size, capY); ctx.stroke();

    const md = modeOf(g);
    if (md === 'outline' && g.commands && g.commands.length) {
      drawPath(g, L);
    } else {
      for (let y = 0; y < n; y++) {
        for (let x = 0; x < n; x++) {
          const v = cellVal(g.grid, x, y);
          if (!v) continue;
          ctx.fillStyle = v;
          ctx.fillRect(L.ox + x * L.cell, L.oy + y * L.cell, L.cell + 0.3, L.cell + 0.3);
        }
      }
    }
    if (drawing && startCell && hover && /^(line|rect|rectf|oval|ovalf|gradient)$/.test(tool)) {
      ctx.save();
      ctx.strokeStyle = 'rgba(28,25,21,.5)';
      ctx.setLineDash([4, 3]);
      const x0 = L.ox + startCell.x * L.cell, y0 = L.oy + startCell.y * L.cell;
      const x1 = L.ox + hover.x * L.cell, y1 = L.oy + hover.y * L.cell;
      ctx.strokeRect(Math.min(x0, x1), Math.min(y0, y1), Math.abs(x1 - x0) + L.cell, Math.abs(y1 - y0) + L.cell);
      ctx.restore();
    }
    ctx.strokeStyle = 'rgba(28,25,21,.4)';
    ctx.strokeRect(L.ox + 0.5, L.oy + 0.5, L.size - 1, L.size - 1);
  }
  function drawPath(g, L) {
    ctx.save();
    ctx.beginPath();
    (g.commands || []).forEach((c) => {
      const p = (x, y) => fontToCanvas(x, y, L);
      if (c.t === 'M') { const q = p(c.x, c.y); ctx.moveTo(q.x, q.y); }
      else if (c.t === 'L') { const q = p(c.x, c.y); ctx.lineTo(q.x, q.y); }
      else if (c.t === 'C') {
        const a = p(c.x1, c.y1), b = p(c.x2, c.y2), q = p(c.x, c.y);
        ctx.bezierCurveTo(a.x, a.y, b.x, b.y, q.x, q.y);
      } else if (c.t === 'Q') {
        const a = p(c.x1, c.y1), q = p(c.x, c.y);
        ctx.quadraticCurveTo(a.x, a.y, q.x, q.y);
      } else if (c.t === 'Z') ctx.closePath();
    });
    ctx.fillStyle = g.color || ink;
    ctx.fill();
    ctx.strokeStyle = 'rgba(28,25,21,.35)';
    ctx.lineWidth = 1;
    ctx.stroke();
    (g.commands || []).forEach((c, i) => {
      const pts = pathPts(c);
      pts.forEach((pt) => {
        const q = fontToCanvas(pt.x, pt.y, L);
        const sel = selectedPt && selectedPt.i === i && selectedPt.k === pt.k;
        ctx.beginPath();
        ctx.arc(q.x, q.y, sel ? 5 : 3.5, 0, Math.PI * 2);
        ctx.fillStyle = pt.k === 'on' ? (sel ? '#111' : '#fff') : (sel ? '#3b82f6' : '#93c5fd');
        ctx.fill();
        ctx.strokeStyle = '#111';
        ctx.stroke();
      });
    });
    ctx.restore();
  }
  function pathPts(c) {
    if (c.t === 'Z' || c.t === 'z') return [];
    const out = [{ x: c.x, y: c.y, k: 'on' }];
    if (c.t === 'C') { out.push({ x: c.x1, y: c.y1, k: 'h1' }); out.push({ x: c.x2, y: c.y2, k: 'h2' }); }
    if (c.t === 'Q') out.push({ x: c.x1, y: c.y1, k: 'h1' });
    return out;
  }
  function hitPoint(px, py, L) {
    const g = cur();
    if (!g.commands) return null;
    let best = null, bestD = 10;
    g.commands.forEach((c, i) => {
      pathPts(c).forEach((pt) => {
        const q = fontToCanvas(pt.x, pt.y, L);
        const d = Math.hypot(q.x - px, q.y - py);
        if (d < bestD) { bestD = d; best = { i, k: pt.k }; }
      });
    });
    return best;
  }
  function movePoint(sel, x, y) {
    const c = cur().commands[sel.i];
    if (!c) return;
    if (sel.k === 'on') { c.x = x; c.y = y; }
    else if (sel.k === 'h1') { c.x1 = x; c.y1 = y; }
    else if (sel.k === 'h2') { c.x2 = x; c.y2 = y; }
  }

  function rasterizePath(g) {
    const n = project.grid;
    const c = document.createElement('canvas');
    c.width = n; c.height = n;
    const x = c.getContext('2d');
    const sx = n / project.upm;
    const sy = n / (project.ascender - project.descender);
    x.save();
    x.translate(0, project.ascender * sy);
    x.scale(sx, -sy);
    x.beginPath();
    (g.commands || []).forEach((cmd) => {
      if (cmd.t === 'M') x.moveTo(cmd.x, cmd.y);
      else if (cmd.t === 'L') x.lineTo(cmd.x, cmd.y);
      else if (cmd.t === 'C') x.bezierCurveTo(cmd.x1, cmd.y1, cmd.x2, cmd.y2, cmd.x, cmd.y);
      else if (cmd.t === 'Q') x.quadraticCurveTo(cmd.x1, cmd.y1, cmd.x, cmd.y);
      else if (cmd.t === 'Z') x.closePath();
    });
    x.fillStyle = g.color || ink;
    x.fill();
    x.restore();
    const img = x.getImageData(0, 0, n, n).data;
    const grid = emptyGrid(n);
    for (let y = 0; y < n; y++) for (let xx = 0; xx < n; xx++) {
      const i = (y * n + xx) * 4;
      if (img[i + 3] > 80) grid[y][xx] = rgbHex(img[i], img[i + 1], img[i + 2]);
    }
    return grid;
  }

  function applyTool(cell, ev, end) {
    const g = cur();
    const md = modeOf(g);
    if (tool === 'pen' || md === 'outline' && (tool === 'pen' || selectedPt)) {
      return applyPen(cell, ev, end);
    }
    if (g.source === 'path' && g.commands && g.commands.length && /pencil|eraser|fill|spray/.test(tool)) {
      if (!end) {
        if (!g._warned) { g._warned = true; toast('Pixel tools rasterize this outline at current resolution'); }
        g.grid = rasterizePath(g);
        g.source = 'pixel';
        g.commands = null;
        editMode = 'pixels';
      }
    }
    const v = tool === 'eraser' ? null : ink;
    if (tool === 'dropper' && !end) {
      const c = cellVal(g.grid, cell.x, cell.y);
      if (c) { ink = c; renderToolbar(); }
      return;
    }
    if (tool === 'pencil' || tool === 'eraser') paintDot(g.grid, cell.x, cell.y, v, brush);
    else if (tool === 'spray' && !end) sprayOn(g.grid, cell.x, cell.y, ink, brush);
    else if (tool === 'fill' && !end) fillOn(g.grid, cell.x, cell.y, ink);
    else if (tool === 'stamp' && !end) stampInto(g, stampChar);
    else if (end && startCell) {
      if (tool === 'line') lineOn(g.grid, startCell.x, startCell.y, cell.x, cell.y, ink, brush);
      if (tool === 'rect') rectOn(g.grid, startCell.x, startCell.y, cell.x, cell.y, ink, false);
      if (tool === 'rectf') rectOn(g.grid, startCell.x, startCell.y, cell.x, cell.y, ink, true);
      if (tool === 'oval') ovalOn(g.grid, startCell.x, startCell.y, cell.x, cell.y, ink, false);
      if (tool === 'ovalf') ovalOn(g.grid, startCell.x, startCell.y, cell.x, cell.y, ink, true);
      if (tool === 'gradient') gradientOn(g.grid, startCell.x, startCell.y, cell.x, cell.y, ink, '#f4f4f5');
    }
  }
  function applyPen(cell, ev, end) {
    const g = cur();
    if (!g.commands) g.commands = [];
    g.source = 'path';
    editMode = 'outline';
    const L = cell.L || layout();
    const ft = canvasToFont(cell.px, cell.py, L);
    if (!end && !drawing) return;
    if (!end) {
      const hit = hitPoint(cell.px, cell.py, L);
      if (hit) { selectedPt = hit; return; }
      selectedPt = null;
      return;
    }
    if (selectedPt) { movePoint(selectedPt, ft.x, ft.y); return; }
    if (tool !== 'pen') return;
    const cmds = g.commands;
    if (!cmds.length || cmds[cmds.length - 1].t === 'Z') cmds.push({ t: 'M', x: ft.x, y: ft.y });
    else cmds.push({ t: 'L', x: ft.x, y: ft.y });
  }

  /* ── preview look ── */
  function blitGlyph(x, g, dx, dy, box) {
    g.grid = migrateGrid(g.grid, project.grid);
    if (modeOf(g) === 'outline' && g.commands && g.commands.length) {
      const scale = box / project.upm;
      x.save();
      x.translate(dx, dy + (project.ascender / project.upm) * box);
      x.scale(scale, -scale);
      x.beginPath();
      g.commands.forEach((c) => {
        if (c.t === 'M') x.moveTo(c.x, c.y);
        else if (c.t === 'L') x.lineTo(c.x, c.y);
        else if (c.t === 'C') x.bezierCurveTo(c.x1, c.y1, c.x2, c.y2, c.x, c.y);
        else if (c.t === 'Q') x.quadraticCurveTo(c.x1, c.y1, c.x, c.y);
        else if (c.t === 'Z') x.closePath();
      });
      x.fillStyle = g.color || ink;
      x.fill();
      x.restore();
      return;
    }
    const n = g.grid.length;
    const cell = box / n;
    for (let y = 0; y < n; y++) for (let xx = 0; xx < n; xx++) {
      const v = cellVal(g.grid, xx, y);
      if (!v) continue;
      x.fillStyle = v;
      x.fillRect(dx + xx * cell, dy + y * cell, cell + 0.2, cell + 0.2);
    }
  }
  function drawPreview() {
    if (!project) return;
    const g = cur();
    const w = pv.width, h = pv.height;
    pvx.fillStyle = '#141416';
    pvx.fillRect(0, 0, w, h);
    const sc = pvScale / 100;
    if (pvMode === 'solo') {
      const box = Math.min(w, h) * 0.84 * Math.min(sc, 2.2) / 1.4;
      blitGlyph(pvx, g, (w - box) / 2, (h - box) / 2, box);
    } else if (pvMode === 'tile') {
      const box = 28 * sc;
      const cols = Math.max(2, Math.floor(w / (box + 6)));
      const rows = Math.max(2, Math.floor(h / (box + 6)));
      for (let y = 0; y < rows; y++) for (let x = 0; x < cols; x++) {
        blitGlyph(pvx, g, 8 + x * (box + 6), 8 + y * (box + 6), box);
      }
    } else {
      const tpl = ($('sentenceIn').value || 'The quick brown {c} fox').replaceAll('{c}', chOf(currentU));
      const chars = Array.from(tpl);
      const box = 22 * sc;
      let x = 10, y = h / 2 - box / 2;
      chars.forEach((ch) => {
        if (ch === '\n') { x = 10; y += box + 6; return; }
        const u = ch.codePointAt(0);
        const gg = project.glyphs[u] || (u === currentU ? g : null);
        if (gg) blitGlyph(pvx, gg, x, y, box);
        x += box * 0.72;
        if (x > w - box) { x = 10; y += box + 6; }
      });
    }
  }
  function schedulePreview() {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(drawPreview, 40);
  }

  /* ── UI ── */
  function renderFilters() {
    $('filters').innerHTML = FILTERS.map((f) =>
      `<button type="button" class="chip ${f.id === filter ? 'on' : ''}" data-f="${f.id}">${esc(f.label)}</button>`
    ).join('');
  }
  function matchFilter(u) {
    if (filter === 'all') return true;
    if (filter === 'upper') return u >= 65 && u <= 90;
    if (filter === 'lower') return u >= 97 && u <= 122;
    if (filter === 'digit') return u >= 48 && u <= 57;
    if (filter === 'punct') return (u >= 33 && u <= 47) || (u >= 58 && u <= 64) || (u >= 91 && u <= 96) || (u >= 123 && u <= 126);
    if (filter === 'sym') return u > 126 && u < 0x1F300;
    if (filter === 'emoji') return u >= 0x1F300 || (u >= 0x2600 && u <= 0x27BF);
    if (filter === 'pua') return u >= 0xE000 && u <= 0xF8FF;
    return true;
  }
  function glyphEmpty(g) {
    if (g.source === 'path' && g.commands && g.commands.length) return false;
    const grid = g.grid;
    if (!grid) return true;
    for (let y = 0; y < grid.length; y++) {
      const row = grid[y];
      if (!row) continue;
      if (Array.isArray(row)) { if (row.some(Boolean)) return false; }
      else if (String(row).includes('1')) return false;
    }
    return true;
  }
  function renderMap() {
    if (!project) return;
    const q = ($('q').value || '').trim().toLowerCase();
    const bits = [];
    Object.keys(project.glyphs).map(Number).sort((a, b) => a - b).forEach((u) => {
      if (!u) return;
      if (!matchFilter(u)) return;
      const ch = chOf(u);
      const g = project.glyphs[u];
      if (q) {
        const name = (g.name || '').toLowerCase();
        const hex = u.toString(16);
        if (!ch.toLowerCase().includes(q) && !name.includes(q) && !hex.includes(q.replace(/^u\+/, ''))) return;
      }
      bits.push(`<button type="button" class="gcell ${u === currentU ? 'on' : ''} ${glyphEmpty(g) ? 'empty' : ''}" data-u="${u}" title="${esc(g.name)} U+${u.toString(16).toUpperCase()}">${esc(ch)}<span class="cp">${u.toString(16)}</span></button>`);
    });
    $('gmap').innerHTML = bits.join('') || '<p class="hint">No glyphs in this filter.</p>';
  }
  function renderLib() {
    const cats = global.FAFO_FOUNDRY_LIB || [];
    $('libCats').innerHTML = cats.map((c) =>
      `<button type="button" class="chip ${c.id === libCat ? 'on' : ''}" data-cat="${c.id}">${esc(c.label)}</button>`
    ).join('');
    const cat = cats.find((c) => c.id === libCat) || cats[0];
    const q = (libQuery || '').toLowerCase();
    let glyphs = cat ? Array.from(cat.glyphs) : [];
    if (q) {
      glyphs = [];
      cats.forEach((c) => Array.from(c.glyphs).forEach((ch) => {
        const u = ch.codePointAt(0);
        if (ch.toLowerCase().includes(q) || u.toString(16).includes(q)) glyphs.push(ch);
      }));
    }
    $('libGrid').innerHTML = glyphs.slice(0, 400).map((ch) =>
      `<button type="button" class="lcell" data-ch="${esc(ch)}" title="U+${ch.codePointAt(0).toString(16).toUpperCase()}">${ch}</button>`
    ).join('');
  }
  function renderMeta() {
    const g = cur();
    $('metaChar').value = chOf(g.unicode);
    $('metaName').value = g.name;
    $('metaAdv').value = g.advance;
    $('gridLbl').textContent = g.grid.length + ' × ' + g.grid.length + ' · ' + glyphCount() + ' glyphs · zoom ' + Math.round(view.zoom * 100) + '%';
  }
  function renderToolbar() {
    const tools = TOOLS.map((ic) =>
      `<button type="button" class="tool ${tool === ic.tool ? 'on' : ''}" data-tool="${ic.tool}" title="${esc(ic.title)}"><svg viewBox="0 0 20 20">${ic.svg}</svg></button>`
    ).join('');
    const sw = INK_SWATCH.map((c) =>
      `<button type="button" class="swatch ${c === ink ? 'on' : ''}" data-ink="${c}" style="background:${c}" title="${c}"></button>`
    ).join('');
    $('toolbar').innerHTML = tools +
      `<span class="tool-lbl">Ink</span><input class="ink" id="ink" type="color" value="${ink}">${sw}` +
      `<span class="tool-lbl">Paper</span><input class="ink" id="paper" type="color" value="${paper}">` +
      `<span class="tool-lbl">Brush</span><input id="brush" type="range" min="1" max="8" value="${brush}" style="width:72px">` +
      `<button type="button" class="chip ${editMode !== 'outline' ? 'on' : ''}" id="btnPix">Pixels</button>` +
      `<button type="button" class="chip ${editMode === 'outline' ? 'on' : ''}" id="btnOut">Outlines</button>` +
      `<button type="button" class="btn ghost" id="btnUndo">Undo</button>` +
      `<button type="button" class="btn ghost" id="btnFit">Fit</button>` +
      `<button type="button" class="btn ghost" id="btnFlipH">Flip H</button>` +
      `<button type="button" class="btn ghost" id="btnFlipV">Flip V</button>` +
      `<button type="button" class="btn ghost" id="btnRot">90°</button>`;
    $('ink').oninput = (e) => { ink = e.target.value; };
    $('paper').oninput = (e) => { paper = e.target.value; drawStage(); };
    $('brush').oninput = (e) => { brush = +e.target.value; };
    $('btnUndo').onclick = restore;
    $('btnFit').onclick = () => { view = { zoom: 1, panX: 0, panY: 0 }; drawStage(); renderMeta(); };
    $('btnPix').onclick = () => { editMode = 'pixels'; if (cur().source === 'path') { cur().grid = rasterizePath(cur()); } renderToolbar(); drawStage(); };
    $('btnOut').onclick = () => { editMode = 'outline'; tool = 'pen'; renderToolbar(); drawStage(); };
    $('btnFlipH').onclick = () => { snapshot(); flip(true); };
    $('btnFlipV').onclick = () => { snapshot(); flip(false); };
    $('btnRot').onclick = () => { snapshot(); rotate90(); };
    $('toolbar').querySelectorAll('[data-ink]').forEach((b) => {
      b.onclick = () => { ink = b.getAttribute('data-ink'); renderToolbar(); };
    });
  }
  function flip(horiz) {
    const g = cur();
    const n = g.grid.length;
    if (modeOf(g) === 'outline' && g.commands) {
      g.commands.forEach((c) => {
        const f = (x, y) => horiz ? { x: project.upm - x, y: y } : { x: x, y: -y };
        if (c.t === 'Z') return;
        const a = f(c.x, c.y); c.x = a.x; c.y = a.y;
        if (c.x1 != null) { const b = f(c.x1, c.y1); c.x1 = b.x; c.y1 = b.y; }
        if (c.x2 != null) { const b = f(c.x2, c.y2); c.x2 = b.x; c.y2 = b.y; }
      });
    } else {
      const src = g.grid.map((r) => r.slice());
      for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
        g.grid[y][x] = horiz ? src[y][n - 1 - x] : src[n - 1 - y][x];
      }
    }
    renderAll(); persist(); schedulePreview();
  }
  function rotate90() {
    const g = cur();
    const n = g.grid.length;
    const src = g.grid.map((r) => r.slice());
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) g.grid[y][x] = src[n - 1 - x][y];
    g.source = 'pixel';
    renderAll(); persist(); schedulePreview();
  }
  function renderPvChrome() {
    $('pvModes').querySelectorAll('[data-pv]').forEach((b) => b.classList.toggle('on', b.dataset.pv === pvMode));
    $('pvScales').querySelectorAll('[data-sc]').forEach((b) => b.classList.toggle('on', +b.dataset.sc === pvScale));
    $('pvRange').value = pvScale;
    $('pvScaleLbl').textContent = pvScale + '%';
  }
  function renderAll() {
    if (!project) return;
    renderFilters();
    renderMap();
    renderMeta();
    renderToolbar();
    renderPvChrome();
    drawStage();
    drawPreview();
  }

  function persist() {
    if (!project) return;
    project.family = $('family').value.trim() || project.family;
    project.style = $('styleName').value.trim() || project.style;
    const packed = Object.assign({}, project, { glyphs: {} });
    Object.keys(project.glyphs).forEach((k) => {
      const g = project.glyphs[k];
      packed.glyphs[k] = Object.assign({}, g, { grid: packGrid(migrateGrid(g.grid, project.grid)) });
    });
    try { localStorage.setItem(LS, JSON.stringify(packed)); }
    catch (_) { try { localStorage.removeItem(LS_OLD); localStorage.setItem(LS, JSON.stringify(packed)); } catch (e2) { /* quota */ } }
  }
  function loadSession() {
    try {
      const r = JSON.parse(localStorage.getItem(LS) || localStorage.getItem(LS_OLD));
      if (r && r.glyphs) return migrateProject(r);
    } catch (_) { /* ignore */ }
    return null;
  }

  function addFromLib(ch) {
    stampChar = ch;
    const u = ch.codePointAt(0);
    snapshot();
    currentU = u;
    const g = ensureGlyph(u);
    stampInto(g, ch);
    if (!recent.includes(ch)) { recent.unshift(ch); recent = recent.slice(0, 24); }
    side = 'font';
    syncSide();
    renderAll(); persist(); schedulePreview();
    toast('Added ' + ch + ' at ' + g.grid.length + 'px — zoom in to edit');
  }
  function addCharFromInput() {
    const u = parseCode($('addChar').value);
    if (u == null) { toast('Type a character or U+0041'); return; }
    ensureGlyph(u);
    currentU = u;
    $('addChar').value = '';
    renderAll(); persist();
  }
  function syncSide() {
    $('tabFont').classList.toggle('on', side === 'font');
    $('tabLib').classList.toggle('on', side === 'lib');
    $('fontPane').hidden = side !== 'font';
    $('libPane').hidden = side !== 'lib';
    if (side === 'lib') renderLib();
  }
  function nudge(dx, dy, step) {
    snapshot();
    const g = cur();
    const s = step || 1;
    if (modeOf(g) === 'outline' && g.commands) {
      if (selectedPt) {
        const c = g.commands[selectedPt.i];
        if (selectedPt.k === 'on') { c.x += dx * s; c.y += dy * s; }
        else if (selectedPt.k === 'h1') { c.x1 += dx * s; c.y1 += dy * s; }
        else { c.x2 += dx * s; c.y2 += dy * s; }
      } else {
        g.commands.forEach((c) => {
          if (c.t === 'Z') return;
          c.x += dx * s; c.y += dy * s;
          if (c.x1 != null) { c.x1 += dx * s; c.y1 += dy * s; }
          if (c.x2 != null) { c.x2 += dx * s; c.y2 += dy * s; }
        });
      }
    } else {
      const n = g.grid.length;
      const src = g.grid.map((r) => r.slice());
      const blank = emptyGrid(n);
      for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
        const nx = x + dx * s, ny = y - dy * s;
        if (nx >= 0 && ny >= 0 && nx < n && ny < n) blank[ny][nx] = src[y][x];
      }
      g.grid = blank;
    }
    drawStage(); persist(); schedulePreview();
  }

  function bind() {
    $('tabFont').onclick = () => { side = 'font'; syncSide(); };
    $('tabLib').onclick = () => { side = 'lib'; syncSide(); };
    $('filters').addEventListener('click', (e) => {
      const b = e.target.closest('[data-f]'); if (!b) return;
      filter = b.dataset.f; renderFilters(); renderMap();
    });
    $('gmap').addEventListener('click', (e) => {
      const b = e.target.closest('[data-u]'); if (!b) return;
      currentU = +b.dataset.u; selectedPt = null; renderAll();
    });
    $('q').addEventListener('input', renderMap);
    $('libQ').addEventListener('input', () => { libQuery = $('libQ').value; renderLib(); });
    $('libCats').addEventListener('click', (e) => {
      const b = e.target.closest('[data-cat]'); if (!b) return;
      libCat = b.dataset.cat; libQuery = ''; $('libQ').value = ''; renderLib();
    });
    $('libGrid').addEventListener('click', (e) => {
      const b = e.target.closest('[data-ch]'); if (!b) return;
      addFromLib(b.getAttribute('data-ch'));
    });
    $('btnAdd').onclick = addCharFromInput;
    $('addChar').addEventListener('keydown', (e) => { if (e.key === 'Enter') addCharFromInput(); });
    $('btnNew').onclick = () => { $('boot').hidden = false; $('btnResume').hidden = !loadSession(); };
    $('btnLoad').onclick = () => $('fileFont').click();
    $('btnSave').onclick = saveCopy;
    $('btnPng').onclick = savePng;
    $('btnProj').onclick = () => {
      persist();
      const blob = new Blob([localStorage.getItem(LS) || '{}'], { type: 'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = (project.family || 'foundry') + '.foundry.json';
      a.click();
    };
    $('fileFont').addEventListener('change', async (e) => {
      const f = e.target.files && e.target.files[0];
      e.target.value = '';
      if (!f) return;
      if (/\.json$/i.test(f.name)) {
        try { project = migrateProject(JSON.parse(await f.text())); currentU = project.glyphs[65] ? 65 : +Object.keys(project.glyphs)[0] || 0; afterProject('Opened project'); }
        catch (_) { toast('Bad project JSON'); }
        return;
      }
      loadFontBuffer(await f.arrayBuffer(), f.name);
    });
    $('fileStamp').addEventListener('change', async (e) => {
      const f = e.target.files && e.target.files[0];
      e.target.value = '';
      if (!f) return;
      const url = URL.createObjectURL(f);
      const img = new Image();
      img.onload = () => {
        snapshot();
        const n = cur().grid.length;
        const c = document.createElement('canvas');
        c.width = n; c.height = n;
        const x = c.getContext('2d');
        const scale = Math.min(n / img.width, n / img.height);
        const dw = img.width * scale, dh = img.height * scale;
        x.clearRect(0, 0, n, n);
        x.drawImage(img, (n - dw) / 2, (n - dh) / 2, dw, dh);
        const data = x.getImageData(0, 0, n, n).data;
        const grid = emptyGrid(n);
        for (let y = 0; y < n; y++) for (let xx = 0; xx < n; xx++) {
          const i = (y * n + xx) * 4;
          if (data[i + 3] > 40) grid[y][xx] = rgbHex(data[i], data[i + 1], data[i + 2]);
        }
        const g = cur();
        g.grid = grid; g.source = 'pixel'; g.commands = null;
        URL.revokeObjectURL(url);
        renderAll(); persist();
        toast('Color-traced image at ' + n + 'px');
      };
      img.src = url;
    });
    $('toolbar').addEventListener('click', (e) => {
      const b = e.target.closest('[data-tool]'); if (!b) return;
      tool = b.dataset.tool;
      if (tool === 'image') { $('fileStamp').click(); tool = 'pencil'; }
      if (tool === 'pen') editMode = 'outline';
      renderToolbar();
    });
    $('family').addEventListener('change', persist);
    $('styleName').addEventListener('change', persist);
    $('sentenceIn').addEventListener('input', drawPreview);
    $('gridSize').addEventListener('change', () => {
      const n = clamp(+($('gridSize').value) || 48, 8, 256);
      project.grid = n;
      Object.values(project.glyphs).forEach((g) => {
        if (g.source === 'path' && g.commands && g.commands.length) return;
        const src = migrateGrid(g.grid, n);
        const nn = src.length;
        const next = emptyGrid(n);
        for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
          const sx = Math.floor(x * nn / n), sy = Math.floor(y * nn / n);
          next[y][x] = src[sy][sx];
        }
        g.grid = next;
      });
      renderAll(); persist();
    });
    ['metaUpm', 'metaAsc', 'metaDesc'].forEach((id) => {
      $(id).addEventListener('change', () => {
        project.upm = +$('metaUpm').value || 1000;
        project.ascender = +$('metaAsc').value || 800;
        project.descender = +$('metaDesc').value || -200;
        drawStage(); persist();
      });
    });
    $('metaName').addEventListener('change', () => { cur().name = $('metaName').value; persist(); });
    $('metaAdv').addEventListener('change', () => { cur().advance = +$('metaAdv').value || cur().advance; persist(); });
    $('metaChar').addEventListener('change', () => {
      const u = parseCode($('metaChar').value); if (u == null) return;
      if (u !== currentU) {
        const copy = JSON.parse(JSON.stringify(cur()));
        copy.unicode = u; copy.name = glyphName(u);
        copy.grid = migrateGrid(copy.grid, project.grid);
        project.glyphs[u] = copy; currentU = u; renderAll(); persist();
      }
    });
    $('btnCopyTo').onclick = () => {
      const u = parseCode($('copyTo').value); if (u == null) return;
      const copy = JSON.parse(JSON.stringify(cur()));
      copy.unicode = u; copy.name = glyphName(u);
      copy.grid = migrateGrid(copy.grid, project.grid);
      project.glyphs[u] = copy; currentU = u; $('copyTo').value = '';
      renderAll(); persist();
    };
    $('btnClear').onclick = () => {
      snapshot();
      const g = cur();
      g.grid = emptyGrid(g.grid.length);
      g.commands = [];
      g.source = editMode === 'outline' ? 'path' : 'pixel';
      renderAll(); persist();
    };
    $('pvModes').addEventListener('click', (e) => {
      const b = e.target.closest('[data-pv]'); if (!b) return;
      pvMode = b.dataset.pv; renderPvChrome(); drawPreview();
    });
    $('pvScales').addEventListener('click', (e) => {
      const b = e.target.closest('[data-sc]'); if (!b) return;
      pvScale = +b.dataset.sc; renderPvChrome(); drawPreview();
    });
    $('pvRange').addEventListener('input', (e) => {
      pvScale = +e.target.value; renderPvChrome(); drawPreview();
    });

    stage.addEventListener('pointerdown', (ev) => {
      if (!project) return;
      if (spaceDown || ev.button === 1) {
        panning = true; lastPan = { x: ev.clientX, y: ev.clientY }; return;
      }
      stage.setPointerCapture(ev.pointerId);
      const cell = cellAt(ev);
      if (tool === 'pen' || modeOf(cur()) === 'outline') {
        const hit = hitPoint(cell.px, cell.py, cell.L);
        selectedPt = hit;
        if (hit) snapshot();
        else if (tool === 'pen') snapshot();
      } else snapshot();
      drawing = true;
      startCell = cell; hover = cell;
      applyTool(cell, ev, false);
      drawStage();
    });
    stage.addEventListener('pointermove', (ev) => {
      if (panning && lastPan) {
        view.panX += ev.clientX - lastPan.x;
        view.panY += ev.clientY - lastPan.y;
        lastPan = { x: ev.clientX, y: ev.clientY };
        drawStage();
        return;
      }
      if (!drawing) return;
      const cell = cellAt(ev);
      hover = cell;
      if (selectedPt && (tool === 'pen' || modeOf(cur()) === 'outline')) {
        const ft = canvasToFont(cell.px, cell.py, cell.L);
        movePoint(selectedPt, ft.x, ft.y);
      } else if (/pencil|eraser|spray/.test(tool)) applyTool(cell, ev, false);
      drawStage();
    });
    function endDraw(ev) {
      if (panning) { panning = false; lastPan = null; return; }
      if (!drawing) return;
      drawing = false;
      const cell = cellAt(ev);
      applyTool(cell, ev, true);
      startCell = null; hover = null;
      renderMap(); drawStage(); persist(); schedulePreview();
    }
    stage.addEventListener('pointerup', endDraw);
    stage.addEventListener('pointercancel', endDraw);
    stage.addEventListener('wheel', (ev) => {
      ev.preventDefault();
      const f = ev.deltaY < 0 ? 1.12 : 1 / 1.12;
      view.zoom = clamp(view.zoom * f, 0.25, 16);
      drawStage(); renderMeta();
    }, { passive: false });

    document.addEventListener('keydown', (e) => {
      if (e.code === 'Space') { spaceDown = true; if (e.target === document.body || e.target === stage) e.preventDefault(); }
      if (e.target && /input|textarea|select/i.test(e.target.tagName)) return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); restore(); }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); saveCopy(); }
      if (e.key === 'b' || e.key === 'B') { tool = 'pencil'; editMode = 'pixels'; renderToolbar(); }
      if (e.key === 'e' || e.key === 'E') { tool = 'eraser'; renderToolbar(); }
      if (e.key === 'g' || e.key === 'G') { tool = 'fill'; renderToolbar(); }
      if (e.key === 'i' || e.key === 'I') { tool = 'dropper'; renderToolbar(); }
      if (e.key === 'p' || e.key === 'P') { tool = 'pen'; editMode = 'outline'; renderToolbar(); }
      if (e.key === '[') { brush = Math.max(1, brush - 1); renderToolbar(); }
      if (e.key === ']') { brush = Math.min(8, brush + 1); renderToolbar(); }
      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (selectedPt && cur().commands) {
          snapshot();
          cur().commands.splice(selectedPt.i, 1);
          selectedPt = null; drawStage(); persist();
        }
      }
      const step = e.shiftKey ? 10 : 1;
      if (e.key === 'ArrowLeft') { e.preventDefault(); nudge(-1, 0, step); }
      if (e.key === 'ArrowRight') { e.preventDefault(); nudge(1, 0, step); }
      if (e.key === 'ArrowUp') { e.preventDefault(); nudge(0, 1, step); }
      if (e.key === 'ArrowDown') { e.preventDefault(); nudge(0, -1, step); }
    });
    document.addEventListener('keyup', (e) => { if (e.code === 'Space') spaceDown = false; });
    document.addEventListener('dragover', (e) => e.preventDefault());
    document.addEventListener('drop', async (e) => {
      e.preventDefault();
      const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (!f) return;
      if (/\.(ttf|otf|woff)$/i.test(f.name)) loadFontBuffer(await f.arrayBuffer(), f.name);
      else if (/\.json$/i.test(f.name)) { project = migrateProject(JSON.parse(await f.text())); afterProject('Opened project'); }
      else if (/^image\//.test(f.type)) {
        const dt = new DataTransfer(); dt.items.add(f); $('fileStamp').files = dt.files;
        $('fileStamp').dispatchEvent(new Event('change'));
      }
    });
    document.querySelectorAll('[data-boot]').forEach((b) => {
      b.addEventListener('click', () => {
        const k = b.dataset.boot;
        if (k === 'blank') bootBlank();
        else if (k === 'trace') bootTrace();
        else if (k === 'file') $('fileFont').click();
        else if (k === 'emoji') bootEmoji();
      });
    });
    $('btnResume').onclick = () => {
      const s = loadSession(); if (!s) return;
      project = s;
      currentU = project.glyphs[65] ? 65 : +Object.keys(project.glyphs).find((k) => +k > 0) || 0;
      afterProject('Resumed last session');
    };
  }

  function start() {
    bind();
    try { new ResizeObserver(resizeStage).observe(document.querySelector('.stage-wrap')); }
    catch (_) { window.addEventListener('resize', resizeStage); }
    resizeStage();
    const s = loadSession();
    $('btnResume').hidden = !s;
    if (s && s.glyphs && Object.keys(s.glyphs).length > 2) {
      project = s;
      currentU = project.glyphs[65] ? 65 : +Object.keys(project.glyphs).find((k) => +k > 0) || 0;
      $('family').value = project.family || 'Foundry Copy';
      $('styleName').value = project.style || 'Regular';
      $('gridSize').value = project.grid || 48;
      $('boot').hidden = true;
      renderAll();
      $('sourceLabel').textContent = 'Restored session · outlines + color pixels';
    } else {
      $('boot').hidden = false;
      renderLib();
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})(window);
