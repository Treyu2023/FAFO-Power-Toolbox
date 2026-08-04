/**
 * AI HTML Toolbox — 90s production-style launch cinematics
 * Three ~5s screens, Space/Enter/Click to skip, folder-backed video BGs.
 * 4K/heavy sources are auto-downscaled to a light 720p (or 540p) proxy for smooth playback.
 */
(function (global) {
    'use strict';

    const DURATION_MS = 5000;
    const LS_PREFS = 'aitoolbox.cine.prefs';
    const IDB_NAME = 'AIToolboxCine';
    const IDB_VER = 1;
    const STORE = 'handles';

    /** Playback proxies — intros only need a short loop, not full 4K masters */
    const PROXY_SECONDS = 8;
    const PROXY_FPS = 24;
    const PROXY_SIZE_SOFT_CAP = 28 * 1024 * 1024; // always proxy blobs bigger than this

    const DEFAULT_PREFS = {
        skipOnLaunch: false,   // daily-driver: skip intros
        muteVideo: true,
        lastPlayedAt: 0
    };

    /** Pick a target size based on the machine so weak PCs stay smooth. */
    function playTarget() {
        const mem = typeof navigator.deviceMemory === 'number' ? navigator.deviceMemory : 8;
        const cores = typeof navigator.hardwareConcurrency === 'number' ? navigator.hardwareConcurrency : 4;
        // Low-end / laptop integrated: 540p
        if (mem <= 4 || cores <= 4) {
            return { maxW: 960, maxH: 540, bitrate: 1_500_000, label: '540p' };
        }
        // Everything else: 720p is plenty for fullscreen dimmed BGs
        return { maxW: 1280, maxH: 720, bitrate: 2_500_000, label: '720p' };
    }

    /** @type {{ skipOnLaunch: boolean, muteVideo: boolean, lastPlayedAt: number }} */
    let prefs = loadPrefs();

    function loadPrefs() {
        try {
            return { ...DEFAULT_PREFS, ...JSON.parse(localStorage.getItem(LS_PREFS) || '{}') };
        } catch (_) {
            return { ...DEFAULT_PREFS };
        }
    }

    function savePrefs(patch) {
        prefs = { ...prefs, ...patch };
        try { localStorage.setItem(LS_PREFS, JSON.stringify(prefs)); } catch (_) { /* ignore */ }
        return prefs;
    }

    function openIdb() {
        return new Promise((resolve, reject) => {
            const req = indexedDB.open(IDB_NAME, IDB_VER);
            req.onupgradeneeded = () => {
                const db = req.result;
                if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE);
            };
            req.onsuccess = () => resolve(req.result);
            req.onerror = () => reject(req.error);
        });
    }

    async function idbGet(key) {
        try {
            const db = await openIdb();
            return await new Promise((res, rej) => {
                const r = db.transaction(STORE, 'readonly').objectStore(STORE).get(key);
                r.onsuccess = () => res(r.result);
                r.onerror = () => rej(r.error);
            });
        } catch (_) {
            return null;
        }
    }

    async function idbPut(key, value) {
        try {
            const db = await openIdb();
            await new Promise((res, rej) => {
                const tx = db.transaction(STORE, 'readwrite');
                tx.objectStore(STORE).put(value, key);
                tx.oncomplete = () => res();
                tx.onerror = () => rej(tx.error);
            });
            return true;
        } catch (_) {
            return false;
        }
    }

    async function ensureDirPermission(handle) {
        if (!handle || !handle.queryPermission) return false;
        try {
            let p = await handle.queryPermission({ mode: 'read' });
            if (p === 'granted') return true;
            p = await handle.requestPermission({ mode: 'read' });
            return p === 'granted';
        } catch (_) {
            return false;
        }
    }

    async function pickDirectory(slotKey) {
        if (!window.showDirectoryPicker) {
            alert('Folder pick needs Chrome/Edge. Use “Pick video file” instead.');
            return null;
        }
        try {
            const handle = await window.showDirectoryPicker({ id: 'cine-' + slotKey, mode: 'read' });
            await idbPut(slotKey, { kind: 'dir', handle, name: handle.name, savedAt: Date.now() });
            return handle;
        } catch (e) {
            if (e && e.name === 'AbortError') return null;
            console.warn('[Cine] directory pick failed', e);
            return null;
        }
    }

    async function pickVideoFile(slotKey, onStatus) {
        return new Promise((resolve) => {
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = 'video/*,.mp4,.webm,.mov,.mkv,.avi';
            input.style.display = 'none';
            document.body.appendChild(input);
            input.onchange = async () => {
                const file = input.files && input.files[0];
                input.remove();
                if (!file) { resolve(null); return; }
                // Downscale heavy 4K masters once on pick, then persist the light proxy
                let storeBlob = file;
                let optimized = false;
                let optLabel = '';
                try {
                    if (onStatus) onStatus('Optimizing video for smooth playback…');
                    const ready = await ensureLightProxy(file, {
                        cacheKey: proxyCacheKey('file', file.name, file.size, file.lastModified || 0),
                        onStatus
                    });
                    if (ready && ready.blob) {
                        storeBlob = ready.blob;
                        optimized = !!ready.scaled;
                        optLabel = ready.scaleLabel || '';
                    }
                } catch (e) {
                    console.warn('[Cine] optimize on pick failed — storing original', e);
                }
                try {
                    await idbPut(slotKey, {
                        kind: 'file',
                        name: file.name,
                        type: storeBlob.type || file.type || 'video/webm',
                        blob: storeBlob,
                        optimized,
                        scaleLabel: optLabel,
                        originalSize: file.size,
                        savedAt: Date.now()
                    });
                } catch (e) {
                    console.warn('[Cine] could not persist video file', e);
                }
                resolve(storeBlob);
            };
            input.click();
        });
    }

    function proxyCacheKey(kind, name, size, mtime) {
        return 'proxy:' + [kind, name || 'v', size || 0, mtime || 0, playTarget().label].join('|');
    }

    function loadVideoMeta(blobOrFile) {
        return new Promise((resolve, reject) => {
            const url = URL.createObjectURL(blobOrFile);
            const v = document.createElement('video');
            v.preload = 'metadata';
            v.muted = true;
            v.playsInline = true;
            v.setAttribute('playsinline', '');
            let settled = false;
            const done = (ok, data) => {
                if (settled) return;
                settled = true;
                v.onloadedmetadata = null;
                v.onerror = null;
                if (!ok) {
                    try { URL.revokeObjectURL(url); } catch (_) { /* ignore */ }
                    reject(data || new Error('video meta failed'));
                    return;
                }
                resolve({ video: v, url, width: v.videoWidth || 0, height: v.videoHeight || 0, duration: v.duration || 0 });
            };
            v.onloadedmetadata = () => done(true);
            v.onerror = () => done(false, new Error('could not load video'));
            setTimeout(() => {
                if (!settled) done(false, new Error('video meta timeout'));
            }, 12000);
            v.src = url;
        });
    }

    function pickRecorderMime() {
        const candidates = [
            'video/webm;codecs=vp9',
            'video/webm;codecs=vp8',
            'video/webm',
            'video/mp4'
        ];
        for (const m of candidates) {
            if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(m)) {
                return m;
            }
        }
        return '';
    }

    /**
     * Re-encode a short loop at 720p/540p so 4K masters never hit the GPU during intros.
     */
    async function downscaleVideoBlob(blobOrFile, opts) {
        opts = opts || {};
        const target = playTarget();
        const maxW = opts.maxW || target.maxW;
        const maxH = opts.maxH || target.maxH;
        const bitrate = opts.bitrate || target.bitrate;
        const mime = pickRecorderMime();
        if (!mime) throw new Error('MediaRecorder not supported');

        const meta = await loadVideoMeta(blobOrFile);
        const { video, url, width, height, duration } = meta;
        try {
            if (!width || !height) throw new Error('unknown video size');

            const scale = Math.min(1, maxW / width, maxH / height);
            // Even-dimension canvas for encoder friendliness
            let w = Math.max(2, Math.round((width * scale) / 2) * 2);
            let h = Math.max(2, Math.round((height * scale) / 2) * 2);
            // Cap absolute pixels hard
            if (w * h > maxW * maxH) {
                const s2 = Math.sqrt((maxW * maxH) / (w * h));
                w = Math.max(2, Math.round((w * s2) / 2) * 2);
                h = Math.max(2, Math.round((h * s2) / 2) * 2);
            }

            const canvas = document.createElement('canvas');
            canvas.width = w;
            canvas.height = h;
            const ctx = canvas.getContext('2d', { alpha: false, desynchronized: true });
            if (!ctx) throw new Error('no 2d context');

            const stream = canvas.captureStream(PROXY_FPS);
            const rec = new MediaRecorder(stream, {
                mimeType: mime,
                videoBitsPerSecond: bitrate
            });
            const chunks = [];
            rec.ondataavailable = (e) => {
                if (e.data && e.data.size) chunks.push(e.data);
            };

            const clipSec = Math.min(
                PROXY_SECONDS,
                Number.isFinite(duration) && duration > 0 ? duration : PROXY_SECONDS
            );

            video.muted = true;
            video.currentTime = 0;
            try { await video.play(); } catch (_) { /* ignore autoplay quirks */ }

            const outBlob = await new Promise((resolve, reject) => {
                let finished = false;
                const finish = () => {
                    if (finished) return;
                    finished = true;
                    try { video.pause(); } catch (_) { /* ignore */ }
                    try {
                        if (rec.state !== 'inactive') rec.stop();
                    } catch (e) {
                        reject(e);
                    }
                };

                rec.onstop = () => {
                    const blob = new Blob(chunks, { type: mime.split(';')[0] || 'video/webm' });
                    resolve(blob);
                };
                rec.onerror = () => reject(rec.error || new Error('recorder error'));

                try { rec.start(200); } catch (e) { reject(e); return; }

                const t0 = performance.now();
                const draw = () => {
                    if (finished) return;
                    try {
                        ctx.drawImage(video, 0, 0, w, h);
                    } catch (_) { /* ignore frame glitches */ }
                    const elapsed = (performance.now() - t0) / 1000;
                    const vTime = video.currentTime || 0;
                    if (opts.onStatus && Math.floor(elapsed * 4) % 2 === 0) {
                        const pct = Math.min(99, Math.round((Math.max(vTime, elapsed) / clipSec) * 100));
                        opts.onStatus(`Scaling ${width}×${height} → ${w}×${h} (${pct}%)`);
                    }
                    if (vTime >= clipSec - 0.05 || elapsed >= clipSec + 0.6 || video.ended) {
                        finish();
                        return;
                    }
                    requestAnimationFrame(draw);
                };
                requestAnimationFrame(draw);
                // Hard stop so we never hang on bad metadata
                setTimeout(finish, (clipSec + 1.2) * 1000);
            });

            if (!outBlob || outBlob.size < 1000) throw new Error('proxy encode empty');
            return {
                blob: outBlob,
                width: w,
                height: h,
                scaleLabel: `${w}×${h}`,
                sourceW: width,
                sourceH: height
            };
        } finally {
            try { video.removeAttribute('src'); video.load(); } catch (_) { /* ignore */ }
            try { URL.revokeObjectURL(url); } catch (_) { /* ignore */ }
        }
    }

    function needsDownscale(width, height, byteSize) {
        const t = playTarget();
        if (byteSize && byteSize > PROXY_SIZE_SOFT_CAP) return true;
        if (!width || !height) return !!(byteSize && byteSize > 12 * 1024 * 1024);
        return width > t.maxW || height > t.maxH;
    }

    /**
     * Return a lightweight blob for smooth intro playback (cached in IDB).
     */
    async function ensureLightProxy(blobOrFile, opts) {
        opts = opts || {};
        const cacheKey = opts.cacheKey || proxyCacheKey('anon', blobOrFile.name || 'clip', blobOrFile.size, blobOrFile.lastModified || 0);
        const t = playTarget();

        // Cached proxy for this machine class
        try {
            const cached = await idbGet(cacheKey);
            if (cached && cached.blob && cached.blob.size > 1000) {
                return {
                    blob: cached.blob,
                    scaled: true,
                    fromCache: true,
                    scaleLabel: cached.scaleLabel || t.label
                };
            }
        } catch (_) { /* ignore */ }

        // Already a small optimized store?
        if (blobOrFile._cineOptimized) {
            return { blob: blobOrFile, scaled: true, scaleLabel: blobOrFile._scaleLabel || t.label };
        }

        let width = 0;
        let height = 0;
        try {
            const meta = await loadVideoMeta(blobOrFile);
            width = meta.width;
            height = meta.height;
            try { meta.video.removeAttribute('src'); meta.video.load(); } catch (_) { /* ignore */ }
            try { URL.revokeObjectURL(meta.url); } catch (_) { /* ignore */ }
        } catch (_) { /* probe failed — may still try encode or pass-through */ }

        if (!needsDownscale(width, height, blobOrFile.size)) {
            return { blob: blobOrFile, scaled: false, scaleLabel: width ? `${width}×${height}` : 'native' };
        }

        if (opts.onStatus) {
            opts.onStatus(`Optimizing ${width || '?'}×${height || '?'} → ${t.label}…`);
        }

        try {
            const result = await downscaleVideoBlob(blobOrFile, {
                onStatus: opts.onStatus,
                maxW: t.maxW,
                maxH: t.maxH,
                bitrate: t.bitrate
            });
            try {
                await idbPut(cacheKey, {
                    kind: 'proxy',
                    blob: result.blob,
                    scaleLabel: result.scaleLabel,
                    sourceW: result.sourceW,
                    sourceH: result.sourceH,
                    target: t.label,
                    savedAt: Date.now()
                });
            } catch (e) {
                console.warn('[Cine] could not cache proxy', e);
            }
            return {
                blob: result.blob,
                scaled: true,
                scaleLabel: result.scaleLabel,
                fromCache: false
            };
        } catch (e) {
            console.warn('[Cine] downscale failed — using original (may lag)', e);
            if (opts.onStatus) opts.onStatus('Using original video (optimize failed)');
            return { blob: blobOrFile, scaled: false, scaleLabel: 'original', error: String(e && e.message || e) };
        }
    }

    async function resolveVideoUrl(slotKey, onStatus) {
        const saved = await idbGet(slotKey);
        if (!saved) return { url: null, label: 'No media folder — synthetic neon BG', source: null };

        if (saved.kind === 'file' && saved.blob) {
            try {
                // Re-optimize legacy 4K blobs that were saved before proxy support
                const ready = await ensureLightProxy(saved.blob, {
                    cacheKey: proxyCacheKey('slot', slotKey, saved.blob.size, saved.savedAt || 0),
                    onStatus
                });
                // Upgrade stored entry if we just scaled a heavy original
                if (ready.scaled && !ready.fromCache && !saved.optimized) {
                    try {
                        await idbPut(slotKey, {
                            ...saved,
                            blob: ready.blob,
                            type: ready.blob.type || saved.type,
                            optimized: true,
                            scaleLabel: ready.scaleLabel,
                            originalSize: saved.originalSize || saved.blob.size,
                            savedAt: Date.now()
                        });
                    } catch (_) { /* ignore upgrade fail */ }
                }
                const url = URL.createObjectURL(ready.blob);
                const tag = ready.scaled ? ` · ${ready.scaleLabel || playTarget().label}` : '';
                return {
                    url,
                    label: (saved.name || 'Saved video') + tag,
                    source: 'file',
                    revoke: url,
                    scaled: ready.scaled
                };
            } catch (_) { /* fall through */ }
        }

        if (saved.kind === 'dir' && saved.handle) {
            const ok = await ensureDirPermission(saved.handle);
            if (!ok) return { url: null, label: 'Folder permission needed — re-pick folder', source: 'dir' };
            try {
                const vids = [];
                for await (const entry of saved.handle.values()) {
                    if (entry.kind === 'file' && /\.(mp4|webm|mov|mkv|avi|m4v)$/i.test(entry.name)) {
                        vids.push(entry);
                    }
                }
                if (!vids.length) {
                    return { url: null, label: `Folder “${saved.name || '…'}” has no videos`, source: 'dir' };
                }
                const pick = vids[Math.floor(Math.random() * vids.length)];
                const file = await pick.getFile();
                const ready = await ensureLightProxy(file, {
                    cacheKey: proxyCacheKey('dir', (saved.name || 'dir') + '/' + pick.name, file.size, file.lastModified || 0),
                    onStatus
                });
                const url = URL.createObjectURL(ready.blob);
                const tag = ready.scaled ? ` · ${ready.scaleLabel || playTarget().label}` : '';
                return {
                    url,
                    label: `${saved.name || 'Folder'} · ${pick.name}${tag}`,
                    source: 'dir',
                    revoke: url,
                    scaled: ready.scaled
                };
            } catch (e) {
                console.warn('[Cine] folder read failed', e);
                return { url: null, label: 'Could not read folder videos', source: 'dir' };
            }
        }

        return { url: null, label: 'Pick a folder or video for this screen', source: null };
    }

    function injectStyles() {
        if (document.getElementById('aitoolbox-cine-css')) return;
        const style = document.createElement('style');
        style.id = 'aitoolbox-cine-css';
        style.textContent = `
/* ── Cinematic overlay ── */
.cine-root {
  position: fixed; inset: 0; z-index: 99999;
  background: #000; color: #e8e8ec;
  font-family: 'Segoe UI', system-ui, sans-serif;
  overflow: hidden;
  opacity: 1; transition: opacity 0.45s ease;
}
.cine-root.cine-exit { opacity: 0; pointer-events: none; }
body.cine-active > :not(.cine-root) { visibility: hidden !important; }
body.cine-active { overflow: hidden; }

.cine-stage {
  position: absolute; inset: 0;
  display: none; align-items: center; justify-content: center;
  flex-direction: column;
}
.cine-stage.active { display: flex; animation: cine-fade-in 0.35s ease both; }

@keyframes cine-fade-in {
  from { opacity: 0; } to { opacity: 1; }
}

.cine-bg-video, .cine-bg-synth {
  position: absolute; inset: 0; width: 100%; height: 100%;
  object-fit: cover; z-index: 0;
  filter: brightness(0.45) saturate(1.15) contrast(1.05);
}
/* Prefer compositor path; proxies are already ≤720p so paint stays cheap */
.cine-bg-video {
  transform: translateZ(0);
  will-change: transform;
  background: #000;
}
.cine-bg-synth {
  background:
    radial-gradient(ellipse at 30% 20%, rgba(0,243,255,0.25), transparent 50%),
    radial-gradient(ellipse at 70% 80%, rgba(255,60,120,0.2), transparent 45%),
    linear-gradient(160deg, #050510 0%, #0a1020 40%, #120818 100%);
  overflow: hidden;
}
.cine-bg-synth::after {
  content: '';
  position: absolute; inset: -20%;
  background:
    repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,243,255,0.04) 3px, rgba(0,243,255,0.04) 4px),
    repeating-linear-gradient(90deg, transparent, transparent 3px, rgba(255,0,128,0.03) 3px, rgba(255,0,128,0.03) 4px);
  animation: cine-scan 8s linear infinite;
  pointer-events: none;
}
@keyframes cine-scan {
  from { transform: translateY(0); } to { transform: translateY(40px); }
}
.cine-vignette {
  position: absolute; inset: 0; z-index: 1; pointer-events: none;
  background:
    radial-gradient(ellipse at center, transparent 30%, rgba(0,0,0,0.75) 100%),
    linear-gradient(180deg, rgba(0,0,0,0.35) 0%, transparent 20%, transparent 80%, rgba(0,0,0,0.55) 100%);
}

.cine-fg {
  position: relative; z-index: 2;
  text-align: center;
  padding: 24px;
  max-width: 96vw;
}

/* Chrome / metal title */
.cine-chrome {
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: none;
  background: linear-gradient(180deg, #ffffff 0%, #c8d0dc 22%, #8a93a3 45%, #eef2f7 55%, #6b7380 78%, #b8c0cc 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  filter: drop-shadow(0 2px 0 #1a1a22) drop-shadow(0 0 18px rgba(0,243,255,0.35));
  font-size: clamp(22px, 5.2vw, 52px);
  line-height: 1.15;
}
.cine-sub {
  margin-top: 14px;
  font-size: clamp(11px, 1.6vw, 14px);
  letter-spacing: 0.35em;
  text-transform: uppercase;
  color: rgba(0,243,255,0.75);
  text-shadow: 0 0 12px rgba(0,243,255,0.4);
}

/* Neon Ninja lockup */
.cine-neon-lockup {
  display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: center;
  gap: 0.15em; row-gap: 0.35em;
  font-size: clamp(20px, 4.8vw, 48px);
  line-height: 1;
}
.cine-neon-lockup .by {
  width: 100%;
  font-size: 0.38em;
  letter-spacing: 0.45em;
  color: rgba(200,210,220,0.7);
  margin-bottom: 0.6em;
  text-transform: uppercase;
  font-weight: 600;
}
.cine-neon-lockup .at {
  font-weight: 700;
  color: #00f3ff;
  text-shadow: 0 0 10px #00f3ff, 0 0 24px rgba(0,243,255,0.5);
  margin-right: 0.12em;
}
.cine-neon-lockup .neon-word {
  font-weight: 900;
  letter-spacing: 0.08em;
  background: linear-gradient(180deg, #e8ffff, #00f3ff 40%, #007a88 70%, #b8ffff);
  -webkit-background-clip: text; background-clip: text; color: transparent;
  filter: drop-shadow(0 0 14px rgba(0,243,255,0.55));
  margin-right: 0.2em;
}
.cine-neon-lockup .ninja-word {
  font-weight: 900;
  letter-spacing: 0.1em;
  background: linear-gradient(180deg, #ffffff 0%, #d0d6e0 25%, #7a8290 48%, #f0f3f8 55%, #5a6270 80%, #c8ced8 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
  filter: drop-shadow(0 2px 0 #111) drop-shadow(0 0 16px rgba(200,210,255,0.35));
  position: relative;
}

/* Ninja "I" character stage */
.cine-ninja-stage {
  position: absolute; inset: 0; z-index: 3; pointer-events: none;
  overflow: hidden;
}
.cine-i-char {
  position: absolute;
  width: 72px; height: 110px;
  left: -10%; top: 55%;
  transform: translate(-50%, -50%);
  transform-origin: 50% 80%;
  animation: cine-i-parkour 3.6s cubic-bezier(0.4, 0, 0.2, 1) forwards;
  will-change: transform, left, top;
}
@keyframes cine-i-parkour {
  0%   { left: -12%; top: 72%; transform: translate(-50%,-50%) rotate(-25deg) scale(0.7); }
  12%  { left: 12%;  top: 48%; transform: translate(-50%,-50%) rotate(320deg) scale(0.9); }
  22%  { left: 22%;  top: 62%; transform: translate(-50%,-50%) rotate(400deg) scale(1); }
  34%  { left: 38%;  top: 28%; transform: translate(-50%,-50%) rotate(720deg) scale(1.05); }
  46%  { left: 52%;  top: 58%; transform: translate(-50%,-50%) rotate(900deg) scale(0.95); }
  58%  { left: 68%;  top: 32%; transform: translate(-50%,-50%) rotate(1080deg) scale(1.08); }
  70%  { left: 78%;  top: 50%; transform: translate(-50%,-50%) rotate(1260deg) scale(1); }
  82%  { left: 50%;  top: 42%; transform: translate(-50%,-50%) rotate(1400deg) scale(1.15); }
  90%  { left: var(--land-x, 72%); top: var(--land-y, 48%); transform: translate(-50%,-50%) rotate(0deg) scale(1.2); }
  100%{ left: var(--land-x, 72%); top: var(--land-y, 48%); transform: translate(-50%,-50%) rotate(0deg) scale(1); }
}
.cine-i-char.landed {
  animation: none;
  left: var(--land-x, 72%) !important;
  top: var(--land-y, 48%) !important;
  transform: translate(-50%, -50%) scale(1);
  transition: left 0.35s ease, top 0.35s ease, transform 0.35s ease;
}

.cine-i-body {
  position: absolute; inset: 18px 22px 10px;
  background: linear-gradient(180deg, #ff6a1a 0%, #ff3b00 40%, #c41e00 100%);
  border-radius: 10px 10px 6px 6px;
  box-shadow:
    0 0 12px #ff4500,
    0 0 28px rgba(255,60,0,0.65),
    inset 0 0 12px rgba(255,220,180,0.35);
  border: 2px solid rgba(255,200,120,0.55);
}
.cine-i-body::before {
  content: '';
  position: absolute; left: 50%; top: -16px;
  width: 28px; height: 14px;
  transform: translateX(-50%);
  background: linear-gradient(180deg, #ff8a3d, #ff4500);
  border-radius: 8px 8px 3px 3px;
  box-shadow: 0 0 10px #ff4500;
}
.cine-i-eye {
  position: absolute; top: 22%; left: 50%;
  width: 8px; height: 8px; border-radius: 50%;
  background: #00f3ff;
  box-shadow: 0 0 8px #00f3ff;
  transform: translateX(-50%);
  animation: cine-blink 2.4s infinite;
}
@keyframes cine-blink {
  0%, 92%, 100% { transform: translateX(-50%) scaleY(1); }
  95% { transform: translateX(-50%) scaleY(0.1); }
}

/* Floating hands */
.cine-hand {
  position: absolute;
  width: 18px; height: 18px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, #ffc08a, #ff4500 70%);
  box-shadow: 0 0 10px #ff4500;
  animation: cine-hand-float 1.1s ease-in-out infinite alternate;
}
.cine-hand.l { left: -6px; top: 42%; animation-delay: 0s; }
.cine-hand.r { right: -6px; top: 40%; animation-delay: 0.35s; }
@keyframes cine-hand-float {
  from { transform: translateY(-4px) scale(1); }
  to   { transform: translateY(6px) scale(1.08); }
}

/* Neon staff / lightsaber */
.cine-staff {
  position: absolute;
  left: 50%; top: 8%;
  width: 8px; height: 96px;
  margin-left: -4px;
  transform-origin: 50% 90%;
  animation: cine-staff-spin 0.55s linear infinite;
}
.cine-i-char.landed .cine-staff {
  animation: cine-staff-pose 0.5s ease forwards;
}
@keyframes cine-staff-spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}
@keyframes cine-staff-pose {
  to { transform: rotate(-28deg) translateY(-4px); }
}
.cine-staff .blade {
  position: absolute; inset: 0 2px 18px;
  border-radius: 4px;
  background: linear-gradient(180deg, #e8ffff, #00f3ff 30%, #0088ff 70%, #004466);
  box-shadow:
    0 0 8px #00f3ff,
    0 0 20px #00f3ff,
    0 0 36px rgba(0,200,255,0.7);
}
.cine-staff .hilt {
  position: absolute; left: 50%; bottom: 0;
  width: 14px; height: 22px; margin-left: -7px;
  border-radius: 3px;
  background: linear-gradient(180deg, #444, #111);
  border: 1px solid #888;
  box-shadow: 0 0 6px rgba(0,243,255,0.4);
}

/* Final lockup I (settles into text) */
.cine-final-i {
  display: inline-block;
  font-weight: 900;
  font-size: 1.15em;
  margin-left: 0.08em;
  color: #ff4500;
  text-shadow:
    0 0 8px #ff4500,
    0 0 22px rgba(255,69,0,0.85),
    0 2px 0 #3a1000;
  opacity: 0;
  transform: scale(0.5);
  vertical-align: -0.05em;
  letter-spacing: 0;
}
.cine-final-i.show {
  animation: cine-i-pop 0.45s cubic-bezier(0.2, 1.4, 0.4, 1) forwards;
}
@keyframes cine-i-pop {
  from { opacity: 0; transform: scale(0.4) rotate(-20deg); }
  to   { opacity: 1; transform: scale(1) rotate(0deg); }
}
.cine-i-char.fade-char {
  opacity: 0;
  transition: opacity 0.35s ease;
}

/* Producer screen */
.cine-producer {
  font-size: clamp(16px, 3.4vw, 36px);
  font-weight: 700;
  letter-spacing: 0.06em;
  line-height: 1.45;
}
.cine-producer .label {
  display: block;
  font-size: 0.55em;
  letter-spacing: 0.5em;
  color: #ffc800;
  text-shadow: 0 0 12px rgba(255,200,0,0.5);
  margin-bottom: 0.55em;
}
.cine-producer .credit {
  background: linear-gradient(90deg, #fff 0%, #ffd700 25%, #fff 50%, #c0c0c0 75%, #fff 100%);
  background-size: 200% auto;
  -webkit-background-clip: text; background-clip: text; color: transparent;
  animation: cine-shimmer 2.5s linear infinite;
  filter: drop-shadow(0 0 10px rgba(255,215,0,0.35));
  word-break: break-word;
}
@keyframes cine-shimmer {
  from { background-position: 0% center; }
  to   { background-position: 200% center; }
}
.cine-producer .marks {
  display: block;
  margin-top: 0.4em;
  font-size: 0.55em;
  color: rgba(200,210,220,0.65);
  letter-spacing: 0.2em;
}

/* Main FAFO / toolbox card */
.cine-main-logo {
  position: relative;
  padding: 28px 40px;
  border: 2px solid rgba(0,243,255,0.45);
  border-radius: 8px;
  background: linear-gradient(145deg, rgba(8,12,20,0.75), rgba(0,0,0,0.55));
  box-shadow:
    0 0 0 1px rgba(255,255,255,0.05) inset,
    0 0 40px rgba(0,243,255,0.2),
    0 20px 60px rgba(0,0,0,0.6);
  animation: cine-logo-pulse 2s ease-in-out infinite alternate;
}
@keyframes cine-logo-pulse {
  from { box-shadow: 0 0 0 1px rgba(255,255,255,0.05) inset, 0 0 30px rgba(0,243,255,0.15), 0 20px 60px rgba(0,0,0,0.6); }
  to   { box-shadow: 0 0 0 1px rgba(255,255,255,0.08) inset, 0 0 55px rgba(0,243,255,0.35), 0 20px 60px rgba(0,0,0,0.6); }
}
.cine-main-logo .fafo {
  font-size: clamp(28px, 7vw, 64px);
  font-weight: 900;
  letter-spacing: 0.28em;
  background: linear-gradient(180deg, #fff 0%, #00f3ff 45%, #007a99 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
  filter: drop-shadow(0 0 20px rgba(0,243,255,0.5));
  margin-bottom: 8px;
}
.cine-main-logo .toolbox {
  font-size: clamp(12px, 2vw, 16px);
  letter-spacing: 0.42em;
  color: rgba(232,232,236,0.85);
  text-transform: uppercase;
}
.cine-main-logo .tag {
  margin-top: 14px;
  font-size: 11px;
  color: rgba(0,243,255,0.7);
  letter-spacing: 0.2em;
}

/* HUD chrome */
.cine-hud {
  position: absolute; z-index: 5;
  left: 0; right: 0; bottom: 0;
  padding: 12px 16px 14px;
  display: flex; flex-wrap: wrap; gap: 10px; align-items: center;
  justify-content: space-between;
  background: linear-gradient(0deg, rgba(0,0,0,0.85), transparent);
  font-size: 11px;
  color: rgba(200,210,220,0.8);
}
.cine-hud .left, .cine-hud .right {
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
}
.cine-hud button {
  background: rgba(0,0,0,0.45);
  border: 1px solid rgba(0,243,255,0.35);
  color: #00f3ff;
  padding: 5px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.cine-hud button:hover {
  background: rgba(0,243,255,0.15);
  box-shadow: 0 0 10px rgba(0,243,255,0.3);
}
.cine-progress {
  position: absolute; left: 0; right: 0; bottom: 0; height: 3px;
  background: rgba(255,255,255,0.08); z-index: 6;
}
.cine-progress > i {
  display: block; height: 100%; width: 0%;
  background: linear-gradient(90deg, #00f3ff, #ff4500);
  box-shadow: 0 0 8px #00f3ff;
  transition: width 0.05s linear;
}
.cine-skip-hint {
  position: absolute; top: 14px; right: 16px; z-index: 5;
  font-size: 11px; letter-spacing: 0.12em;
  color: rgba(200,210,220,0.55);
  text-transform: uppercase;
}
.cine-skip-hint kbd {
  border: 1px solid rgba(255,255,255,0.25);
  border-radius: 3px;
  padding: 1px 6px;
  margin: 0 3px;
  color: #00f3ff;
  font-family: inherit;
}
.cine-screen-label {
  position: absolute; top: 14px; left: 16px; z-index: 5;
  font-size: 10px; letter-spacing: 0.2em;
  color: rgba(0,243,255,0.55);
  text-transform: uppercase;
}
.cine-media-label {
  max-width: 42vw;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  opacity: 0.75;
}

/* CRT scanlines */
.cine-crt {
  position: absolute; inset: 0; z-index: 4; pointer-events: none;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0,0,0,0.12) 2px,
    rgba(0,0,0,0.12) 3px
  );
  mix-blend-mode: multiply;
  opacity: 0.45;
}

@media (prefers-reduced-motion: reduce) {
  .cine-i-char { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; }
  .cine-staff { animation: none !important; }
  .cine-bg-synth::after { animation: none !important; }
}
`;
        document.head.appendChild(style);
    }

    function el(tag, cls, html) {
        const n = document.createElement(tag);
        if (cls) n.className = cls;
        if (html != null) n.innerHTML = html;
        return n;
    }

    /**
     * Run the full cinematic sequence.
     * @param {{ force?: boolean }} opts
     * @returns {Promise<void>}
     */
    async function play(opts) {
        opts = opts || {};
        prefs = loadPrefs();
        if (!opts.force && prefs.skipOnLaunch) {
            return;
        }

        injectStyles();
        document.body.classList.add('cine-active');

        const root = el('div', 'cine-root');
        root.id = 'cinematicIntro';
        root.setAttribute('role', 'dialog');
        root.setAttribute('aria-label', 'Launch intro sequence');

        const screens = [
            {
                id: 'neon',
                slot: 'bg-neon',
                label: 'PRODUCTION · 1 / 3',
                buildFg: buildNeonScreen
            },
            {
                id: 'producer',
                slot: 'bg-producer',
                label: 'PRODUCTION · 2 / 3',
                buildFg: buildProducerScreen
            },
            {
                id: 'main',
                slot: 'bg-main',
                label: 'PRODUCTION · 3 / 3',
                buildFg: buildMainScreen
            }
        ];

        const stages = [];
        for (const s of screens) {
            const stage = el('div', 'cine-stage');
            stage.dataset.screen = s.id;
            stage.dataset.slot = s.slot;

            const synth = el('div', 'cine-bg-synth');
            stage.appendChild(synth);

            const video = document.createElement('video');
            video.className = 'cine-bg-video';
            video.muted = prefs.muteVideo !== false;
            video.loop = true;
            video.playsInline = true;
            video.preload = 'auto';
            video.setAttribute('playsinline', '');
            video.setAttribute('webkit-playsinline', '');
            video.disablePictureInPicture = true;
            // Keep decode cost low even if a full-res file slips through
            try { video.setAttribute('width', String(playTarget().maxW)); } catch (_) { /* ignore */ }
            video.style.display = 'none';
            stage.appendChild(video);

            stage.appendChild(el('div', 'cine-vignette'));
            stage.appendChild(el('div', 'cine-crt'));

            const fg = el('div', 'cine-fg');
            s.buildFg(fg, stage);
            stage.appendChild(fg);

            stages.push({ meta: s, stage, video, synth });
            root.appendChild(stage);
        }

        // HUD
        const skipHint = el('div', 'cine-skip-hint', 'Skip <kbd>Space</kbd> · Hold <kbd>S</kbd> skip all');
        const screenLabel = el('div', 'cine-screen-label', screens[0].label);
        const progress = el('div', 'cine-progress', '<i></i>');
        const hud = el('div', 'cine-hud');
        hud.innerHTML = `
          <div class="left">
            <button type="button" data-act="folder">📁 BG folder</button>
            <button type="button" data-act="file">🎬 BG video</button>
            <button type="button" data-act="mute">${prefs.muteVideo !== false ? '🔇 Muted' : '🔊 Sound'}</button>
            <span class="cine-media-label" data-media-label>…</span>
          </div>
          <div class="right">
            <button type="button" data-act="skip">Skip ›</button>
            <button type="button" data-act="skipall">Skip all</button>
            <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:10px;">
              <input type="checkbox" data-act="skiplaunch" ${prefs.skipOnLaunch ? 'checked' : ''}>
              Skip intros next launch
            </label>
          </div>`;
        root.appendChild(skipHint);
        root.appendChild(screenLabel);
        root.appendChild(progress);
        root.appendChild(hud);
        document.body.appendChild(root);

        let idx = 0;
        let timer = null;
        let raf = null;
        let startedAt = 0;
        let settled = false;
        let currentRevoke = null;
        const progressBar = progress.querySelector('i');
        const mediaLabel = hud.querySelector('[data-media-label]');

        function clearTimers() {
            if (timer) { clearTimeout(timer); timer = null; }
            if (raf) { cancelAnimationFrame(raf); raf = null; }
        }

        function stopVideo(stageObj) {
            try {
                stageObj.video.pause();
                stageObj.video.removeAttribute('src');
                stageObj.video.load();
                stageObj.video.style.display = 'none';
            } catch (_) { /* ignore */ }
            if (currentRevoke) {
                try { URL.revokeObjectURL(currentRevoke); } catch (_) { /* ignore */ }
                currentRevoke = null;
            }
        }

        async function loadBg(stageObj) {
            const loadToken = (stageObj._loadToken = (stageObj._loadToken || 0) + 1);
            stopVideo(stageObj);
            // Keep synth visible while 4K → proxy encodes so the intro never freezes on a black frame
            stageObj.synth.style.opacity = '1';
            stageObj.video.style.display = 'none';
            if (mediaLabel) mediaLabel.textContent = 'Loading BG…';

            const info = await resolveVideoUrl(stageObj.meta.slot, (msg) => {
                if (mediaLabel && !settled && stages[idx] === stageObj) mediaLabel.textContent = msg;
            });
            const stale = settled || stages[idx] !== stageObj || stageObj._loadToken !== loadToken;
            if (stale) {
                if (info && info.revoke) {
                    try { URL.revokeObjectURL(info.revoke); } catch (_) { /* ignore */ }
                }
                return;
            }
            if (mediaLabel) mediaLabel.textContent = info.label || '';
            if (info.url) {
                stageObj.video.src = info.url;
                stageObj.video.style.display = 'block';
                // Fade synth under the light proxy once frames are rolling
                stageObj.synth.style.opacity = '0.15';
                currentRevoke = info.revoke || null;
                try {
                    stageObj.video.muted = prefs.muteVideo !== false;
                    await stageObj.video.play();
                    if (stages[idx] === stageObj && stageObj._loadToken === loadToken) {
                        stageObj.synth.style.opacity = '0';
                    }
                } catch (e) {
                    // Autoplay with sound often blocked — force mute retry
                    stageObj.video.muted = true;
                    try {
                        await stageObj.video.play();
                        if (stages[idx] === stageObj && stageObj._loadToken === loadToken) {
                            stageObj.synth.style.opacity = '0';
                        }
                    } catch (_) {
                        stageObj.synth.style.opacity = '1';
                        stageObj.video.style.display = 'none';
                    }
                }
            } else {
                stageObj.synth.style.opacity = '1';
                stageObj.video.style.display = 'none';
            }
        }

        function tickProgress() {
            const t = Date.now() - startedAt;
            const p = Math.min(1, t / DURATION_MS);
            if (progressBar) progressBar.style.width = (p * 100) + '%';
            if (p < 1 && !settled) raf = requestAnimationFrame(tickProgress);
        }

        async function showScreen(i) {
            clearTimers();
            idx = i;
            stages.forEach((s, n) => {
                s.stage.classList.toggle('active', n === i);
                if (n !== i) stopVideo(s);
            });
            screenLabel.textContent = stages[i].meta.label;
            if (progressBar) progressBar.style.width = '0%';
            await loadBg(stages[i]);

            // Restart neon animation if revisiting
            if (stages[i].meta.id === 'neon') {
                restartNeonAnim(stages[i].stage);
            }

            startedAt = Date.now();
            tickProgress();
            timer = setTimeout(() => advance(1), DURATION_MS);
        }

        function advance(delta) {
            if (settled) return;
            const next = idx + (delta || 1);
            if (next >= stages.length) {
                finish();
            } else if (next < 0) {
                showScreen(0);
            } else {
                showScreen(next);
            }
        }

        function finish() {
            if (settled) return;
            settled = true;
            clearTimers();
            stages.forEach(stopVideo);
            savePrefs({ lastPlayedAt: Date.now() });
            root.classList.add('cine-exit');
            setTimeout(() => {
                root.remove();
                document.body.classList.remove('cine-active');
            }, 480);
            cleanup();
            resolveDone();
        }

        let resolveDone;
        const donePromise = new Promise((r) => { resolveDone = r; });

        function onKey(e) {
            if (settled) return;
            if (e.code === 'Space' || e.code === 'Enter' || e.key === ' ') {
                e.preventDefault();
                advance(1);
            } else if (e.key === 's' || e.key === 'S' || e.key === 'Escape') {
                e.preventDefault();
                finish();
            }
        }

        function onClickRoot(e) {
            // Don't skip when clicking HUD buttons
            if (e.target.closest('.cine-hud')) return;
            if (e.target.closest('button')) return;
            advance(1);
        }

        async function onHudClick(e) {
            const btn = e.target.closest('[data-act]');
            if (!btn) {
                if (e.target.matches('input[data-act="skiplaunch"]')) {
                    savePrefs({ skipOnLaunch: !!e.target.checked });
                }
                return;
            }
            const act = btn.getAttribute('data-act');
            const slot = stages[idx].meta.slot;
            if (act === 'skip') advance(1);
            else if (act === 'skipall') finish();
            else if (act === 'mute') {
                const next = !(prefs.muteVideo !== false);
                savePrefs({ muteVideo: next });
                btn.textContent = next ? '🔇 Muted' : '🔊 Sound';
                stages[idx].video.muted = next;
            } else if (act === 'folder') {
                const h = await pickDirectory(slot);
                if (h) await loadBg(stages[idx]);
            } else if (act === 'file') {
                const f = await pickVideoFile(slot, (msg) => {
                    if (mediaLabel && !settled) mediaLabel.textContent = msg;
                });
                if (f) await loadBg(stages[idx]);
            }
        }

        function cleanup() {
            document.removeEventListener('keydown', onKey, true);
            root.removeEventListener('click', onClickRoot);
            hud.removeEventListener('click', onHudClick);
            hud.removeEventListener('change', onHudClick);
        }

        document.addEventListener('keydown', onKey, true);
        root.addEventListener('click', onClickRoot);
        hud.addEventListener('click', onHudClick);
        hud.addEventListener('change', onHudClick);

        await showScreen(0);
        return donePromise;
    }

    function buildNeonScreen(fg, stage) {
        const ninjaStage = el('div', 'cine-ninja-stage');
        const char = el('div', 'cine-i-char');
        char.innerHTML = `
          <div class="cine-staff"><div class="blade"></div><div class="hilt"></div></div>
          <div class="cine-hand l"></div>
          <div class="cine-hand r"></div>
          <div class="cine-i-body"><div class="cine-i-eye"></div></div>
        `;
        ninjaStage.appendChild(char);
        stage.appendChild(ninjaStage);

        const lockup = el('div', 'cine-neon-lockup');
        lockup.innerHTML = `
          <div class="by">Brought to you by</div>
          <span class="at">@</span>
          <span class="neon-word">NEON</span>
          <span class="ninja-word" data-ninja-word>NINJA</span><span class="cine-final-i" data-final-i>I</span>
        `;
        fg.appendChild(lockup);
        fg.appendChild(el('div', 'cine-sub', 'EST. NEON DISTRICT · SOFTWARE PRODUCTIONS'));

        // After parkour (~3.6s), snap character to text and show final I
        const landTimer = setTimeout(() => landNinjaI(stage), 3600);
        stage._cineLandTimer = landTimer;
    }

    function landNinjaI(stage) {
        const char = stage.querySelector('.cine-i-char');
        const word = stage.querySelector('[data-ninja-word]');
        const finalI = stage.querySelector('[data-final-i]');
        if (!char || !word) return;

        const wr = word.getBoundingClientRect();
        const sr = stage.getBoundingClientRect();
        // Place just after NINJA
        const xPct = ((wr.right - sr.left + 18) / sr.width) * 100;
        const yPct = ((wr.top + wr.height * 0.45 - sr.top) / sr.height) * 100;
        char.style.setProperty('--land-x', xPct + '%');
        char.style.setProperty('--land-y', yPct + '%');
        char.classList.add('landed');

        setTimeout(() => {
            char.classList.add('fade-char');
            if (finalI) finalI.classList.add('show');
        }, 420);
    }

    function restartNeonAnim(stage) {
        if (stage._cineLandTimer) clearTimeout(stage._cineLandTimer);
        const char = stage.querySelector('.cine-i-char');
        const finalI = stage.querySelector('[data-final-i]');
        if (finalI) finalI.classList.remove('show');
        if (char) {
            char.classList.remove('landed', 'fade-char');
            // reflow restart
            void char.offsetWidth;
            char.style.animation = 'none';
            void char.offsetWidth;
            char.style.animation = '';
        }
        stage._cineLandTimer = setTimeout(() => landNinjaI(stage), 3600);
    }

    function buildProducerScreen(fg) {
        const box = el('div', 'cine-producer');
        box.innerHTML = `
          <span class="label">Producer</span>
          <span class="credit">⟦⟧Sir⟬⟭Khan⟬⟭Deez⟬⟭Nutz⟦⟧</span>
          <span class="marks">©™ · ALL RIGHTS RESERVED · NO REFUNDS</span>
        `;
        fg.appendChild(box);
        fg.appendChild(el('div', 'cine-sub', 'A NEON NINJA PRESENTATION'));
    }

    function buildMainScreen(fg) {
        const logo = el('div', 'cine-main-logo');
        logo.innerHTML = `
          <div class="fafo">FAFO</div>
          <div class="toolbox">AI HTML TOOLBOX</div>
          <div class="tag">LOCAL · NO CLOUD · FULL SEND</div>
        `;
        fg.appendChild(logo);
        fg.appendChild(el('div', 'cine-sub', 'LOADING CONTROL SURFACE…'));
    }

    /**
     * Small settings helper for the main launcher UI.
     */
    function openSettings(anchorBtn) {
        injectStyles();
        prefs = loadPrefs();
        const existing = document.getElementById('cineSettingsPop');
        if (existing) { existing.remove(); return; }

        const pop = el('div', '');
        pop.id = 'cineSettingsPop';
        pop.style.cssText = [
            'position:fixed', 'z-index:100000', 'right:16px', 'top:60px',
            'width:min(360px,92vw)', 'padding:16px',
            'background:#0c0c12', 'border:1px solid rgba(0,243,255,0.35)',
            'border-radius:12px', 'box-shadow:0 12px 40px rgba(0,0,0,0.55)',
            'font-size:12px', 'color:#e8e8ec'
        ].join(';');
        pop.innerHTML = `
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <strong style="color:#00f3ff;letter-spacing:.08em;">INTRO CINEMATICS</strong>
            <button type="button" data-x style="background:none;border:none;color:#888;cursor:pointer;font-size:16px;">✕</button>
          </div>
          <label style="display:flex;gap:8px;align-items:center;margin-bottom:10px;cursor:pointer;">
            <input type="checkbox" data-skip ${prefs.skipOnLaunch ? 'checked' : ''}>
            Skip intros on launch (daily driver)
          </label>
          <label style="display:flex;gap:8px;align-items:center;margin-bottom:14px;cursor:pointer;">
            <input type="checkbox" data-mute ${prefs.muteVideo !== false ? 'checked' : ''}>
            Mute background videos
          </label>
          <p style="color:#888;margin-bottom:10px;line-height:1.4;">
            Each of the 3 screens can use its own video folder (random pick) or a single file. Chrome/Edge recommended for folders.
            <br><br>
            <strong style="color:#c8d0dc;">4K / heavy clips auto-scale to ${playTarget().label}</strong> (short ~8s loop, cached) so intros stay smooth on any machine.
          </p>
          <div style="display:grid;gap:8px;margin-bottom:12px;">
            <button type="button" data-folder="bg-neon" class="ui-btn ghost" style="width:100%">📁 Neon Ninja BG folder</button>
            <button type="button" data-folder="bg-producer" class="ui-btn ghost" style="width:100%">📁 Producer BG folder</button>
            <button type="button" data-folder="bg-main" class="ui-btn ghost" style="width:100%">📁 Main / FAFO BG folder</button>
          </div>
          <button type="button" data-replay class="ui-btn primary" style="width:100%">▶ Replay intro now</button>
        `;
        // Style buttons if ui-btn missing
        pop.querySelectorAll('button[data-folder],button[data-replay]').forEach(b => {
            if (!b.classList.contains('ui-btn')) {
                b.style.cssText += ';background:transparent;border:1px solid #00f3ff;color:#00f3ff;padding:8px;border-radius:6px;cursor:pointer;';
            }
        });
        document.body.appendChild(pop);

        pop.querySelector('[data-x]').onclick = () => pop.remove();
        pop.querySelector('[data-skip]').onchange = (e) => savePrefs({ skipOnLaunch: e.target.checked });
        pop.querySelector('[data-mute]').onchange = (e) => savePrefs({ muteVideo: e.target.checked });
        pop.querySelectorAll('[data-folder]').forEach(btn => {
            btn.onclick = async () => {
                await pickDirectory(btn.getAttribute('data-folder'));
                btn.textContent = '✓ ' + btn.textContent.replace(/^✓\s*/, '');
            };
        });
        pop.querySelector('[data-replay]').onclick = async () => {
            pop.remove();
            await play({ force: true });
        };

        // click outside
        setTimeout(() => {
            const closer = (e) => {
                if (!pop.contains(e.target) && e.target !== anchorBtn) {
                    pop.remove();
                    document.removeEventListener('mousedown', closer, true);
                }
            };
            document.addEventListener('mousedown', closer, true);
        }, 0);
    }

    /**
     * Collect muted BG clips from the 3 intro slots (folder/file picks).
     * Used by the launcher marquee — already proxy-scaled when needed.
     */
    async function getMarqueeClips(onStatus) {
        const slots = ['bg-neon', 'bg-producer', 'bg-main'];
        const out = [];
        for (const slot of slots) {
            try {
                const info = await resolveVideoUrl(slot, onStatus);
                if (info && info.url) {
                    out.push({
                        url: info.url,
                        label: info.label || slot,
                        slot,
                        revoke: info.revoke || null
                    });
                }
            } catch (_) { /* skip slot */ }
        }
        return out;
    }

    global.AIToolboxCinematic = {
        play,
        openSettings,
        getPrefs: () => loadPrefs(),
        setPrefs: savePrefs,
        playTarget,
        getMarqueeClips,
        resolveVideoUrl,
        DURATION_MS
    };
})(typeof window !== 'undefined' ? window : globalThis);
