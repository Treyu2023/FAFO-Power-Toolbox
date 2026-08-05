/**
 * FAFO Mythos — adventure unlocks, day-rotating paths, dragon ban, local vault.
 * Secrets stay in localStorage on this machine only.
 */
(function (global) {
  'use strict';

  const R = () => global.FAFO_ROADMAP;
  const P = () => (R() && R().mythos && R().mythos.storagePrefix) || 'fafo.mythos.';

  function key(k) {
    return P() + k;
  }

  function getJson(k, fallback) {
    try {
      const raw = localStorage.getItem(key(k));
      return raw ? JSON.parse(raw) : fallback;
    } catch (_) {
      return fallback;
    }
  }

  function setJson(k, v) {
    try {
      localStorage.setItem(key(k), JSON.stringify(v));
    } catch (e) {
      console.warn('[mythos] storage', e);
    }
  }

  /** Day key YYYY-MM-DD local — paths rotate daily */
  function dayKey(d) {
    const x = d || new Date();
    return x.getFullYear() + '-' + String(x.getMonth() + 1).padStart(2, '0') + '-' + String(x.getDate()).padStart(2, '0');
  }

  function dayIndex() {
    // Stable 0..2 from date string
    const s = dayKey();
    let h = 0;
    for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
    return h % 3;
  }

  /**
   * Three access paths — which one works rotates by day.
   * pathId 0 = Lodge (default story you described)
   * pathId 1 = Cartographer (map pin must be cyan after bookshelf)
   * pathId 2 = Architect (tower landmark after bookshelf)
   */
  const PATHS = [
    {
      id: 'lodge',
      name: 'Lodge path',
      needRunePos: 2,
      needRuneRot: 180,
      needCandle: true,
      needGreenBook: true,
      needTree: true,
      extra: null,
    },
    {
      id: 'cartographer',
      name: 'Cartographer path',
      needRunePos: 0,
      needRuneRot: 90,
      needCandle: true,
      needGreenBook: true,
      needTree: true,
      extra: 'pin-cyan',
    },
    {
      id: 'architect',
      name: 'Architect path',
      needRunePos: 1,
      needRuneRot: 270,
      needCandle: true,
      needGreenBook: true,
      needTree: true,
      extra: 'tower-landmark',
    },
  ];

  function activePath() {
    return PATHS[dayIndex()];
  }

  function defaultAdventure() {
    return {
      day: dayKey(),
      runeRot: 0,
      runePos: 0,
      candleTilt: false,
      greenBookOpened: false,
      gardenUnlocked: false,
      treeTouched: false,
      /** decorative gem states still used by path extras */
      ring: 'spring',
      pin: 'amber',
      tower: 'short',
    };
  }

  function getAdventure() {
    let a = getJson('adventure', null);
    if (!a || typeof a !== 'object') a = defaultAdventure();
    // New calendar day → soft reset of path progress (keep vault)
    if (a.day !== dayKey()) {
      const kept = {
        ring: a.ring,
        pin: a.pin,
        tower: a.tower,
      };
      a = { ...defaultAdventure(), ...kept, day: dayKey() };
      // Don't keep garden open across days — new path
      a.gardenUnlocked = false;
      a.greenBookOpened = false;
      a.candleTilt = false;
      a.treeTouched = false;
      setJson('adventure', a);
      setJson('unlocked', false);
    }
    // defaults
    if (typeof a.runeRot !== 'number') a.runeRot = 0;
    if (typeof a.runePos !== 'number') a.runePos = 0;
    a.candleTilt = !!a.candleTilt;
    a.greenBookOpened = !!a.greenBookOpened;
    a.gardenUnlocked = !!a.gardenUnlocked;
    a.treeTouched = !!a.treeTouched;
    return a;
  }

  function saveAdventure(a) {
    setJson('adventure', a);
    return a;
  }

  function patchAdventure(patch) {
    const a = { ...getAdventure(), ...patch };
    return saveAdventure(a);
  }

  /** Click rune: rotate 90° */
  function rotateRune() {
    const a = getAdventure();
    a.runeRot = (a.runeRot + 90) % 360;
    return saveAdventure(a);
  }

  /** Move rune to next of 3 positions */
  function moveRune() {
    const a = getAdventure();
    a.runePos = (a.runePos + 1) % 3;
    return saveAdventure(a);
  }

  function toggleCandle() {
    const a = getAdventure();
    a.candleTilt = !a.candleTilt;
    return saveAdventure(a);
  }

  /** Bookshelf appears only when today's path rune requirements are met */
  function isBookshelfVisible() {
    const a = getAdventure();
    const p = activePath();
    return a.runePos === p.needRunePos && a.runeRot === p.needRuneRot;
  }

  function openGreenBook() {
    const a = getAdventure();
    if (!isBookshelfVisible()) {
      return { ok: false, reason: 'no-shelf' };
    }
    if (!a.candleTilt) {
      return { ok: false, reason: 'candle' };
    }
    a.greenBookOpened = true;
    a.gardenUnlocked = true;
    saveAdventure(a);
    return { ok: true };
  }

  function touchTree() {
    const a = getAdventure();
    if (!a.gardenUnlocked) {
      return { ok: false, reason: 'no-garden' };
    }
    const p = activePath();
    // Path extras: cartographer needs pin cyan; architect needs tower landmark
    if (p.extra === 'pin-cyan' && a.pin !== 'cyan') {
      return { ok: false, reason: 'need-pin-cyan' };
    }
    if (p.extra === 'tower-landmark' && a.tower !== 'landmark') {
      return { ok: false, reason: 'need-tower' };
    }
    a.treeTouched = true;
    saveAdventure(a);
    // Unlock chamber if path complete
    const check = evaluatePathComplete(a);
    if (check) {
      setUnlocked(true);
      return { ok: true, unlocked: true };
    }
    return { ok: true, unlocked: false };
  }

  function evaluatePathComplete(a) {
    a = a || getAdventure();
    const p = activePath();
    if (a.runePos !== p.needRunePos || a.runeRot !== p.needRuneRot) return false;
    if (p.needCandle && !a.candleTilt) return false;
    if (p.needGreenBook && !a.greenBookOpened) return false;
    if (p.needTree && !a.treeTouched) return false;
    if (p.extra === 'pin-cyan' && a.pin !== 'cyan') return false;
    if (p.extra === 'tower-landmark' && a.tower !== 'landmark') return false;
    if (isDragonBanning()) return false;
    return true;
  }

  function isUnlocked() {
    return !!getJson('unlocked', false) && !isDragonBanning() && evaluatePathComplete();
  }

  function setUnlocked(v) {
    setJson('unlocked', !!v);
  }

  function dragonBanUntil() {
    return Number(getJson('dragonBanUntil', 0)) || 0;
  }

  function isDragonBanning() {
    return Date.now() < dragonBanUntil();
  }

  function banDragon() {
    const ms = (R() && R().mythos && R().mythos.dragonBanMs) || 300000;
    const until = Date.now() + ms;
    setJson('dragonBanUntil', until);
    setUnlocked(false);
    // Soft reset path progress so they re-walk
    const a = getAdventure();
    a.gardenUnlocked = false;
    a.greenBookOpened = false;
    a.treeTouched = false;
    a.candleTilt = false;
    saveAdventure(a);
    return until;
  }

  function banRemainingMs() {
    return Math.max(0, dragonBanUntil() - Date.now());
  }

  function tryUnlock() {
    if (isDragonBanning()) {
      return { ok: false, reason: 'dragon', until: dragonBanUntil() };
    }
    if (evaluatePathComplete()) {
      setUnlocked(true);
      return { ok: true };
    }
    return { ok: false, reason: 'path', path: activePath(), adventure: getAdventure() };
  }

  /** Decorative gem cycles (still used for path extras + pretty pages) */
  const RING_CYCLE = ['spring', 'summer', 'fall', 'winter'];
  const PIN_CYCLE = ['amber', 'cyan', 'violet', 'ember'];
  const TOWER_CYCLE = ['short', 'mid', 'landmark'];

  function cycleGem(part) {
    const cycles = { ring: RING_CYCLE, pin: PIN_CYCLE, tower: TOWER_CYCLE };
    const list = cycles[part];
    if (!list) return getAdventure();
    const a = getAdventure();
    const i = Math.max(0, list.indexOf(a[part]));
    a[part] = list[(i + 1) % list.length];
    return saveAdventure(a);
  }

  // Back-compat aliases used by older canvas code
  function getStates() {
    const a = getAdventure();
    return { ring: a.ring, pin: a.pin, tower: a.tower };
  }
  function setState(part, value) {
    const a = getAdventure();
    a[part] = value;
    return saveAdventure(a);
  }
  function cycle(part) {
    return cycleGem(part);
  }
  function checkCombo() {
    return evaluatePathComplete();
  }

  /** Site vault — local only */
  function getVault() {
    const base = {
      sites: [],
      customerPasswords: [],
      verifoneBackdoors: defaultVerifoneBackdoorSheet(),
      puttyNotes: defaultPuttyScroll(),
      scrapeLog: [],
      updatedAt: null,
    };
    const v = getJson('vault', base) || base;
    if (!Array.isArray(v.sites)) v.sites = [];
    if (!Array.isArray(v.customerPasswords)) v.customerPasswords = [];
    if (!Array.isArray(v.verifoneBackdoors) || !v.verifoneBackdoors.length) {
      v.verifoneBackdoors = defaultVerifoneBackdoorSheet();
    }
    if (!v.puttyNotes) v.puttyNotes = defaultPuttyScroll();
    if (!Array.isArray(v.scrapeLog)) v.scrapeLog = [];
    return v;
  }

  function saveVault(v) {
    v.updatedAt = new Date().toISOString();
    setJson('vault', v);
    return v;
  }

  function defaultVerifoneBackdoorSheet() {
    return [
      { system: 'Commander / VAPS', model: 'generic', role: 'tech / service menu', user: '', secret: '', notes: 'Fill from OEM/site packet' },
      { system: 'Commander / VAPS', model: 'generic', role: 'manager', user: '', secret: '', notes: 'Usually per-site' },
      { system: 'Commander / VAPS', model: 'generic', role: 'cashier', user: '', secret: '', notes: '' },
      { system: 'Ruby / Sapphire / Topaz', model: 'legacy', role: 'manager', user: '', secret: '', notes: '' },
      { system: 'Ruby / Sapphire / Topaz', model: 'legacy', role: 'tech', user: '', secret: '', notes: '' },
      { system: 'UX / PIN pad admin', model: 'MX / UX family', role: 'admin / config', user: '', secret: '', notes: '' },
      { system: 'CRIND / outdoor', model: 'Encore / FlexPay', role: 'tech menu', user: '', secret: '', notes: '' },
      { system: 'Site network gear', model: 'router / firewall', role: 'admin', user: '', secret: '', notes: '' },
      { system: 'TLS / ATG', model: 'Veeder-Root', role: 'console', user: '', secret: '', notes: '' },
      { system: 'CUSTOM', model: '', role: '', user: '', secret: '', notes: 'Add rows as needed' },
    ];
  }

  function defaultPuttyScroll() {
    return [
      'VERIFONE / PUTTY FIELD SCROLL (generic — customize per site)',
      '',
      '1. Confirm site IP / VPN / jump host with MOD or ticket.',
      '2. Open PuTTY (or equivalent SSH/serial).',
      '3. Session: Host = site controller IP; Port = 22 (SSH) or site-specific.',
      '4. Connection type: SSH unless serial console is required.',
      '5. Saved sessions: name by SITE CODE — never commit passwords into git.',
      '6. First login: use approved tech credentials; escalate for root only if needed.',
      '7. Before changes: capture running config / export if available.',
      '8. After changes: verify payment path + one FP auth if fuel-related.',
      '9. Log ticket: what changed, who approved, rollback note.',
      '10. Close session cleanly; do not leave idle roots open on counter PCs.',
      '',
      'Serial tip: correct COM port, baud (often 9600/115200 — verify plate/docs).',
      '',
      'This scroll is a template. Site-specific hosts go in the vault tables.',
    ].join('\n');
  }

  function scrapePasswordsFromText(text, sourceLabel) {
    const src = sourceLabel || 'text';
    const lines = String(text || '').replace(/\r/g, '').split('\n');
    const hits = [];
    const seen = new Set();
    const passRe = [
      /(?:\bUN\b|\buser(?:name)?\b|\blogin\b)\s*[=:]\s*(\S+).{0,40}?(?:\bPW\b|\bpass(?:word)?\b|\bpwd\b)\s*[=:]\s*(\S+)/i,
      /(?:\bPW\b|\bpass(?:word)?\b|\bpwd\b)\s*[=:]\s*(\S+).{0,40}?(?:\bUN\b|\buser(?:name)?\b)\s*[=:]\s*(\S+)/i,
      /(?:\bpass(?:word)?\b|\bpwd\b|\bPW\b)\s*[=:]\s*([^\s,;]{3,64})/i,
      /\b(manager|cashier|backdoor|tech|service|admin|root)\s+(?:pass(?:word)?|pw|login|pin)\s*[=:]?\s*([^\s,;]{3,64})/i,
      /pass(?:word)?\s+for\s+([^:=\n]{2,40})\s*[=:]\s*([^\s,;]{3,64})/i,
    ];

    function guessRole(line) {
      const l = line.toLowerCase();
      if (/backdoor|service tech|tech menu|diag/.test(l)) return 'backdoor';
      if (/manager|mgr|mod\b/.test(l)) return 'manager';
      if (/cashier|clerk|pos user/.test(l)) return 'cashier';
      if (/admin|root/.test(l)) return 'admin';
      if (/router|firewall|wifi/.test(l)) return 'network';
      return 'unknown';
    }

    function pushHit(row) {
      const secret = (row.secret || '').trim();
      if (!secret || secret.length < 3) return;
      if (/^(http|https|true|false|null|undefined)$/i.test(secret)) return;
      if (/^sk-[a-zA-Z0-9_-]{10,}$/i.test(secret)) {
        row.role = row.role || 'api-key';
        row.notes = (row.notes || '') + ' [possible API key — rotate if live]';
      }
      const k = [row.site, row.user, secret, row.role].join('|').toLowerCase();
      if (seen.has(k)) return;
      seen.add(k);
      hits.push({
        source: src,
        site: row.site || '',
        customer: row.customer || '',
        role: row.role || 'unknown',
        user: row.user || '',
        secret,
        notes: row.notes || '',
        confidence: row.confidence || 'medium',
        scrapedAt: new Date().toISOString(),
      });
    }

    let lastSite = '';
    let lastCustomer = '';
    for (let i = 0; i < lines.length; i++) {
      let line = lines[i].trim();
      if (!line) continue;
      line = line.replace(/\\id=[a-z0-9-]+\s*/gi, '').replace(/<[^>]+>/g, '').trim();
      if (!line) continue;

      const siteM = line.match(/\b(?:site|store|gpm|circle\s*k|customer)\s*[=:#-]?\s*(.+)$/i);
      if (siteM && siteM[1].length < 60) lastSite = siteM[1].trim();
      if (/^[A-Z][A-Za-z0-9 &'-]{2,40}$/.test(line) && /market|mart|oil|stop|grocery|circle|gpm|fafo/i.test(line)) {
        lastCustomer = line;
      }

      let m = line.match(passRe[0]);
      if (m) {
        pushHit({ site: lastSite, customer: lastCustomer, user: m[1], secret: m[2], role: guessRole(line), confidence: 'high' });
        continue;
      }
      m = line.match(passRe[1]);
      if (m) {
        pushHit({ site: lastSite, customer: lastCustomer, user: m[2], secret: m[1], role: guessRole(line), confidence: 'high' });
        continue;
      }
      m = line.match(passRe[3]);
      if (m) {
        pushHit({ site: lastSite, customer: lastCustomer, role: m[1].toLowerCase(), secret: m[2], confidence: 'high' });
        continue;
      }
      m = line.match(passRe[4]);
      if (m) {
        pushHit({ site: m[1].trim(), customer: lastCustomer, secret: m[2], role: guessRole(line), confidence: 'medium' });
        continue;
      }
      m = line.match(passRe[2]);
      if (m) {
        const prev = (lines[i - 1] || '').replace(/\\id=[a-z0-9-]+\s*/gi, '').trim();
        const um = prev.match(/(?:\bUN\b|\buser(?:name)?\b|\blogin\b)\s*[=:]\s*(\S+)/i);
        pushHit({
          site: lastSite,
          customer: lastCustomer,
          user: um ? um[1] : '',
          secret: m[1],
          role: guessRole(line + ' ' + prev),
          confidence: um ? 'high' : 'low',
        });
      }

      if (/\b(managers?|cashier|backdoor|tech)\s+pass/i.test(line) && i + 1 < lines.length) {
        const next = lines[i + 1].replace(/\\id=[a-z0-9-]+\s*/gi, '').trim();
        if (!/^(UN|user|login)\s*[=:]/i.test(next) && next.length >= 3 && next.length <= 40 && !/\s{3,}/.test(next)) {
          const roleM = line.match(/\b(managers?|cashier|backdoor|tech)\b/i);
          pushHit({
            site: lastSite,
            customer: lastCustomer,
            role: roleM ? roleM[1].toLowerCase() : 'unknown',
            secret: next.replace(/^(PW|pass(word)?)\s*[=:]\s*/i, ''),
            confidence: 'medium',
            notes: 'value on following line',
          });
        }
      }
    }
    return hits;
  }

  function mergeScrapedPasswords(hits, sourceLabel) {
    const v = getVault();
    const existing = new Set(
      (v.customerPasswords || []).map((r) => [r.site, r.user, r.secret].join('|').toLowerCase())
    );
    let added = 0;
    (hits || []).forEach((h) => {
      const k = [h.site, h.user, h.secret].join('|').toLowerCase();
      if (existing.has(k)) return;
      existing.add(k);
      v.customerPasswords.push(h);
      added++;
    });
    v.scrapeLog = v.scrapeLog || [];
    v.scrapeLog.unshift({
      at: new Date().toISOString(),
      source: sourceLabel || 'scrape',
      found: (hits || []).length,
      added,
    });
    v.scrapeLog = v.scrapeLog.slice(0, 30);
    saveVault(v);
    return { added, total: v.customerPasswords.length, found: (hits || []).length };
  }

  function demoSites() {
    return [
      { customer: 'Circle K', letter: 'C', city: 'Greensboro', sites: 4, tanks: 3, dispensers: 8, billed: 42000, lat: 36.07, lng: -79.79 },
      { customer: 'GPM', letter: 'G', city: 'Reidsville', sites: 2, tanks: 2, dispensers: 4, billed: 18000, lat: 36.35, lng: -79.66 },
      { customer: 'Apple Market', letter: 'A', city: 'South Boston', sites: 1, tanks: 2, dispensers: 6, billed: 9000, lat: 36.70, lng: -78.90 },
      { customer: 'FAFO Lab', letter: 'F', city: 'Home base', sites: 1, tanks: 1, dispensers: 2, billed: 1000, lat: 36.1, lng: -79.8 },
      { customer: 'High Falls Oil', letter: 'H', city: 'Greensboro', sites: 3, tanks: 4, dispensers: 10, billed: 31000, lat: 36.05, lng: -79.85 },
      { customer: 'West Side Market', letter: 'W', city: 'Sanford', sites: 1, tanks: 2, dispensers: 4, billed: 7000, lat: 35.48, lng: -79.18 },
      { customer: 'Loveleen Sites', letter: 'L', city: 'Lexington', sites: 2, tanks: 3, dispensers: 6, billed: 22000, lat: 35.82, lng: -80.25 },
      { customer: 'Tokheim Corner', letter: 'T', city: 'Eden', sites: 1, tanks: 2, dispensers: 3, billed: 5000, lat: 36.49, lng: -79.76 },
    ];
  }

  function letterHue(letter) {
    const L = (letter || 'A').toUpperCase().charCodeAt(0) - 65;
    const hues = [35, 50, 180, 200, 160, 120, 90, 280, 300, 320, 15, 190, 210, 140, 25, 260, 40, 0, 170, 220, 60, 240, 10, 185, 55, 310];
    return hues[((L % 26) + 26) % 26];
  }

  /** Soft progress hints without spoiling (for UI) */
  function pathProgressHint() {
    const a = getAdventure();
    const p = activePath();
    const steps = [];
    steps.push({
      id: 'rune',
      ok: a.runePos === p.needRunePos && a.runeRot === p.needRuneRot,
      label: 'The mark must rest correctly',
    });
    steps.push({ id: 'shelf', ok: isBookshelfVisible(), label: 'A shelf may reveal itself' });
    steps.push({ id: 'candle', ok: a.candleTilt, label: 'Something on the mantle tilts' });
    steps.push({ id: 'book', ok: a.greenBookOpened, label: 'A green volume opens a path' });
    steps.push({ id: 'garden', ok: a.gardenUnlocked, label: 'The garden is reachable' });
    steps.push({ id: 'tree', ok: a.treeTouched, label: 'The tree remembers' });
    if (p.extra === 'pin-cyan') steps.push({ id: 'extra', ok: a.pin === 'cyan', label: 'The map hums cyan' });
    if (p.extra === 'tower-landmark') steps.push({ id: 'extra', ok: a.tower === 'landmark', label: 'A tower stands as landmark' });
    return { pathName: p.name, pathId: p.id, day: dayKey(), steps, complete: evaluatePathComplete(a) };
  }

  global.FAFOMythos = {
    // adventure
    getAdventure,
    patchAdventure,
    rotateRune,
    moveRune,
    toggleCandle,
    isBookshelfVisible,
    openGreenBook,
    touchTree,
    evaluatePathComplete,
    activePath,
    PATHS,
    dayKey,
    dayIndex,
    pathProgressHint,
    // chamber
    tryUnlock,
    isUnlocked,
    setUnlocked,
    isDragonBanning,
    banDragon,
    banRemainingMs,
    dragonBanUntil,
    // gems back-compat
    getStates,
    setState,
    cycle,
    checkCombo,
    RING_CYCLE,
    PIN_CYCLE,
    TOWER_CYCLE,
    // vault
    getVault,
    saveVault,
    defaultPuttyScroll,
    defaultVerifoneBackdoorSheet,
    scrapePasswordsFromText,
    mergeScrapedPasswords,
    demoSites,
    letterHue,
  };
})(typeof window !== 'undefined' ? window : globalThis);
