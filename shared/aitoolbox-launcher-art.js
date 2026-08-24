/**
 * AI HTML Toolbox — Launcher card art
 * - Pattern packs for tiles/sections (scale + shift + rotate axes)
 * - Icon image cropper (square crop before save)
 *
 * Pattern geometry inspired by open free CSS/SVG tiling styles
 * (Hero Patterns / geometric packs) — generated locally as SVG data-URIs.
 * Color count is intentionally not capped — wild multi-stop palettes.
 */
(function (global) {
  'use strict';

  const PAT_LS = 'aitoolbox.launcher.patterns';

  function hashStr(s) {
    let h = 2166136261;
    const str = String(s || '');
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }

  function mulberry32(a) {
    return function () {
      let t = (a += 0x6d2b79f5);
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function hsl(h, s, l, a) {
    return `hsla(${((h % 360) + 360) % 360}, ${s}%, ${l}%, ${a == null ? 1 : a})`;
  }

  /** Wild multi-color palette (not limited to 3). */
  function wildPalette(seed, n) {
    const rnd = mulberry32(seed || 1);
    const count = Math.max(3, Math.min(12, n || 5 + Math.floor(rnd() * 6)));
    const base = rnd() * 360;
    const cols = [];
    for (let i = 0; i < count; i++) {
      const h = base + i * (360 / count) + (rnd() - 0.5) * 40;
      const s = 55 + rnd() * 45;
      const l = 42 + rnd() * 28;
      cols.push(hsl(h, s, l, 0.55 + rnd() * 0.4));
    }
    return cols;
  }

  function svgUri(svg) {
    return 'url("data:image/svg+xml,' + encodeURIComponent(svg.replace(/\s+/g, ' ').trim()) + '")';
  }

  /**
   * Pattern generators — each returns CSS background-image layers + motion vars.
   * Axes: scale (tile size), ox/oy (shift), rot (degrees).
   */
  const PACKS = [
    {
      id: 'prism-chevrons',
      name: 'Prism Chevrons',
      gen(seed, cols) {
        const c0 = cols[0], c1 = cols[1], c2 = cols[2] || cols[0];
        return {
          image: [
            `repeating-linear-gradient(45deg, transparent 0 12px, ${c0} 12px 14px)`,
            `repeating-linear-gradient(-45deg, transparent 0 12px, ${c1} 12px 14px)`,
            `radial-gradient(circle at 30% 40%, ${c2}, transparent 55%)`
          ].join(','),
          size: 'var(--pat-scale) var(--pat-scale), var(--pat-scale) var(--pat-scale), 140% 140%',
        };
      }
    },
    {
      id: 'hex-field',
      name: 'Hex Field',
      gen(seed, cols) {
        const c = cols;
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="56" height="100" viewBox="0 0 56 100">
          <g fill="none" stroke="${c[0]}" stroke-width="1.2" opacity="0.85">
            <path d="M28 2 L54 18 V50 L28 66 L2 50 V18 Z"/>
            <path d="M28 34 L54 50 V82 L28 98 L2 82 V50 Z"/>
          </g>
          <g fill="${c[1]}" opacity="0.35">
            <circle cx="28" cy="34" r="3"/>
            <circle cx="28" cy="66" r="2.2"/>
          </g>
          <path d="M2 18 L28 2 L54 18" stroke="${c[2] || c[0]}" stroke-width="1" fill="none" opacity="0.6"/>
        </svg>`;
        return {
          image: `${svgUri(svg)}, radial-gradient(ellipse at 70% 20%, ${c[3] || c[0]}, transparent 50%)`,
          size: 'var(--pat-scale) calc(var(--pat-scale) * 1.78), 160% 160%',
        };
      }
    },
    {
      id: 'circuit-lattice',
      name: 'Circuit Lattice',
      gen(seed, cols) {
        const c = cols;
        return {
          image: [
            `linear-gradient(${c[0]} 1px, transparent 1px)`,
            `linear-gradient(90deg, ${c[1]} 1px, transparent 1px)`,
            `radial-gradient(circle, ${c[2] || c[0]} 1.5px, transparent 2px)`,
            `linear-gradient(135deg, transparent 40%, ${c[3] || c[1]} 41%, transparent 42%)`
          ].join(','),
          size: 'var(--pat-scale) var(--pat-scale), var(--pat-scale) var(--pat-scale), calc(var(--pat-scale) * 0.45) calc(var(--pat-scale) * 0.45), calc(var(--pat-scale) * 2) calc(var(--pat-scale) * 2)',
        };
      }
    },
    {
      id: 'confetti-dots',
      name: 'Confetti Dots',
      gen(seed, cols) {
        const rnd = mulberry32(seed);
        const layers = cols.slice(0, 8).map((col, i) => {
          const x = 10 + ((i * 37 + rnd() * 20) % 80);
          const y = 12 + ((i * 53 + rnd() * 25) % 76);
          return `radial-gradient(circle at ${x}% ${y}%, ${col} 0 18%, transparent 19%)`;
        });
        return {
          image: layers.join(','),
          size: cols.map(() => 'var(--pat-scale) var(--pat-scale)').join(','),
        };
      }
    },
    {
      id: 'zebra-slash',
      name: 'Zebra Slash',
      gen(seed, cols) {
        const stops = cols.map((c, i) => `${c} ${i * 8}px, ${c} ${i * 8 + 4}px`).join(', ');
        return {
          image: `repeating-linear-gradient(var(--pat-rot, 28deg), ${stops}), radial-gradient(circle at 80% 80%, ${cols[cols.length - 1]}, transparent 45%)`,
          size: 'auto, 180% 180%',
        };
      }
    },
    {
      id: 'aurora-waves',
      name: 'Aurora Waves',
      gen(seed, cols) {
        const c = cols;
        return {
          image: [
            `repeating-radial-gradient(circle at 0 50%, transparent 0 14px, ${c[0]} 14px 16px)`,
            `repeating-radial-gradient(circle at 100% 50%, transparent 0 18px, ${c[1]} 18px 20px)`,
            `linear-gradient(120deg, ${c[2] || c[0]}, transparent 60%, ${c[3] || c[1]})`
          ].join(','),
          size: 'var(--pat-scale) var(--pat-scale), calc(var(--pat-scale) * 1.2) calc(var(--pat-scale) * 1.2), 200% 200%',
        };
      }
    },
    {
      id: 'diamond-ops',
      name: 'Diamond Ops',
      gen(seed, cols) {
        const c = cols;
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40">
          <path d="M20 2 L38 20 L20 38 L2 20 Z" fill="none" stroke="${c[0]}" stroke-width="1.4"/>
          <path d="M20 10 L30 20 L20 30 L10 20 Z" fill="${c[1]}" opacity="0.35"/>
          <circle cx="20" cy="20" r="2.5" fill="${c[2] || c[0]}"/>
        </svg>`;
        return {
          image: `${svgUri(svg)}, linear-gradient(160deg, ${c[3] || c[0]}, transparent 55%)`,
          size: 'var(--pat-scale) var(--pat-scale), 100% 100%',
        };
      }
    },
    {
      id: 'tri-tess',
      name: 'Tri Tessellation',
      gen(seed, cols) {
        const c = cols;
        return {
          image: [
            `repeating-linear-gradient(60deg, transparent 0 16px, ${c[0]} 16px 17px)`,
            `repeating-linear-gradient(-60deg, transparent 0 16px, ${c[1]} 16px 17px)`,
            `repeating-linear-gradient(0deg, transparent 0 22px, ${c[2] || c[0]} 22px 23px)`,
            `radial-gradient(circle at 50% 50%, ${c[3] || c[1]}, transparent 60%)`
          ].join(','),
          size: 'var(--pat-scale) var(--pat-scale), var(--pat-scale) var(--pat-scale), var(--pat-scale) var(--pat-scale), 160% 160%',
        };
      }
    },
    {
      id: 'neon-grid-plus',
      name: 'Neon Grid+',
      gen(seed, cols) {
        const c = cols;
        return {
          image: [
            `linear-gradient(${c[0]} 1px, transparent 1px)`,
            `linear-gradient(90deg, ${c[1]} 1px, transparent 1px)`,
            `linear-gradient(${c[2] || c[0]} 2px, transparent 2px)`,
            `linear-gradient(90deg, ${c[3] || c[1]} 2px, transparent 2px)`,
            `radial-gradient(circle at 50% 0%, ${c[4] || c[0]}, transparent 55%)`
          ].join(','),
          size: 'calc(var(--pat-scale) * 0.5) calc(var(--pat-scale) * 0.5), calc(var(--pat-scale) * 0.5) calc(var(--pat-scale) * 0.5), var(--pat-scale) var(--pat-scale), var(--pat-scale) var(--pat-scale), 140% 140%',
        };
      }
    },
    {
      id: 'plasma-ribbons',
      name: 'Plasma Ribbons',
      gen(seed, cols) {
        const c = cols;
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="80" height="40">
          <path d="M0 20 Q20 0 40 20 T80 20" fill="none" stroke="${c[0]}" stroke-width="2" opacity="0.8"/>
          <path d="M0 28 Q20 8 40 28 T80 28" fill="none" stroke="${c[1]}" stroke-width="1.5" opacity="0.7"/>
          <path d="M0 12 Q20 32 40 12 T80 12" fill="none" stroke="${c[2] || c[0]}" stroke-width="1.2" opacity="0.6"/>
        </svg>`;
        return {
          image: `${svgUri(svg)}, linear-gradient(45deg, ${c[3] || c[0]}, transparent 50%, ${c[4] || c[1]})`,
          size: 'var(--pat-scale) calc(var(--pat-scale) * 0.5), 200% 200%',
        };
      }
    }
  ];

  const SECTION_PACK = {
    verifone: 'prism-chevrons',
    media: 'hex-field',
    av: 'plasma-ribbons',
    system: 'circuit-lattice',
    'files-dev': 'neon-grid-plus',
    tax: 'diamond-ops',
    utils: 'confetti-dots'
  };

  function pickPack(idOrSeed) {
    if (typeof idOrSeed === 'string') {
      const found = PACKS.find((p) => p.id === idOrSeed);
      if (found) return found;
    }
    const h = typeof idOrSeed === 'number' ? idOrSeed : hashStr(idOrSeed);
    return PACKS[h % PACKS.length];
  }

  function motionFor(seed) {
    const rnd = mulberry32(seed || 1);
    // Scale in px for tile size; shift %; rot degrees
    const scale = 22 + Math.floor(rnd() * 48); // 22–70px
    const ox = Math.floor(rnd() * 100);
    const oy = Math.floor(rnd() * 100);
    const rot = Math.floor(rnd() * 360);
    const dur = 18 + Math.floor(rnd() * 28); // slow drift
    const shiftAmp = 8 + Math.floor(rnd() * 24);
    const rotAmp = 4 + Math.floor(rnd() * 16);
    return { scale, ox, oy, rot, dur, shiftAmp, rotAmp };
  }

  function styleForKey(key, packId) {
    const seed = hashStr(key);
    const pack = packId ? pickPack(packId) : pickPack(seed);
    const cols = wildPalette(seed ^ 0x9e3779b9, 4 + (seed % 7));
    const gen = pack.gen(seed, cols);
    const m = motionFor(seed);
    return {
      packId: pack.id,
      packName: pack.name,
      colors: cols,
      motion: m,
      css: {
        '--pat-scale': m.scale + 'px',
        '--pat-ox': m.ox + '%',
        '--pat-oy': m.oy + '%',
        '--pat-rot': m.rot + 'deg',
        '--pat-dur': m.dur + 's',
        '--pat-shift': m.shiftAmp + 'px',
        '--pat-rot-amp': m.rotAmp + 'deg',
        '--pat-image': gen.image,
        '--pat-size': gen.size || 'var(--pat-scale) var(--pat-scale)',
        '--pat-pos': `var(--pat-ox) var(--pat-oy)`,
      }
    };
  }

  function applyToElement(el, key, opts) {
    if (!el) return null;
    const packId = opts && opts.packId;
    const art = styleForKey(key, packId || (opts && opts.section && SECTION_PACK[opts.section]));
    el.classList.add('fafo-pat');
    if (opts && opts.kind) el.classList.add('fafo-pat-' + opts.kind);
    Object.entries(art.css).forEach(([k, v]) => el.style.setProperty(k, v));
    el.dataset.patPack = art.packId;
    el.title = (el.title ? el.title + ' · ' : '') + 'Pattern: ' + art.packName;
    return art;
  }

  function injectPatternCss() {
    if (document.getElementById('aitoolbox-launcher-art-css')) return;
    const style = document.createElement('style');
    style.id = 'aitoolbox-launcher-art-css';
    style.textContent = `
/* Live multi-axis tiling patterns (scale · shift · rotate) */
.fafo-pat {
  --pat-scale: 36px;
  --pat-ox: 0%;
  --pat-oy: 0%;
  --pat-rot: 0deg;
  --pat-dur: 28s;
  --pat-shift: 14px;
  --pat-rot-amp: 8deg;
  position: relative;
}
.fafo-pat::after {
  content: '';
  position: absolute;
  inset: -20%;
  z-index: 0;
  pointer-events: none;
  background-image: var(--pat-image);
  background-size: var(--pat-size);
  background-position: var(--pat-pos);
  opacity: 0.55;
  mix-blend-mode: screen;
  transform-origin: 50% 50%;
  animation: fafoPatDrift var(--pat-dur) linear infinite;
}
.fafo-pat > * { position: relative; z-index: 1; }
.fafo-pat-icon {
  overflow: hidden;
}
.fafo-pat-icon::after {
  inset: -30%;
  opacity: 0.75;
  mix-blend-mode: soft-light;
}
.fafo-pat-section::after {
  opacity: 0.35;
  mix-blend-mode: soft-light;
  border-radius: inherit;
}
@keyframes fafoPatDrift {
  0% {
    background-position:
      var(--pat-ox) var(--pat-oy),
      calc(var(--pat-ox) + 10%) calc(var(--pat-oy) + 6%),
      var(--pat-ox) var(--pat-oy),
      var(--pat-ox) var(--pat-oy),
      50% 50%;
    transform: rotate(var(--pat-rot)) scale(1);
  }
  50% {
    background-position:
      calc(var(--pat-ox) + var(--pat-shift)) calc(var(--pat-oy) - var(--pat-shift)),
      calc(var(--pat-ox) - var(--pat-shift)) calc(var(--pat-oy) + var(--pat-shift)),
      calc(var(--pat-ox) + 8%) calc(var(--pat-oy) - 10%),
      calc(var(--pat-ox) - 6%) calc(var(--pat-oy) + 12%),
      48% 52%;
    transform: rotate(calc(var(--pat-rot) + var(--pat-rot-amp))) scale(1.06);
  }
  100% {
    background-position:
      calc(var(--pat-ox) + calc(var(--pat-shift) * 2)) calc(var(--pat-oy) + var(--pat-shift)),
      calc(var(--pat-ox) - calc(var(--pat-shift) * 1.4)) calc(var(--pat-oy) - var(--pat-shift)),
      calc(var(--pat-ox) + 16%) calc(var(--pat-oy) + 8%),
      calc(var(--pat-ox) - 12%) calc(var(--pat-oy) - 6%),
      52% 48%;
    transform: rotate(calc(var(--pat-rot) + calc(var(--pat-rot-amp) * 2))) scale(1);
  }
}
@media (prefers-reduced-motion: reduce) {
  .fafo-pat::after { animation: none; }
}

/* Icon crop modal — above tooltips (100000) and launcher chrome */
#fafoIconCropModal {
  position: fixed; inset: 0; z-index: 200000;
  display: none; align-items: center; justify-content: center;
  background: rgba(0,0,0,0.72); backdrop-filter: blur(6px);
  padding: 16px;
}
#fafoIconCropModal.open { display: flex; }
#fafoIconCropModal .ic-card {
  width: min(520px, 96vw);
  background: #0c0f16;
  border: 1px solid rgba(0,243,255,0.35);
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.55), 0 0 30px rgba(0,243,255,0.12);
  padding: 16px 18px 14px;
  color: #e2e8f0;
  font-family: 'Segoe UI', system-ui, sans-serif;
}
#fafoIconCropModal h3 {
  margin: 0 0 6px; font-size: 15px; color: #00f3ff; letter-spacing: 0.04em;
}
#fafoIconCropModal .ic-sub {
  font-size: 12px; color: #94a3b8; margin-bottom: 12px; line-height: 1.4;
}
#fafoIconCropModal .ic-stage {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  max-height: min(52vh, 380px);
  background: #000;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid rgba(0,243,255,0.22);
  touch-action: none;
  cursor: grab;
}
#fafoIconCropModal .ic-stage:active { cursor: grabbing; }
#fafoIconCropModal canvas {
  position: absolute; inset: 0; width: 100%; height: 100%;
}
#fafoIconCropModal .ic-frame {
  position: absolute; inset: 8%;
  border: 2px solid rgba(0,243,255,0.85);
  border-radius: 12px;
  box-shadow: 0 0 0 9999px rgba(0,0,0,0.45);
  pointer-events: none;
}
#fafoIconCropModal .ic-row {
  display: flex; flex-wrap: wrap; gap: 10px; align-items: center;
  margin-top: 12px;
}
#fafoIconCropModal label {
  font-size: 11px; color: #94a3b8; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
}
#fafoIconCropModal input[type=range] { flex: 1; min-width: 120px; accent-color: #00f3ff; }
#fafoIconCropModal .ic-actions {
  display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; margin-top: 14px;
}
#fafoIconCropModal button {
  border-radius: 8px; padding: 8px 14px; font-weight: 700; font-size: 12px; cursor: pointer;
  border: 1px solid rgba(0,243,255,0.4); background: rgba(0,243,255,0.12); color: #00f3ff;
}
#fafoIconCropModal button.primary { background: #00f3ff; color: #041018; }
#fafoIconCropModal button.ghost { border-color: rgba(255,255,255,0.18); color: #94a3b8; background: transparent; }
#fafoIconCropModal button:hover { filter: brightness(1.08); }
`;
    document.head.appendChild(style);
  }

  /**
   * Interactive square crop. Returns Promise<dataURL|null>.
   * null = user cancelled. Decode failures return the original (MIME-fixed) data URL
   * so Edit Icons still saves .ico / octet-stream files instead of aborting.
   * GIFs / SVG: skip crop and resolve original dataURL.
   */
  function openIconCropper(fileOrDataUrl, opts) {
    injectPatternCss();
    opts = opts || {};
    const outSize = opts.outSize || 256;

    return new Promise((resolve) => {
      let settled = false;
      function fail(msg, fallback) {
        if (settled) return;
        settled = true;
        try {
          if (global.AIToolboxUI?.toast) AIToolboxUI.toast(msg || 'Crop skipped', 'warn');
        } catch (_) { /* ignore */ }
        resolve(fallback || null);
      }

      const name = (fileOrDataUrl && fileOrDataUrl.name) || (opts.filename || '');
      const type = (fileOrDataUrl && fileOrDataUrl.type) || '';
      const isGif = /gif/i.test(type) || /\.gif$/i.test(name);
      const isSvg = /svg/i.test(type) || /\.svg$/i.test(name);
      const isIco = /icon/i.test(type) || /\.ico$/i.test(name);

      const loadAsDataUrl = () =>
        new Promise((res, rej) => {
          if (typeof fileOrDataUrl === 'string') {
            res(fileOrDataUrl);
            return;
          }
          const r = new FileReader();
          r.onload = () => res(r.result);
          r.onerror = () => rej(new Error('read failed'));
          r.readAsDataURL(fileOrDataUrl);
        });

      function fixMime(dataUrl) {
        if (global.AIToolbox?.normalizeImageDataUrl) {
          return global.AIToolbox.normalizeImageDataUrl(dataUrl, name);
        }
        if (typeof dataUrl === 'string' && /^data:(application\/octet-stream|;base64|,)/i.test(dataUrl)) {
          const ext = (name.split('.').pop() || '').toLowerCase();
          const mime = {
            png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', gif: 'image/gif',
            webp: 'image/webp', ico: 'image/x-icon', svg: 'image/svg+xml', bmp: 'image/bmp'
          }[ext] || 'image/png';
          return dataUrl.replace(/^data:[^,]*,/, 'data:' + mime + ';base64,');
        }
        return dataUrl;
      }

      loadAsDataUrl()
        .then((rawUrl) => {
          const dataUrl = fixMime(rawUrl);
          // Preserve animation / vectors. ICO can crop if the browser can decode it;
          // if decode fails we still save the original below.
          if (isGif || isSvg) {
            settled = true;
            resolve(dataUrl);
            return;
          }

          let modal = document.getElementById('fafoIconCropModal');
          if (!modal) {
            modal = document.createElement('div');
            modal.id = 'fafoIconCropModal';
            modal.innerHTML = `
              <div class="ic-card" role="dialog" aria-modal="true" aria-label="Crop tool icon">
                <h3>Crop tool icon</h3>
                <p class="ic-sub">Drag to pan · wheel or slider to zoom · square crop for the card. Apply saves the cropped PNG. ICO/GIF keep the original if crop can't read them.</p>
                <div class="ic-stage" id="icStage">
                  <canvas id="icCanvas"></canvas>
                  <div class="ic-frame"></div>
                </div>
                <div class="ic-row">
                  <label for="icZoom">Zoom</label>
                  <input type="range" id="icZoom" min="100" max="400" value="100">
                  <span id="icZoomLbl" style="font-size:11px;color:#94a3b8;min-width:40px">100%</span>
                </div>
                <div class="ic-actions">
                  <button type="button" class="ghost" id="icCancel">Cancel</button>
                  <button type="button" class="ghost" id="icFull">Use full image</button>
                  <button type="button" class="primary" id="icApply">Apply crop</button>
                </div>
              </div>`;
            document.body.appendChild(modal);
          }

          const canvas = modal.querySelector('#icCanvas');
          const ctx = canvas.getContext('2d');
          const stage = modal.querySelector('#icStage');
          const zoomEl = modal.querySelector('#icZoom');
          const zoomLbl = modal.querySelector('#icZoomLbl');
          const img = new Image();
          let scale = 1;
          let ox = 0;
          let oy = 0;
          let drag = null;
          let baseFit = 1;
          let opened = false;
          // settled lives on the outer promise so fail()/close() share it

          function layout() {
            const rect = stage.getBoundingClientRect();
            const dpr = Math.min(window.devicePixelRatio || 1, 2);
            canvas.width = Math.floor((rect.width || 360) * dpr);
            canvas.height = Math.floor((rect.height || 360) * dpr);
            canvas.style.width = (rect.width || 360) + 'px';
            canvas.style.height = (rect.height || 360) + 'px';
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            draw();
          }

          function draw() {
            const w = canvas.clientWidth || 360;
            const h = canvas.clientHeight || 360;
            ctx.clearRect(0, 0, w, h);
            ctx.fillStyle = '#000';
            ctx.fillRect(0, 0, w, h);
            if (!img.naturalWidth) return;
            const s = baseFit * scale;
            const dw = img.naturalWidth * s;
            const dh = img.naturalHeight * s;
            const dx = (w - dw) / 2 + ox;
            const dy = (h - dh) / 2 + oy;
            ctx.imageSmoothingEnabled = true;
            ctx.imageSmoothingQuality = 'high';
            ctx.drawImage(img, dx, dy, dw, dh);
          }

          function exportCrop(useFull) {
            if (useFull) {
              const c = document.createElement('canvas');
              c.width = outSize;
              c.height = outSize;
              const g = c.getContext('2d');
              g.fillStyle = '#000';
              g.fillRect(0, 0, outSize, outSize);
              const s = Math.min(outSize / img.naturalWidth, outSize / img.naturalHeight);
              const dw = img.naturalWidth * s;
              const dh = img.naturalHeight * s;
              g.drawImage(img, (outSize - dw) / 2, (outSize - dh) / 2, dw, dh);
              return c.toDataURL('image/png');
            }
            const w = canvas.clientWidth || 360;
            const h = canvas.clientHeight || 360;
            const frameInset = 0.08;
            const fw = w * (1 - frameInset * 2);
            const fh = h * (1 - frameInset * 2);
            const fx = w * frameInset;
            const fy = h * frameInset;
            const s = baseFit * scale;
            const dw = img.naturalWidth * s;
            const dh = img.naturalHeight * s;
            const dx = (w - dw) / 2 + ox;
            const dy = (h - dh) / 2 + oy;
            const sx = (fx - dx) / s;
            const sy = (fy - dy) / s;
            const sw = fw / s;
            const sh = fh / s;
            const c = document.createElement('canvas');
            c.width = outSize;
            c.height = outSize;
            const g = c.getContext('2d');
            g.fillStyle = '#000';
            g.fillRect(0, 0, outSize, outSize);
            g.imageSmoothingEnabled = true;
            g.imageSmoothingQuality = 'high';
            g.drawImage(img, sx, sy, sw, sh, 0, 0, outSize, outSize);
            return c.toDataURL('image/png');
          }

          function close(result) {
            if (settled) return;
            settled = true;
            modal.classList.remove('open');
            stage.onpointerdown = null;
            window.removeEventListener('pointermove', onMove);
            window.removeEventListener('pointerup', onUp);
            resolve(result);
          }

          function onMove(e) {
            if (!drag) return;
            ox = drag.ox + (e.clientX - drag.x);
            oy = drag.oy + (e.clientY - drag.y);
            draw();
          }
          function onUp() {
            drag = null;
          }

          img.onload = () => {
            if (!img.naturalWidth || !img.naturalHeight) {
              fail('Image has no size — saving original file', dataUrl);
              return;
            }
            const w = stage.clientWidth || 360;
            const h = stage.clientHeight || 360;
            baseFit = Math.max(w / img.naturalWidth, h / img.naturalHeight) * 1.05;
            scale = 1;
            ox = 0;
            oy = 0;
            zoomEl.value = '100';
            zoomLbl.textContent = '100%';
            modal.classList.add('open');
            opened = true;
            layout();
          };
          img.onerror = () => {
            // ICO/BMP with odd MIME, or unsupported codec — still assign the original.
            fail(isIco ? 'ICO preview skipped — saving original icon' : 'Could not preview image — saving original file', dataUrl);
          };
          img.src = dataUrl;

          zoomEl.oninput = () => {
            scale = (parseInt(zoomEl.value, 10) || 100) / 100;
            zoomLbl.textContent = Math.round(scale * 100) + '%';
            draw();
          };
          stage.onpointerdown = (e) => {
            drag = { x: e.clientX, y: e.clientY, ox, oy };
            stage.setPointerCapture?.(e.pointerId);
          };
          window.addEventListener('pointermove', onMove);
          window.addEventListener('pointerup', onUp);
          stage.onwheel = (e) => {
            e.preventDefault();
            const next = Math.max(1, Math.min(4, scale + (e.deltaY > 0 ? -0.08 : 0.08)));
            scale = next;
            zoomEl.value = String(Math.round(scale * 100));
            zoomLbl.textContent = Math.round(scale * 100) + '%';
            draw();
          };

          modal.querySelector('#icCancel').onclick = () => close(null);
          modal.querySelector('#icFull').onclick = () => {
            try { close(exportCrop(true)); } catch (_) { close(dataUrl); }
          };
          modal.querySelector('#icApply').onclick = () => {
            try { close(exportCrop(false)); } catch (_) { close(dataUrl); }
          };
          modal.onclick = (e) => {
            if (e.target === modal) close(null);
          };

          // Safety: if neither load nor error fires (some ICO paths), save original.
          setTimeout(() => {
            if (!settled && !opened && !modal.classList.contains('open')) {
              fail('Crop timed out — saving original file', dataUrl);
            }
          }, 4000);
        })
        .catch(() => fail('Could not read image'));
    });
  }

  function listPacks() {
    return PACKS.map((p) => ({ id: p.id, name: p.name }));
  }

  global.AIToolboxLauncherArt = {
    listPacks,
    styleForKey,
    applyToElement,
    openIconCropper,
    injectPatternCss,
    SECTION_PACK,
    wildPalette
  };
})(typeof window !== 'undefined' ? window : globalThis);
