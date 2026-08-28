/**
 * FAFO Ops Stats — lifetime + session tallies for toolbox tools.
 *
 * Flexible per-tool metrics: cleanup (files/bytes), pairing (matches/rejects/syncs),
 * typing (by player name), renames, conversions, scans, etc.
 * Sessions are only persisted when something actually changed.
 *
 * Usage:
 *   FAFOOpsStats.record({
 *     tool: 'duplicate-file-manager',
 *     action: 'merge',
 *     filesRemoved: 3,
 *     bytesFreed: 12_000_000,
 *     groupsMerged: 1,
 *   });
 *   FAFOOpsStats.record({
 *     tool: 'guided-pair-match',
 *     action: 'match',
 *     metrics: { pairMatches: 1 },
 *   });
 *   FAFOOpsStats.record({
 *     tool: 'typing-assistant',
 *     action: 'run-complete',
 *     actor: 'Ryan Key',
 *     metrics: { typingRuns: 1, typingChars: 420, typingWpmSum: 65, typingBestWpm: 65 },
 *   });
 *   FAFOOpsStats.snapshot(); // totals + current session + recent sessions
 */
(function (global) {
  'use strict';

  const LS_KEY = 'fafo_ops_stats_v1';
  const MAX_SESSIONS = 250;
  const SCHEMA = 2;
  const DEFAULT_TYPING_ACTOR = 'Ryan Key';

  /** @type {Record<string, {label: string, emoji: string, color: string}>} */
  const TOOL_META = {
    'duplicate-file-manager': { label: 'Duplicate File Manager', emoji: '🗑️', color: '#ff6b35' },
    'media-library-manager': { label: 'Media Library', emoji: '📚', color: '#00f3ff' },
    'file-organizer': { label: 'File Organizer', emoji: '✏️', color: '#7c5cff' },
    'vsr-pipeline-manager': { label: 'Mismatched Source Companion', emoji: '🔗', color: '#a78bfa' },
    'batch-media-converter': { label: 'Batch Converter', emoji: '🔄', color: '#34d399' },
    'fafo-vid-trim': { label: 'VID ŦRIM', emoji: '🎬', color: '#38bdf8' },
    'disk-space-analyzer': { label: 'Disk Analyzer', emoji: '💾', color: '#fbbf24' },
    'guided-pair-match': { label: 'Guided Pair Match', emoji: '🎯', color: '#f472b6' },
    'pair-review-queue': { label: 'Pair Review Queue', emoji: '🔎', color: '#fb7185' },
    'typing-assistant': { label: 'KEYFLARE', emoji: '⚡', color: '#22d3ee' },
    'other': { label: 'Other tools', emoji: '🧰', color: '#94a3b8' },
  };

  /**
   * Metric definitions.
   * mode: 'sum' (default) | 'max'
   */
  const METRIC_DEFS = {
    filesRemoved: { label: 'Files removed', mode: 'sum', primary: true },
    bytesFreed: { label: 'Storage freed', mode: 'sum', primary: true, format: 'bytes' },
    groupsMerged: { label: 'Groups merged', mode: 'sum', primary: true },
    pairMatches: { label: 'Correct pair matches', mode: 'sum', primary: true },
    pairRejects: { label: 'Incorrect / rejected', mode: 'sum', primary: true },
    pairSkips: { label: 'Pairs skipped', mode: 'sum' },
    syncsCompleted: { label: 'Syncs completed', mode: 'sum', primary: true },
    renamesApplied: { label: 'Renames applied', mode: 'sum', primary: true },
    pairsSaved: { label: 'Pairs saved', mode: 'sum', primary: true },
    pairsDeleted: { label: 'Pair links deleted', mode: 'sum' },
    scansCompleted: { label: 'Scans completed', mode: 'sum' },
    filesOrganized: { label: 'Files organized', mode: 'sum', primary: true },
    conversions: { label: 'Conversions done', mode: 'sum', primary: true },
    typingRuns: { label: 'Typing runs', mode: 'sum', primary: true },
    typingChars: { label: 'Characters typed', mode: 'sum', primary: true },
    typingWpmSum: { label: 'WPM sum (for avg)', mode: 'sum' },
    typingBestWpm: { label: 'Best WPM', mode: 'max', primary: true },
    actions: { label: 'Actions', mode: 'sum' },
  };

  const METRIC_KEYS = Object.keys(METRIC_DEFS);

  function emptyMetrics() {
    const m = {};
    for (const k of METRIC_KEYS) m[k] = 0;
    return m;
  }

  function emptyStore() {
    return {
      schema: SCHEMA,
      lifetime: {
        ...emptyMetrics(),
        byTool: {},
        byActor: {},
        firstAt: null,
        lastAt: null,
        sessionCount: 0,
      },
      sessions: [],
      openSession: null,
    };
  }

  function ensureMetricsShape(obj) {
    if (!obj || typeof obj !== 'object') return emptyMetrics();
    for (const k of METRIC_KEYS) {
      if (typeof obj[k] !== 'number' || !Number.isFinite(obj[k])) obj[k] = 0;
    }
    return obj;
  }

  function load() {
    try {
      const raw = JSON.parse(localStorage.getItem(LS_KEY) || 'null');
      if (!raw || typeof raw !== 'object') return emptyStore();
      if (!raw.lifetime) raw.lifetime = emptyStore().lifetime;
      ensureMetricsShape(raw.lifetime);
      if (!Array.isArray(raw.sessions)) raw.sessions = [];
      if (!raw.lifetime.byTool || typeof raw.lifetime.byTool !== 'object') raw.lifetime.byTool = {};
      if (!raw.lifetime.byActor || typeof raw.lifetime.byActor !== 'object') raw.lifetime.byActor = {};
      // migrate schema
      raw.schema = SCHEMA;
      // ensure open session metrics shape
      if (raw.openSession) {
        ensureMetricsShape(raw.openSession);
        if (!raw.openSession.byActor || typeof raw.openSession.byActor !== 'object') {
          raw.openSession.byActor = {};
        }
      }
      return raw;
    } catch (_) {
      return emptyStore();
    }
  }

  function save(store) {
    try {
      localStorage.setItem(LS_KEY, JSON.stringify(store));
      return true;
    } catch (e) {
      console.warn('[FAFOOpsStats] save failed', e);
      return false;
    }
  }

  function nowIso() {
    return new Date().toISOString();
  }

  function metricValue(obj, key) {
    return Math.max(0, Number(obj && obj[key]) || 0);
  }

  function sessionDirty(s) {
    if (!s) return false;
    if ((s.actions || 0) > 0) return true;
    for (const k of METRIC_KEYS) {
      if (k === 'actions') continue;
      if (metricValue(s, k) > 0) return true;
    }
    return false;
  }

  function ensureToolBucket(store, tool) {
    const key = tool || 'other';
    if (!store.lifetime.byTool[key]) {
      store.lifetime.byTool[key] = { ...emptyMetrics(), sessions: 0 };
    } else {
      ensureMetricsShape(store.lifetime.byTool[key]);
    }
    return store.lifetime.byTool[key];
  }

  function ensureActorBucket(parent, actor) {
    const name = String(actor || '').trim() || 'Anonymous';
    if (!parent.byActor || typeof parent.byActor !== 'object') parent.byActor = {};
    if (!parent.byActor[name]) {
      parent.byActor[name] = { ...emptyMetrics() };
    } else {
      ensureMetricsShape(parent.byActor[name]);
    }
    return parent.byActor[name];
  }

  function applyDelta(target, deltas) {
    for (const k of Object.keys(deltas)) {
      if (!METRIC_DEFS[k]) continue;
      const v = Math.max(0, Number(deltas[k]) || 0);
      if (!v) continue;
      const mode = METRIC_DEFS[k].mode || 'sum';
      if (mode === 'max') {
        target[k] = Math.max(metricValue(target, k), v);
      } else {
        target[k] = metricValue(target, k) + v;
      }
    }
  }

  /**
   * Normalize event into a metric delta map (only positive values).
   * Nested `metrics` wins over same-named top-level keys (no double count).
   */
  function extractDeltas(evt) {
    const deltas = {};
    const seen = Object.create(null);

    function addMetric(k, raw, fromMetricsObj) {
      if (!METRIC_DEFS[k] || k === 'actions') return;
      if (seen[k] && !fromMetricsObj) return; // already took nested metrics
      const mode = METRIC_DEFS[k].mode || 'sum';
      let v = Number(raw);
      if (!Number.isFinite(v) || v <= 0) return;
      if (mode === 'max') {
        v = Math.round(v);
        deltas[k] = Math.max(deltas[k] || 0, v);
      } else {
        // allow fractional WPM sum; floor other ints
        v = (k === 'typingWpmSum') ? Math.round(v) : Math.max(0, Math.floor(v));
        if (!v) return;
        deltas[k] = (deltas[k] || 0) + v;
      }
      if (fromMetricsObj) seen[k] = true;
    }

    if (evt.metrics && typeof evt.metrics === 'object') {
      for (const k of Object.keys(evt.metrics)) {
        addMetric(k, evt.metrics[k], true);
      }
    }
    for (const k of METRIC_KEYS) {
      if (k === 'actions') continue;
      if (evt[k] != null && evt[k] !== '') addMetric(k, evt[k], false);
    }
    return deltas;
  }

  function hasAnyDelta(deltas) {
    return Object.keys(deltas).some((k) => (deltas[k] || 0) > 0);
  }

  function beginSession(tool, meta) {
    const store = load();
    if (store.openSession && sessionDirty(store.openSession)) {
      finalizeOpenSession(store);
    } else {
      store.openSession = null;
    }
    const toolId = tool || 'other';
    store.openSession = {
      id: 's_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 7),
      tool: toolId,
      label: (meta && meta.label) || (TOOL_META[toolId] && TOOL_META[toolId].label) || toolId,
      startedAt: nowIso(),
      endedAt: null,
      ...emptyMetrics(),
      byActor: {},
      events: [],
    };
    save(store);
    return store.openSession;
  }

  function getOpenSession(tool) {
    const store = load();
    if (store.openSession && (!tool || store.openSession.tool === tool)) {
      return store.openSession;
    }
    return null;
  }

  function ensureSession(tool, meta) {
    let s = getOpenSession(tool);
    if (!s) s = beginSession(tool, meta);
    return s;
  }

  function finalizeOpenSession(store) {
    const s = store.openSession;
    if (!s) return false;
    if (!sessionDirty(s)) {
      store.openSession = null;
      return false;
    }
    s.endedAt = nowIso();
    if (Array.isArray(s.events) && s.events.length > 40) {
      s.events = s.events.slice(-40);
    }
    store.sessions.unshift(s);
    if (store.sessions.length > MAX_SESSIONS) {
      store.sessions = store.sessions.slice(0, MAX_SESSIONS);
    }
    store.lifetime.sessionCount = (store.lifetime.sessionCount || 0) + 1;
    const bucket = ensureToolBucket(store, s.tool);
    bucket.sessions = (bucket.sessions || 0) + 1;
    store.openSession = null;
    return true;
  }

  /**
   * Record an ops event. No-op if all deltas are zero.
   * @param {object} evt
   * @param {string} evt.tool
   * @param {string} [evt.action]
   * @param {string} [evt.actor] — player / operator name (typing, multi-user)
   * @param {object} [evt.metrics] — flexible metric map
   * @param {number} [evt.filesRemoved]
   * @param {number} [evt.bytesFreed]
   * @param {number} [evt.groupsMerged]
   * @param {object} [evt.extra]
   */
  function record(evt) {
    if (!evt || typeof evt !== 'object') return null;
    const deltas = extractDeltas(evt);
    if (!hasAnyDelta(deltas)) return null;

    const tool = evt.tool || 'other';
    const actor = evt.actor != null ? String(evt.actor).trim() : '';
    const store = load();
    if (!store.openSession || store.openSession.tool !== tool) {
      if (store.openSession && sessionDirty(store.openSession)) finalizeOpenSession(store);
      store.openSession = {
        id: 's_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 7),
        tool,
        label: (TOOL_META[tool] && TOOL_META[tool].label) || tool,
        startedAt: nowIso(),
        endedAt: null,
        ...emptyMetrics(),
        byActor: {},
        events: [],
      };
    }

    const s = store.openSession;
    ensureMetricsShape(s);
    applyDelta(s, deltas);
    s.actions = (s.actions || 0) + 1;

    const event = {
      at: nowIso(),
      action: evt.action || 'action',
      ...deltas,
    };
    if (actor) event.actor = actor;
    if (evt.extra && typeof evt.extra === 'object') event.extra = evt.extra;
    s.events.push(event);
    if (s.events.length > 60) s.events = s.events.slice(-60);

    // lifetime totals
    ensureMetricsShape(store.lifetime);
    applyDelta(store.lifetime, deltas);
    store.lifetime.actions = (store.lifetime.actions || 0) + 1;
    if (!store.lifetime.firstAt) store.lifetime.firstAt = event.at;
    store.lifetime.lastAt = event.at;

    const bucket = ensureToolBucket(store, tool);
    applyDelta(bucket, deltas);
    bucket.actions = (bucket.actions || 0) + 1;

    // per-actor (typing / multi-user tools)
    if (actor) {
      const lifeActor = ensureActorBucket(store.lifetime, actor);
      applyDelta(lifeActor, deltas);
      lifeActor.actions = (lifeActor.actions || 0) + 1;

      if (!s.byActor || typeof s.byActor !== 'object') s.byActor = {};
      const sessActor = ensureActorBucket(s, actor);
      applyDelta(sessActor, deltas);
      sessActor.actions = (sessActor.actions || 0) + 1;
    }

    save(store);
    try {
      global.dispatchEvent(new CustomEvent('fafo-ops-stats', {
        detail: { type: 'record', event, session: { ...s }, lifetime: { ...store.lifetime } },
      }));
    } catch (_) { /* ignore */ }
    return { session: s, lifetime: store.lifetime, event };
  }

  function endSession() {
    const store = load();
    const wrote = finalizeOpenSession(store);
    save(store);
    return wrote;
  }

  function snapshot(opts) {
    opts = opts || {};
    const store = load();
    const limit = Math.max(1, Math.min(MAX_SESSIONS, opts.limit || 50));
    let sessions = store.sessions.slice();
    if (opts.tool) sessions = sessions.filter((s) => s.tool === opts.tool);
    // Include open session in a copy for UI if requested
    return {
      lifetime: store.lifetime,
      openSession: store.openSession,
      sessions: sessions.slice(0, limit),
      tools: TOOL_META,
      metricDefs: METRIC_DEFS,
      schema: SCHEMA,
      defaultTypingActor: DEFAULT_TYPING_ACTOR,
    };
  }

  function formatBytes(n) {
    n = Number(n) || 0;
    if (n < 1024) return n + ' B';
    const u = ['KB', 'MB', 'GB', 'TB', 'PB'];
    let i = -1;
    let v = n;
    do {
      v /= 1024;
      i++;
    } while (v >= 1024 && i < u.length - 1);
    return (v >= 10 || i === 0 ? v.toFixed(1) : v.toFixed(2)) + ' ' + u[i];
  }

  function formatMetric(key, value) {
    const def = METRIC_DEFS[key];
    const n = Number(value) || 0;
    if (def && def.format === 'bytes') return formatBytes(n);
    return n.toLocaleString();
  }

  function avgWpm(bucket) {
    if (!bucket) return 0;
    const runs = metricValue(bucket, 'typingRuns');
    const sum = metricValue(bucket, 'typingWpmSum');
    if (!runs) return 0;
    return Math.round(sum / runs);
  }

  function toolMeta(id) {
    return TOOL_META[id] || TOOL_META.other;
  }

  function resetAll() {
    save(emptyStore());
    try {
      global.dispatchEvent(new CustomEvent('fafo-ops-stats', { detail: { type: 'reset' } }));
    } catch (_) { /* ignore */ }
    return true;
  }

  // Auto-flush dirty session on page hide
  if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
    const flush = () => {
      try {
        const store = load();
        if (store.openSession && sessionDirty(store.openSession)) {
          finalizeOpenSession(store);
          save(store);
        }
      } catch (_) { /* ignore */ }
    };
    window.addEventListener('pagehide', flush);
    window.addEventListener('beforeunload', flush);
  }

  global.FAFOOpsStats = {
    record,
    beginSession,
    endSession,
    ensureSession,
    getOpenSession,
    snapshot,
    formatBytes,
    formatMetric,
    avgWpm,
    toolMeta,
    resetAll,
    TOOL_META,
    METRIC_DEFS,
    DEFAULT_TYPING_ACTOR,
    LS_KEY,
  };
})(typeof window !== 'undefined' ? window : globalThis);
