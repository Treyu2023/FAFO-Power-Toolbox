/**
 * AI HTML Toolbox — Launcher polish
 * Multi-layer depth marquee (scroll-slowed parallax), tessellation lighting
 * on tiles/panels, idle anti-burn-in motion, mouse trail + soft sounds.
 */
(function (global) {
    'use strict';

    const LS = 'aitoolbox.launcher.fx';
    const DEFAULTS = {
        enabled: true,
        sounds: true,
        marquee: true,
        intensity: 1 // 0.5–1.5
    };

    let prefs = loadPrefs();
    let audioCtx = null;
    let root = null;
    let marqueeTracks = { far: null, mid: null, near: null };
    let marqueeStage = null;
    let marqueeOffsets = { far: 0, mid: 0, near: 0 };
    let marqueeLastTs = 0;
    let marqueePaused = false;
    let scrollProgress = 0;
    let canvas = null;
    let ctx = null;
    let rafId = 0;
    let mouse = { x: 0.5, y: 0.5, px: 0.5, py: 0.5, active: false };
    let sparks = [];
    let tracers = [];
    let lastSoundAt = 0;
    let clipUrls = [];
    let reducedMotion = false;
    let started = false;

    function loadPrefs() {
        try {
            return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(LS) || '{}') };
        } catch (_) {
            return { ...DEFAULTS };
        }
    }
    function savePrefs(patch) {
        prefs = { ...prefs, ...patch };
        try { localStorage.setItem(LS, JSON.stringify(prefs)); } catch (_) { /* ignore */ }
        applyEnabled();
        return prefs;
    }

    function injectStyles() {
        if (document.getElementById('aitoolbox-launcher-fx-css')) return;
        const style = document.createElement('style');
        style.id = 'aitoolbox-launcher-fx-css';
        style.textContent = `
/* ── Launcher ambient FX (depth marquee + tessellation) ── */
:root {
  --lx-scroll: 0;
  --lx-lx: 28%;
  --lx-ly: 18%;
  --lx-lz: 0.5;
  --lx-tess: 1;
}
#lxRoot {
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  overflow: hidden; opacity: 1; transition: opacity 0.5s;
}
body.lx-off #lxRoot { opacity: 0; visibility: hidden; }
body.lx-active { position: relative; }
body.lx-active > :not(#lxRoot):not(.cine-root):not(#cineSettingsPop) {
  position: relative; z-index: 1;
}
body.lx-active .section-nav { z-index: 40; }

#lxCanvas {
  position: absolute; inset: 0; width: 100%; height: 100%;
  opacity: 0.5; mix-blend-mode: screen;
}

.lx-wash {
  position: absolute; inset: -12%;
  background:
    radial-gradient(ellipse at var(--lx-lx) var(--lx-ly), rgba(0,243,255,0.16), transparent 52%),
    radial-gradient(ellipse at calc(100% - var(--lx-lx)) calc(100% - var(--lx-ly)), rgba(124,92,255,0.16), transparent 48%),
    radial-gradient(ellipse at 50% 100%, rgba(0,255,136,0.08), transparent 42%);
  animation: lxWash 48s ease-in-out infinite alternate;
  filter: blur(2px);
  transition: background 0.2s linear;
}
@keyframes lxWash {
  0%   { transform: translate(0,0) scale(1); filter: hue-rotate(0deg) blur(2px); opacity: 0.75; }
  50%  { transform: translate(-2%, 2%) scale(1.05); filter: hue-rotate(22deg) blur(3px); opacity: 1; }
  100% { transform: translate(2%, -1%) scale(0.98); filter: hue-rotate(-18deg) blur(2px); opacity: 0.82; }
}

/* Triangular / tessellation lattice behind content */
.lx-tess-field {
  position: absolute; inset: 0;
  opacity: 0.35;
  background-image:
    repeating-linear-gradient(60deg, transparent 0 22px, rgba(0,243,255,0.035) 22px 23px),
    repeating-linear-gradient(-60deg, transparent 0 22px, rgba(124,92,255,0.03) 22px 23px),
    repeating-linear-gradient(0deg, transparent 0 38px, rgba(255,255,255,0.015) 38px 39px);
  background-size: 100% 100%, 100% 100%, 100% 100%;
  background-position:
    calc(var(--lx-lx) * 0.15) calc(var(--lx-ly) * 0.1),
    calc(var(--lx-lx) * -0.1) calc(var(--lx-ly) * 0.2),
    0 calc(var(--lx-scroll) * 40px);
  mask-image: radial-gradient(ellipse at 50% 40%, #000 10%, transparent 78%);
  -webkit-mask-image: radial-gradient(ellipse at 50% 40%, #000 10%, transparent 78%);
  mix-blend-mode: screen;
}

.lx-grid {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(0,243,255,0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(124,92,255,0.04) 1px, transparent 1px);
  background-size: 56px 56px;
  animation: lxGrid 72s linear infinite;
  opacity: 0.4;
  mask-image: radial-gradient(ellipse at center, #000 15%, transparent 78%);
  -webkit-mask-image: radial-gradient(ellipse at center, #000 15%, transparent 78%);
}
@keyframes lxGrid {
  0% { background-position: 0 0, 0 0; }
  100% { background-position: 56px 56px, 56px 56px; }
}

.lx-scan {
  position: absolute; left: 0; right: 0; height: 16%;
  background: linear-gradient(180deg, transparent, rgba(0,243,255,0.05), transparent);
  animation: lxScan 16s ease-in-out infinite;
  opacity: 0.65;
}
@keyframes lxScan {
  0% { top: -20%; }
  100% { top: 110%; }
}

/* ── Multi-layer depth marquee (large cinema ribbon) ── */
.lx-marquee-stage {
  position: absolute; left: 0; right: 0; bottom: 0;
  height: min(44vh, 420px);
  perspective: 1100px;
  perspective-origin: 50% 100%;
  transform-style: preserve-3d;
  pointer-events: none;
  /* lifts slightly as you scroll — depth cue */
  transform: translate3d(0, calc(var(--lx-scroll) * 36px), 0);
  transition: transform 0.08s linear;
}
.lx-marquee {
  position: absolute; left: -4%; right: -4%;
  overflow: hidden;
  mask-image:
    linear-gradient(90deg, transparent, #000 6%, #000 94%, transparent),
    linear-gradient(180deg, transparent, #000 18%, #000 100%);
  -webkit-mask-image:
    linear-gradient(90deg, transparent, #000 6%, #000 94%, transparent),
    linear-gradient(180deg, transparent, #000 18%, #000 100%);
  mask-composite: intersect;
  -webkit-mask-composite: source-in;
  will-change: transform, opacity, filter;
}
.lx-marquee-track {
  display: flex; gap: 18px; height: 100%;
  width: max-content;
  will-change: transform;
  /* position driven by JS for scroll-linked speed */
}
/* Far = smaller, softer, slower (set in JS) */
.lx-m-far {
  height: 58%; bottom: 30%;
  opacity: 0.26;
  filter: blur(2.8px) saturate(0.85) brightness(0.75);
  transform: scale(0.9) translateZ(-120px);
}
.lx-m-mid {
  height: 74%; bottom: 12%;
  opacity: 0.4;
  filter: blur(1.1px) saturate(1.05) brightness(0.88);
  transform: scale(0.96) translateZ(-40px);
}
.lx-m-near {
  height: 100%; bottom: 0;
  opacity: 0.58;
  filter: saturate(1.2) brightness(0.95) contrast(1.05);
  transform: scale(1) translateZ(0);
  /* near layer accepts hover pause via pointer-events on stage region */
}
.lx-marquee-stage:hover .lx-m-near { opacity: 0.72; }
.lx-tile {
  flex: 0 0 auto;
  height: 100%;
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid rgba(0,243,255,0.22);
  box-shadow:
    0 12px 40px rgba(0,0,0,0.55),
    inset 0 1px 0 rgba(255,255,255,0.08),
    0 0 0 1px rgba(0,0,0,0.35);
  position: relative;
  background:
    linear-gradient(145deg, rgba(20,24,36,0.9), rgba(6,8,14,0.95));
}
.lx-m-far .lx-tile { width: min(26vw, 220px); border-radius: 10px; }
.lx-m-mid .lx-tile { width: min(34vw, 300px); border-radius: 14px; }
.lx-m-near .lx-tile { width: min(42vw, 400px); border-radius: 18px; }
.lx-tile video {
  width: 100%; height: 100%;
  object-fit: cover;
  display: block;
  pointer-events: none;
}
.lx-tile::before {
  content: '';
  position: absolute; inset: 0; z-index: 1; pointer-events: none;
  background:
    repeating-linear-gradient(60deg, transparent 0 14px, rgba(0,243,255,0.04) 14px 15px),
    repeating-linear-gradient(-60deg, transparent 0 14px, rgba(124,92,255,0.035) 14px 15px),
    radial-gradient(ellipse 90% 70% at var(--lx-lx) var(--lx-ly), rgba(0,243,255,0.18), transparent 55%),
    linear-gradient(180deg, rgba(255,255,255,0.06), transparent 28%, transparent 55%, rgba(5,5,8,0.65));
  mix-blend-mode: soft-light;
}
.lx-tile::after {
  content: '';
  position: absolute; inset: 0; z-index: 2; pointer-events: none;
  box-shadow: inset 0 0 40px rgba(0,0,0,0.35);
  background: linear-gradient(125deg, rgba(255,255,255,0.1) 0%, transparent 32%, transparent 68%, rgba(0,243,255,0.08) 100%);
}
.lx-empty-hint {
  position: absolute; bottom: 16px; left: 50%; transform: translateX(-50%);
  font-size: 10px; color: rgba(136,136,160,0.55); letter-spacing: 0.08em;
  white-space: nowrap; pointer-events: none; z-index: 3;
}

/* Soft floor fade so content stays readable over large marquee */
.lx-marquee-stage::after {
  content: '';
  position: absolute; left: 0; right: 0; top: 0; height: 40%;
  background: linear-gradient(180deg, rgba(5,5,8,0.55), transparent);
  pointer-events: none; z-index: 4;
}

/* Cursor glow */
.lx-cursor {
  position: absolute; width: 320px; height: 320px;
  margin: -160px 0 0 -160px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(0,243,255,0.18), rgba(124,92,255,0.1) 40%, transparent 70%);
  left: 0; top: 0;
  opacity: 0.85;
  transition: opacity 0.3s;
  mix-blend-mode: screen;
  will-change: transform;
}

/* ── Tessellated materials on homepage tiles & blocks ── */
body.lx-active .tool-card,
body.lx-active .hub-card,
body.lx-active .section-header,
body.lx-active .get-started,
body.lx-active .get-started-step {
  --tess-a: rgba(0,243,255, calc(0.1 * var(--lx-tess, 1)));
  --tess-b: rgba(124,92,255, calc(0.09 * var(--lx-tess, 1)));
  background-color: #0a0c14;
  background-image:
    radial-gradient(ellipse 130% 90% at var(--lx-lx) var(--lx-ly),
      rgba(0,243,255, calc(0.16 * var(--lx-tess, 1))), transparent 58%),
    radial-gradient(ellipse 100% 80% at calc(100% - var(--lx-lx)) calc(100% - var(--lx-ly)),
      rgba(124,92,255, calc(0.14 * var(--lx-tess, 1))), transparent 55%),
    repeating-linear-gradient(60deg,
      transparent 0 11px, rgba(0,243,255,0.035) 11px 12px),
    repeating-linear-gradient(-60deg,
      transparent 0 11px, rgba(124,92,255,0.028) 11px 12px),
    repeating-linear-gradient(0deg,
      transparent 0 19px, rgba(255,255,255,0.012) 19px 20px),
    linear-gradient(155deg, rgba(28,32,48,0.96) 0%, rgba(12,14,22,0.98) 48%, rgba(8,9,14,0.99) 100%);
  background-blend-mode: soft-light, soft-light, normal, normal, normal, normal;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.07),
    inset 0 -1px 0 rgba(0,0,0,0.45),
    0 10px 28px rgba(0,0,0,0.35);
  border-color: rgba(0,243,255,0.28);
  transition:
    transform 0.22s cubic-bezier(.2,.8,.2,1),
    box-shadow 0.22s, border-color 0.22s, filter 0.22s,
    background-position 0.15s linear;
  background-position:
    0 0, 0 0,
    calc(var(--lx-lx) * 0.2) calc(var(--lx-ly) * 0.15),
    calc(var(--lx-lx) * -0.15) calc(var(--lx-ly) * 0.2),
    0 calc(var(--lx-scroll) * 24px),
    0 0;
}
body.lx-active .tool-card.featured {
  background-image:
    radial-gradient(ellipse 120% 90% at var(--lx-lx) var(--lx-ly),
      rgba(255,200,80,0.14), transparent 55%),
    radial-gradient(ellipse 100% 80% at calc(100% - var(--lx-lx)) calc(100% - var(--lx-ly)),
      rgba(0,243,255,0.1), transparent 50%),
    repeating-linear-gradient(60deg, transparent 0 11px, rgba(255,200,80,0.04) 11px 12px),
    repeating-linear-gradient(-60deg, transparent 0 11px, rgba(0,243,255,0.03) 11px 12px),
    linear-gradient(155deg, rgba(36,30,18,0.97), rgba(12,12,18,0.99));
  border-color: rgba(255,200,0,0.45);
}
body.lx-active .tool-card:hover,
body.lx-active .hub-card:hover {
  transform: translateY(-6px) scale(1.025);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.1),
    0 16px 40px rgba(0,0,0,0.5),
    0 0 28px rgba(0,243,255,0.22);
  border-color: rgba(0,243,255,0.6);
  filter: brightness(1.06) saturate(1.08);
}
body.lx-active .tool-card .icon-wrap,
body.lx-active .hub-card .hub-emoji {
  box-shadow:
    inset 0 0 20px rgba(0,243,255,0.08),
    0 4px 14px rgba(0,0,0,0.4);
  border-color: rgba(0,243,255,0.35);
  background:
    radial-gradient(circle at var(--lx-lx) var(--lx-ly), rgba(0,243,255,0.12), transparent 60%),
    #05060a;
}
body.lx-active .section-header,
body.lx-active .get-started {
  backdrop-filter: blur(10px);
}
body.lx-active .get-started-step {
  border-radius: 12px;
  border: 1px solid rgba(0,243,255,0.18);
  padding: 12px;
}
body.lx-active .sec-btn {
  background:
    radial-gradient(ellipse at var(--lx-lx) var(--lx-ly), rgba(0,243,255,0.12), transparent 70%),
    rgba(5,5,10,0.65);
  border-color: rgba(0,243,255,0.32);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
}
body.lx-active .sec-btn.active {
  box-shadow: 0 0 16px rgba(0,243,255,0.35), inset 0 1px 0 rgba(255,255,255,0.2);
}

body.lx-active .tool-card.lx-pop { animation: lxPop 0.55s cubic-bezier(.2,1.2,.3,1) both; }
body.lx-active .tool-card.lx-spin { animation: lxSpin 0.65s cubic-bezier(.2,.8,.2,1) both; }
body.lx-active .tool-card.lx-flash { animation: lxFlash 0.5s ease both; }
body.lx-active .tool-card.lx-glitch { animation: lxGlitch 0.45s steps(2) both; }
body.lx-active .tool-card.lx-rise { animation: lxRise 0.55s cubic-bezier(.2,.9,.2,1) both; }
@keyframes lxPop {
  0% { transform: scale(1); filter: brightness(1); }
  40% { transform: scale(1.08) rotate(-1deg); filter: brightness(1.25); box-shadow: 0 0 40px rgba(0,243,255,0.5); }
  100% { transform: scale(1); filter: brightness(1); }
}
@keyframes lxSpin {
  0% { transform: scale(1) rotate(0); }
  50% { transform: scale(1.06) rotate(3deg); filter: hue-rotate(40deg); }
  100% { transform: scale(1) rotate(0); }
}
@keyframes lxFlash {
  0%, 100% { filter: brightness(1); }
  30% { filter: brightness(1.5) saturate(1.4); box-shadow: 0 0 48px rgba(124,92,255,0.55); }
  60% { filter: brightness(1.15); }
}
@keyframes lxGlitch {
  0% { transform: translate(0); filter: none; }
  25% { transform: translate(-4px, 1px); filter: hue-rotate(90deg); }
  50% { transform: translate(4px, -1px); filter: hue-rotate(-60deg); }
  75% { transform: translate(-2px, 0); }
  100% { transform: translate(0); filter: none; }
}
@keyframes lxRise {
  0% { transform: translateY(0) scale(1); opacity: 1; }
  45% { transform: translateY(-14px) scale(1.05); box-shadow: 0 16px 40px rgba(0,255,136,0.25); }
  100% { transform: translateY(0) scale(1); }
}

.lx-burst {
  position: fixed; inset: 0; z-index: 50; pointer-events: none;
  opacity: 0;
  background: radial-gradient(circle at var(--bx,50%) var(--by,50%), rgba(0,243,255,0.22), transparent 45%);
  transition: opacity 0.15s;
}
.lx-burst.on { opacity: 1; animation: lxBurstFade 0.7s ease forwards; }
@keyframes lxBurstFade {
  0% { opacity: 1; }
  100% { opacity: 0; }
}

#lxToggle {
  position: fixed; bottom: 14px; right: 14px; z-index: 60;
  pointer-events: auto;
  font-size: 10px; font-weight: 700; letter-spacing: 0.06em;
  padding: 7px 11px; border-radius: 999px; cursor: pointer;
  border: 1px solid rgba(0,243,255,0.35);
  background: rgba(8,8,14,0.85); color: #88c;
  backdrop-filter: blur(8px);
  transition: 0.2s;
}
#lxToggle:hover { color: #00f3ff; border-color: #00f3ff; box-shadow: 0 0 12px rgba(0,243,255,0.3); }
#lxToggle.on { color: #00ff88; border-color: rgba(0,255,136,0.45); }

@media (prefers-reduced-motion: reduce) {
  .lx-wash, .lx-grid, .lx-scan { animation: none !important; }
  #lxCanvas { opacity: 0.15; }
  body.lx-active .tool-card:hover, body.lx-active .hub-card:hover { transform: none; }
  .lx-marquee-stage { height: min(22vh, 180px); }
}
@media (max-width: 700px) {
  .lx-marquee-stage { height: min(32vh, 260px); }
  .lx-m-far { display: none; }
}
`;
        document.head.appendChild(style);
    }

    function ensureAudio() {
        if (!prefs.sounds) return null;
        if (!audioCtx) {
            try {
                audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            } catch (_) {
                return null;
            }
        }
        if (audioCtx.state === 'suspended') audioCtx.resume().catch(() => {});
        return audioCtx;
    }

    function tone(freq, dur, type, gain, when) {
        const ac = ensureAudio();
        if (!ac) return;
        const t0 = (when != null ? when : ac.currentTime);
        const o = ac.createOscillator();
        const g = ac.createGain();
        o.type = type || 'sine';
        o.frequency.setValueAtTime(freq, t0);
        g.gain.setValueAtTime(0.0001, t0);
        g.gain.exponentialRampToValueAtTime(gain || 0.04, t0 + 0.015);
        g.gain.exponentialRampToValueAtTime(0.0001, t0 + (dur || 0.12));
        o.connect(g);
        g.connect(ac.destination);
        o.start(t0);
        o.stop(t0 + (dur || 0.12) + 0.02);
    }

    function playHoverSound() {
        if (!prefs.sounds || !prefs.enabled) return;
        const now = performance.now();
        if (now - lastSoundAt < 45) return;
        lastSoundAt = now;
        const f = 420 + Math.random() * 280;
        tone(f, 0.06, 'triangle', 0.018);
    }

    function playClickSound() {
        if (!prefs.sounds || !prefs.enabled) return;
        const ac = ensureAudio();
        if (!ac) return;
        const t0 = ac.currentTime;
        // soft arpeggio
        tone(523.25, 0.09, 'sine', 0.05, t0);
        tone(659.25, 0.1, 'sine', 0.04, t0 + 0.05);
        tone(783.99, 0.14, 'triangle', 0.035, t0 + 0.1);
    }

    function playWhoosh() {
        if (!prefs.sounds || !prefs.enabled) return;
        const ac = ensureAudio();
        if (!ac) return;
        const t0 = ac.currentTime;
        const o = ac.createOscillator();
        const g = ac.createGain();
        const f = ac.createBiquadFilter();
        o.type = 'sawtooth';
        o.frequency.setValueAtTime(180, t0);
        o.frequency.exponentialRampToValueAtTime(40, t0 + 0.28);
        f.type = 'lowpass';
        f.frequency.setValueAtTime(1200, t0);
        f.frequency.exponentialRampToValueAtTime(200, t0 + 0.28);
        g.gain.setValueAtTime(0.0001, t0);
        g.gain.exponentialRampToValueAtTime(0.03, t0 + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.3);
        o.connect(f); f.connect(g); g.connect(ac.destination);
        o.start(t0); o.stop(t0 + 0.32);
    }

    function buildDom() {
        if (root) return;
        root = document.createElement('div');
        root.id = 'lxRoot';
        root.setAttribute('aria-hidden', 'true');
        root.innerHTML = `
          <div class="lx-wash"></div>
          <div class="lx-tess-field"></div>
          <div class="lx-grid"></div>
          <div class="lx-scan"></div>
          <canvas id="lxCanvas"></canvas>
          <div class="lx-cursor" id="lxCursor"></div>
          <div class="lx-marquee-stage" id="lxMarqueeStage">
            <div class="lx-marquee lx-m-far" id="lxMarqueeFar">
              <div class="lx-marquee-track" data-layer="far"></div>
            </div>
            <div class="lx-marquee lx-m-mid" id="lxMarqueeMid">
              <div class="lx-marquee-track" data-layer="mid"></div>
            </div>
            <div class="lx-marquee lx-m-near" id="lxMarqueeNear">
              <div class="lx-marquee-track" data-layer="near"></div>
            </div>
            <div class="lx-empty-hint" id="lxEmptyHint" style="display:none">
              🎬 Intros → pick BG folders for the depth marquee
            </div>
          </div>
          <div class="lx-burst" id="lxBurst"></div>
        `;
        document.body.prepend(root);
        document.body.classList.add('lx-active');

        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.id = 'lxToggle';
        toggle.title = 'Toggle ambient FX / depth marquee / soft sounds (anti burn-in)';
        toggle.textContent = '✦ FX';
        toggle.classList.toggle('on', prefs.enabled);
        toggle.addEventListener('click', () => {
            savePrefs({ enabled: !prefs.enabled });
            toggle.classList.toggle('on', prefs.enabled);
            try {
                if (global.AIToolboxUI?.toast) {
                    AIToolboxUI.toast(prefs.enabled ? 'Launcher FX on' : 'Launcher FX off', 'ok');
                }
            } catch (_) { /* ignore */ }
        });
        toggle.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            savePrefs({ sounds: !prefs.sounds });
            try {
                if (global.AIToolboxUI?.toast) {
                    AIToolboxUI.toast(prefs.sounds ? 'Soft sounds on' : 'Sounds muted', 'ok');
                }
            } catch (_) { /* ignore */ }
        });
        document.body.appendChild(toggle);

        canvas = document.getElementById('lxCanvas');
        ctx = canvas.getContext('2d');
        marqueeStage = document.getElementById('lxMarqueeStage');
        marqueeTracks.far = root.querySelector('.lx-marquee-track[data-layer="far"]');
        marqueeTracks.mid = root.querySelector('.lx-marquee-track[data-layer="mid"]');
        marqueeTracks.near = root.querySelector('.lx-marquee-track[data-layer="near"]');
        // Hover near layer pauses scroll-linked drift slightly
        marqueeStage?.addEventListener('pointerenter', () => { marqueePaused = true; });
        marqueeStage?.addEventListener('pointerleave', () => { marqueePaused = false; });
        // Stage is pointer-events none; allow pause when hovering bottom of viewport via body
        resizeCanvas();
        seedTracers();
    }

    function applyEnabled() {
        document.body.classList.toggle('lx-off', !prefs.enabled);
        document.getElementById('lxToggle')?.classList.toggle('on', prefs.enabled);
        if (marqueeStage) {
            marqueeStage.style.display = prefs.marquee && prefs.enabled ? '' : 'none';
        }
    }

    function updateScrollLighting() {
        const maxScroll = Math.max(1, (document.documentElement.scrollHeight || 1) - window.innerHeight);
        const p = Math.min(1, Math.max(0, window.scrollY / maxScroll));
        scrollProgress = p;
        // Light source drifts as you scroll — tessellation “faces” catch light
        const lx = 22 + p * 48 + Math.sin(p * Math.PI * 2) * 8;
        const ly = 14 + p * 42 + Math.cos(p * Math.PI) * 10;
        const rootEl = document.documentElement;
        rootEl.style.setProperty('--lx-scroll', p.toFixed(4));
        rootEl.style.setProperty('--lx-lx', lx.toFixed(1) + '%');
        rootEl.style.setProperty('--lx-ly', ly.toFixed(1) + '%');
        rootEl.style.setProperty('--lx-lz', (0.35 + p * 0.55).toFixed(3));
        rootEl.style.setProperty('--lx-tess', (1 - p * 0.15).toFixed(3));
    }

    function stepMarquee(now) {
        if (!prefs.enabled || !prefs.marquee || reducedMotion) return;
        if (!marqueeLastTs) marqueeLastTs = now;
        let dt = now - marqueeLastTs;
        marqueeLastTs = now;
        if (dt > 64) dt = 64;
        if (marqueePaused) dt *= 0.15;

        // Depth: as you scroll down, ribbon slows (recedes) and softens
        const p = scrollProgress;
        const intensity = prefs.intensity || 1;
        // px/ms at top → slower at bottom
        const nearSpeed = (0.042 - p * 0.028) * intensity;
        const midSpeed = nearSpeed * 0.58;
        const farSpeed = nearSpeed * 0.32;

        marqueeOffsets.near += nearSpeed * dt;
        marqueeOffsets.mid += midSpeed * dt;
        marqueeOffsets.far += farSpeed * dt;

        for (const layer of ['far', 'mid', 'near']) {
            const track = marqueeTracks[layer];
            if (!track) continue;
            const half = track.scrollWidth / 2;
            if (half > 8) {
                while (marqueeOffsets[layer] >= half) marqueeOffsets[layer] -= half;
            }
            track.style.transform = `translate3d(${-marqueeOffsets[layer]}px, 0, 0)`;
        }

        // Layer opacity / blur shift with scroll (extra depth)
        const far = document.getElementById('lxMarqueeFar');
        const mid = document.getElementById('lxMarqueeMid');
        const near = document.getElementById('lxMarqueeNear');
        if (far) far.style.opacity = String(0.22 + p * 0.12);
        if (mid) mid.style.opacity = String(0.36 + p * 0.08);
        if (near) near.style.opacity = String(0.62 - p * 0.18);
    }

    function resizeCanvas() {
        if (!canvas) return;
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        canvas.width = Math.floor(window.innerWidth * dpr);
        canvas.height = Math.floor(window.innerHeight * dpr);
        canvas.style.width = window.innerWidth + 'px';
        canvas.style.height = window.innerHeight + 'px';
        if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function seedTracers() {
        tracers = [];
        const n = reducedMotion ? 3 : 7;
        for (let i = 0; i < n; i++) {
            tracers.push({
                x: Math.random(),
                y: Math.random(),
                vx: (Math.random() - 0.5) * 0.00035,
                vy: (Math.random() - 0.5) * 0.00035,
                life: 0.3 + Math.random() * 0.7,
                hue: Math.random() * 360,
                path: []
            });
        }
    }

    function tick(now) {
        rafId = requestAnimationFrame(tick);
        stepMarquee(now);
        if (!prefs.enabled || !ctx || !canvas) return;
        const w = window.innerWidth;
        const h = window.innerHeight;
        ctx.clearRect(0, 0, w, h);

        // Soft mouse light
        if (mouse.active) {
            const gx = mouse.x * w;
            const gy = mouse.y * h;
            const g = ctx.createRadialGradient(gx, gy, 0, gx, gy, 180);
            g.addColorStop(0, 'rgba(0,243,255,0.12)');
            g.addColorStop(0.4, 'rgba(124,92,255,0.06)');
            g.addColorStop(1, 'transparent');
            ctx.fillStyle = g;
            ctx.fillRect(0, 0, w, h);
        }

        // Pattern tracers (anti burn-in)
        const t = now * 0.001;
        for (const tr of tracers) {
            tr.x += tr.vx + Math.sin(t * 0.4 + tr.hue) * 0.00008;
            tr.y += tr.vy + Math.cos(t * 0.35 + tr.life) * 0.00008;
            if (tr.x < 0 || tr.x > 1) tr.vx *= -1;
            if (tr.y < 0 || tr.y > 1) tr.vy *= -1;
            tr.x = Math.max(0, Math.min(1, tr.x));
            tr.y = Math.max(0, Math.min(1, tr.y));
            tr.path.push({ x: tr.x, y: tr.y });
            if (tr.path.length > 28) tr.path.shift();

            // attract slightly toward mouse
            if (mouse.active) {
                tr.vx += (mouse.x - tr.x) * 0.00002;
                tr.vy += (mouse.y - tr.y) * 0.00002;
            }

            ctx.beginPath();
            for (let i = 0; i < tr.path.length; i++) {
                const p = tr.path[i];
                const px = p.x * w;
                const py = p.y * h;
                if (i === 0) ctx.moveTo(px, py);
                else ctx.lineTo(px, py);
            }
            const alpha = 0.15 + 0.2 * Math.sin(t + tr.hue);
            ctx.strokeStyle = `hsla(${(tr.hue + t * 20) % 360}, 90%, 65%, ${alpha})`;
            ctx.lineWidth = 1.2;
            ctx.stroke();

            ctx.beginPath();
            ctx.arc(tr.x * w, tr.y * h, 2.2, 0, Math.PI * 2);
            ctx.fillStyle = `hsla(${(tr.hue + t * 20) % 360}, 100%, 70%, 0.55)`;
            ctx.fill();
        }

        // Sparks from mouse / clicks
        for (let i = sparks.length - 1; i >= 0; i--) {
            const s = sparks[i];
            s.x += s.vx;
            s.y += s.vy;
            s.vy += 0.04;
            s.life -= 0.02;
            if (s.life <= 0) {
                sparks.splice(i, 1);
                continue;
            }
            ctx.beginPath();
            ctx.arc(s.x, s.y, s.r * s.life, 0, Math.PI * 2);
            ctx.fillStyle = `hsla(${s.hue}, 95%, 65%, ${s.life})`;
            ctx.fill();
        }

        // Slow drifting rings (idle pixel refresh)
        for (let i = 0; i < 3; i++) {
            const cx = w * (0.2 + 0.3 * i + 0.05 * Math.sin(t * 0.15 + i));
            const cy = h * (0.35 + 0.15 * Math.cos(t * 0.12 + i * 1.3));
            const r = 40 + 30 * Math.sin(t * 0.2 + i) + i * 20;
            ctx.beginPath();
            ctx.arc(cx, cy, r, 0, Math.PI * 2);
            ctx.strokeStyle = `rgba(${i === 1 ? '124,92,255' : '0,243,255'}, ${0.04 + 0.03 * Math.sin(t + i)})`;
            ctx.lineWidth = 1;
            ctx.stroke();
        }
    }

    function spawnSparks(x, y, n, hueBase) {
        const count = n || 10;
        for (let i = 0; i < count; i++) {
            const a = Math.random() * Math.PI * 2;
            const sp = 1 + Math.random() * 4;
            sparks.push({
                x, y,
                vx: Math.cos(a) * sp,
                vy: Math.sin(a) * sp - 1,
                r: 1.5 + Math.random() * 2.5,
                life: 0.7 + Math.random() * 0.4,
                hue: (hueBase != null ? hueBase : 180) + Math.random() * 60
            });
        }
    }

    function fillTrack(track, factory, count, dup) {
        if (!track) return;
        track.innerHTML = '';
        const n = Math.max(count, 4);
        for (let i = 0; i < n; i++) track.appendChild(factory(i));
        if (dup) {
            const clone = track.cloneNode(true);
            while (clone.firstChild) track.appendChild(clone.firstChild);
        }
    }

    async function loadMarquee() {
        if (!prefs.marquee) return;
        if (!marqueeTracks.near) return;

        clipUrls.forEach((u) => {
            try { URL.revokeObjectURL(u); } catch (_) { /* ignore */ }
        });
        clipUrls = [];
        marqueeOffsets = { far: 0, mid: 0, near: 0 };

        let clips = [];
        try {
            if (global.AIToolboxCinematic?.getMarqueeClips) {
                clips = await AIToolboxCinematic.getMarqueeClips();
            }
        } catch (e) {
            console.warn('[LauncherFX] marquee clips', e);
        }

        const hint = document.getElementById('lxEmptyHint');
        const synthBg = [
            'linear-gradient(135deg,#0a1a22,#1a0a28)',
            'linear-gradient(135deg,#120a20,#0a1820)',
            'linear-gradient(135deg,#0a2018,#1a1028)',
            'linear-gradient(135deg,#181028,#0a1420)',
            'linear-gradient(135deg,#0c1824,#20102a)'
        ];

        const makeSynth = (i) => {
            const tile = document.createElement('div');
            tile.className = 'lx-tile';
            tile.style.background = synthBg[i % synthBg.length];
            return tile;
        };

        const makeVideoTile = (clip) => {
            const tile = document.createElement('div');
            tile.className = 'lx-tile';
            if (!clip) return makeSynth(0);
            const v = document.createElement('video');
            v.muted = true;
            v.defaultMuted = true;
            v.loop = true;
            v.playsInline = true;
            v.setAttribute('playsinline', '');
            v.setAttribute('muted', '');
            v.preload = 'metadata';
            v.src = clip.url;
            if (clip.revoke) clipUrls.push(clip.revoke);
            v.addEventListener('loadeddata', () => { v.play().catch(() => {}); });
            tile.appendChild(v);
            tile.title = clip.label || '';
            return tile;
        };

        if (!clips.length) {
            if (hint) hint.style.display = '';
            fillTrack(marqueeTracks.far, makeSynth, 6, true);
            fillTrack(marqueeTracks.mid, makeSynth, 6, true);
            fillTrack(marqueeTracks.near, makeSynth, 6, true);
            return;
        }
        if (hint) hint.style.display = 'none';

        // Far: fewer/lighter (still videos when available)
        const farClips = clips.length > 2 ? clips.filter((_, i) => i % 2 === 0) : clips;
        fillTrack(marqueeTracks.far, (i) => makeVideoTile(farClips[i % farClips.length]), Math.max(farClips.length, 4), true);
        fillTrack(marqueeTracks.mid, (i) => makeVideoTile(clips[i % clips.length]), Math.max(clips.length, 4), true);
        fillTrack(marqueeTracks.near, (i) => makeVideoTile(clips[i % clips.length]), Math.max(clips.length, 5), true);

        const playAll = () => {
            root?.querySelectorAll('.lx-marquee-track video').forEach((v) => {
                v.muted = true;
                v.play().catch(() => {});
            });
        };
        document.addEventListener('pointerdown', playAll, { once: true });
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) playAll();
        });
        setTimeout(playAll, 400);
    }

    const SELECT_ANIMS = ['lx-pop', 'lx-spin', 'lx-flash', 'lx-glitch', 'lx-rise'];

    function animateToolSelect(cardEl, clientX, clientY) {
        if (!prefs.enabled || !cardEl) return;
        playClickSound();
        playWhoosh();

        const anim = SELECT_ANIMS[Math.floor(Math.random() * SELECT_ANIMS.length)];
        cardEl.classList.remove(...SELECT_ANIMS);
        void cardEl.offsetWidth;
        cardEl.classList.add(anim);
        setTimeout(() => cardEl.classList.remove(anim), 700);

        const burst = document.getElementById('lxBurst');
        if (burst) {
            const x = clientX != null ? clientX : window.innerWidth / 2;
            const y = clientY != null ? clientY : window.innerHeight / 2;
            burst.style.setProperty('--bx', x + 'px');
            burst.style.setProperty('--by', y + 'px');
            burst.classList.remove('on');
            void burst.offsetWidth;
            burst.classList.add('on');
            setTimeout(() => burst.classList.remove('on'), 700);
            spawnSparks(x, y, 18, Math.random() > 0.5 ? 180 : 280);
        }

        // Brief body flash class
        document.body.classList.add('lx-select-flash');
        setTimeout(() => document.body.classList.remove('lx-select-flash'), 400);
    }

    function wireInteractions() {
        const cursor = document.getElementById('lxCursor');

        window.addEventListener('pointermove', (e) => {
            mouse.px = mouse.x;
            mouse.py = mouse.y;
            mouse.x = e.clientX / window.innerWidth;
            mouse.y = e.clientY / window.innerHeight;
            mouse.active = true;
            if (cursor) {
                cursor.style.transform = `translate(${e.clientX}px, ${e.clientY}px)`;
            }
            // Light follows mouse a bit on top of scroll-driven lamp
            if (prefs.enabled) {
                const mx = 15 + mouse.x * 70;
                const my = 10 + mouse.y * 55;
                // blend mouse into scroll lamp (gentle)
                const p = scrollProgress;
                const lx = mx * 0.35 + (22 + p * 48) * 0.65;
                const ly = my * 0.35 + (14 + p * 42) * 0.65;
                document.documentElement.style.setProperty('--lx-lx', lx.toFixed(1) + '%');
                document.documentElement.style.setProperty('--lx-ly', ly.toFixed(1) + '%');
            }
            // Pause near marquee when pointer is in bottom cinema band
            marqueePaused = prefs.enabled && mouse.y > 0.72;
            if (prefs.enabled && Math.random() < 0.1) {
                spawnSparks(e.clientX, e.clientY, 2, 190);
            }
        }, { passive: true });

        window.addEventListener('pointerleave', () => {
            mouse.active = false;
            marqueePaused = false;
        });
        window.addEventListener('resize', () => {
            resizeCanvas();
            updateScrollLighting();
        });

        let scrollRaf = 0;
        window.addEventListener('scroll', () => {
            if (scrollRaf) return;
            scrollRaf = requestAnimationFrame(() => {
                scrollRaf = 0;
                updateScrollLighting();
            });
        }, { passive: true });
        updateScrollLighting();

        document.addEventListener('pointerover', (e) => {
            const card = e.target.closest?.('.tool-card, .hub-card, .sec-btn, .ui-btn, .btn');
            if (!card || !prefs.enabled) return;
            playHoverSound();
            if (card.classList.contains('tool-card') || card.classList.contains('hub-card')) {
                spawnSparks(
                    e.clientX || window.innerWidth / 2,
                    e.clientY || window.innerHeight / 2,
                    4,
                    200
                );
            }
        }, true);

        document.addEventListener('pointerdown', (e) => {
            if (!prefs.enabled) return;
            if (e.target.closest?.('#lxToggle')) return;
            ensureAudio();
            if (!e.target.closest?.('.tool-card')) {
                tone(220 + Math.random() * 80, 0.05, 'sine', 0.012);
                spawnSparks(e.clientX, e.clientY, 5, 160);
            }
        }, true);
    }

    /**
     * Call before navigating to a tool — plays random select animation + sound.
     * Returns a short Promise delay so the animation is visible.
     */
    function onToolSelect(cardEl, event) {
        const x = event?.clientX;
        const y = event?.clientY;
        animateToolSelect(cardEl, x, y);
        return new Promise((r) => setTimeout(r, prefs.enabled ? 280 : 0));
    }

    async function start() {
        if (started) return;
        started = true;
        reducedMotion = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
        if (reducedMotion) {
            prefs = { ...prefs, marquee: false };
        }
        injectStyles();
        buildDom();
        applyEnabled();
        wireInteractions();
        requestAnimationFrame(tick);
        await loadMarquee();
    }

    function refreshMarquee() {
        return loadMarquee();
    }

    global.AIToolboxLauncherFX = {
        start,
        onToolSelect,
        refreshMarquee,
        getPrefs: () => ({ ...prefs }),
        setPrefs: savePrefs,
        playHoverSound,
        playClickSound
    };
})(typeof window !== 'undefined' ? window : globalThis);
