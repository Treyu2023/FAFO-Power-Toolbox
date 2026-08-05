/**
 * TaxForge — shared local store (localStorage)
 * Organization tools only. Not tax, legal, or accounting advice.
 */
(function (global) {
  'use strict';

  const PREFIX = 'taxforge.';
  const KEYS = {
    mileage: 'mileage',
    expenses: 'expenses',
    quarterly: 'quarterly',
    checklist: 'checklist',
    settings: 'settings',
    questions: 'questions'
  };

  const DEFAULT_SETTINGS = {
    businessName: 'FAFO Petro Services',
    // Default to 2025 while extended 2025 returns are the active filing focus
    taxYear: 2025,
    mileageRate: 0.70,
    defaultVehicle: '',
    seRatePercent: 15.3,
    incomeTaxBufferPercent: 25
  };

  const DEFAULT_CHECKLIST = [
    { id: 'c1', label: 'Bank / card statements (full year)', done: false, notes: '' },
    { id: 'c2', label: 'Income: 1099s / invoices / deposits', done: false, notes: '' },
    { id: 'c3', label: 'Mileage log complete', done: false, notes: '' },
    { id: 'c4', label: 'Business expenses categorized', done: false, notes: '' },
    { id: 'c5', label: 'Quarterly estimated payments recorded', done: false, notes: '' },
    { id: 'c6', label: 'Asset purchases / equipment list', done: false, notes: '' },
    { id: 'c7', label: 'Home office / workspace notes (if any)', done: false, notes: '' },
    { id: 'c8', label: 'Prior-year return / CPA notes', done: false, notes: '' },
    { id: 'c9', label: 'Entity docs (AOI, EIN, registrations)', done: false, notes: '' },
    { id: 'c10', label: 'Partner / owner draws & capital notes', done: false, notes: '' },
    { id: 'c11', label: 'Open questions list for CPA', done: false, notes: '' },
    { id: 'c12', label: 'Share pack exported for accountant', done: false, notes: '' }
  ];

  const EXPENSE_CATEGORIES = [
    'Vehicle / Fuel',
    'Mileage (standard rate)',
    'Tools & Equipment',
    'Supplies',
    'Software / Subscriptions',
    'Phone / Internet',
    'Insurance',
    'Professional Services',
    'Training / Education',
    'Travel',
    'Meals (business)',
    'Advertising / Marketing',
    'Office / Workspace',
    'Licenses / Fees',
    'Repairs & Maintenance',
    'Uniforms / Safety',
    'Shipping / Postage',
    'Bank / Payment Fees',
    'Other'
  ];

  function uid(prefix) {
    return (prefix || 'id') + '_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8);
  }

  function load(key, fallback) {
    try {
      const raw = localStorage.getItem(PREFIX + key);
      if (raw == null) return typeof fallback === 'function' ? fallback() : structuredCloneSafe(fallback);
      return JSON.parse(raw);
    } catch (e) {
      console.warn('[TaxForge] load failed', key, e);
      return typeof fallback === 'function' ? fallback() : structuredCloneSafe(fallback);
    }
  }

  function structuredCloneSafe(v) {
    if (v == null) return v;
    try {
      return JSON.parse(JSON.stringify(v));
    } catch (_) {
      return v;
    }
  }

  function save(key, data) {
    localStorage.setItem(PREFIX + key, JSON.stringify(data));
    try {
      global.dispatchEvent(new CustomEvent('taxforge:change', { detail: { key } }));
    } catch (_) { /* ignore */ }
  }

  function getSettings() {
    return Object.assign({}, DEFAULT_SETTINGS, load(KEYS.settings, {}));
  }

  function setSettings(partial) {
    const next = Object.assign(getSettings(), partial || {});
    save(KEYS.settings, next);
    return next;
  }

  function getMileage() {
    return load(KEYS.mileage, []);
  }

  function setMileage(rows) {
    save(KEYS.mileage, Array.isArray(rows) ? rows : []);
  }

  function getExpenses() {
    return load(KEYS.expenses, []);
  }

  function setExpenses(rows) {
    save(KEYS.expenses, Array.isArray(rows) ? rows : []);
  }

  function getQuarterly() {
    const year = getSettings().taxYear;
    const data = load(KEYS.quarterly, {});
    if (!data[year]) {
      data[year] = defaultQuarters(year);
      save(KEYS.quarterly, data);
    }
    return data;
  }

  function setQuarterly(data) {
    save(KEYS.quarterly, data || {});
  }

  function defaultQuarters(year) {
    // Typical US estimated-tax due months (calendar year) — informational only
    return {
      Q1: { label: 'Q1', dueDate: year + '-04-15', grossIncome: 0, deductions: 0, estimatedPaid: 0, notes: '', paid: false },
      Q2: { label: 'Q2', dueDate: year + '-06-15', grossIncome: 0, deductions: 0, estimatedPaid: 0, notes: '', paid: false },
      Q3: { label: 'Q3', dueDate: year + '-09-15', grossIncome: 0, deductions: 0, estimatedPaid: 0, notes: '', paid: false },
      Q4: { label: 'Q4', dueDate: (year + 1) + '-01-15', grossIncome: 0, deductions: 0, estimatedPaid: 0, notes: '', paid: false }
    };
  }

  function getChecklist() {
    const rows = load(KEYS.checklist, null);
    if (!rows || !rows.length) {
      const d = structuredCloneSafe(DEFAULT_CHECKLIST);
      save(KEYS.checklist, d);
      return d;
    }
    return rows;
  }

  function setChecklist(rows) {
    save(KEYS.checklist, Array.isArray(rows) ? rows : []);
  }

  function getQuestions() {
    return load(KEYS.questions, []);
  }

  function setQuestions(rows) {
    save(KEYS.questions, Array.isArray(rows) ? rows : []);
  }

  function formatMoney(n) {
    const v = Number(n) || 0;
    return v.toLocaleString(undefined, { style: 'currency', currency: 'USD' });
  }

  function formatDate(d) {
    if (!d) return '';
    try {
      const dt = typeof d === 'string' && d.length <= 10 ? new Date(d + 'T12:00:00') : new Date(d);
      if (isNaN(dt.getTime())) return String(d);
      return dt.toLocaleDateString();
    } catch (_) {
      return String(d);
    }
  }

  function todayISO() {
    const d = new Date();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return d.getFullYear() + '-' + m + '-' + day;
  }

  function download(filename, text, mime) {
    const blob = new Blob([text], { type: mime || 'text/plain;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      URL.revokeObjectURL(a.href);
      a.remove();
    }, 500);
  }

  function toCsv(rows, columns) {
    const esc = (v) => {
      const s = v == null ? '' : String(v);
      if (/[",\n\r]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
      return s;
    };
    const header = columns.map((c) => esc(c.label || c.key)).join(',');
    const lines = rows.map((r) =>
      columns.map((c) => esc(typeof c.get === 'function' ? c.get(r) : r[c.key])).join(',')
    );
    return [header].concat(lines).join('\r\n');
  }

  function exportAll() {
    return {
      version: 1,
      exportedAt: new Date().toISOString(),
      disclaimer: 'TaxForge export — organization only, not tax advice.',
      settings: getSettings(),
      mileage: getMileage(),
      expenses: getExpenses(),
      quarterly: getQuarterly(),
      checklist: getChecklist(),
      questions: getQuestions()
    };
  }

  function importAll(obj, mode) {
    if (!obj || typeof obj !== 'object') throw new Error('Invalid import payload');
    const merge = mode === 'merge';
    if (obj.settings) setSettings(merge ? Object.assign(getSettings(), obj.settings) : obj.settings);
    if (Array.isArray(obj.mileage)) {
      setMileage(merge ? getMileage().concat(obj.mileage) : obj.mileage);
    }
    if (Array.isArray(obj.expenses)) {
      setExpenses(merge ? getExpenses().concat(obj.expenses) : obj.expenses);
    }
    if (obj.quarterly && typeof obj.quarterly === 'object') {
      if (merge) {
        const cur = getQuarterly();
        setQuarterly(Object.assign({}, cur, obj.quarterly));
      } else {
        setQuarterly(obj.quarterly);
      }
    }
    if (Array.isArray(obj.checklist)) setChecklist(obj.checklist);
    if (Array.isArray(obj.questions)) {
      setQuestions(merge ? getQuestions().concat(obj.questions) : obj.questions);
    }
    return exportAll();
  }

  function stats() {
    const year = getSettings().taxYear;
    const rate = Number(getSettings().mileageRate) || 0;
    const miles = getMileage().filter((r) => String(r.date || '').startsWith(String(year)));
    const busMiles = miles.reduce((s, r) => s + (r.business === false ? 0 : Number(r.miles) || 0), 0);
    const expenses = getExpenses().filter((r) => String(r.date || '').startsWith(String(year)) || Number(r.taxYear) === year);
    const expTotal = expenses.reduce((s, r) => {
      const amt = Number(r.amount) || 0;
      const pct = r.businessUsePct == null ? 100 : Number(r.businessUsePct);
      return s + amt * (pct / 100);
    }, 0);
    const q = getQuarterly()[year] || defaultQuarters(year);
    const paid = ['Q1', 'Q2', 'Q3', 'Q4'].reduce((s, k) => s + (Number(q[k].estimatedPaid) || 0), 0);
    const checklist = getChecklist();
    const done = checklist.filter((c) => c.done).length;
    return {
      taxYear: year,
      tripCount: miles.length,
      businessMiles: busMiles,
      mileageValue: busMiles * rate,
      expenseCount: expenses.length,
      expenseTotal: expTotal,
      quarterlyPaid: paid,
      checklistDone: done,
      checklistTotal: checklist.length,
      openQuestions: getQuestions().filter((q) => !q.resolved).length
    };
  }

  /** Minimal CSV line parser (supports quoted fields with commas). */
  function parseCsvLine(line) {
    const out = [];
    let cur = '';
    let inQ = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (inQ) {
        if (ch === '"') {
          if (line[i + 1] === '"') {
            cur += '"';
            i++;
          } else {
            inQ = false;
          }
        } else {
          cur += ch;
        }
      } else if (ch === '"') {
        inQ = true;
      } else if (ch === ',') {
        out.push(cur);
        cur = '';
      } else {
        cur += ch;
      }
    }
    out.push(cur);
    return out;
  }

  function normalizeHeader(h) {
    return String(h || '')
      .replace(/^\uFEFF/, '')
      .trim()
      .replace(/\*$/g, '')
      .toLowerCase()
      .replace(/\s+/g, '_');
  }

  function parseMileIQDate(raw) {
    if (!raw) return null;
    const s = String(raw).trim();
    // MM/DD/YYYY HH:MM or MM/DD/YYYY
    const m = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?/);
    if (m) {
      const mm = m[1].padStart(2, '0');
      const dd = m[2].padStart(2, '0');
      const yyyy = m[3];
      return {
        date: yyyy + '-' + mm + '-' + dd,
        time: m[4] != null ? m[4].padStart(2, '0') + ':' + m[5] : null
      };
    }
    // ISO-ish
    const d = new Date(s);
    if (!isNaN(d.getTime())) {
      const mm = String(d.getMonth() + 1).padStart(2, '0');
      const dd = String(d.getDate()).padStart(2, '0');
      return {
        date: d.getFullYear() + '-' + mm + '-' + dd,
        time: null
      };
    }
    return null;
  }

  function parseNumberLoose(v) {
    if (v == null || v === '') return 0;
    const s = String(v).replace(/[$,]/g, '').trim();
    if (!s || s.charAt(0) === '=') return 0; // formula cells — ignore
    const n = Number(s);
    return isNaN(n) ? 0 : n;
  }

  function tripFingerprint(r) {
    return [
      r.date || '',
      (r.from || '').toLowerCase().trim(),
      (r.to || '').toLowerCase().trim(),
      String(Number(r.miles) || 0),
      (r.purpose || '').toLowerCase().trim(),
      r.business === false ? 'p' : 'b'
    ].join('|');
  }

  /**
   * Parse a MileIQ All Drives / Detailed Log CSV export.
   * Supports layouts with or without a RATE column (2025 annual vs newer monthly).
   * @returns {{ trips: object[], meta: object, errors: string[] }}
   */
  function parseMileIQCsv(text, sourceName) {
    const errors = [];
    const meta = {
      source: sourceName || 'mileiq.csv',
      businessRate: null,
      headerRow: null,
      rawRows: 0
    };
    if (!text || !String(text).trim()) {
      return { trips: [], meta, errors: ['Empty file'] };
    }

    const lines = String(text).replace(/^\uFEFF/, '').split(/\r?\n/);
    // Rate line: rates >>>,business $,0.725,...
    for (let i = 0; i < Math.min(lines.length, 8); i++) {
      if (/^rates\s*>>>/i.test(lines[i])) {
        const parts = parseCsvLine(lines[i]);
        for (let j = 0; j < parts.length - 1; j++) {
          if (/business\s*\$/i.test(parts[j])) {
            meta.businessRate = parseNumberLoose(parts[j + 1]);
          }
        }
        break;
      }
    }

    let headerIdx = -1;
    for (let i = 0; i < lines.length; i++) {
      const n = normalizeHeader(parseCsvLine(lines[i])[0] || '');
      if (n === 'start_date' || lines[i].indexOf('START_DATE') === 0) {
        headerIdx = i;
        break;
      }
    }
    if (headerIdx < 0) {
      return { trips: [], meta, errors: ['No DETAILED LOG header (START_DATE*) found — is this a MileIQ CSV?'] };
    }

    const headers = parseCsvLine(lines[headerIdx]).map(normalizeHeader);
    meta.headerRow = headers;

    const col = {};
    headers.forEach((h, i) => {
      col[h] = i;
    });

    // Required columns (MileIQ names normalized)
    const need = ['start_date', 'category', 'start', 'stop', 'miles'];
    for (let k = 0; k < need.length; k++) {
      if (col[need[k]] == null) {
        // some exports use start* already stripped
        errors.push('Missing column: ' + need[k]);
      }
    }
    if (errors.length) return { trips: [], meta, errors };

    const trips = [];
    for (let i = headerIdx + 1; i < lines.length; i++) {
      const line = lines[i];
      if (!line || !line.trim()) continue;
      // stop if another section starts
      if (/^(SUMMARY|DETAILED|rates\s*>>>|VEHICLE)/i.test(line.trim()) && i > headerIdx + 1) break;

      const cells = parseCsvLine(line);
      if (cells.length < 5) continue;

      const startRaw = cells[col.start_date] || '';
      const parsed = parseMileIQDate(startRaw);
      if (!parsed) {
        // skip totals / garbage
        if (/total/i.test(startRaw)) continue;
        errors.push('Skip unreadable date on line ' + (i + 1) + ': ' + startRaw);
        continue;
      }

      const category = String(cells[col.category] || '').trim();
      const purposeRaw = col.purpose != null ? String(cells[col.purpose] || '').trim() : '';
      const notesRaw = col.notes != null ? String(cells[col.notes] || '').trim() : '';
      const miles = parseNumberLoose(cells[col.miles]);
      if (!miles && !startRaw) continue;

      const parking = col.parking != null ? parseNumberLoose(cells[col.parking]) : 0;
      const tolls = col.tolls != null ? parseNumberLoose(cells[col.tolls]) : 0;
      const rateCol = col.rate != null ? parseNumberLoose(cells[col.rate]) : 0;
      const vehicle = col.vehicle != null ? String(cells[col.vehicle] || '').trim() : '';
      const from = String(cells[col.start] || '').trim();
      const to = String(cells[col.stop] || '').trim();

      const catLower = category.toLowerCase();
      const isBusiness = catLower === 'business' || catLower === 'medical' || catLower === 'charity' || catLower === 'moving';
      // TaxForge "business" flag = deductible-ish trip for tracking; category preserved
      const isPersonal = catLower === 'personal' || catLower === 'commute' || catLower === 'personal (other)';

      const noteParts = [];
      if (notesRaw) noteParts.push(notesRaw);
      if (category && purposeRaw && purposeRaw.toLowerCase() !== category.toLowerCase()) {
        /* keep both */
      }
      if (parking) noteParts.push('Parking: $' + parking.toFixed(2));
      if (tolls) noteParts.push('Tolls: $' + tolls.toFixed(2));
      if (parsed.time) noteParts.push('Start: ' + parsed.time);
      noteParts.push('MileIQ');

      const purpose = purposeRaw || category || 'Drive';
      const row = {
        id: uid('mileiq'),
        date: parsed.date,
        miles: miles,
        purpose: purpose,
        from: from,
        to: to,
        vehicle: vehicle,
        odometer: null,
        business: isPersonal ? false : isBusiness || catLower === '' ? true : true,
        category: category || (isPersonal ? 'Personal' : 'Business'),
        parking: parking,
        tolls: tolls,
        rate: rateCol || meta.businessRate || null,
        notes: noteParts.join(' · '),
        source: 'mileiq',
        sourceFile: sourceName || null,
        importedAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      };
      // fingerprint for dedupe
      row._fp = tripFingerprint(row);
      trips.push(row);
      meta.rawRows += 1;
    }

    return { trips, meta, errors };
  }

  /**
   * Merge parsed MileIQ trips into existing mileage log.
   * @param {object[]} trips
   * @param {{ mode?: 'merge'|'replace', skipDuplicates?: boolean }} opts
   */
  function importMileIQTrips(trips, opts) {
    opts = opts || {};
    const mode = opts.mode || 'merge';
    const skipDup = opts.skipDuplicates !== false;
    let existing = mode === 'replace' ? [] : getMileage();
    const fps = new Set(existing.map(tripFingerprint));
    let added = 0;
    let skipped = 0;
    const incoming = Array.isArray(trips) ? trips : [];
    incoming.forEach((t) => {
      const fp = t._fp || tripFingerprint(t);
      if (skipDup && fps.has(fp)) {
        skipped += 1;
        return;
      }
      const clean = Object.assign({}, t);
      delete clean._fp;
      if (!clean.id) clean.id = uid('mileiq');
      existing.push(clean);
      fps.add(fp);
      added += 1;
    });
    // newest first
    existing.sort((a, b) => String(b.date).localeCompare(String(a.date)));
    setMileage(existing);

    // Optionally adopt MileIQ business rate if Hub rate looks default and import has rate
    if (opts.applyRate && incoming.length) {
      const rate = incoming.find((t) => t.rate)?.rate;
      if (rate) setSettings({ mileageRate: Number(rate) });
    }

    return { added, skipped, total: existing.length };
  }

  global.TaxForge = {
    KEYS,
    EXPENSE_CATEGORIES,
    DEFAULT_SETTINGS,
    uid,
    load,
    save,
    getSettings,
    setSettings,
    getMileage,
    setMileage,
    getExpenses,
    setExpenses,
    getQuarterly,
    setQuarterly,
    defaultQuarters,
    getChecklist,
    setChecklist,
    getQuestions,
    setQuestions,
    formatMoney,
    formatDate,
    todayISO,
    download,
    toCsv,
    exportAll,
    importAll,
    stats,
    parseCsvLine,
    parseMileIQCsv,
    importMileIQTrips,
    tripFingerprint
  };
})(typeof window !== 'undefined' ? window : globalThis);
