/**
 * shared/fafo-qr.js — tiny QR encoder for LAN / Pages share URLs.
 * Byte mode, versions 1–5, ECC L, mask 0. No network, no CDN.
 * API: FafoQR.matrix(text) → 0/1 rows; FafoQR.svg(text, opts) → SVG string.
 */
(function (global) {
  'use strict';

  var EXP = new Array(512);
  var LOG = new Array(256);
  (function initGF() {
    var x = 1;
    for (var i = 0; i < 255; i++) {
      EXP[i] = x;
      LOG[x] = i;
      x <<= 1;
      if (x & 0x100) x ^= 0x11d;
    }
    for (var j = 255; j < 512; j++) EXP[j] = EXP[j - 255];
  })();

  function gfMul(a, b) {
    if (!a || !b) return 0;
    return EXP[LOG[a] + LOG[b]];
  }

  function rsGenerator(n) {
    /* poly[0] = leading (highest degree) coefficient */
    var poly = [1];
    for (var i = 0; i < n; i++) {
      var next = new Array(poly.length + 1);
      var k;
      for (k = 0; k < next.length; k++) next[k] = 0;
      for (k = 0; k < poly.length; k++) {
        next[k] ^= poly[k];
        next[k + 1] ^= gfMul(poly[k], EXP[i]);
      }
      poly = next;
    }
    return poly;
  }

  function rsEncode(data, ecCount) {
    var gen = rsGenerator(ecCount);
    var buf = data.slice();
    var i, j;
    for (i = 0; i < ecCount; i++) buf.push(0);
    for (i = 0; i < data.length; i++) {
      var coef = buf[i];
      if (!coef) continue;
      for (j = 0; j < gen.length; j++) buf[i + j] ^= gfMul(gen[j], coef);
    }
    return buf.slice(data.length);
  }

  /* ECC L, 1 block (versions 1–5). dataCW, ecCW */
  var VERS = [
    null,
    { size: 21, data: 19, ec: 7, align: [] },
    { size: 25, data: 34, ec: 10, align: [18] },
    { size: 29, data: 55, ec: 15, align: [22] },
    { size: 33, data: 80, ec: 20, align: [26] },
    { size: 37, data: 108, ec: 26, align: [30] }
  ];

  /* ECC L (01) + mask 0 (000) format bits (already masked with 0x5412). */
  var FORMAT_L_MASK0 = '111011111000100';

  function bytesOf(text) {
    var out = [];
    var s = String(text || '');
    for (var i = 0; i < s.length; i++) {
      var c = s.charCodeAt(i);
      if (c < 128) out.push(c);
      else {
        var enc = unescape(encodeURIComponent(s.charAt(i)));
        for (var j = 0; j < enc.length; j++) out.push(enc.charCodeAt(j) & 255);
      }
    }
    return out;
  }

  function pickVersion(nBytes) {
    var need = nBytes + 2;
    for (var v = 1; v <= 5; v++) {
      if (VERS[v].data >= need) return v;
    }
    return 0;
  }

  function packData(payload, ver) {
    var spec = VERS[ver];
    var bits = [];
    function pushBits(val, n) {
      for (var i = n - 1; i >= 0; i--) bits.push((val >> i) & 1);
    }
    pushBits(0x4, 4);
    pushBits(payload.length, 8);
    for (var i = 0; i < payload.length; i++) pushBits(payload[i], 8);
    var maxBits = spec.data * 8;
    var term = Math.min(4, maxBits - bits.length);
    for (i = 0; i < term; i++) bits.push(0);
    while (bits.length % 8) bits.push(0);
    var bytes = [];
    for (i = 0; i < bits.length; i += 8) {
      var b = 0;
      for (var j = 0; j < 8; j++) b = (b << 1) | bits[i + j];
      bytes.push(b);
    }
    var pad = 0xEC;
    while (bytes.length < spec.data) {
      bytes.push(pad);
      pad = pad === 0xEC ? 0x11 : 0xEC;
    }
    return bytes.concat(rsEncode(bytes, spec.ec));
  }

  function finder(mod, r, c) {
    for (var y = -1; y <= 7; y++) {
      for (var x = -1; x <= 7; x++) {
        var rr = r + y, cc = c + x;
        if (rr < 0 || cc < 0 || rr >= mod.length || cc >= mod.length) continue;
        var on = (x >= 0 && x <= 6 && y >= 0 && y <= 6) &&
          (x === 0 || x === 6 || y === 0 || y === 6 || (x >= 2 && x <= 4 && y >= 2 && y <= 4));
        if (y === -1 || y === 7 || x === -1 || x === 7) on = false;
        mod[rr][cc] = on ? 1 : 0;
      }
    }
  }

  function alignment(mod, cx, cy) {
    for (var y = -2; y <= 2; y++) {
      for (var x = -2; x <= 2; x++) {
        var on = x === -2 || x === 2 || y === -2 || y === 2 || (x === 0 && y === 0);
        mod[cy + y][cx + x] = on ? 1 : 0;
      }
    }
  }

  function reservedMap(size, align) {
    var n = size;
    var res = new Array(n);
    var r, c;
    for (r = 0; r < n; r++) {
      res[r] = new Array(n);
      for (c = 0; c < n; c++) res[r][c] = 0;
    }
    function markFinder(fr, fc) {
      for (r = fr - 1; r <= fr + 7; r++) {
        for (c = fc - 1; c <= fc + 7; c++) {
          if (r >= 0 && c >= 0 && r < n && c < n) res[r][c] = 1;
        }
      }
    }
    markFinder(0, 0);
    markFinder(0, n - 7);
    markFinder(n - 7, 0);
    for (c = 0; c < n; c++) { res[6][c] = 1; res[c][6] = 1; }
    for (c = 0; c < 9; c++) {
      res[8][c] = 1; res[c][8] = 1;
    }
    for (c = n - 8; c < n; c++) {
      res[8][c] = 1; res[c][8] = 1;
    }
    res[n - 8][8] = 1;
    for (var i = 0; i < align.length; i++) {
      var a = align[i];
      for (r = a - 2; r <= a + 2; r++) {
        for (c = a - 2; c <= a + 2; c++) res[r][c] = 1;
      }
    }
    return res;
  }

  function placeFormat(mod) {
    var b = FORMAT_L_MASK0;
    var n = mod.length;
    function f(i) { return b.charAt(i) === '1' ? 1 : 0; }
    var i;
    for (i = 0; i < 6; i++) mod[8][i] = f(i);
    mod[8][7] = f(6);
    mod[8][8] = f(7);
    for (i = 0; i < 8; i++) mod[8][n - 1 - i] = f(14 - i);
    for (i = 0; i < 6; i++) mod[i][8] = f(14 - i);
    mod[7][8] = f(8);
    for (i = 0; i < 7; i++) mod[n - 1 - i][8] = f(i);
    mod[n - 8][8] = 1;
  }

  function matrix(text) {
    var payload = bytesOf(text);
    var ver = pickVersion(payload.length);
    if (!ver) throw new Error('QR text too long for this encoder (max ~100 bytes)');
    var spec = VERS[ver];
    var n = spec.size;
    var mod = new Array(n);
    var r, c;
    for (r = 0; r < n; r++) {
      mod[r] = new Array(n);
      for (c = 0; c < n; c++) mod[r][c] = 0;
    }
    finder(mod, 0, 0);
    finder(mod, 0, n - 7);
    finder(mod, n - 7, 0);
    for (c = 8; c < n - 8; c++) {
      mod[6][c] = c % 2 === 0 ? 1 : 0;
      mod[c][6] = c % 2 === 0 ? 1 : 0;
    }
    for (var a = 0; a < spec.align.length; a++) alignment(mod, spec.align[a], spec.align[a]);
    mod[n - 8][8] = 1;
    placeFormat(mod);
    var res = reservedMap(n, spec.align);
    var code = packData(payload, ver);
    var bitRow = [];
    for (r = 0; r < code.length; r++) {
      for (c = 7; c >= 0; c--) bitRow.push((code[r] >> c) & 1);
    }
    var bi = 0;
    var dir = -1;
    for (c = n - 1; c > 0; c -= 2) {
      if (c === 6) c--;
      for (var y = 0; y < n; y++) {
        r = dir < 0 ? n - 1 - y : y;
        for (var k = 0; k < 2; k++) {
          var cc = c - k;
          if (res[r][cc]) continue;
          var bit = bi < bitRow.length ? bitRow[bi++] : 0;
          if (((r + cc) % 2) === 0) bit ^= 1;
          mod[r][cc] = bit;
        }
      }
      dir = -dir;
    }
    placeFormat(mod);
    return mod;
  }

  function svg(text, opts) {
    opts = opts || {};
    var mod = matrix(text);
    var n = mod.length;
    var quiet = opts.quiet == null ? 4 : opts.quiet;
    var dark = opts.dark || '#041018';
    var light = opts.light || '#e8eef4';
    var dim = n + quiet * 2;
    var parts = [
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + dim + ' ' + dim +
        '" role="img" aria-label="QR code"><rect width="' + dim + '" height="' + dim +
        '" fill="' + light + '"/>'
    ];
    for (var r = 0; r < n; r++) {
      for (var c = 0; c < n; c++) {
        if (!mod[r][c]) continue;
        parts.push('<rect x="' + (c + quiet) + '" y="' + (r + quiet) + '" width="1" height="1" fill="' + dark + '"/>');
      }
    }
    parts.push('</svg>');
    return parts.join('');
  }

  function draw(el, text, opts) {
    if (!el) return;
    el.innerHTML = svg(text, opts);
    var node = el.firstElementChild;
    if (node) {
      node.style.width = '100%';
      node.style.height = 'auto';
      node.style.display = 'block';
    }
  }

  global.FafoQR = {
    matrix: matrix,
    svg: svg,
    draw: draw,
    maxBytes: 106,
    _codewords: function (text) {
      var payload = bytesOf(text);
      var ver = pickVersion(payload.length);
      if (!ver) throw new Error('too long');
      return packData(payload, ver);
    }
  };
})(typeof window !== 'undefined' ? window : globalThis);
