/**
 * TaxForge shared helpers — localStorage, FX particles, toasts, demo Xero data.
 * Live Xero OAuth is scaffolded; secrets never hard-coded (enter client id locally).
 */
(function (global) {
  'use strict';

  const NS = 'taxforge.';
  const TaxForge = {};

  TaxForge.storage = {
    get(key, fallback) {
      try {
        const v = JSON.parse(localStorage.getItem(NS + key) || 'null');
        return v == null ? fallback : v;
      } catch (_) {
        return fallback;
      }
    },
    set(key, val) {
      localStorage.setItem(NS + key, JSON.stringify(val));
    },
    remove(key) {
      localStorage.removeItem(NS + key);
    },
  };

  TaxForge.toast = function (msg, ms) {
    let el = document.getElementById('tfToast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'tfToast';
      el.className = 'tf-toast';
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(TaxForge.toast._t);
    TaxForge.toast._t = setTimeout(() => el.classList.remove('show'), ms || 1800);
  };

  /** Soft particle field for tax suite pages */
  TaxForge.mountFx = function () {
    let c = document.getElementById('tfFx');
    if (!c) {
      c = document.createElement('canvas');
      c.id = 'tfFx';
      document.body.prepend(c);
    }
    const ctx = c.getContext('2d');
    const parts = [];
    function resize() {
      c.width = window.innerWidth;
      c.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);
    for (let i = 0; i < 48; i++) {
      parts.push({
        x: Math.random() * c.width,
        y: Math.random() * c.height,
        r: 0.6 + Math.random() * 1.8,
        vx: (Math.random() - 0.5) * 0.25,
        vy: -0.15 - Math.random() * 0.35,
        a: 0.15 + Math.random() * 0.4,
        hue: Math.random() > 0.55 ? '0,232,162' : Math.random() > 0.5 ? '255,209,102' : '61,158,255',
      });
    }
    function tick() {
      ctx.clearRect(0, 0, c.width, c.height);
      for (const p of parts) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.y < -10) { p.y = c.height + 10; p.x = Math.random() * c.width; }
        if (p.x < -10) p.x = c.width + 10;
        if (p.x > c.width + 10) p.x = -10;
        ctx.beginPath();
        ctx.fillStyle = `rgba(${p.hue},${p.a})`;
        ctx.shadowBlur = 8;
        ctx.shadowColor = `rgba(${p.hue},0.6)`;
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.shadowBlur = 0;
      requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  };

  TaxForge.burst = function (x, y, color) {
    // lightweight DOM burst for score / save moments
    const n = 14;
    for (let i = 0; i < n; i++) {
      const d = document.createElement('div');
      d.style.cssText = `position:fixed;left:${x}px;top:${y}px;width:6px;height:6px;border-radius:50%;
        background:${color || '#00e8a2'};pointer-events:none;z-index:150;
        box-shadow:0 0 10px ${color || '#00e8a2'};`;
      document.body.appendChild(d);
      const a = (Math.PI * 2 * i) / n;
      const dist = 40 + Math.random() * 50;
      d.animate([
        { transform: 'translate(0,0) scale(1)', opacity: 1 },
        { transform: `translate(${Math.cos(a) * dist}px,${Math.sin(a) * dist}px) scale(0)`, opacity: 0 },
      ], { duration: 600 + Math.random() * 300, easing: 'cubic-bezier(.2,.7,.2,1)' }).onfinish = () => d.remove();
    }
  };

  /** Demo org + accounts mimicking Xero-style structure */
  TaxForge.demoOrg = function () {
    return {
      id: 'demo-org-001',
      name: 'Summit Field Services LLC',
      baseCurrency: 'USD',
      country: 'US',
      financialYearEnd: '12-31',
      connected: false,
      mode: 'demo',
      lastSync: null,
    };
  };

  TaxForge.demoAccounts = function () {
    return [
      { code: '200', name: 'Sales', type: 'REVENUE', taxType: 'OUTPUT', class: 'REVENUE' },
      { code: '260', name: 'Other Revenue', type: 'REVENUE', taxType: 'OUTPUT', class: 'REVENUE' },
      { code: '400', name: 'Advertising', type: 'EXPENSE', taxType: 'INPUT', class: 'EXPENSE' },
      { code: '404', name: 'Bank Fees', type: 'EXPENSE', taxType: 'NONE', class: 'EXPENSE' },
      { code: '412', name: 'Consulting & Accounting', type: 'EXPENSE', taxType: 'INPUT', class: 'EXPENSE' },
      { code: '420', name: 'Entertainment', type: 'EXPENSE', taxType: 'INPUT', class: 'EXPENSE' },
      { code: '429', name: 'General Expenses', type: 'EXPENSE', taxType: 'INPUT', class: 'EXPENSE' },
      { code: '433', name: 'Insurance', type: 'EXPENSE', taxType: 'INPUT', class: 'EXPENSE' },
      { code: '441', name: 'Legal Expenses', type: 'EXPENSE', taxType: 'INPUT', class: 'EXPENSE' },
      { code: '445', name: 'Light, Power, Heating', type: 'EXPENSE', taxType: 'INPUT', class: 'EXPENSE' },
      { code: '449', name: 'Motor Vehicle Expenses', type: 'EXPENSE', taxType: 'INPUT', class: 'EXPENSE' },
      { code: '453', name: 'Office Expenses', type: 'EXPENSE', taxType: 'INPUT', class: 'EXPENSE' },
      { code: '461', name: 'Printing & Stationery', type: 'EXPENSE', taxType: 'INPUT', class: 'EXPENSE' },
      { code: '469', name: 'Rent', type: 'EXPENSE', taxType: 'INPUT', class: 'EXPENSE' },
      { code: '473', name: 'Repairs & Maintenance', type: 'EXPENSE', taxType: 'INPUT', class: 'EXPENSE' },
      { code: '477', name: 'Wages and Salaries', type: 'EXPENSE', taxType: 'NONE', class: 'EXPENSE' },
      { code: '485', name: 'Subscriptions', type: 'EXPENSE', taxType: 'INPUT', class: 'EXPENSE' },
      { code: '489', name: 'Telephone & Internet', type: 'EXPENSE', taxType: 'INPUT', class: 'EXPENSE' },
      { code: '493', name: 'Travel - National', type: 'EXPENSE', taxType: 'INPUT', class: 'EXPENSE' },
      { code: '497', name: 'Travel - International', type: 'EXPENSE', taxType: 'INPUT', class: 'EXPENSE' },
      { code: '610', name: 'Accounts Receivable', type: 'ASSET', taxType: 'NONE', class: 'ASSET' },
      { code: '800', name: 'Accounts Payable', type: 'LIABILITY', taxType: 'NONE', class: 'LIABILITY' },
      { code: '820', name: 'GST/VAT', type: 'LIABILITY', taxType: 'NONE', class: 'LIABILITY' },
      { code: '850', name: 'Suspense', type: 'LIABILITY', taxType: 'NONE', class: 'LIABILITY' },
      { code: '090', name: 'Business Bank Account', type: 'BANK', taxType: 'NONE', class: 'ASSET' },
    ];
  };

  TaxForge.demoTransactions = function () {
    const cats = [
      ['Office Expenses', '453', 48.2],
      ['Subscriptions', '485', 29],
      ['Motor Vehicle Expenses', '449', 86.4],
      ['Travel - National', '493', 214.5],
      ['Advertising', '400', 150],
      ['Telephone & Internet', '489', 89.99],
      ['Meals (partial)', '420', 62.3],
      ['Bank Fees', '404', 12],
      ['Software SaaS', '485', 45],
      ['Client Lunch', '420', 78],
      ['Fuel', '449', 54.2],
      ['Printer ink', '461', 33.1],
      ['Uncategorized', '', 199],
      ['Amazon misc', '', 67.4],
      ['Stripe fee', '404', 18.2],
    ];
    const now = new Date();
    return cats.map((c, i) => {
      const d = new Date(now);
      d.setDate(d.getDate() - i * 3 - (i % 4));
      return {
        id: 'txn-' + (1000 + i),
        date: d.toISOString().slice(0, 10),
        contact: ['Acme Supply', 'Shell', 'AWS', 'Delta', 'Staples', 'Verizon', 'Unknown Vendor'][i % 7],
        description: c[0],
        accountCode: c[1],
        accountName: c[0],
        amount: c[2],
        tax: Math.round(c[2] * 0.08 * 100) / 100,
        status: c[1] ? 'coded' : 'needs-review',
        deductible: c[1] && c[1] !== '420' ? 'likely' : c[1] === '420' ? 'partial' : 'unknown',
      };
    });
  };

  /** Parse simple Xero-style bank CSV: Date,Amount,Payee,Description,Reference */
  TaxForge.parseXeroCsv = function (text) {
    const lines = text.replace(/\r/g, '').split('\n').filter((l) => l.trim());
    if (lines.length < 2) return [];
    const headers = splitCsvLine(lines[0]).map((h) => h.trim().toLowerCase());
    const idx = (names) => {
      for (const n of names) {
        const i = headers.indexOf(n);
        if (i >= 0) return i;
      }
      return -1;
    };
    const iDate = idx(['date', 'transaction date', 'dated']);
    const iAmt = idx(['amount', 'spent', 'received']);
    const iPayee = idx(['payee', 'contact', 'name']);
    const iDesc = idx(['description', 'narration', 'particulars', 'reference']);
    const iAccount = idx(['account code', 'accountcode', 'account']);
    const rows = [];
    for (let r = 1; r < lines.length; r++) {
      const cols = splitCsvLine(lines[r]);
      if (!cols.length) continue;
      const amount = Math.abs(parseFloat(String(cols[iAmt] || '0').replace(/[,$]/g, '')) || 0);
      if (!amount) continue;
      const code = iAccount >= 0 ? String(cols[iAccount] || '').trim() : '';
      rows.push({
        id: 'imp-' + r + '-' + Date.now(),
        date: normalizeDate(cols[iDate] || ''),
        contact: (cols[iPayee] || 'Unknown').trim(),
        description: (cols[iDesc] || cols[iPayee] || 'Import').trim(),
        accountCode: code,
        accountName: code || 'Uncategorized',
        amount,
        tax: 0,
        status: code ? 'coded' : 'needs-review',
        deductible: code ? 'likely' : 'unknown',
      });
    }
    return rows;
  };

  function splitCsvLine(line) {
    const out = [];
    let cur = '';
    let q = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (ch === '"') {
        if (q && line[i + 1] === '"') { cur += '"'; i++; }
        else q = !q;
      } else if (ch === ',' && !q) {
        out.push(cur); cur = '';
      } else cur += ch;
    }
    out.push(cur);
    return out;
  }

  function normalizeDate(s) {
    s = String(s || '').trim();
    if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.slice(0, 10);
    const m = s.match(/^(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{2,4})$/);
    if (m) {
      let y = +m[3];
      if (y < 100) y += 2000;
      return `${y}-${String(m[1]).padStart(2, '0')}-${String(m[2]).padStart(2, '0')}`;
    }
    return new Date().toISOString().slice(0, 10);
  }

  /**
   * Xero OAuth scaffold (Authorization Code + PKCE-ready).
   * User supplies clientId; redirect URI must be registered in Xero app.
   * Token exchange should ideally run on local toolbox server — never ship client_secret in HTML.
   */
  TaxForge.xero = {
    AUTH: 'https://login.xero.com/identity/connect/authorize',
    TOKEN: 'https://identity.xero.com/connect/token',
    API: 'https://api.xero.com/api.xro/2.0',
    scopes: 'openid profile email offline_access accounting.transactions.read accounting.contacts.read accounting.settings.read',

    getConfig() {
      return TaxForge.storage.get('xero.config', { clientId: '', redirectUri: location.href.split('#')[0], tenantId: '' });
    },
    saveConfig(cfg) {
      TaxForge.storage.set('xero.config', cfg);
    },
    getSession() {
      return TaxForge.storage.get('xero.session', null);
    },
    saveSession(s) {
      TaxForge.storage.set('xero.session', s);
    },
    clearSession() {
      TaxForge.storage.remove('xero.session');
    },

    /** Build authorize URL (public client — use PKCE in production server path) */
    buildAuthUrl() {
      const cfg = this.getConfig();
      if (!cfg.clientId) throw new Error('Enter a Xero Client ID first.');
      const state = Math.random().toString(36).slice(2) + Date.now().toString(36);
      TaxForge.storage.set('xero.oauth_state', state);
      const params = new URLSearchParams({
        response_type: 'code',
        client_id: cfg.clientId,
        redirect_uri: cfg.redirectUri || location.href.split('#')[0],
        scope: this.scopes,
        state,
      });
      return this.AUTH + '?' + params.toString();
    },

    /** Read OAuth return code from query (user completes login in browser) */
    consumeRedirect() {
      const q = new URLSearchParams(location.search);
      const code = q.get('code');
      const state = q.get('state');
      if (!code) return null;
      const expect = TaxForge.storage.get('xero.oauth_state', '');
      if (state && expect && state !== expect) {
        TaxForge.toast('OAuth state mismatch — try connect again');
        return null;
      }
      // Clean URL
      try {
        const u = new URL(location.href);
        u.search = '';
        history.replaceState({}, '', u.toString());
      } catch (_) {}
      return { code, note: 'Exchange this authorization code on your local secure backend for tokens. TaxForge stores the code only as a pending handoff.' };
    },
  };

  TaxForge.nav = function (active) {
    const items = [
      { id: 'hub', href: 'TaxForge Hub.html', label: 'Hub' },
      { id: 'ledger', href: 'LedgerLink Console.html', label: 'LedgerLink' },
      { id: 'pulse', href: 'Compliance Pulse.html', label: 'Compliance Pulse' },
      { id: 'warroom', href: 'Year-End War Room.html', label: 'War Room' },
      { id: 'writeoff', href: 'Write-Off Workshop.html', label: 'Write-Off' },
    ];
    return `<nav class="tf-nav">${items.map((i) =>
      `<a href="${i.href}" class="${i.id === active ? 'active' : ''}">${i.label}</a>`
    ).join('')}</nav>`;
  };

  TaxForge.setRing = function (svgCircle, pct) {
    if (!svgCircle) return;
    const c = 2 * Math.PI * 65; // r=65
    const p = Math.max(0, Math.min(100, pct));
    svgCircle.style.strokeDasharray = String(c);
    svgCircle.style.strokeDashoffset = String(c * (1 - p / 100));
  };

  global.TaxForge = TaxForge;
})(window);
