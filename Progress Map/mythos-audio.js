/**
 * Quiet original chiptune-style cues for Mythos (not Nintendo IP).
 * Soft volume by default — atmosphere, not arcade blasts.
 * Background ambient slowly builds as unlock progress approaches 1.
 */
(function (global) {
  'use strict';

  let ctx = null;
  let master = null;
  let enabled = true;
  let volume = 0.12; // quiet master for one-shot cues

  /** Ambient layer (separate quieter bus) */
  let ambBus = null;
  let ambRunning = false;
  let ambTimer = null;
  let ambRaf = null;
  let ambIntensity = 0; // smoothed 0..1
  let ambTarget = 0; // desired 0..1 from path progress
  let ambDrones = []; // { osc, g, basePeak }
  let lastPulseAt = 0;

  function ensure() {
    if (!enabled) return null;
    try {
      const AC = global.AudioContext || global.webkitAudioContext;
      if (!AC) return null;
      if (!ctx) {
        ctx = new AC();
        master = ctx.createGain();
        master.gain.value = volume;
        master.connect(ctx.destination);

        ambBus = ctx.createGain();
        ambBus.gain.value = 0.0001;
        ambBus.connect(ctx.destination);
      }
      if (ctx.state === 'suspended') ctx.resume();
      return ctx;
    } catch (_) {
      return null;
    }
  }

  function setEnabled(on) {
    enabled = !!on;
    if (!enabled) stopChamberAmbience();
  }

  function setVolume(v) {
    volume = Math.max(0, Math.min(0.4, Number(v) || 0));
    if (master) master.gain.value = volume;
  }

  function envGain(g, t0, attack, peak, hold, release) {
    const g_ = g.gain;
    g_.cancelScheduledValues(t0);
    g_.setValueAtTime(0.0001, t0);
    g_.exponentialRampToValueAtTime(Math.max(0.0002, peak), t0 + attack);
    g_.exponentialRampToValueAtTime(Math.max(0.0002, peak * 0.7), t0 + attack + hold);
    g_.exponentialRampToValueAtTime(0.0001, t0 + attack + hold + release);
  }

  /** Soft square/triangle blip */
  function tone({ freq = 440, dur = 0.08, type = 'square', peak = 0.15, detune = 0, dest }) {
    const c = ensure();
    if (!c || !master) return;
    const t0 = c.currentTime;
    const osc = c.createOscillator();
    const g = c.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, t0);
    if (detune) osc.detune.setValueAtTime(detune, t0);
    envGain(g, t0, 0.008, peak, dur * 0.35, dur * 0.55);
    osc.connect(g);
    g.connect(dest || master);
    osc.start(t0);
    osc.stop(t0 + dur + 0.05);
  }

  function chord(freqs, opts) {
    freqs.forEach((f, i) => {
      setTimeout(() => tone({ ...opts, freq: f }), i * (opts.stagger || 0));
    });
  }

  /** Quiet “tick” — neutral click */
  function tick() {
    tone({ freq: 880, dur: 0.04, type: 'triangle', peak: 0.06 });
  }

  /** Soft confirm — right-ish step */
  function softOk() {
    tone({ freq: 523.25, dur: 0.07, type: 'triangle', peak: 0.09 });
    setTimeout(() => tone({ freq: 659.25, dur: 0.09, type: 'triangle', peak: 0.08 }), 55);
  }

  /** Subtle wrong / nothing */
  function softNo() {
    tone({ freq: 196, dur: 0.1, type: 'triangle', peak: 0.07 });
    setTimeout(() => tone({ freq: 165, dur: 0.12, type: 'sine', peak: 0.05 }), 40);
  }

  /** Rune rotate — tiny glass click */
  function runeRotate() {
    tone({ freq: 1200, dur: 0.035, type: 'square', peak: 0.045 });
    tone({ freq: 1800, dur: 0.025, type: 'triangle', peak: 0.03 });
  }

  /** Rune moves */
  function runeMove() {
    tone({ freq: 400, dur: 0.05, type: 'triangle', peak: 0.06 });
    setTimeout(() => tone({ freq: 600, dur: 0.06, type: 'triangle', peak: 0.05 }), 45);
  }

  /** Bookshelf appears */
  function shelfReveal() {
    chord([261.63, 329.63, 392], { type: 'triangle', peak: 0.07, dur: 0.12, stagger: 40 });
  }

  /** Candle tilt */
  function candle() {
    tone({ freq: 300, dur: 0.08, type: 'sine', peak: 0.05 });
    setTimeout(() => tone({ freq: 450, dur: 0.06, type: 'triangle', peak: 0.04 }), 30);
  }

  /** Green book */
  function bookOpen() {
    chord([349.23, 440, 523.25], { type: 'triangle', peak: 0.08, dur: 0.14, stagger: 50 });
  }

  /** Garden open */
  function garden() {
    chord([392, 493.88, 587.33, 784], { type: 'triangle', peak: 0.07, dur: 0.15, stagger: 60 });
  }

  /** Tree accept */
  function treeOk() {
    chord([523.25, 659.25, 783.99], { type: 'square', peak: 0.06, dur: 0.1, stagger: 45 });
  }

  /** Seal / chamber unlock — short original 8-bit “secret found” style sting (not Zelda IP) */
  function chamberUnlock() {
    const c = ensure();
    if (!c || !master) return;
    const notes = [523.25, 659.25, 783.99, 1046.5, 783.99, 1046.5, 1318.5];
    notes.forEach((f, i) => {
      setTimeout(() => {
        tone({ freq: f, dur: 0.11, type: i % 2 ? 'triangle' : 'square', peak: 0.07 });
      }, i * 70);
    });
    setTimeout(() => {
      const t0 = c.currentTime;
      const osc = c.createOscillator();
      const g = c.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(1046.5, t0);
      g.gain.setValueAtTime(0.0001, t0);
      g.gain.exponentialRampToValueAtTime(0.04, t0 + 0.05);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + 1.2);
      osc.connect(g);
      g.connect(master);
      osc.start(t0);
      osc.stop(t0 + 1.25);
    }, notes.length * 70);
  }

  /** Dragon wake — short growl-ish low buzz */
  function dragon() {
    const c = ensure();
    if (!c || !master) return;
    const t0 = c.currentTime;
    const osc = c.createOscillator();
    const g = c.createGain();
    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(80, t0);
    osc.frequency.exponentialRampToValueAtTime(45, t0 + 0.35);
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(0.08, t0 + 0.04);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.4);
    osc.connect(g);
    g.connect(master);
    osc.start(t0);
    osc.stop(t0 + 0.45);
  }

  /* ── Progress-linked ambient ───────────────────────────────────────────
   * Low drone + soft pulse layers. Intensity 0..1 from path steps complete.
   * Quiet at start; denser / slightly louder as the secret chamber nears.
   */

  function createDrones() {
    const c = ensure();
    if (!c || !ambBus || ambDrones.length) return;

    // Three stacked partials — very soft sine/triangle “cave air”
    const specs = [
      { freq: 55, type: 'sine', peak: 0.035 },
      { freq: 82.5, type: 'sine', peak: 0.022 },
      { freq: 110, type: 'triangle', peak: 0.012 },
    ];
    ambDrones = specs.map((s) => {
      const osc = c.createOscillator();
      const g = c.createGain();
      osc.type = s.type;
      osc.frequency.value = s.freq;
      g.gain.value = 0.0001;
      osc.connect(g);
      g.connect(ambBus);
      osc.start();
      return { osc, g, basePeak: s.peak, baseFreq: s.freq };
    });
  }

  function disposeDrones() {
    ambDrones.forEach((d) => {
      try {
        d.osc.stop();
        d.osc.disconnect();
        d.g.disconnect();
      } catch (_) { /* ignore */ }
    });
    ambDrones = [];
  }

  /** Soft harmonic shimmer pulse — denser as intensity rises */
  function ambientPulse(intensity) {
    const c = ensure();
    if (!c || !ambBus || intensity < 0.04) return;

    // Root + fifth + octave fragments, peak scaled by intensity
    const base = 130.81 + intensity * 40; // slightly brighter near unlock
    const peak = 0.008 + intensity * 0.028;
    const dur = 0.35 + intensity * 0.25;

    tone({ freq: base, dur, type: 'sine', peak, dest: ambBus });
    if (intensity > 0.25) {
      setTimeout(() => {
        tone({ freq: base * 1.5, dur: dur * 0.85, type: 'triangle', peak: peak * 0.65, dest: ambBus });
      }, 180);
    }
    if (intensity > 0.55) {
      setTimeout(() => {
        tone({ freq: base * 2, dur: 0.2, type: 'triangle', peak: peak * 0.45, dest: ambBus });
      }, 320);
    }
    // Near unlock: soft high “edge of discovery” sparkle
    if (intensity > 0.8) {
      setTimeout(() => {
        tone({ freq: 1046.5, dur: 0.12, type: 'triangle', peak: 0.012 + (intensity - 0.8) * 0.04, dest: ambBus });
      }, 90);
    }
  }

  function scheduleNextPulse() {
    if (!ambRunning || !enabled) return;
    // Interval shortens as intensity rises: ~3.2s → ~1.1s
    const ms = Math.round(3200 - ambIntensity * 2100);
    ambTimer = setTimeout(() => {
      if (!ambRunning) return;
      ambientPulse(ambIntensity);
      lastPulseAt = Date.now();
      scheduleNextPulse();
    }, Math.max(900, ms));
  }

  function ambTick() {
    if (!ambRunning || !enabled) {
      ambRaf = null;
      return;
    }
    const c = ensure();
    if (!c || !ambBus) {
      ambRaf = null;
      return;
    }

    // Smooth toward target (slow build / gentle fade)
    const delta = ambTarget - ambIntensity;
    const rate = delta > 0 ? 0.018 : 0.03; // build slower than decay
    ambIntensity += delta * rate;
    if (Math.abs(delta) < 0.002) ambIntensity = ambTarget;

    // Master amb bus: nearly silent at 0 → still quiet at 1 (~0.09)
    const busPeak = 0.0001 + ambIntensity * 0.09;
    const now = c.currentTime;
    ambBus.gain.cancelScheduledValues(now);
    ambBus.gain.setTargetAtTime(busPeak, now, 0.35);

    // Drones swell with intensity
    ambDrones.forEach((d, i) => {
      const peak = d.basePeak * (0.15 + ambIntensity * 0.85);
      d.g.gain.setTargetAtTime(Math.max(0.0001, peak), now, 0.4);
      // Slight detune shimmer near the end
      if (ambIntensity > 0.6) {
        const wobble = 1 + Math.sin(now * (0.4 + i * 0.15)) * 0.004 * ambIntensity;
        d.osc.frequency.setTargetAtTime(d.baseFreq * wobble, now, 0.2);
      }
    });

    ambRaf = (global.requestAnimationFrame || ((fn) => setTimeout(fn, 50)))(ambTick);
  }

  /**
   * Set unlock progress 0..1 (from path steps completed).
   * Ambient auto-starts when progress > 0 and builds toward the chamber.
   */
  function setUnlockProgress(ratio) {
    const r = Math.max(0, Math.min(1, Number(ratio) || 0));
    // Ease so late steps feel more dramatic (slight ease-in)
    ambTarget = r * r * 0.35 + r * 0.65;
    if (r > 0 || ambIntensity > 0.01) {
      startChamberAmbience();
    }
    if (r >= 1) {
      // Peak briefly then settle after unlock sting
      ambTarget = 1;
    }
  }

  /** Derive progress from FAFOMythos pathProgressHint() or { steps, complete } */
  function syncFromHint(hint) {
    if (!hint || !hint.steps || !hint.steps.length) {
      setUnlockProgress(0);
      return 0;
    }
    const ok = hint.steps.filter((s) => s.ok).length;
    const ratio = hint.complete ? 1 : ok / hint.steps.length;
    setUnlockProgress(ratio);
    return ratio;
  }

  function startChamberAmbience() {
    if (!enabled) return;
    const c = ensure();
    if (!c || !ambBus) return;
    if (ambRunning) return;
    ambRunning = true;
    createDrones();
    // Immediate soft presence if any progress
    if (ambIntensity < 0.02 && ambTarget > 0) ambIntensity = Math.min(0.08, ambTarget * 0.5);
    if (!ambRaf) ambTick();
    if (!ambTimer) {
      ambientPulse(Math.max(ambIntensity, ambTarget * 0.4));
      scheduleNextPulse();
    }
  }

  function stopChamberAmbience() {
    ambRunning = false;
    ambTarget = 0;
    ambIntensity = 0;
    if (ambTimer) {
      clearTimeout(ambTimer);
      ambTimer = null;
    }
    if (ambRaf) {
      try {
        if (global.cancelAnimationFrame) global.cancelAnimationFrame(ambRaf);
      } catch (_) { /* ignore */ }
      ambRaf = null;
    }
    disposeDrones();
    if (ambBus && ctx) {
      try {
        ambBus.gain.cancelScheduledValues(ctx.currentTime);
        ambBus.gain.setTargetAtTime(0.0001, ctx.currentTime, 0.15);
      } catch (_) { /* ignore */ }
    }
  }

  /** Fade ambient after successful unlock (call after chamber sting) */
  function celebrateThenSettle() {
    setUnlockProgress(1);
    startChamberAmbience();
    setTimeout(() => {
      ambTarget = 0.35; // residual afterglow, not silent
    }, 1800);
  }

  function play(name) {
    const map = {
      tick,
      ok: softOk,
      no: softNo,
      runeRotate,
      runeMove,
      shelf: shelfReveal,
      candle,
      book: bookOpen,
      garden,
      tree: treeOk,
      chamber: chamberUnlock,
      dragon,
    };
    const fn = map[name];
    if (fn) {
      try {
        ensure();
        fn();
      } catch (_) { /* ignore */ }
    }
  }

  global.FAFOMythosAudio = {
    play,
    setEnabled,
    setVolume,
    setUnlockProgress,
    syncFromHint,
    startChamberAmbience,
    stopChamberAmbience,
    celebrateThenSettle,
    ensure,
    /** for debug / UI */
    getIntensity: () => ambIntensity,
  };
})(typeof window !== 'undefined' ? window : globalThis);
