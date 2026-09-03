/* FAFO Imagine HAVE/MISS painter
 * Run on grok.com/imagine/saved (bookmarklet from Imagine Vault, or paste in console).
 * Also paints every version tile when a post is opened.
 * Talks only to the local vault. Cyan = on disk, magenta = seen but not saved.
 */
(function fafoImaginePaint(global) {
  'use strict';
  const VAULT = 'http://127.0.0.1:18767';
  const UUID_RE = /(?:grok-video-|grok-image-|share-videos\/|share-images\/|generated\/|\/imagine\/(?:post\/|saved\/)?)([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i;
  const BARE = /\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b/i;
  const CSS = `
    .fafo-im-hud{position:fixed;right:16px;bottom:16px;z-index:2147483646;font:700 12px/1.3 Segoe UI,system-ui,sans-serif;
      color:#e8f6ff;background:rgba(6,10,18,.92);border:1px solid rgba(0,240,255,.45);border-radius:12px;padding:10px 12px;
      box-shadow:0 12px 40px rgba(0,0,0,.55),0 0 18px rgba(0,240,255,.18);pointer-events:none;max-width:240px}
    .fafo-im-hud b{display:block;letter-spacing:.08em;font-size:10px;color:#67e8f9;margin-bottom:6px}
    .fafo-im-have{outline:3px solid #00f0ff !important;box-shadow:0 0 16px #00f0ff, inset 0 0 0 1px rgba(0,240,255,.4) !important;border-radius:10px}
    .fafo-im-miss{outline:3px solid #ff2bd6 !important;box-shadow:0 0 16px #ff2bd6, inset 0 0 0 1px rgba(255,43,214,.4) !important;border-radius:10px}
    .fafo-im-stamp{position:absolute;top:8px;left:8px;z-index:2;font:800 11px/1 Segoe UI,system-ui,sans-serif;
      letter-spacing:.08em;padding:5px 8px;border-radius:999px;pointer-events:none}
    .fafo-im-stamp.have{color:#001018;background:#00f0ff;box-shadow:0 0 12px #00f0ff}
    .fafo-im-stamp.miss{color:#fff;background:#ff2bd6;box-shadow:0 0 12px #ff2bd6}
    .fafo-im-compact>.fafo-im-stamp{font-size:8px;padding:3px 5px;top:4px;left:4px}
  `;

  function idsFrom(text) {
    const s = String(text || '');
    let m = UUID_RE.exec(s);
    if (m) return m[1].toLowerCase();
    if (/grok-video|vidgen|assets\.grok|imagine-public|share-videos|share-images/i.test(s)) {
      m = BARE.exec(s);
      if (m) return m[1].toLowerCase();
    }
    return '';
  }

  function harvestNode(el) {
    if (!el || el.nodeType !== 1) return '';
    const bits = [
      el.getAttribute('src'), el.getAttribute('poster'), el.getAttribute('href'),
      el.getAttribute('data-src'), el.currentSrc, el.src,
    ];
    try {
      const st = getComputedStyle(el);
      bits.push(st.backgroundImage);
    } catch (_) {}
    for (let i = 0; i < bits.length; i++) {
      const id = idsFrom(bits[i]);
      if (id) return id;
    }
    return '';
  }

  function closestCard(el) {
    if (!el) return el;
    const mediaRect = el.getBoundingClientRect();
    let n = el;
    let best = el;
    for (let i = 0; i < 14 && n && n !== document.body; i += 1, n = n.parentElement) {
      const r = n.getBoundingClientRect();
      if (r.width < 36 || r.height < 36) continue;
      if (r.width > window.innerWidth * 0.94 && r.height > window.innerHeight * 0.72) break;
      const mw = Math.max(mediaRect.width, 36);
      const mh = Math.max(mediaRect.height, 36);
      if (r.width > mw * 2.6 && r.height > mh * 2.8 && r.width > 280) break;
      best = n;
      if (r.width <= 880 && r.height <= 1100) return n;
    }
    return best.closest('article, a, [role="listitem"], figure, li') || best;
  }

  function stamp(card, have) {
    card.classList.toggle('fafo-im-have', !!have);
    card.classList.toggle('fafo-im-miss', !have);
    const box = card.getBoundingClientRect();
    card.classList.toggle('fafo-im-compact', box.width < 150 || box.height < 150);
    card.style.position = card.style.position || 'relative';
    let badge = card.querySelector(':scope > .fafo-im-stamp');
    if (!badge) {
      badge = document.createElement('div');
      badge.className = 'fafo-im-stamp';
      card.appendChild(badge);
    }
    badge.className = 'fafo-im-stamp ' + (have ? 'have' : 'miss');
    badge.textContent = have ? 'HAVE' : 'MISS';
  }

  async function loadMap() {
    const r = await fetch(VAULT + '/ids', { cache: 'no-store' });
    const j = await r.json();
    return (j && j.items) || {};
  }

  function paint(map) {
    const seen = new Set();
    let have = 0, miss = 0, marked = 0;
    const nodes = document.querySelectorAll('img, video, source, a[href], [style*="background"], [poster]');
    nodes.forEach((node) => {
      const id = harvestNode(node);
      if (!id || seen.has(id + node.tagName)) return;
      seen.add(id + node.tagName);
      const rec = map[id];
      if (!rec) return;
      const card = closestCard(node);
      stamp(card, !!rec.hasFile);
      marked++;
      if (rec.hasFile) have++; else miss++;
    });
    let hud = document.getElementById('fafo-im-hud');
    if (!hud) {
      hud = document.createElement('div');
      hud.id = 'fafo-im-hud';
      hud.className = 'fafo-im-hud';
      document.documentElement.appendChild(hud);
    }
    hud.innerHTML = '<b>IMAGINE VAULT</b>Cyan HAVE ' + have + '<br>Magenta MISS ' + miss +
      '<br><span style="color:#94a3b8;font-weight:600">' + marked + ' tiles painted</span>';
    return { have, miss, marked };
  }

  async function run() {
    if (!document.getElementById('fafo-im-css')) {
      const s = document.createElement('style');
      s.id = 'fafo-im-css';
      s.textContent = CSS;
      document.documentElement.appendChild(s);
    }
    try {
      const map = await loadMap();
      paint(map);
      if (!global.__fafoImObs) {
        let t = 0;
        const obs = new MutationObserver(() => {
          clearTimeout(t);
          t = setTimeout(() => loadMap().then(paint).catch(() => {}), 400);
        });
        obs.observe(document.body || document.documentElement, { childList: true, subtree: true });
        global.__fafoImObs = obs;
      }
    } catch (e) {
      let hud = document.getElementById('fafo-im-hud');
      if (!hud) {
        hud = document.createElement('div');
        hud.id = 'fafo-im-hud';
        hud.className = 'fafo-im-hud';
        document.documentElement.appendChild(hud);
      }
      hud.innerHTML = '<b>IMAGINE VAULT</b>Vault offline — open Imagine Vault in the toolbox and Start vault, then click Paint again.';
    }
  }

  global.FAFOImaginePaint = run;
  run();
})(typeof window !== 'undefined' ? window : this);
