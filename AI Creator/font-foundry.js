/**
 * Font Foundry — pixel / path glyph editor that always exports a copy.
 * Depends on global `opentype` (shared/vendor/opentype.min.js).
 */
(function (global) {
  'use strict';

  const LS = 'fafo_font_foundry_v1';
  const $ = (id) => document.getElementById(id);
  const ASCIINAMES = { 32: 'space', 33: 'exclam', 34: 'quotedbl', 35: 'numbersign', 36: 'dollar', 37: 'percent', 38: 'ampersand', 39: 'quotesingle', 40: 'parenleft', 41: 'parenright', 42: 'asterisk', 43: 'plus', 44: 'comma', 45: 'hyphen', 46: 'period', 47: 'slash', 48: 'zero', 49: 'one', 50: 'two', 51: 'three', 52: 'four', 53: 'five', 54: 'six', 55: 'seven', 56: 'eight', 57: 'nine', 58: 'colon', 59: 'semicolon', 60: 'less', 61: 'equal', 62: 'greater', 63: 'question', 64: 'at', 65: 'A', 91: 'bracketleft', 92: 'backslash', 93: 'bracketright', 94: 'asciicircum', 95: 'underscore', 96: 'grave', 97: 'a', 123: 'braceleft', 124: 'bar', 125: 'braceright', 126: 'asciitilde' };

  const FILTERS = [
    { id: 'all', label: 'All' },
    { id: 'upper', label: 'A–Z' },
    { id: 'lower', label: 'a–z' },
    { id: 'digit', label: '0–9' },
    { id: 'punct', label: 'Punct' },
    { id: 'sym', label: 'Symbols' },
    { id: 'emoji', label: 'Emoji' },
    { id: 'pua', label: 'Icons' },
  ];

  const SYMBOLS = Array.from('$¢£€¥₹©®™°§¶•●○■□▲▼★☆✦✓✗←→↑↓↔⇒±×÷≠≈∞');
  const EMOJI = Array.from('😀😁😂😍😎😭😡🥰🤔😴❤💔🔥⭐👍👎✅❌⚠💡🎵🎬⚙☀☂☃');

  const ICONS = [
    { svg: '<path d="M4 14h8"/><path d="M4 10h12"/><path d="M4 6h10"/>', tool: 'pencil', title: 'Pencil (B)' },
    { svg: '<path d="M5 5l10 10M15 5L5 15"/>', tool: 'eraser', title: 'Eraser (E)' },
    { svg: '<path d="M8 4h4v6H8z"/><path d="M6 14h8v4H6z"/>', tool: 'fill', title: 'Fill (G)' },
    { svg: '<path d="M4 12h12"/><path d="M12 8l4 4-4 4"/>', tool: 'line', title: 'Line' },
    { svg: '<rect x="4" y="5" width="12" height="10" rx="1"/>', tool: 'rect', title: 'Rectangle' },
    { svg: '<circle cx="10" cy="10" r="6"/>', tool: 'oval', title: 'Oval' },
    { svg: '<path d="M8 4v12M4 8h12"/>', tool: 'stamp', title: 'Stamp character' },
    { svg: '<rect x="3" y="5" width="14" height="10" rx="1"/><circle cx="8" cy="9" r="1.4"/><path d="M7 15l3-3 2 2 3-4"/>', tool: 'image', title: 'Trace image' },
  ];

  let project = null;
  let currentU = 65;
  let tool = 'pencil';
  let brush = 1;
  let filter = 'all';
  let drawing = false;
  let startCell = null;
  let hover = null;
  let undo = [];
  let previewUrl = null;
  let previewName = '';
  let previewTimer = 0;
  let stampChar = '★';
  let statusTimer = 0;

  function toast(msg) {
    const el = $('toast');
    el.textContent = msg;
    el.classList.add('on');
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove('on'), 2200);
  }
  function setStatus(msg) {
    $('status').textContent = msg;
    clearTimeout(statusTimer);
    statusTimer = setTimeout(() => { if ($('status').textContent === msg) $('status').textContent = glyphCount() + ' glyphs'; }, 2400);
  }
  function esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&', '<': '<', '>': '>', '"': '"', "'": '&#39;' }[c]));
  }
  function uid() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 7); }
  function glyphName(u) {
    if (u === 0) return '.notdef';
    if (ASCIINAMES[u]) return ASCIINAMES[u];
    if (u >= 65 && u <= 90) return String.fromCharCode(u);
    if (u >= 97 && u <= 122) return String.fromCharCode(u);
    return 'uni' + u.toString(16).toUpperCase().padStart(4, '0');
  }
  function chOf(u) {
    try { return String.fromCodePoint(u); } catch (_) { return ''; }
  }
  function parseCode(raw) {
    const s = String(raw || '').trim();
    if (!s) return null;
    const hex = s.match(/^(?:U\+?|0x)?([0-9a-f]{2,6})$/i);
    if (hex && (s[0] === 'U' || s[0] === 'u' || s.startsWith('0x') || s.startsWith('0X'))) {
      const n = parseInt(hex[1], 16);
      if (n >= 0 && n <= 0x10ffff) return n;
    }
    const cps = Array.from(s);
    if (cps.length === 1) return cps[0].codePointAt(0);
    if (/^[0-9]{2,7}$/.test(s)) {
      const n = +s;
      if (n <= 0x10ffff) return n;
    }
    return cps[0].codePointAt(0);
  }
  function emptyGrid(n) {
    n = Math.max(8, Math.min(64, n | 0));
    return Array.from({ length: n }, () => '0'.repeat(n));
  }
  function cloneGrid(g) { return g.map((r) => r); }
  function setCell(grid, x, y, v) {
    if (y < 0 || y >= grid.length || x < 0 || x >= grid[0].length) return;
    const row = grid[y].split('');
    row[x] = v;
    grid[y] = row.join('');
  }
  function getCell(grid, x, y) {
    if (y < 0 || y >= grid.length || x < 0 || x >= grid[0].length) return '0';
    return grid[y][x];
  }
  function paintDot(grid, x, y, v, size) {
    const r = Math.max(0, (size | 0) - 1);
    for (let yy = y - r; yy <= y + r; yy++) {
      for (let xx = x - r; xx <= x + r; xx++) {
        if ((xx - x) * (xx - x) + (yy - y) * (yy - y) <= r * r + 0.2) setCell(grid, xx, yy, v);
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
  function rectOn(grid, x0, y0, x1, y1, v) {
    const xa = Math.min(x0, x1), xb = Math.max(x0, x1);
    const ya = Math.min(y0, y1), yb = Math.max(y0, y1);
    for (let y = ya; y <= yb; y++) for (let x = xa; x <= xb; x++) {
      if (y === ya || y === yb || x === xa || x === xb) setCell(grid, x, y, v);
    }
  }
  function ovalOn(grid, x0, y0, x1, y1, v) {
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    const rx = Math.max(0.5, Math.abs(x1 - x0) / 2), ry = Math.max(0.5, Math.abs(y1 - y0) / 2);
    const xa = Math.floor(cx - rx), xb = Math.ceil(cx + rx);
    const ya = Math.floor(cy - ry), yb = Math.ceil(cy + ry);
    for (let y = ya; y <= yb; y++) for (let x = xa; x <= xb; x++) {
      const nx = (x - cx) / rx, ny = (y - cy) / ry;
      const d = nx * nx + ny * ny;
      if (d <= 1.05 && d >= 0.55) setCell(grid, x, y, v);
    }
  }
  function fillOn(grid, x, y, v) {
    const from = getCell(grid, x, y);
    if (from === v) return;
    const w = grid[0].length, h = grid.length;
    const stack = [[x, y]];
    const seen = new Uint8Array(w * h);
    while (stack.length) {
      const [cx, cy] = stack.pop();
      if (cx < 0 || cy < 0 || cx >= w || cy >= h) continue;
      const i = cy * w + cx;
      if (seen[i]) continue;
      seen[i] = 1;
      if (getCell(grid, cx, cy) !== from) continue;
      setCell(grid, cx, cy, v);
      stack.push([cx + 1, cy], [cx - 1, cy], [cx, cy + 1], [cx, cy - 1]);
    }
  }
  function glyphCount() { return project ? Object.keys(project.glyphs).length : 0; }

  function newProject(opts) {
    const n = opts.size || 16;
    const family = opts.family || 'Foundry Copy';
    const p = {
      id: uid(),
      family,
      style: opts.style || 'Regular',
      upm: 1000,
      ascender: 800,
      descender: -200,
      grid: n,
      source: opts.source || 'blank',
      sourceFile: opts.sourceFile || '',
      glyphs: {},
    };
    p.glyphs[0] = makeGlyph(0, n, { name: '.notdef' });
    boxNotdef(p.glyphs[0]);
    p.glyphs[32] = makeGlyph(32, n, { name: 'space' });
    return p;
  }
  function makeGlyph(u, n, extra) {
    return Object.assign({
      unicode: u,
      name: glyphName(u),
      advance: 600,
      source: 'pixel',
      grid: emptyGrid(n),
      commands: null,
    }, extra || {});
  }
  function boxNotdef(g) {
    const n = g.grid.length;
    for (let i = 2; i < n - 2; i++) {
      setCell(g.grid, 2, i, '1'); setCell(g.grid, n - 3, i, '1');
      setCell(g.grid, i, 2, '1'); setCell(g.grid, i, n - 3, '1');
    }
  }
  function ensureGlyph(u) {
    if (!project.glyphs[u]) {
      project.glyphs[u] = makeGlyph(u, project.grid);
    }
    return project.glyphs[u];
  }
  function cur() { return ensureGlyph(currentU); }

  function snapshot() {
    undo.push(JSON.stringify({ u: currentU, g: cur() }));
    if (undo.length > 80) undo.shift();
  }
  function restore() {
    const s = undo.pop();
    if (!s) return;
    const { u, g } = JSON.parse(s);
    project.glyphs[u] = g;
    currentU = u;
    renderAll();
    schedulePreview();
  }

  /* ── rasterize system / emoji ── */
  function traceChar(ch, cols, rows, family, weight) {
    const c = document.createElement('canvas');
    c.width = cols; c.height = rows;
    const x = c.getContext('2d');
    x.clearRect(0, 0, cols, rows);
    const size = Math.floor(rows * 0.78);
    x.font = (weight || '600') + ' ' + size + 'px ' + family;
    x.textAlign = 'center';
    x.textBaseline = 'alphabetic';
    x.fillStyle = '#000';
    x.fillText(ch, cols / 2, Math.round(rows * 0.78));
    const img = x.getImageData(0, 0, cols, rows).data;
    const grid = [];
    for (let y = 0; y < rows; y++) {
      let row = '';
      for (let xx = 0; xx < cols; xx++) {
        const a = img[(y * cols + xx) * 4 + 3];
        const lum = img[(y * cols + xx) * 4];
        row += (a > 90 || lum < 140 && a > 40) ? '1' : '0';
      }
      grid.push(row);
    }
    return trimGrid(grid);
  }
  function trimGrid(grid) {
    // keep square; don't shrink (metrics stay aligned). Return as-is.
    return grid;
  }
  function stampInto(g, ch, family) {
    g.grid = traceChar(ch, g.grid.length, g.grid.length, family || 'Segoe UI Emoji, Apple Color Emoji, Noto Color Emoji, sans-serif', '600');
    g.source = 'pixel';
    g.commands = null;
  }

  function asciiSet() {
    const out = [];
    for (let i = 33; i <= 126; i++) out.push(i);
    return out;
  }

  function bootBlank() {
    project = newProject({ family: 'Foundry Copy', size: +$('gridSize').value || 16, source: 'blank' });
    for (const u of asciiSet()) ensureGlyph(u);
    currentU = 65;
    afterProject('Blank pixel font');
  }
  function bootTrace() {
    const family = $('traceFace').value;
    const n = +$('gridSize').value || 16;
    project = newProject({ family: 'Foundry Copy', size: n, source: 'trace:' + family });
    const face = family;
    for (const u of [32].concat(asciiSet())) {
      const g = ensureGlyph(u);
      if (u === 32) continue;
      g.grid = traceChar(chOf(u), n, n, face, '600');
    }
    currentU = 65;
    afterProject('Traced ' + family.split(',')[0]);
  }
  function bootEmoji() {
    const n = Math.max(24, +$('gridSize').value || 24);
    $('gridSize').value = n;
    project = newProject({ family: 'Foundry Marks', size: n, source: 'emoji-kit' });
    const pack = Array.from(new Set([...SYMBOLS, ...EMOJI]));
    pack.forEach((ch) => {
      const u = ch.codePointAt(0);
      const g = ensureGlyph(u);
      stampInto(g, ch);
    });
    ['A', 'B', 'C', 'O', 'I', 'X'].forEach((ch) => {
      const u = ch.codePointAt(0);
      const g = ensureGlyph(u);
      g.grid = traceChar(ch, n, n, 'Segoe UI, system-ui, sans-serif', '700');
    });
    currentU = '★'.codePointAt(0);
    afterProject('Emoji & symbols kit');
  }

  function afterProject(label) {
    $('boot').hidden = true;
    $('family').value = project.family;
    $('styleName').value = project.style;
    $('gridSize').value = project.grid;
    $('gridLbl').textContent = project.grid + ' × ' + project.grid + ' pixels';
    $('sourceLabel').textContent = label + (project.sourceFile ? ' — ' + project.sourceFile : '') + ' · saving always makes a new file';
    persist();
    renderAll();
    schedulePreview();
    toast(label);
  }

  /* ── opentype load / save ── */
  function loadFontBuffer(buf, filename) {
    if (!global.opentype) { toast('Font engine missing'); return; }
    let font;
    try { font = global.opentype.parse(buf); }
    catch (e) { toast('Could not read that font'); console.warn(e); return; }
    const n = +$('gridSize').value || 16;
    const fam = (font.names && font.names.fontFamily && (font.names.fontFamily.en || Object.values(font.names.fontFamily)[0])) || 'Imported';
    project = newProject({
      family: String(fam) + ' Copy',
      style: (font.names && font.names.fontSubfamily && (font.names.fontSubfamily.en || 'Regular')) || 'Regular',
      size: n,
      source: 'file',
      sourceFile: filename || '',
    });
    project.upm = font.unitsPerEm || 1000;
    project.ascender = font.ascender || 800;
    project.descender = font.descender || -200;
    const glyphs = font.glyphs;
    const count = glyphs.length || (glyphs.glyphs && Object.keys(glyphs.glyphs).length) || 0;
    const limit = 800;
    let added = 0;
    for (let i = 0; i < count && added < limit; i++) {
      const gl = glyphs.get ? glyphs.get(i) : glyphs.glyphs[i];
      if (!gl) continue;
      const u = (gl.unicode != null) ? gl.unicode : (gl.unicodes && gl.unicodes[0]);
      if (u == null || u === 0) {
        if (gl.name === '.notdef') {
          project.glyphs[0] = otToGlyph(gl, 0);
          added++;
        }
        continue;
      }
      project.glyphs[u] = otToGlyph(gl, u);
      added++;
    }
    if (!project.glyphs[32]) project.glyphs[32] = makeGlyph(32, n, { name: 'space', advance: Math.round(project.upm * 0.3) });
    currentU = project.glyphs[65] ? 65 : +Object.keys(project.glyphs).find((k) => +k > 32) || 0;
    afterProject('Editing copy of ' + (filename || fam));
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
      unicode: u,
      name: gl.name || glyphName(u),
      advance: Math.round(gl.advanceWidth || project.upm * 0.6),
      source: cmds.length ? 'path' : 'pixel',
      grid: emptyGrid(project.grid),
      commands: cmds.length ? cmds : null,
    };
  }

  function gridToPath(grid, g) {
    const path = new global.opentype.Path();
    const rows = grid.length, cols = grid[0].length;
    const usable = project.ascender - project.descender;
    const cw = (g.advance || (project.upm * 0.6)) / cols;
    const ch = usable / rows;
    for (let y = 0; y < rows; y++) {
      let x = 0;
      while (x < cols) {
        while (x < cols && grid[y][x] !== '1') x++;
        if (x >= cols) break;
        let x2 = x;
        while (x2 < cols && grid[y][x2] === '1') x2++;
        const xL = Math.round(x * cw);
        const xR = Math.round(x2 * cw);
        const yT = Math.round(project.ascender - y * ch);
        const yB = Math.round(project.ascender - (y + 1) * ch);
        path.moveTo(xL, yB);
        path.lineTo(xR, yB);
        path.lineTo(xR, yT);
        path.lineTo(xL, yT);
        path.close();
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
    if (!global.opentype) throw new Error('opentype missing');
    const notdef = project.glyphs[0] || makeGlyph(0, project.grid, { name: '.notdef' });
    const list = [];
    const push = (g) => {
      const path = (g.source === 'path' && g.commands && g.commands.length)
        ? commandsToPath(g.commands)
        : gridToPath(g.grid || emptyGrid(project.grid), g);
      const opts = {
        name: g.name || glyphName(g.unicode),
        advanceWidth: Math.max(0, Math.round(g.advance || project.upm * 0.5)),
        path,
      };
      if (g.unicode) opts.unicode = g.unicode;
      list.push(new global.opentype.Glyph(opts));
    };
    push(notdef);
    Object.keys(project.glyphs).map(Number).sort((a, b) => a - b).forEach((u) => {
      if (u === 0) return;
      push(project.glyphs[u]);
    });
    return new global.opentype.Font({
      familyName: ($('family').value || project.family || 'Foundry Copy').trim() || 'Foundry Copy',
      styleName: ($('styleName').value || project.style || 'Regular').trim() || 'Regular',
      unitsPerEm: project.upm,
      ascender: project.ascender,
      descender: project.descender,
      glyphs: list,
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
      toast('Downloaded ' + safe + '.otf  (original not changed)');
      setStatus('Saved copy');
    } catch (e) {
      console.warn(e);
      toast('Could not build TTF — ' + (e.message || e));
    }
  }

  function schedulePreview() {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(refreshPreview, 280);
  }
  async function refreshPreview() {
    try {
      const font = buildFont();
      const buf = font.toArrayBuffer();
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      const blob = new Blob([buf], { type: 'font/ttf' });
      previewUrl = URL.createObjectURL(blob);
      previewName = 'FoundryPreview' + Date.now();
      const face = new FontFace(previewName, "url(" + previewUrl + ")");
      await face.load();
      document.fonts.add(face);
      document.documentElement.style.setProperty('--foundry', previewName);
      $('sampleOut').classList.add('live');
    } catch (e) {
      console.warn('preview', e);
    }
  }

  /* ── editor canvas ── */
  function resizeStage() {
    const wrap = document.querySelector('.stage-wrap');
    if (!wrap) return;
    const r = wrap.getBoundingClientRect();
    const size = Math.max(220, Math.floor(Math.min(r.width, r.height) - 2));
    if (size > 10 && (stage.width !== size || stage.height !== size)) {
      stage.width = size;
      stage.height = size;
    }
    if (project) drawStage();
  }

  function cellAt(ev) {
    const g = cur();
    const n = g.grid.length;
    const r = stage.getBoundingClientRect();
    const x = (ev.clientX - r.left) * (stage.width / r.width);
    const y = (ev.clientY - r.top) * (stage.height / r.height);
    const pad = 36;
    const inner = Math.min(stage.width, stage.height) - pad * 2;
    const cx = Math.floor((x - pad) / inner * n);
    const cy = Math.floor((y - pad) / inner * n);
    return { x: cx, y: cy, n, pad, inner };
  }
  function drawStage() {
    const g = cur();
    const n = g.grid.length;
    const w = stage.width, h = stage.height;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--paper').trim() || '#efece4';
    ctx.fillRect(0, 0, w, h);
    const pad = 36;
    const inner = Math.min(w, h) - pad * 2;
    const originX = (w - inner) / 2;
    const originY = (h - inner) / 2;
    const cell = inner / n;

    // guides
    ctx.strokeStyle = 'rgba(28,25,21,.12)';
    ctx.lineWidth = 1;
    if (n <= 32) {
      ctx.beginPath();
      for (let i = 0; i <= n; i++) {
        ctx.moveTo(originX + i * cell, originY);
        ctx.lineTo(originX + i * cell, originY + inner);
        ctx.moveTo(originX, originY + i * cell);
        ctx.lineTo(originX + inner, originY + i * cell);
      }
      ctx.stroke();
    }
    // baseline-ish
    ctx.strokeStyle = 'rgba(180,40,40,.35)';
    ctx.beginPath();
    ctx.moveTo(originX, originY + inner * 0.82);
    ctx.lineTo(originX + inner, originY + inner * 0.82);
    ctx.stroke();
    ctx.strokeStyle = 'rgba(40,80,160,.28)';
    ctx.beginPath();
    ctx.moveTo(originX, originY + inner * 0.22);
    ctx.lineTo(originX + inner, originY + inner * 0.22);
    ctx.stroke();

    if (g.source === 'path' && g.commands && g.commands.length) {
      const sx = inner / project.upm;
      const sy = inner / (project.ascender - project.descender);
      ctx.save();
      ctx.translate(originX, originY + (project.ascender * sy));
      ctx.scale(sx, -sy);
      ctx.beginPath();
      g.commands.forEach((c) => {
        if (c.t === 'M') ctx.moveTo(c.x, c.y);
        else if (c.t === 'L') ctx.lineTo(c.x, c.y);
        else if (c.t === 'C') ctx.bezierCurveTo(c.x1, c.y1, c.x2, c.y2, c.x, c.y);
        else if (c.t === 'Q') ctx.quadraticCurveTo(c.x1, c.y1, c.x, c.y);
        else if (c.t === 'Z') ctx.closePath();
      });
      ctx.fillStyle = '#1c1915';
      ctx.fill();
      ctx.restore();
    } else {
      ctx.fillStyle = '#1c1915';
      for (let y = 0; y < n; y++) {
        for (let x = 0; x < n; x++) {
          if (g.grid[y][x] === '1') {
            ctx.fillRect(originX + x * cell, originY + y * cell, cell + 0.4, cell + 0.4);
          }
        }
      }
    }
    if (drawing && startCell && hover && (tool === 'line' || tool === 'rect' || tool === 'oval')) {
      ctx.save();
      ctx.strokeStyle = 'rgba(28,25,21,.45)';
      ctx.setLineDash([4, 3]);
      const x0 = originX + startCell.x * cell, y0 = originY + startCell.y * cell;
      const x1 = originX + hover.x * cell, y1 = originY + hover.y * cell;
      ctx.strokeRect(Math.min(x0, x1), Math.min(y0, y1), Math.abs(x1 - x0) + cell, Math.abs(y1 - y0) + cell);
      ctx.restore();
    }
    ctx.strokeStyle = 'rgba(28,25,21,.35)';
    ctx.strokeRect(originX + 0.5, originY + 0.5, inner - 1, inner - 1);
  }

  function applyTool(cell, ev, end) {
    const g = cur();
    if (g.source === 'path' && g.commands && g.commands.length && tool !== 'stamp' && tool !== 'image' && tool !== 'fill') {
      // first pixel edit converts
      if (!end && (tool === 'pencil' || tool === 'eraser')) {
        if (!g._warned) {
          g._warned = true;
          toast('Pixel drawing replaces the outline for this glyph');
        }
        g.grid = rasterizePath(g);
        g.source = 'pixel';
        g.commands = null;
      }
    }
    const v = tool === 'eraser' ? '0' : '1';
    if (tool === 'pencil' || tool === 'eraser') {
      paintDot(g.grid, cell.x, cell.y, v, brush);
    } else if (tool === 'fill' && !end) {
      fillOn(g.grid, cell.x, cell.y, '1');
    } else if (tool === 'stamp' && !end) {
      stampInto(g, stampChar);
    } else if ((tool === 'line' || tool === 'rect' || tool === 'oval') && end && startCell) {
      if (tool === 'line') lineOn(g.grid, startCell.x, startCell.y, cell.x, cell.y, '1', brush);
      if (tool === 'rect') rectOn(g.grid, startCell.x, startCell.y, cell.x, cell.y, '1');
      if (tool === 'oval') ovalOn(g.grid, startCell.x, startCell.y, cell.x, cell.y, '1');
    }
  }
  function rasterizePath(g) {
    const n = project.grid;
    const c = document.createElement('canvas');
    c.width = n; c.height = n;
    const x = c.getContext('2d');
    x.fillStyle = '#000';
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
    x.fill();
    x.restore();
    const img = x.getImageData(0, 0, n, n).data;
    const grid = [];
    for (let y = 0; y < n; y++) {
      let row = '';
      for (let xx = 0; xx < n; xx++) row += img[(y * n + xx) * 4 + 3] > 80 ? '1' : '0';
      grid.push(row);
    }
    return grid;
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
    if (filter === 'sym') return (u > 126 && u < 0x1F300) || SYMBOLS.some((ch) => ch.codePointAt(0) === u);
    if (filter === 'emoji') return u >= 0x1F300 || (u >= 0x2600 && u <= 0x27BF) || u === 0x2764;
    if (filter === 'pua') return u >= 0xE000 && u <= 0xF8FF;
    return true;
  }
  function renderMap() {
    const q = ($('q').value || '').trim().toLowerCase();
    const keys = Object.keys(project.glyphs).map(Number).sort((a, b) => a - b);
    const bits = [];
    keys.forEach((u) => {
      if (u === 0) return;
      if (!matchFilter(u)) return;
      const ch = chOf(u);
      if (q) {
        const name = (project.glyphs[u].name || '').toLowerCase();
        const hex = u.toString(16);
        if (!ch.toLowerCase().includes(q) && !name.includes(q) && !hex.includes(q.replace(/^u\+/, ''))) return;
      }
      const g = project.glyphs[u];
      const empty = g.source === 'pixel' && g.grid.every((r) => !r.includes('1'));
      bits.push(`<button type="button" class="gcell ${u === currentU ? 'on' : ''} ${empty ? 'empty' : ''}" data-u="${u}" title="${esc(g.name)} U+${u.toString(16).toUpperCase()}">${ch === '<' ? '<' : ch === '&' ? '&' : esc(ch)}<span class="cp">${u.toString(16)}</span></button>`);
    });
    $('gmap').innerHTML = bits.join('') || '<p class="hint">No glyphs in this filter.</p>';
  }
  function renderMeta() {
    const g = cur();
    $('metaChar').value = chOf(g.unicode);
    $('metaName').value = g.name;
    $('metaAdv').value = g.advance;
  }
  function renderToolbar() {
    const tools = ICONS.map((ic) =>
      `<button type="button" class="tool ${tool === ic.tool ? 'on' : ''}" data-tool="${ic.tool}" title="${esc(ic.title)}"><svg viewBox="0 0 20 20">${ic.svg}</svg></button>`
    ).join('');
    $('toolbar').innerHTML = tools +
      `<span class="tool-lbl">Brush</span><input id="brush" type="range" min="1" max="5" value="${brush}" style="width:80px">` +
      `<span class="tool-lbl" id="modeTag">${cur().source === 'path' ? 'outline' : 'pixels'}</span>` +
      `<button type="button" class="btn ghost" id="btnUndo" title="Undo (Ctrl+Z)">Undo</button>` +
      `<button type="button" class="btn ghost" id="btnMirrorH">Flip H</button>` +
      `<button type="button" class="btn ghost" id="btnMirrorV">Flip V</button>` +
      `<button type="button" class="btn ghost" id="btnInvert">Invert</button>`;
    $('brush').oninput = (e) => { brush = +e.target.value; };
    $('btnUndo').onclick = restore;
    $('btnMirrorH').onclick = () => { snapshot(); const g = cur(); g.grid = g.grid.map((r) => r.split('').reverse().join('')); g.source = 'pixel'; renderAll(); schedulePreview(); persist(); };
    $('btnMirrorV').onclick = () => { snapshot(); const g = cur(); g.grid = g.grid.slice().reverse(); g.source = 'pixel'; renderAll(); schedulePreview(); persist(); };
    $('btnInvert').onclick = () => { snapshot(); const g = cur(); g.grid = g.grid.map((r) => r.replace(/0/g, 'x').replace(/1/g, '0').replace(/x/g, '1')); g.source = 'pixel'; renderAll(); schedulePreview(); persist(); };
  }
  function renderPals() {
    $('symPal').innerHTML = SYMBOLS.map((ch) => `<button type="button" data-ch="${esc(ch)}" title="Stamp ${esc(ch)}">${ch}</button>`).join('');
    $('emoPal').innerHTML = EMOJI.map((ch) => `<button type="button" data-ch="${esc(ch)}" title="Stamp">${ch}</button>`).join('');
  }
  function renderAll() {
    if (!project) return;
    renderFilters();
    renderMap();
    renderMeta();
    renderToolbar();
    drawStage();
    $('gridLbl').textContent = project.grid + ' × ' + project.grid + ' pixels · ' + glyphCount() + ' glyphs';
  }

  function persist() {
    if (!project) return;
    project.family = $('family').value.trim() || project.family;
    project.style = $('styleName').value.trim() || project.style;
    try { localStorage.setItem(LS, JSON.stringify(project)); } catch (_) { /* quota */ }
  }
  function loadSession() {
    try {
      const r = JSON.parse(localStorage.getItem(LS));
      if (r && r.glyphs) return r;
    } catch (_) { /* ignore */ }
    return null;
  }

  function addCharFromInput() {
    const u = parseCode($('addChar').value);
    if (u == null) { toast('Type a character or U+0041'); return; }
    ensureGlyph(u);
    currentU = u;
    $('addChar').value = '';
    renderAll(); persist();
    toast('Added U+' + u.toString(16).toUpperCase());
  }

  function bind() {
    $('filters').addEventListener('click', (e) => {
      const b = e.target.closest('[data-f]');
      if (!b) return;
      filter = b.dataset.f;
      renderFilters(); renderMap();
    });
    $('gmap').addEventListener('click', (e) => {
      const b = e.target.closest('[data-u]');
      if (!b) return;
      currentU = +b.dataset.u;
      renderAll();
    });
    $('q').addEventListener('input', renderMap);
    $('btnAdd').onclick = addCharFromInput;
    $('addChar').addEventListener('keydown', (e) => { if (e.key === 'Enter') addCharFromInput(); });
    $('btnNew').onclick = () => { $('boot').hidden = false; $('btnResume').hidden = !loadSession(); };
    $('btnLoad').onclick = () => $('fileFont').click();
    $('btnSave').onclick = saveCopy;
    $('btnProj').onclick = () => {
      const blob = new Blob([JSON.stringify(project, null, 2)], { type: 'application/json' });
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
        try {
          project = JSON.parse(await f.text());
          currentU = project.glyphs[65] ? 65 : +Object.keys(project.glyphs)[0] || 0;
          afterProject('Opened project');
        } catch (_) { toast('Bad project JSON'); }
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
        x.fillStyle = '#fff'; x.fillRect(0, 0, n, n);
        const scale = Math.min(n / img.width, n / img.height);
        const dw = img.width * scale, dh = img.height * scale;
        x.drawImage(img, (n - dw) / 2, (n - dh) / 2, dw, dh);
        const data = x.getImageData(0, 0, n, n).data;
        const grid = [];
        for (let y = 0; y < n; y++) {
          let row = '';
          for (let xx = 0; xx < n; xx++) {
            const i = (y * n + xx) * 4;
            const lum = (data[i] + data[i + 1] + data[i + 2]) / 3;
            row += (data[i + 3] > 80 && lum < 160) ? '1' : '0';
          }
          grid.push(row);
        }
        const g = cur();
        g.grid = grid; g.source = 'pixel'; g.commands = null;
        URL.revokeObjectURL(url);
        renderAll(); schedulePreview(); persist();
        toast('Traced image into this glyph');
      };
      img.src = url;
    });
    $('toolbar').addEventListener('click', (e) => {
      const b = e.target.closest('[data-tool]');
      if (!b) return;
      tool = b.dataset.tool;
      if (tool === 'image') { $('fileStamp').click(); tool = 'pencil'; }
      renderToolbar();
    });
    $('family').addEventListener('change', () => { persist(); schedulePreview(); });
    $('styleName').addEventListener('change', persist);
    $('sampleIn').addEventListener('input', () => { $('sampleOut').textContent = $('sampleIn').value; });
    $('gridSize').addEventListener('change', () => {
      const n = Math.max(8, Math.min(48, +$('gridSize').value || 16));
      project.grid = n;
      Object.values(project.glyphs).forEach((g) => {
        if (g.source === 'path') return;
        // nearest resample
        const src = g.grid;
        const nn = src.length;
        const next = emptyGrid(n);
        for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
          const sx = Math.floor(x * nn / n), sy = Math.floor(y * nn / n);
          if (src[sy][sx] === '1') setCell(next, x, y, '1');
        }
        g.grid = next;
      });
      renderAll(); schedulePreview(); persist();
    });
    $('metaName').addEventListener('change', () => { cur().name = $('metaName').value; persist(); });
    $('metaAdv').addEventListener('change', () => { cur().advance = +$('metaAdv').value || cur().advance; persist(); schedulePreview(); });
    $('metaChar').addEventListener('change', () => {
      const u = parseCode($('metaChar').value);
      if (u == null) return;
      if (u !== currentU) {
        const g = cur();
        const copy = JSON.parse(JSON.stringify(g));
        copy.unicode = u; copy.name = glyphName(u);
        project.glyphs[u] = copy;
        currentU = u;
        renderAll(); persist();
      }
    });
    $('btnCopyTo').onclick = () => {
      const u = parseCode($('copyTo').value);
      if (u == null) { toast('Pick a character to copy onto'); return; }
      const copy = JSON.parse(JSON.stringify(cur()));
      copy.unicode = u; copy.name = glyphName(u);
      project.glyphs[u] = copy;
      currentU = u;
      $('copyTo').value = '';
      renderAll(); persist(); schedulePreview();
      toast('Duplicated onto U+' + u.toString(16).toUpperCase());
    };
    $('btnClear').onclick = () => {
      snapshot();
      const g = cur();
      g.grid = emptyGrid(g.grid.length);
      g.commands = null;
      g.source = 'pixel';
      renderAll(); persist(); schedulePreview();
    };
    $('symPal').addEventListener('click', onPal);
    $('emoPal').addEventListener('click', onPal);
    function onPal(e) {
      const b = e.target.closest('[data-ch]');
      if (!b) return;
      stampChar = b.getAttribute('data-ch');
      const u = stampChar.codePointAt(0);
      snapshot();
      currentU = u;
      stampInto(ensureGlyph(u), stampChar);
      renderAll(); persist(); schedulePreview();
      toast('Editing ' + stampChar + '  (U+' + u.toString(16).toUpperCase() + ')');
    }

    stage.addEventListener('pointerdown', (ev) => {
      if (!project) return;
      stage.setPointerCapture(ev.pointerId);
      snapshot();
      drawing = true;
      const cell = cellAt(ev);
      startCell = cell;
      hover = cell;
      applyTool(cell, ev, false);
      drawStage();
    });
    stage.addEventListener('pointermove', (ev) => {
      if (!drawing) return;
      const cell = cellAt(ev);
      hover = cell;
      if (tool === 'pencil' || tool === 'eraser') applyTool(cell, ev, false);
      drawStage();
    });
    function endDraw(ev) {
      if (!drawing) return;
      drawing = false;
      const cell = cellAt(ev);
      applyTool(cell, ev, true);
      startCell = null;
      hover = null;
      renderMap();
      drawStage();
      persist();
      schedulePreview();
    }
    stage.addEventListener('pointerup', endDraw);
    stage.addEventListener('pointercancel', endDraw);

    document.addEventListener('keydown', (e) => {
      if (e.target && /input|textarea|select/i.test(e.target.tagName)) return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); restore(); }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); saveCopy(); }
      if (e.key === 'b' || e.key === 'B') { tool = 'pencil'; renderToolbar(); }
      if (e.key === 'e' || e.key === 'E') { tool = 'eraser'; renderToolbar(); }
      if (e.key === 'g' || e.key === 'G') { tool = 'fill'; renderToolbar(); }
      if (e.key === '[') { brush = Math.max(1, brush - 1); renderToolbar(); }
      if (e.key === ']') { brush = Math.min(5, brush + 1); renderToolbar(); }
    });

    document.addEventListener('dragover', (e) => { e.preventDefault(); });
    document.addEventListener('drop', async (e) => {
      e.preventDefault();
      const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (!f) return;
      if (/\.(ttf|otf|woff)$/i.test(f.name)) loadFontBuffer(await f.arrayBuffer(), f.name);
      else if (/\.json$/i.test(f.name)) {
        project = JSON.parse(await f.text());
        afterProject('Opened project');
      } else if (/^image\//.test(f.type) || /\.(png|svg|jpg|jpeg|webp)$/i.test(f.name)) {
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
      const s = loadSession();
      if (!s) return;
      project = s;
      currentU = project.glyphs[65] ? 65 : +Object.keys(project.glyphs).find((k) => +k > 0) || 0;
      afterProject('Resumed last session');
    };
  }

  function start() {
    renderPals();
    bind();
    try {
      new ResizeObserver(resizeStage).observe(document.querySelector('.stage-wrap'));
    } catch (_) {
      window.addEventListener('resize', resizeStage);
    }
    resizeStage();
    const s = loadSession();
    $('btnResume').hidden = !s;
    if (s && s.glyphs && Object.keys(s.glyphs).length > 2) {
      project = s;
      currentU = project.glyphs[65] ? 65 : +Object.keys(project.glyphs).find((k) => +k > 0) || 0;
      $('family').value = project.family || 'Foundry Copy';
      $('styleName').value = project.style || 'Regular';
      $('gridSize').value = project.grid || 16;
      $('boot').hidden = true;
      renderAll();
      schedulePreview();
      $('sourceLabel').textContent = 'Restored session · Save copy downloads a new .otf';
    } else {
      $('boot').hidden = false;
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})(window);
