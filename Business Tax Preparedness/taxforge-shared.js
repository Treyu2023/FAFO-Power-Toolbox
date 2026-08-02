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
      { id: 'partner', href: 'Partner Period Desk.html', label: 'Partner Desk' },
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

  /**
   * 2026 IRS standard mileage rates (business) — reference helpers only.
   * Not tax advice. Confirm current IRS rates before filing.
   * H1 (Jan 1 – Jun 30): 72.5¢/mi · H2 (Jul 1 – Dec 31): 76¢/mi
   */
  TaxForge.mileage = {
    YEAR: 2026,
    H1_RATE: 0.725,
    H2_RATE: 0.76,
    /** cents/mi labels for UI */
    H1_CENTS: 72.5,
    H2_CENTS: 76,

    rateForDate(dateStr) {
      const d = String(dateStr || '').slice(0, 10);
      const m = d.match(/^(\d{4})-(\d{2})-(\d{2})$/);
      if (!m) return this.H1_RATE;
      const month = +m[2];
      return month <= 6 ? this.H1_RATE : this.H2_RATE;
    },

    rateLabel(dateStr) {
      const r = this.rateForDate(dateStr);
      return (r * 100).toFixed(1) + '¢/mi';
    },

    /**
     * Parse MileIQ-style / generic mileage CSV.
     * Accepts flexible headers: Date, Miles|Distance|Mileage, Purpose|Note|Notes|Category (optional).
     */
    parseCsv(text) {
      const lines = String(text || '').replace(/\r/g, '').split('\n').filter((l) => l.trim());
      if (lines.length < 2) return { rows: [], errors: ['File needs a header row and at least one data row.'] };
      const headers = splitCsvLine(lines[0]).map((h) => h.trim().toLowerCase());
      const idx = (names) => {
        for (const n of names) {
          const i = headers.indexOf(n);
          if (i >= 0) return i;
        }
        return -1;
      };
      const iDate = idx(['date', 'trip date', 'start date', 'day']);
      const iMiles = idx(['miles', 'distance', 'mileage', 'mi', 'business miles', 'total miles']);
      const iPurpose = idx(['purpose', 'note', 'notes', 'category', 'description', 'business purpose', 'reason']);
      if (iDate < 0 || iMiles < 0) {
        return {
          rows: [],
          errors: ['Need Date and Miles (or Distance/Mileage) columns. Got: ' + headers.join(', ')],
        };
      }
      const rows = [];
      const errors = [];
      for (let r = 1; r < lines.length; r++) {
        const cols = splitCsvLine(lines[r]);
        if (!cols.length || cols.every((c) => !String(c).trim())) continue;
        const date = normalizeDate(cols[iDate] || '');
        const milesRaw = String(cols[iMiles] || '').replace(/[,\s]/g, '');
        const miles = parseFloat(milesRaw);
        if (!miles || miles <= 0 || !isFinite(miles)) {
          errors.push('Row ' + (r + 1) + ': skip — invalid miles');
          continue;
        }
        const rate = this.rateForDate(date);
        const amount = Math.round(miles * rate * 100) / 100;
        rows.push({
          id: 'mi-' + r + '-' + Date.now(),
          date,
          miles: Math.round(miles * 100) / 100,
          purpose: iPurpose >= 0 ? String(cols[iPurpose] || '').trim() : '',
          rate,
          rateLabel: this.rateLabel(date),
          amount,
          half: date.slice(5, 7) <= '06' ? 'H1' : 'H2',
        });
      }
      return { rows, errors };
    },

    summarize(rows) {
      let miles = 0;
      let amount = 0;
      let h1Miles = 0;
      let h2Miles = 0;
      let h1Amount = 0;
      let h2Amount = 0;
      (rows || []).forEach((r) => {
        miles += r.miles || 0;
        amount += r.amount || 0;
        if (r.half === 'H2') {
          h2Miles += r.miles || 0;
          h2Amount += r.amount || 0;
        } else {
          h1Miles += r.miles || 0;
          h1Amount += r.amount || 0;
        }
      });
      return {
        count: (rows || []).length,
        miles: Math.round(miles * 100) / 100,
        amount: Math.round(amount * 100) / 100,
        h1Miles: Math.round(h1Miles * 100) / 100,
        h2Miles: Math.round(h2Miles * 100) / 100,
        h1Amount: Math.round(h1Amount * 100) / 100,
        h2Amount: Math.round(h2Amount * 100) / 100,
      };
    },

    /** CSV export for accountant / Xero draft expense import */
    toExportCsv(rows) {
      const header = 'Date,Miles,Purpose,RatePerMile,DeductionAmount,HalfYear,AccountCode,AccountName';
      const lines = (rows || []).map((r) => {
        const purpose = '"' + String(r.purpose || 'Business mileage').replace(/"/g, '""') + '"';
        return [
          r.date,
          r.miles,
          purpose,
          r.rate,
          r.amount,
          r.half,
          '449',
          'Motor Vehicle Expenses',
        ].join(',');
      });
      return [header].concat(lines).join('\n');
    },
  };

  /**
   * Rough SE / quarterly estimate helpers for preparedness only.
   * SE tax ≈ 15.3% on 92.35% of net earnings from self-employment.
   * SS wage base 2026: $184,500 (for capacity note only).
   * Not tax advice — federal income tax, state, credits, and safe-harbor rules are out of scope.
   */
  TaxForge.quarterly = {
    SE_RATE: 0.153,
    SE_BASE_PCT: 0.9235,
    SS_WAGE_BASE_2026: 184500,
    /** Federal estimated tax installment deadlines (calendar-year filer, next year Jan for Q4) */
    DEADLINES: [
      { id: 'Q1', label: 'Q1', month: 4, day: 15 },
      { id: 'Q2', label: 'Q2', month: 6, day: 15 },
      { id: 'Q3', label: 'Q3', month: 9, day: 15 },
      { id: 'Q4', label: 'Q4', month: 1, day: 15, nextYear: true },
    ],

    seTaxOnNet(netProfit) {
      const net = Math.max(0, Number(netProfit) || 0);
      const seBase = Math.round(net * this.SE_BASE_PCT * 100) / 100;
      const seTax = Math.round(seBase * this.SE_RATE * 100) / 100;
      return { net, seBase, seTax };
    },

    /** Remaining room under SS wage base for SE earnings base (simplified note, not wage calc) */
    ssBaseCapacity(ytdSeBase) {
      const used = Math.max(0, Number(ytdSeBase) || 0);
      const remaining = Math.max(0, this.SS_WAGE_BASE_2026 - used);
      return {
        wageBase: this.SS_WAGE_BASE_2026,
        used: Math.round(used * 100) / 100,
        remaining: Math.round(remaining * 100) / 100,
        pctUsed: Math.min(100, Math.round((used / this.SS_WAGE_BASE_2026) * 1000) / 10),
      };
    },

    /**
     * Next unpaid deadline relative to "now".
     * Returns { id, label, date, daysLeft, year }
     */
    nextDeadline(now) {
      const n = now ? new Date(now) : new Date();
      const y = n.getFullYear();
      const candidates = [];
      this.DEADLINES.forEach((d) => {
        const year = d.nextYear ? y : y;
        // Q4 Jan deadline: if we're past Jan 15 this year, next is next year's Jan
        let date = new Date(year, d.month - 1, d.day, 23, 59, 59);
        if (d.nextYear) {
          // Q4 for year Y is due Jan 15 of Y+1; if today is after that Jan deadline, use following year
          date = new Date(y, 0, 15, 23, 59, 59);
          if (n > date) date = new Date(y + 1, 0, 15, 23, 59, 59);
        } else {
          date = new Date(y, d.month - 1, d.day, 23, 59, 59);
          if (n > date) date = new Date(y + 1, d.month - 1, d.day, 23, 59, 59);
        }
        candidates.push({
          id: d.id,
          label: d.label,
          date,
          year: date.getFullYear(),
          daysLeft: Math.ceil((date - n) / 86400000),
        });
      });
      candidates.sort((a, b) => a.date - b.date);
      return candidates[0];
    },

    /**
     * Rough remaining quarterly SE-tax shares.
     * Splits YTD SE tax across 4 equal installments conceptually; remaining = annualized SE − paid.
     * annualize: if ytdMonths provided (1–12), scale net to full year; else treat net as full-year estimate.
     */
    remainingQuarters(opts) {
      const netYtd = Math.max(0, Number(opts && opts.netProfit) || 0);
      const paid = Math.max(0, Number(opts && opts.paidToDate) || 0);
      const ytdMonths = Math.min(12, Math.max(1, Number(opts && opts.ytdMonths) || 12));
      const annualNet = ytdMonths >= 12 ? netYtd : (netYtd / ytdMonths) * 12;
      const se = this.seTaxOnNet(annualNet);
      const remainingTax = Math.max(0, Math.round((se.seTax - paid) * 100) / 100);
      const next = this.nextDeadline(opts && opts.now);
      // Count unpaid deadlines still ahead in this calendar cycle (rough: 4 minus how many deadlines already passed this year)
      const now = (opts && opts.now) ? new Date(opts.now) : new Date();
      let remainingInstallments = 0;
      const y = now.getFullYear();
      [
        new Date(y, 3, 15),
        new Date(y, 5, 15),
        new Date(y, 8, 15),
        new Date(y + 1, 0, 15),
      ].forEach((d) => {
        if (d >= new Date(now.getFullYear(), now.getMonth(), now.getDate())) remainingInstallments++;
      });
      if (remainingInstallments < 1) remainingInstallments = 1;
      const perInstallment = Math.round((remainingTax / remainingInstallments) * 100) / 100;
      const ss = this.ssBaseCapacity(se.seBase);
      return {
        annualNet: Math.round(annualNet * 100) / 100,
        seBase: se.seBase,
        seTaxAnnual: se.seTax,
        paid,
        remainingTax,
        remainingInstallments,
        perInstallment,
        nextDeadline: next,
        ss,
      };
    },
  };

  TaxForge.DISCLAIMER =
    'This is not tax, legal, or accounting advice — for preparedness and bookkeeping support only.';

  /**
   * Partner / reimbursement / investor period helpers.
   * Fix “wrong bucket” lines by reclassifying without re-typing amounts.
   * Profit-share math is a bookkeeping helper only — not a partnership legal opinion.
   */
  TaxForge.partner = {
    KINDS: [
      { id: 'reimb_owner', label: 'Reimbursement → due to owner', party: 'owner', polarity: 'reimb' },
      { id: 'reimb_investor', label: 'Reimbursement → due to investor', party: 'investor', polarity: 'reimb' },
      { id: 'parts_investor', label: 'Investor paid for parts/COGS', party: 'investor', polarity: 'parts' },
      { id: 'parts_owner', label: 'Owner paid for parts/COGS', party: 'owner', polarity: 'parts' },
      { id: 'sale', label: 'Sale / revenue (gross)', party: 'company', polarity: 'sale' },
      { id: 'ops_expense', label: 'Ops expense (non-parts)', party: 'company', polarity: 'expense' },
      { id: 'profit_paid', label: 'Profit share paid out', party: 'investor', polarity: 'payout' },
      { id: 'misplaced', label: 'Misplaced / needs reclass', party: 'unknown', polarity: 'flag' },
      { id: 'other', label: 'Other / note only', party: 'unknown', polarity: 'other' },
    ],

    kindMeta(id) {
      return this.KINDS.find((k) => k.id === id) || this.KINDS[this.KINDS.length - 1];
    },

    defaultSettings() {
      return {
        fiscalYearStartMonth: 1, // 1=Jan calendar; e.g. 10 = Oct fiscal start
        investorSharePct: 50, // default 50/50 style — owner can change
        investorName: 'Investor',
        ownerName: 'Owner',
        entityName: 'FAFO Petro LLC',
        currency: 'USD',
      };
    },

    getSettings() {
      return Object.assign(this.defaultSettings(), TaxForge.storage.get('partner.settings', {}));
    },
    saveSettings(s) {
      TaxForge.storage.set('partner.settings', s);
    },

    getLines() {
      return TaxForge.storage.get('partner.lines', []);
    },
    saveLines(lines) {
      TaxForge.storage.set('partner.lines', lines);
    },

    /** Parse flexible partner/reimbursement CSV */
    parseCsv(text) {
      const lines = String(text || '').replace(/\r/g, '').split('\n').filter((l) => l.trim());
      if (lines.length < 2) return { rows: [], errors: ['Need header + data rows'] };
      const headers = splitCsvLine(lines[0]).map((h) => h.trim().toLowerCase());
      const idx = (names) => {
        for (const n of names) {
          const i = headers.indexOf(n);
          if (i >= 0) return i;
        }
        return -1;
      };
      const iDate = idx(['date', 'txn date', 'transaction date', 'purchase date', 'purchased']);
      const iAmt = idx(['amount', 'cost', 'total', 'price', 'our cost', 'spend', '$']);
      const iDesc = idx(['description', 'item', 'item / asset', 'memo', 'notes', 'purpose', 'name']);
      const iKind = idx(['kind', 'type', 'bucket', 'category', 'class']);
      const iParty = idx(['party', 'who paid', 'paid by', 'payer']);
      const iVendor = idx(['vendor', 'payee', 'contact', 'serial #', 'serial']);
      const iSource = idx(['source', 'from', 'original', 'wrong spot', 'location']);
      if (iAmt < 0) {
        return { rows: [], errors: ['Need an Amount (or Cost/Total) column. Headers: ' + headers.join(', ')] };
      }
      const rows = [];
      const errors = [];
      for (let r = 1; r < lines.length; r++) {
        const cols = splitCsvLine(lines[r]);
        if (!cols.length || cols.every((c) => !String(c).trim())) continue;
        const amount = Math.abs(parseFloat(String(cols[iAmt] || '0').replace(/[$,]/g, '')) || 0);
        if (!amount) {
          errors.push('Row ' + (r + 1) + ': skip — no amount');
          continue;
        }
        const rawKind = iKind >= 0 ? String(cols[iKind] || '').trim() : '';
        const kind = mapKindGuess(rawKind, iDesc >= 0 ? cols[iDesc] : '');
        rows.push({
          id: 'pl-' + Date.now() + '-' + r + '-' + Math.random().toString(36).slice(2, 6),
          date: normalizeDate(iDate >= 0 ? cols[iDate] : ''),
          amount: Math.round(amount * 100) / 100,
          description: iDesc >= 0 ? String(cols[iDesc] || '').trim() : 'Line ' + r,
          kind,
          party: iParty >= 0 ? normalizeParty(cols[iParty]) : this.kindMeta(kind).party,
          vendor: iVendor >= 0 ? String(cols[iVendor] || '').trim() : '',
          sourceNote: iSource >= 0 ? String(cols[iSource] || '').trim() : 'csv-import',
          originalKind: rawKind || 'unknown',
          status: kind === 'misplaced' ? 'needs-reclass' : 'ok',
          createdAt: Date.now(),
        });
      }
      return { rows, errors };
    },

    /**
     * Fiscal period keys.
     * monthKey: YYYY-MM
     * calendarYear: YYYY
     * fiscalYear: label e.g. FY2026 (year of fiscal year END when start month > 1)
     */
    periodKeys(dateStr, fiscalStartMonth) {
      const d = String(dateStr || '').slice(0, 10);
      const m = d.match(/^(\d{4})-(\d{2})-(\d{2})$/);
      const now = new Date();
      const y = m ? +m[1] : now.getFullYear();
      const mo = m ? +m[2] : now.getMonth() + 1;
      const monthKey = y + '-' + String(mo).padStart(2, '0');
      const calYear = String(y);
      const fsm = Math.min(12, Math.max(1, Number(fiscalStartMonth) || 1));
      let fyEndYear = y;
      if (fsm !== 1) {
        // FY labeled by end year: if start is Oct, Oct 2025–Sep 2026 = FY2026
        fyEndYear = mo >= fsm ? y + 1 : y;
      }
      const fiscalYear = fsm === 1 ? 'CY' + y : 'FY' + fyEndYear;
      return { monthKey, calYear, fiscalYear, year: y, month: mo };
    },

    /** Reclassify without changing amount/date/description */
    reclassify(line, kind, extra) {
      const meta = this.kindMeta(kind);
      return Object.assign({}, line, extra || {}, {
        kind,
        party: (extra && extra.party) || meta.party,
        status: kind === 'misplaced' ? 'needs-reclass' : 'ok',
        reclassedAt: Date.now(),
        previousKind: line.kind,
      });
    },

    /**
     * Roll up lines into period buckets.
     * @param {object} opts { lines, fiscalStartMonth, periodType: 'month'|'year'|'fiscal' }
     */
    rollup(opts) {
      const lines = (opts && opts.lines) || this.getLines();
      const fsm = (opts && opts.fiscalStartMonth) || this.getSettings().fiscalYearStartMonth;
      const periodType = (opts && opts.periodType) || 'month';
      const buckets = {};
      lines.forEach((line) => {
        const pk = this.periodKeys(line.date, fsm);
        const key = periodType === 'year' ? pk.calYear
          : periodType === 'fiscal' ? pk.fiscalYear
            : pk.monthKey;
        if (!buckets[key]) {
          buckets[key] = emptyBucket(key, periodType);
        }
        const b = buckets[key];
        const amt = Number(line.amount) || 0;
        b.lineCount++;
        b.byKind[line.kind] = (b.byKind[line.kind] || 0) + amt;
        const pol = this.kindMeta(line.kind).polarity;
        if (pol === 'sale') b.sales += amt;
        if (pol === 'parts') b.partsCost += amt;
        if (pol === 'expense') b.opsExpense += amt;
        if (pol === 'reimb') {
          b.reimbTotal += amt;
          if (line.kind === 'reimb_owner') b.reimbOwner += amt;
          if (line.kind === 'reimb_investor') b.reimbInvestor += amt;
        }
        if (pol === 'payout') b.profitPaid += amt;
        if (line.kind === 'parts_investor') b.partsInvestor += amt;
        if (line.kind === 'parts_owner') b.partsOwner += amt;
        if (line.status === 'needs-reclass' || line.kind === 'misplaced') b.needsReclass++;
      });
      // derived
      Object.keys(buckets).forEach((k) => {
        const b = buckets[k];
        b.grossProfit = Math.round((b.sales - b.partsCost) * 100) / 100;
        b.netAfterOps = Math.round((b.grossProfit - b.opsExpense) * 100) / 100;
        roundBucket(b);
      });
      return buckets;
    },

    /**
     * Investor share estimate for a period bucket (bookkeeping helper).
     * shareBase defaults to netAfterOps (sales - parts - ops). Can use grossProfit.
     */
    shareForBucket(bucket, settings) {
      const s = settings || this.getSettings();
      const pct = Math.min(100, Math.max(0, Number(s.investorSharePct) || 0));
      const base = Number(bucket.netAfterOps) || 0;
      const investorShare = Math.round(base * (pct / 100) * 100) / 100;
      const ownerShare = Math.round((base - investorShare) * 100) / 100;
      const alreadyPaid = Number(bucket.profitPaid) || 0;
      const investorOwed = Math.round((investorShare - alreadyPaid) * 100) / 100;
      // Capital: investor parts still out vs reimbursements already logged
      const investorCapitalIn = Number(bucket.partsInvestor) || 0;
      const investorReimbLogged = Number(bucket.reimbInvestor) || 0;
      return {
        shareBase: base,
        investorSharePct: pct,
        investorShare,
        ownerShare,
        alreadyPaid,
        investorOwedEstimate: investorOwed,
        investorPartsIn: investorCapitalIn,
        investorReimbLogged,
        note: 'Estimates only — confirm partnership terms with your advisor. Not tax advice.',
      };
    },

    buildExpertPack(opts) {
      const settings = this.getSettings();
      const lines = this.getLines();
      const periodType = (opts && opts.periodType) || 'month';
      const buckets = this.rollup({ lines, periodType, fiscalStartMonth: settings.fiscalYearStartMonth });
      const periods = Object.keys(buckets).sort().map((k) => {
        const b = buckets[k];
        return { period: k, totals: b, share: this.shareForBucket(b, settings) };
      });
      const needs = lines.filter((l) => l.status === 'needs-reclass' || l.kind === 'misplaced');
      return {
        kind: 'fafo-partner-period-pack',
        exportedAt: new Date().toISOString(),
        disclaimer: TaxForge.DISCLAIMER,
        entity: settings.entityName,
        settings: {
          fiscalYearStartMonth: settings.fiscalYearStartMonth,
          investorSharePct: settings.investorSharePct,
          investorName: settings.investorName,
          ownerName: settings.ownerName,
        },
        summary: {
          lineCount: lines.length,
          needsReclass: needs.length,
          periodType,
          periodCount: periods.length,
        },
        periods,
        needsReclassSample: needs.slice(0, 50),
        lines,
      };
    },

    packToMarkdown(pack) {
      const p = pack || this.buildExpertPack({});
      const lines = [
        '# FAFO Partner / Reimbursement Period Pack',
        '',
        '- Exported: ' + p.exportedAt,
        '- Entity: ' + p.entity,
        '- Investor share %: ' + p.settings.investorSharePct,
        '- Fiscal year start month: ' + p.settings.fiscalYearStartMonth,
        '- Lines: ' + p.summary.lineCount + ' · Needs reclass: ' + p.summary.needsReclass,
        '',
        '>' + p.disclaimer,
        '',
        '## Periods (' + p.summary.periodType + ')',
        '',
      ];
      p.periods.forEach((per) => {
        const t = per.totals;
        const s = per.share;
        lines.push('### ' + per.period);
        lines.push('- Sales: $' + t.sales + ' · Parts COGS: $' + t.partsCost + ' · Ops: $' + t.opsExpense);
        lines.push('- Gross (sales−parts): $' + t.grossProfit + ' · Net after ops: $' + t.netAfterOps);
        lines.push('- Reimb owner: $' + t.reimbOwner + ' · Reimb investor: $' + t.reimbInvestor);
        lines.push('- Investor parts in: $' + t.partsInvestor + ' · Profit paid: $' + t.profitPaid);
        lines.push('- Investor share @ ' + s.investorSharePct + '%: $' + s.investorShare + ' · Est. still owed: $' + s.investorOwedEstimate);
        lines.push('- Lines: ' + t.lineCount + ' · Needs reclass: ' + t.needsReclass);
        lines.push('');
      });
      if (p.needsReclassSample && p.needsReclassSample.length) {
        lines.push('## Needs reclass (sample)');
        lines.push('');
        p.needsReclassSample.forEach((l) => {
          lines.push('- ' + l.date + ' · $' + l.amount + ' · ' + l.description + ' · was: ' + (l.originalKind || l.kind));
        });
        lines.push('');
      }
      lines.push('## Expert ask');
      lines.push('Review reclass rules, investor share base (gross vs net), and reimbursement vs capital contribution treatment.');
      lines.push('');
      return lines.join('\n');
    },
  };

  function emptyBucket(key, periodType) {
    return {
      key,
      periodType,
      lineCount: 0,
      sales: 0,
      partsCost: 0,
      partsInvestor: 0,
      partsOwner: 0,
      opsExpense: 0,
      reimbTotal: 0,
      reimbOwner: 0,
      reimbInvestor: 0,
      profitPaid: 0,
      grossProfit: 0,
      netAfterOps: 0,
      needsReclass: 0,
      byKind: {},
    };
  }

  function roundBucket(b) {
    ['sales', 'partsCost', 'partsInvestor', 'partsOwner', 'opsExpense', 'reimbTotal',
      'reimbOwner', 'reimbInvestor', 'profitPaid', 'grossProfit', 'netAfterOps'].forEach((k) => {
      b[k] = Math.round((b[k] || 0) * 100) / 100;
    });
  }

  function normalizeParty(s) {
    s = String(s || '').toLowerCase();
    if (/sumran|invest/.test(s)) return 'investor';
    if (/owner|me|self|trey|builder/.test(s)) return 'owner';
    if (/company|llc|fafo|biz/.test(s)) return 'company';
    return 'unknown';
  }

  function mapKindGuess(raw, desc) {
    const s = (String(raw || '') + ' ' + String(desc || '')).toLowerCase();
    if (/misplac|wrong|fix later|uncategor/.test(s)) return 'misplaced';
    if (/reimb.*invest|due to invest|sumran reimb/.test(s)) return 'reimb_investor';
    if (/reimb|repay me|due to owner|owner reimb/.test(s)) return 'reimb_owner';
    if (/invest.*part|sumran.*part|part.*invest|investor cogs|investor cost/.test(s)) return 'parts_investor';
    if (/owner.*part|my part|parts owner|owner cogs/.test(s)) return 'parts_owner';
    if (/profit.?share|payout|distribution/.test(s)) return 'profit_paid';
    if (/sale|revenue|sold|invoice/.test(s)) return 'sale';
    if (/expense|ops|fee|rent|software/.test(s)) return 'ops_expense';
    if (/part|cogs|inventory|serial|device|verifone|kit/.test(s)) return 'parts_owner';
    if (raw && String(raw).trim()) return 'misplaced'; // had a label we didn't understand → flag
    return 'misplaced';
  }

  global.TaxForge = TaxForge;
})(window);
