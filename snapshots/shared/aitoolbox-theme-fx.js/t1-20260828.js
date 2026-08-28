/**
 * FAFO Toolbox — named lighting themes
 *   sparkysparks     fireworks click, falling bloom sparks, glowing piles
 *   paintonsalought  same motion with neon / blacklight paint specks
 *
 * Driven by AIToolboxPrefs.fxTheme. Pointer-events none; listens on window.
 * Snapshots: snapshots/shared/aitoolbox-theme-fx.js/
 */
(function (global) {
  'use strict';

  const MAX_LIVE = 720;
  const BINS = 28;
  const FW_HUES = [12, 32, 48, 190, 268, 310, 140];
  const PAINT_HUES = [188, 272, 300, 164, 220, 128];

  let canvas = null;
  let ctx = null;
  let raf = 0;
  let w = 0;
  let h = 0;
  let dpr = 1;
  let mode = 'off';
  let particles = [];
  let bolts = [];
  let piles = [];
  let lastMove = 0;
  let lastPt = { x: 0, y: 0 };
  let wind = 0;
  let lastTs = 0;
  let skip = 0;
  let reduced = false;
  let glowMul = 1;
  let bound = false;

  function hueColor(hue, a, lit) {
    const l = lit == null ? 62 : lit;
    return 'hsla(' + (hue % 360) + ',100%,' + l + '%,' + a + ')';
  }

  function isPaint() { return mode === 'paintonsalought'; }

  function paletteHue() {
    const arr = isPaint() ? PAINT_HUES : FW_HUES;
    return arr[(Math.random() * arr.length) | 0];
  }

  function resize() {
    if (!canvas) return;
    dpr = Math.min(1.5, window.devicePixelRatio || 1);
    w = window.innerWidth || 1;
    h = window.innerHeight || 1;
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (!piles.length) {
      for (let i = 0; i < BINS; i++) piles.push({ m: 0, hue: 200, glow: 0 });
    }
  }

  function inject() {
    if (canvas) return;
    const css = document.createElement('style');
    css.id = 'atx-theme-fx-css';
    css.textContent = `
#atx-theme-fx{position:fixed;inset:0;z-index:99970;pointer-events:none;mix-blend-mode:screen}
html[data-atx-fx="sparkysparks"], html[data-atx-fx="paintonsalought"]{
  --atx-bolt: transparent;
}
html[data-atx-fx="sparkysparks"] body,
html[data-atx-fx="paintonsalought"] body{
  box-shadow:
    inset 0 0 0 2px var(--atx-bolt, transparent),
    inset 0 0 28px var(--atx-bolt, transparent);
  transition: box-shadow .12s linear;
}
html[data-atx-fx="paintonsalought"] #atx-theme-fx{mix-blend-mode:plus-lighter}
@media (prefers-reduced-motion: reduce){
  #atx-theme-fx{display:none !important}
}
`;
    (document.head || document.documentElement).appendChild(css);
    canvas = document.createElement('canvas');
    canvas.id = 'atx-theme-fx';
    canvas.setAttribute('aria-hidden', 'true');
    (document.body || document.documentElement).appendChild(canvas);
    ctx = canvas.getContext('2d', { alpha: true });
    resize();
  }

  function spawn(p) {
    if (particles.length >= MAX_LIVE) {
      particles.splice(0, particles.length - MAX_LIVE + 8);
    }
    particles.push(p);
  }

  function burstFirework(x, y, hue) {
    const n = 28 + ((Math.random() * 22) | 0);
    const paint = isPaint();
    for (let i = 0; i < n; i++) {
      const a = (Math.PI * 2 * i) / n + Math.random() * 0.2;
      const v = paint ? (1.4 + Math.random() * 3.2) : (2.2 + Math.random() * 5.4);
      spawn({
        kind: paint ? 'paint' : 'fw',
        x, y,
        vx: Math.cos(a) * v,
        vy: Math.sin(a) * v - (paint ? 0.4 : 1.2),
        life: 1,
        decay: paint ? 0.008 + Math.random() * 0.012 : 0.012 + Math.random() * 0.018,
        size: paint ? 5 + Math.random() * 10 : 2 + Math.random() * 3.5,
        hue: hue + (Math.random() - 0.5) * 28,
        bloom: paint ? 0.55 + Math.random() * 0.4 : 0.25 + Math.random() * 0.5,
        grav: paint ? 0.04 : 0.065,
        settled: false,
      });
    }
    // delayed color-shift pop
    setTimeout(function () {
      if (mode === 'off') return;
      const h2 = hue + 40 + Math.random() * 80;
      const n2 = 10 + ((Math.random() * 10) | 0);
      for (let i = 0; i < n2; i++) {
        const a = Math.random() * Math.PI * 2;
        const v = 1.2 + Math.random() * 3;
        spawn({
          kind: paint ? 'paint' : 'fw',
          x: x + (Math.random() - 0.5) * 12,
          y: y + (Math.random() - 0.5) * 12,
          vx: Math.cos(a) * v,
          vy: Math.sin(a) * v - 0.6,
          life: 1,
          decay: 0.02,
          size: paint ? 4 + Math.random() * 7 : 1.5 + Math.random() * 2.5,
          hue: h2,
          bloom: 0.7,
          grav: 0.05,
          settled: false,
        });
      }
      flashBolt(h2);
    }, 90 + Math.random() * 120);
    flashBolt(hue);
  }

  function shower(x, y, n) {
    const paint = isPaint();
    n = n || (1 + ((Math.random() * 3) | 0));
    for (let i = 0; i < n; i++) {
      spawn({
        kind: paint ? 'paint' : 'spark',
        x: x + (Math.random() - 0.5) * 18,
        y: y + (Math.random() - 0.5) * 10,
        vx: (Math.random() - 0.5) * (paint ? 0.6 : 0.9) + wind * 0.15,
        vy: paint ? (0.15 + Math.random() * 0.55) : (0.35 + Math.random() * 1.1),
        life: 1,
        decay: paint ? 0.0018 + Math.random() * 0.003 : 0.0022 + Math.random() * 0.004,
        size: paint ? 4 + Math.random() * 9 : 1.6 + Math.random() * 3.4,
        hue: paletteHue() + (Math.random() - 0.5) * 18,
        bloom: paint ? 0.35 + Math.random() * 0.55 : 0.2 + Math.random() * 0.55,
        grav: paint ? 0.025 : 0.045,
        settled: false,
        reactive: paint,
      });
    }
  }

  function flashBolt(hue) {
    const dur = 90 + Math.random() * 140;
    bolts.push({
      hue,
      life: 1,
      decay: 1 / (dur / 16),
      side: (Math.random() * 4) | 0,
      pts: makeBolt(hue),
    });
    try {
      document.documentElement.style.setProperty('--atx-bolt', hueColor(hue, 0.85, 70));
      setTimeout(function () {
        document.documentElement.style.setProperty('--atx-bolt', 'transparent');
      }, dur);
    } catch (_) { /* ignore */ }
  }

  function makeBolt(hue) {
    const pts = [];
    const side = (Math.random() * 4) | 0;
    let x, y, dx, dy, steps;
    if (side === 0) { x = Math.random() * w; y = 0; dx = 0; dy = 1; steps = 8; }
    else if (side === 1) { x = w; y = Math.random() * h; dx = -1; dy = 0; steps = 8; }
    else if (side === 2) { x = Math.random() * w; y = h; dx = 0; dy = -1; steps = 8; }
    else { x = 0; y = Math.random() * h; dx = 1; dy = 0; steps = 8; }
    const len = 40 + Math.random() * 90;
    pts.push({ x, y, hue });
    for (let i = 0; i < steps; i++) {
      x += dx * (len / steps) + (Math.random() - 0.5) * 18;
      y += dy * (len / steps) + (Math.random() - 0.5) * 18;
      pts.push({ x, y, hue });
    }
    return pts;
  }

  function floorY() {
    try {
      if (document.body && document.body.classList.contains('atx-pro-pad')) return h - 54;
    } catch (_) { /* ignore */ }
    return h - 10;
  }

  function binAt(x) {
    const i = Math.max(0, Math.min(BINS - 1, Math.floor((x / Math.max(1, w)) * BINS)));
    return i;
  }

  function settle(p) {
    const i = binAt(p.x);
    const pile = piles[i];
    pile.m = Math.min(90, pile.m + (isPaint() ? 1.6 : 1));
    pile.hue = pile.hue * 0.82 + p.hue * 0.18;
    pile.glow = Math.min(1, pile.glow + 0.08);
    p.settled = true;
    p.life = 0;
  }

  function blowPiles(force) {
    const f = Math.max(0.4, Math.min(6, Math.abs(force) * 0.04));
    const dir = force >= 0 ? 1 : -1;
    for (let i = 0; i < BINS; i++) {
      const pile = piles[i];
      if (pile.m < 2) continue;
      const take = Math.min(pile.m, 2 + f * 2);
      pile.m -= take;
      const n = Math.min(14, 2 + (take | 0));
      const cx = ((i + 0.5) / BINS) * w;
      for (let k = 0; k < n; k++) {
        spawn({
          kind: isPaint() ? 'paint' : 'spark',
          x: cx + (Math.random() - 0.5) * 16,
          y: floorY() - Math.random() * pile.m,
          vx: dir * (1.6 + Math.random() * 3.4) * f + (Math.random() - 0.5),
          vy: -1.2 - Math.random() * 3.5,
          life: 1,
          decay: 0.012 + Math.random() * 0.02,
          size: isPaint() ? 4 + Math.random() * 8 : 1.8 + Math.random() * 3,
          hue: pile.hue + (Math.random() - 0.5) * 20,
          bloom: 0.55,
          grav: 0.07,
          settled: false,
        });
      }
    }
  }

  function step(ts) {
    raf = requestAnimationFrame(step);
    if (mode === 'off' || !ctx) return;
    const dt = Math.min(32, (ts - lastTs) || 16) / 16;
    lastTs = ts;
    skip++;
    if (glowMul < 0.15) return;

    wind *= 0.92;
    ctx.clearRect(0, 0, w, h);
    ctx.globalCompositeOperation = isPaint() ? 'lighter' : 'screen';

    const mx = lastPt.x;
    const my = lastPt.y;
    const next = [];
    for (let i = 0; i < particles.length; i++) {
      const p = particles[i];
      if (p.reactive && isPaint()) {
        const dx = p.x - mx;
        const dy = p.y - my;
        const d2 = dx * dx + dy * dy;
        if (d2 < 90 * 90) {
          const d = Math.sqrt(d2) || 1;
          p.size = Math.min(p.size * 1.03, 22);
          p.bloom = Math.min(1, p.bloom + 0.04);
          p.vx += (dx / d) * 0.05;
          p.vy += (dy / d) * 0.03;
        }
      }
      p.vx += wind * 0.04 * dt;
      p.vy += p.grav * dt * 16 * 0.06;
      p.x += p.vx * dt * 6;
      p.y += p.vy * dt * 6;
      p.vx *= 0.995;
      p.life -= p.decay * dt;
      const floor = floorY();
      if (!p.settled && p.y >= floor && p.vy > 0) {
        settle(p);
        continue;
      }
      if (p.life <= 0 || p.x < -40 || p.x > w + 40 || p.y < -80) continue;
      next.push(p);

      const a = Math.max(0, p.life) * glowMul;
      const r = p.size * (0.7 + p.bloom);
      const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r * (isPaint() ? 3.2 : 2.4));
      g.addColorStop(0, hueColor(p.hue, Math.min(1, a * (p.bloom + 0.35)), isPaint() ? 68 : 72));
      g.addColorStop(0.45, hueColor(p.hue, a * 0.35, isPaint() ? 55 : 58));
      g.addColorStop(1, hueColor(p.hue, 0, 40));
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(p.x, p.y, r * (isPaint() ? 3.2 : 2.4), 0, Math.PI * 2);
      ctx.fill();
    }
    particles = next;

    // glowing piles
    for (let i = 0; i < BINS; i++) {
      const pile = piles[i];
      pile.glow *= 0.985;
      if (pile.m <= 0.4) continue;
      const cx = ((i + 0.5) / BINS) * w;
      const ph = Math.min(64, pile.m * 0.85);
      const pw = (w / BINS) * 0.92;
      const fy = floorY();
      const g = ctx.createRadialGradient(cx, fy, 0, cx, fy, pw * 1.6);
      const a = (0.25 + pile.glow * 0.7) * glowMul;
      g.addColorStop(0, hueColor(pile.hue, Math.min(0.95, a), isPaint() ? 62 : 66));
      g.addColorStop(0.55, hueColor(pile.hue, a * 0.35, 50));
      g.addColorStop(1, hueColor(pile.hue, 0, 40));
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.ellipse(cx, fy + 4, pw * 0.7, ph * 0.55, 0, 0, Math.PI * 2);
      ctx.fill();
    }

    // lightning bolts from firework/paint colors
    ctx.globalCompositeOperation = 'lighter';
    const keepB = [];
    for (let i = 0; i < bolts.length; i++) {
      const b = bolts[i];
      b.life -= b.decay;
      if (b.life <= 0) continue;
      keepB.push(b);
      ctx.strokeStyle = hueColor(b.hue, b.life * 0.9, 78);
      ctx.lineWidth = isPaint() ? 2.4 : 1.6;
      ctx.shadowColor = hueColor(b.hue, 0.8, 70);
      ctx.shadowBlur = 14;
      ctx.beginPath();
      if (b.pts[0]) ctx.moveTo(b.pts[0].x, b.pts[0].y);
      for (let k = 1; k < b.pts.length; k++) ctx.lineTo(b.pts[k].x, b.pts[k].y);
      ctx.stroke();
      ctx.shadowBlur = 0;
    }
    bolts = keepB;
  }

  function ignoreTarget(t) {
    if (!t || !t.closest) return false;
    return !!(t.closest('#atx-look') || t.closest('#atx-pro-help') || t.closest('input') || t.closest('textarea') || t.closest('select'));
  }

  function onPointerMove(e) {
    if (mode === 'off') return;
    const x = e.clientX;
    const y = e.clientY;
    const now = performance.now();
    const dx = x - lastPt.x;
    const dy = y - lastPt.y;
    lastPt.x = x;
    lastPt.y = y;
    if (now - lastMove < 24) return;
    lastMove = now;
    const dist = Math.hypot(dx, dy);
    if (dist < 4) return;
    const n = dist > 40 ? 3 : 1;
    shower(x, y, n);
  }

  function onPointerDown(e) {
    if (mode === 'off' || e.button !== 0) return;
    if (ignoreTarget(e.target)) return;
    lastPt.x = e.clientX;
    lastPt.y = e.clientY;
    burstFirework(e.clientX, e.clientY, paletteHue());
  }

  function onScroll(e) {
    if (mode === 'off') return;
    if (e && e.ctrlKey) return;
    const dy = e && typeof e.deltaY === 'number' ? e.deltaY : 0;
    wind += Math.max(-8, Math.min(8, dy * 0.02));
    if (Math.abs(dy) > 4) blowPiles(dy);
  }

  function bind() {
    if (bound) return;
    bound = true;
    window.addEventListener('pointermove', onPointerMove, { passive: true });
    window.addEventListener('pointerdown', onPointerDown, { capture: true });
    window.addEventListener('wheel', onScroll, { passive: true });
    window.addEventListener('resize', resize);
  }

  function unbind() {
    if (!bound) return;
    bound = false;
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerdown', onPointerDown, { capture: true });
    window.removeEventListener('wheel', onScroll);
    window.removeEventListener('resize', resize);
  }

  function setMode(next) {
    const m = next === 'sparkysparks' || next === 'paintonsalought' ? next : 'off';
    try {
      reduced = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    } catch (_) { reduced = false; }
    if (reduced) {
      mode = 'off';
      unbind();
      if (raf) { cancelAnimationFrame(raf); raf = 0; }
      if (canvas) ctx && ctx.clearRect(0, 0, w, h);
      document.documentElement.removeAttribute('data-atx-fx');
      return;
    }
    mode = m;
    document.documentElement.setAttribute('data-atx-fx', mode);
    if (mode === 'off') {
      unbind();
      if (raf) { cancelAnimationFrame(raf); raf = 0; }
      particles = [];
      bolts = [];
      if (canvas && ctx) ctx.clearRect(0, 0, w, h);
      return;
    }
    inject();
    bind();
    if (!raf) {
      lastTs = performance.now();
      raf = requestAnimationFrame(step);
    }
  }

  function sync() {
    let theme = 'off';
    try {
      const p = global.AIToolboxPrefs && global.AIToolboxPrefs.get && global.AIToolboxPrefs.get();
      if (p) {
        theme = p.fxTheme || 'off';
        glowMul = Math.max(0.2, (Number(p.glow) || 55) / 50);
        if (p.lighting === 'flat') glowMul *= 0.15;
        else if (p.lighting === 'dim') glowMul *= 0.45;
        else if (p.lighting === 'soft') glowMul *= 0.75;
        if (p.ambient === false) glowMul *= 0.55;
      }
    } catch (_) { /* ignore */ }
    setMode(theme);
  }

  function boot() {
    sync();
    document.addEventListener('fafo-shell-prefs', sync);
    global.addEventListener('fafo-shell-prefs', sync);
  }

  global.AIToolboxThemeFx = { sync, setMode };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})(typeof window !== 'undefined' ? window : globalThis);
