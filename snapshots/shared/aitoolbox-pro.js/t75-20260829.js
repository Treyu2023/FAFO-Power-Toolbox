/**
 * AI Toolbox Pro shell — professional chrome for every tool.
 *
 * Auto-features (when this script loads):
 *  1. Counterpart / related-tools ribbon
 *  2. Keyboard help (? or Ctrl+/) + quick actions
 *  3. Focus mode (F), density toggle, copy page report, recents
 *  4. Look panel (O) — Layout (phone/desktop) and Lighting (glow/accents) are separate
 *
 * Page authors can refine with:
 *   <meta name="aitoolbox-tool-id" content="event-viewer">
 *   window.AITOOLBOX_PRO = { toolId, title, counterparts, actions: [{id,label,run}] }
 *
 * Snapshots: newest 5 copies of THIS file live in snapshots/shared/aitoolbox-pro.js/
 * (per app, not a global pool). Never leave .bak next to live files. See snapshots/README.md
 */
(function (global) {
  'use strict';

  const LS_RECENT = 'aitoolbox.pro.recents';
  const LS_FOCUS = 'aitoolbox.pro.focus';
  const LS_DENSE = 'aitoolbox.pro.dense';
  const LS_MINI = 'aitoolbox.pro.minibar';
  const MAX_RECENT = 14;

  (function loadPrefsModule() {
    if (global.AIToolboxPrefs) return;
    try {
      const cur = document.currentScript;
      const src = (cur && (cur.src || cur.getAttribute('src'))) || '';
      if (!src) return;
      const url = src.replace(/aitoolbox-pro\.js(\?.*)?$/i, 'aitoolbox-prefs.js');
      if (url === src) return;
      const s = document.createElement('script');
      s.src = url;
      s.async = false;
      cur.parentNode.insertBefore(s, cur.nextSibling);
    } catch (_) { /* prefs still optional */ }
  })();

  /** Canonical tool graph: path fragment → meta + counterparts */
  const REGISTRY = {
    'toolbox launcher': {
      id: 'launcher', title: 'Toolbox Launcher', emoji: '🚀',
      counterparts: ['startup-command-board', 'setup-configurator'],
    },
    'startup command board': {
      id: 'startup-command-board', title: 'Startup Command Board', emoji: '🖥',
      path: 'Startup Command Board.html',
      counterparts: ['setup-configurator', 'sys-health-desk'],
    },
    'setup configurator': {
      id: 'setup-configurator', title: 'Setup Configurator', emoji: '⚙',
      path: 'Setup Configurator.html',
      counterparts: ['startup-command-board'],
    },
    'media hub': {
      id: 'media-hub', title: 'Media Hub', emoji: '🗂️',
      path: 'Movie File Manager/Media Hub.html',
      counterparts: ['compare-hub', 'vsr-pipeline', 'duplicate-finder'],
    },
    'compare hub': {
      id: 'compare-hub', title: 'Compare Hub', emoji: '⇄',
      path: 'Movie File Manager/Compare Hub.html',
      counterparts: ['media-hub', 'guided-pair-match', 'vsr-pipeline'],
    },
    'guided pair match': {
      id: 'guided-pair-match', title: 'Guided Pair Match', emoji: '🎯',
      path: 'Movie File Manager/Guided Pair Match.html',
      counterparts: ['pair-review', 'compare-hub', 'media-hub'],
    },
    'pair review': {
      id: 'pair-review', title: 'Pair Review Queue', emoji: '🔎',
      path: 'Movie File Manager/Pair Review Queue.html',
      counterparts: ['guided-pair-match', 'compare-hub', 'video-compare'],
    },
    'media library': {
      id: 'media-library', title: 'Media Library', emoji: '📚',
      path: 'Movie File Manager/Media Library Manager.html',
      counterparts: ['media-hub', 'file-organizer', 'duplicate-finder'],
    },
    'file organizer': {
      id: 'file-organizer', title: 'File Organizer', emoji: '✏️',
      path: 'Movie File Manager/File Organizer.html',
      counterparts: ['media-hub', 'media-library', 'vsr-pipeline'],
    },
    'vsr pipeline': {
      id: 'vsr-pipeline', title: 'Mismatched Source Companion', emoji: '🔗',
      path: 'Movie File Manager/Mismatched Source Companion.html',
      counterparts: ['media-hub', 'compare-hub', 'batch-media'],
    },
    'mismatched source': {
      id: 'vsr-pipeline', title: 'Mismatched Source Companion', emoji: '🔗',
      path: 'Movie File Manager/Mismatched Source Companion.html',
      counterparts: ['media-hub', 'compare-hub', 'batch-media'],
    },
    'video comparison': {
      id: 'video-compare', title: 'Video Comparator', emoji: '🎬',
      path: 'Video Tools/Video Comparison Slider Tool.html',
      counterparts: ['image-compare', 'compare-hub', 'fafo-vid-trim'],
    },
    'image comparitor': {
      id: 'image-compare', title: 'Image Comparator', emoji: '🖼️',
      path: 'Image tools/Image Comparitor With Slider.html',
      counterparts: ['video-compare', 'compare-hub', 'image-cropper'],
    },
    'image comparator': {
      id: 'image-compare', title: 'Image Comparator', emoji: '🖼️',
      path: 'Image tools/Image Comparitor With Slider.html',
      counterparts: ['video-compare', 'compare-hub', 'image-cropper'],
    },
    'fafo_vid_trim': {
      id: 'fafo-vid-trim', title: 'FAFO VID TRIM', emoji: '🥷',
      path: 'Video Tools/FAFO_VID_TRIM.html',
      counterparts: ['image-cropper', 'batch-media', 'video-compare'],
    },
    'gemplay': {
      id: 'video-wall', title: 'Video Wall', emoji: '📺',
      path: 'Video Tools/GEMPlayHTML.html',
      counterparts: ['media-hub', 'video-compare', 'batch-media'],
    },
    'batch media converter': {
      id: 'batch-media', title: 'Batch Media Converter', emoji: '🔄',
      path: 'System Tools/Batch Media Converter.html',
      counterparts: ['fafo-vid-trim', 'vsr-pipeline', 'media-hub'],
    },
    'image converter_cropper': {
      id: 'image-cropper', title: 'Image Cropper', emoji: '✂️',
      path: 'Image tools/image Converter_Cropper for chrome store resolution.html',
      counterparts: ['fafo-vid-trim', 'image-compare'],
    },
    'event viewer': {
      id: 'event-viewer', title: 'Event Viewer', emoji: '📜',
      path: 'System Tools/Event Viewer.html',
      counterparts: ['event-deep-dive', 'health-dashboard', 'pc-diagnostics'],
    },
    'event deep dive': {
      id: 'event-deep-dive', title: 'Event Deep Dive', emoji: '🔎',
      path: 'System Tools/Event Deep Dive.html',
      counterparts: ['event-viewer', 'health-dashboard', 'malware-defender'],
    },
    'system health dashboard': {
      id: 'health-dashboard', title: 'Health Dashboard', emoji: '📊',
      path: 'System Tools/System Health Dashboard.html',
      counterparts: ['sys-health-desk', 'pc-diagnostics', 'event-viewer'],
    },
    'system health desk': {
      id: 'sys-health-desk', title: 'System Health Desk', emoji: '🩺',
      path: 'System Tools/System Health Desk.html',
      counterparts: ['health-dashboard', 'secrets-presence', 'pc-diagnostics'],
    },
    'pc diagnostics': {
      id: 'pc-diagnostics', title: 'PC Diagnostics HUD', emoji: '🩺',
      path: 'System Tools/PC Diagnostics HUD.html',
      counterparts: ['health-dashboard', 'hardware-board', 'disk-analyzer'],
    },
    'hardware board': {
      id: 'hardware-board', title: 'Hardware Board Map', emoji: '🔌',
      path: 'System Tools/Hardware Board Map.html',
      counterparts: ['pc-diagnostics', 'ghost-device', 'health-dashboard'],
    },
    'lan task manager': {
      id: 'lan-task', title: 'LAN & Task Manager', emoji: '📶',
      path: 'System Tools/LAN Task Manager.html',
      counterparts: ['fafo-task-pro', 'hosts-blocker', 'ip-profile'],
    },
    'fafo task manager pro': {
      id: 'fafo-task-pro', title: 'Task Manager Pro', emoji: '🧠',
      path: 'System Tools/FAFO Task Manager Pro.html',
      counterparts: ['lan-task', 'startup-manager', 'malware-defender'],
    },
    'malware defender': {
      id: 'malware-defender', title: 'Malware Defender', emoji: '🛡️',
      path: 'System Tools/Malware Defender.html',
      counterparts: ['hosts-blocker', 'fafo-task-pro', 'secrets-presence'],
    },
    'hosts dns blocker': {
      id: 'hosts-blocker', title: 'Hosts & DNS Blocker', emoji: '🔒',
      path: 'System Tools/Hosts DNS Blocker.html',
      counterparts: ['malware-defender', 'lan-task', 'ip-profile'],
    },
    'ip profile switcher': {
      id: 'ip-profile', title: 'IP Profile Switcher', emoji: '🌐',
      path: 'System Tools/IP Profile Switcher.html',
      counterparts: ['lan-task', 'hosts-blocker'],
    },
    'startup service manager': {
      id: 'startup-manager', title: 'Startup & Services', emoji: '🚀',
      path: 'System Tools/Startup Service Manager.html',
      counterparts: ['fafo-task-pro', 'disk-analyzer', 'health-dashboard'],
    },
    'disk space analyzer': {
      id: 'disk-analyzer', title: 'Disk Space Analyzer', emoji: '💾',
      path: 'System Tools/Disk Space Analyzer.html',
      counterparts: ['startup-manager', 'duplicate-finder', 'fafo-ops-stats', 'media-hub'],
    },
    'secrets presence': {
      id: 'secrets-presence', title: 'Secrets Presence', emoji: '🔐',
      path: 'System Tools/Secrets Presence Console.html',
      counterparts: ['sys-health-desk', 'malware-defender'],
    },
    'ditto groups': {
      id: 'ditto-groups', title: 'Ditto Groups', emoji: '📋',
      path: 'System Tools/Ditto Groups.html',
      counterparts: ['startup-command-board', 'sys-health-desk'],
    },
    'transfer monitor': {
      id: 'transfer-monitor', title: 'Transfer Monitor', emoji: '📡',
      path: 'System Tools/TransferMonitor/Transfer Monitor.html',
      counterparts: ['disk-analyzer', 'batch-media', 'vsr-pipeline'],
    },
    'pc reports': {
      id: 'pc-reports', title: 'PC Reports & Logs', emoji: '📋',
      path: 'System Tools/PC Reports and Log Viewer/index.html',
      counterparts: ['event-viewer', 'health-dashboard', 'pc-diagnostics'],
    },
    'windows reg qol': {
      id: 'reg-qol', title: 'REG QoL Tweaks', emoji: '⚙️',
      path: 'REG Tweak AI Bat Files/Windows REG QoL Tweaks.html',
      counterparts: ['startup-manager', 'ghost-device'],
    },
    'clear-ghostdevices': {
      id: 'ghost-device', title: 'Ghost Buster', emoji: '👻',
      path: 'GhostDeviceCleaner/Clear-GhostDevices.html',
      counterparts: ['hardware-board', 'reg-qol', 'pc-diagnostics'],
    },
    'git repository manager': {
      id: 'git-manager', title: 'Git Repository Manager', emoji: '🔀',
      path: 'Developer Tools/Git Repository Manager.html',
      counterparts: ['launcher'],
    },
    'fafo ops stats': {
      id: 'fafo-ops-stats', title: 'FAFO Ops Stats', emoji: '📊',
      path: 'System Tools/FAFO Ops Stats.html',
      counterparts: ['duplicate-finder', 'disk-analyzer', 'media-hub'],
    },
    'ops stats': {
      id: 'fafo-ops-stats', title: 'FAFO Ops Stats', emoji: '📊',
      path: 'System Tools/FAFO Ops Stats.html',
      counterparts: ['duplicate-finder', 'disk-analyzer', 'media-hub'],
    },
    'duplicate file manager': {
      id: 'duplicate-finder', title: 'Duplicate File Manager', emoji: '🗑️',
      path: 'File Tools/Duplicate File Manager.html',
      counterparts: ['media-hub', 'disk-analyzer', 'fafo-ops-stats', 'file-organizer'],
    },
    'commander site console': {
      id: 'commander-console', title: 'Commander Site Console', emoji: '🛰️',
      path: 'Verifone Tools/Commander Site Console.html',
      counterparts: ['commander-hud', 'phone-assist', 'pre-reload'],
    },
    'commander status hud': {
      id: 'commander-hud', title: 'Commander Status HUD', emoji: '📡',
      path: 'Verifone Tools/Commander Status HUD.html',
      counterparts: ['commander-console'],
    },
    'phone assist navigator': {
      id: 'phone-assist', title: 'Phone Assist Navigator', emoji: '📞',
      path: 'Verifone Tools/Phone Assist Navigator.html',
      counterparts: ['commander-console', 'pre-reload'],
    },
    'pre-reload punch list': {
      id: 'pre-reload', title: 'Pre-Reload Punch List', emoji: '✅',
      path: 'Verifone Tools/Pre-Reload Punch List.html',
      counterparts: ['phone-assist', 'commander-console'],
    },
    'amoritization': {
      id: 'loan-calc', title: 'Loan Calculator', emoji: '💰',
      path: 'Accounting Tools and calculators/Amoritization loan calculator2.html',
      counterparts: ['universal-converter'],
    },
    'universal converter': {
      id: 'universal-converter', title: 'Universal Converter', emoji: '🧮',
      path: 'Accounting Tools and calculators/Universal Converter.html',
      counterparts: ['loan-calc'],
    },
    'typing assistant trainer': {
      id: 'typing-trainer', title: 'KEYFLARE', emoji: '⚡',
      path: 'Typing Assistant Trainer.html',
      counterparts: ['bloodmoon', 'empire-seed'],
    },
    'keyflare': {
      id: 'typing-trainer', title: 'KEYFLARE', emoji: '⚡',
      path: 'Typing Assistant Trainer.html',
      counterparts: ['bloodmoon', 'empire-seed'],
    },
    'bloodmoon survivor': {
      id: 'bloodmoon', title: 'Bloodmoon Survivor', emoji: '🦇',
      path: 'Bloodmoon Survivor.html',
      counterparts: ['typing-trainer', 'empire-seed'],
    },
    'empire seed': {
      id: 'empire-seed', title: 'Empire Seed 3D', emoji: '👑',
      path: 'Empire Seed.html',
      counterparts: ['typing-trainer', 'bloodmoon'],
    },
    'solar system debris': {
      id: 'solar-debris', title: 'Debris Tracker', emoji: '🪐',
      path: 'Solar System Debris Tracker.html',
      counterparts: ['launcher'],
    },
  };

  const BY_ID = {};
  Object.values(REGISTRY).forEach((m) => {
    if (m.id) BY_ID[m.id] = m;
  });

  function detectTool() {
    const meta = document.querySelector('meta[name="aitoolbox-tool-id"]');
    if (meta && meta.content && BY_ID[meta.content]) {
      return { ...BY_ID[meta.content] };
    }
    const cfg = global.AITOOLBOX_PRO || {};
    if (cfg.toolId && BY_ID[cfg.toolId]) {
      return { ...BY_ID[cfg.toolId], ...cfg };
    }
    const title = (document.title || '').toLowerCase();
    const path = (location.pathname || location.href || '').toLowerCase();
    const hay = title + ' ' + path.replace(/%20/g, ' ').replace(/\\/g, '/');
    let best = null;
    let bestScore = 0;
    Object.keys(REGISTRY).forEach((key) => {
      if (hay.includes(key)) {
        const score = key.length;
        if (score > bestScore) {
          bestScore = score;
          best = REGISTRY[key];
        }
      }
    });
    if (best) return { ...best, ...cfg };
    return {
      id: 'unknown',
      title: document.title || 'Toolbox Tool',
      emoji: '🧰',
      counterparts: ['launcher'],
      path: null,
      ...cfg,
    };
  }

  function resolveHref(toolMeta) {
    if (!toolMeta) return null;
    if (toolMeta.id === 'launcher') {
      try {
        if (global.AIToolboxUI?.launcherHref) return global.AIToolboxUI.launcherHref();
      } catch { /* ignore */ }
      return '../Toolbox Launcher.html';
    }
    if (!toolMeta.path) return null;
    // Build path relative to current page depth
    try {
      const scripts = document.getElementsByTagName('script');
      for (let i = scripts.length - 1; i >= 0; i--) {
        const src = scripts[i].src || '';
        if (src.includes('aitoolbox-pro.js') || src.includes('aitoolbox-ui.js') || src.includes('aitoolbox-api.js')) {
          return new URL('../' + toolMeta.path, src).href;
        }
      }
    } catch { /* ignore */ }
    // file:// depth guess
    const parts = (location.pathname || '').split('/').filter(Boolean);
    const depth = Math.max(0, parts.length - 1);
    // if in subfolder of production
    if (location.protocol === 'http:' || location.protocol === 'https:') {
      try {
        const origin = global.AITOOLBOX_CONFIG?.ORIGIN || 'http://127.0.0.87:18765';
        const rawPath = String(toolMeta.path || '');
        const hashAt = rawPath.indexOf('#');
        const hash = hashAt >= 0 ? rawPath.slice(hashAt) : '';
        const noHash = hashAt >= 0 ? rawPath.slice(0, hashAt) : rawPath;
        const qAt = noHash.indexOf('?');
        const query = qAt >= 0 ? noHash.slice(qAt) : '';
        const filePath = qAt >= 0 ? noHash.slice(0, qAt) : noHash;
        return origin.replace(/\/$/, '') + '/toolbox/' + filePath.split('/').filter(Boolean).map(encodeURIComponent).join('/') + query + hash;
      } catch { /* ignore */ }
    }
    const up = depth >= 2 ? '../' : (depth === 1 ? '' : '../');
    return up + toolMeta.path;
  }

  function loadRecents() {
    try {
      return JSON.parse(localStorage.getItem(LS_RECENT) || '[]');
    } catch {
      return [];
    }
  }

  function pushRecent(tool) {
    if (!tool || !tool.id || tool.id === 'unknown') return;
    let list = loadRecents().filter((x) => x.id !== tool.id);
    list.unshift({
      id: tool.id,
      title: tool.title,
      emoji: tool.emoji || '🧰',
      path: tool.path || null,
      at: Date.now(),
    });
    list = list.slice(0, MAX_RECENT);
    try {
      localStorage.setItem(LS_RECENT, JSON.stringify(list));
    } catch { /* ignore */ }
  }

  function ensureStyles() {
    if (document.getElementById('aitoolbox-pro-css')) return;
    const css = document.createElement('style');
    css.id = 'aitoolbox-pro-css';
    css.textContent = `
#atx-pro-bar{
  position:fixed;left:0;right:0;bottom:0;z-index:99980;
  display:flex;align-items:center;gap:8px;flex-wrap:wrap;
  padding:6px 10px 8px;
  background:linear-gradient(180deg,rgba(10,12,18,.92),rgba(6,8,12,.97));
  border-top:1px solid rgba(0,243,255,.22);
  backdrop-filter:blur(10px);
  font:600 11px/1.3 "Segoe UI",system-ui,sans-serif;
  color:#c8d4e0;
  box-shadow:0 -8px 28px rgba(0,0,0,.35);
}
#atx-pro-bar .atx-brand{
  color:#00f3ff;letter-spacing:.08em;text-transform:uppercase;font-size:10px;
  white-space:nowrap;
}
#atx-pro-bar .atx-chips{display:flex;gap:6px;flex-wrap:wrap;flex:1;min-width:120px}
#atx-pro-bar a.atx-chip, #atx-pro-bar button.atx-chip{
  appearance:none;border:1px solid rgba(0,243,255,.28);background:rgba(0,243,255,.06);
  color:#d7f7ff;border-radius:999px;padding:4px 10px;cursor:pointer;text-decoration:none;
  font:600 10px/1 "Segoe UI",system-ui,sans-serif;white-space:nowrap;
}
#atx-pro-bar a.atx-chip:hover, #atx-pro-bar button.atx-chip:hover{
  border-color:#00f3ff;background:rgba(0,243,255,.14);color:#fff;
}
#atx-pro-bar a.atx-chip.primary{
  background:linear-gradient(135deg,rgba(0,243,255,.25),rgba(124,92,255,.25));
  border-color:rgba(0,243,255,.55);
}
#atx-pro-bar .atx-actions{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
#atx-pro-bar .atx-kbd{
  opacity:.65;font-size:9px;border:1px solid rgba(255,255,255,.12);
  border-radius:4px;padding:1px 4px;margin-left:4px;
}
body.atx-pro-pad{padding-bottom:52px !important}
body.atx-pro-min #atx-pro-bar{transform:translateY(72%);opacity:.45}
body.atx-pro-min #atx-pro-bar:hover, body.atx-pro-min #atx-pro-bar:focus-within{
  transform:none;opacity:1
}
body.atx-focus #atx-pro-bar{opacity:.18;transform:translateY(70%);transition:.25s}
body.atx-focus #atx-pro-bar:hover, body.atx-focus #atx-pro-bar:focus-within{
  opacity:1;transform:none
}
body.atx-dense .ui-card, body.atx-dense .panel, body.atx-dense .card{
  padding-top:10px !important;padding-bottom:10px !important;margin-bottom:10px !important
}
body.atx-dense{--ui-ease:linear}
#atx-pro-help{
  position:fixed;inset:0;z-index:99990;display:none;place-items:center;
  background:rgba(0,0,0,.55);backdrop-filter:blur(4px);
}
#atx-pro-help.open{display:grid}
#atx-pro-help .panel{
  width:min(520px,92vw);max-height:80vh;overflow:auto;
  background:#0c1018;border:1px solid rgba(0,243,255,.35);border-radius:14px;
  padding:18px 18px 14px;color:#e8eef6;box-shadow:0 20px 60px rgba(0,0,0,.5);
}
#atx-pro-help h2{margin:0 0 8px;font-size:15px;color:#00f3ff;letter-spacing:.06em}
#atx-pro-help ul{margin:0;padding:0 0 0 16px;font-size:12px;line-height:1.7;color:#b8c4d4}
#atx-pro-help kbd{
  font:600 10px ui-monospace,Consolas,monospace;border:1px solid rgba(255,255,255,.2);
  border-bottom-width:2px;border-radius:4px;padding:1px 5px;background:rgba(255,255,255,.06)
}
#atx-pro-help .row{display:flex;justify-content:flex-end;gap:8px;margin-top:12px}
#atx-pro-help button{
  border:1px solid rgba(0,243,255,.4);background:rgba(0,243,255,.12);color:#9ff;
  border-radius:8px;padding:7px 12px;cursor:pointer;font-weight:700;font-size:11px
}
#atx-pro-toast{
  position:fixed;bottom:58px;right:14px;z-index:99985;
  background:rgba(8,14,20,.95);border:1px solid rgba(0,243,255,.35);
  color:#dff;padding:8px 12px;border-radius:10px;font:600 11px/1.3 "Segoe UI",system-ui,sans-serif;
  opacity:0;transform:translateY(8px);transition:.2s;pointer-events:none;max-width:360px
}
#atx-pro-toast.show{opacity:1;transform:none}
@media print{
  #atx-pro-bar, #atx-pro-help, #atx-pro-toast{display:none !important}
  body.atx-pro-pad{padding-bottom:0 !important}
}
`;
    document.head.appendChild(css);
  }

  function toast(msg) {
    let el = document.getElementById('atx-pro-toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'atx-pro-toast';
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove('show'), 2200);
  }

  function copyText(text) {
    if (navigator.clipboard?.writeText) {
      return navigator.clipboard.writeText(text).then(() => true).catch(() => false);
    }
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      ta.remove();
      return Promise.resolve(true);
    } catch {
      return Promise.resolve(false);
    }
  }

  function buildReport(tool) {
    const lines = [
      'FAFO Toolbox — tool snapshot',
      '============================',
      'Tool: ' + (tool.emoji || '') + ' ' + tool.title + ' (' + tool.id + ')',
      'URL: ' + location.href,
      'Time: ' + new Date().toISOString(),
      'UserAgent: ' + navigator.userAgent,
      'Online: ' + (navigator.onLine ? 'yes' : 'no'),
      '',
      'Counterparts: ' + (tool.counterparts || []).join(', '),
      '',
      'Title: ' + document.title,
      'Body text sample:',
      (document.body?.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 1200),
    ];
    return lines.join('\n');
  }

  function openHelp(tool) {
    let el = document.getElementById('atx-pro-help');
    if (!el) {
      el = document.createElement('div');
      el.id = 'atx-pro-help';
      el.innerHTML = '<div class="panel" role="dialog" aria-modal="true" aria-label="Keyboard shortcuts"></div>';
      el.addEventListener('click', (e) => {
        if (e.target === el) el.classList.remove('open');
      });
      document.body.appendChild(el);
    }
    const panel = el.querySelector('.panel');
    const custom = (global.AITOOLBOX_PRO && global.AITOOLBOX_PRO.helpLines) || [];
    let lastErr = '';
    try { lastErr = sessionStorage.getItem('atx_last_error') || ''; } catch { lastErr = ''; }
    panel.innerHTML = `
      <h2>${tool.emoji || '🧰'} ${escapeHtml(tool.title)} — Pro shortcuts</h2>
      <ul>
        <li><kbd>?</kbd> or <kbd>Ctrl</kbd>+<kbd>/</kbd> — this help</li>
        <li><kbd>/</kbd> — jump to search / filter box</li>
        <li><kbd>F</kbd> — focus mode (dim chrome)</li>
        <li><kbd>D</kbd> — compact density</li>
        <li><kbd>O</kbd> — Look (layout vs lighting)</li>
        <li><kbd>B</kbd> — previous tool (recents)</li>
        <li><kbd>L</kbd> — Toolbox launcher</li>
        <li><kbd>C</kbd> — jump first counterpart</li>
        <li><kbd>R</kbd> — copy page report to clipboard</li>
        <li><kbd>Esc</kbd> — close overlays, then back to launcher</li>
        <li>Ctrl/⌘-click a launcher card — open in a new tab</li>
        ${custom.map((x) => '<li>' + escapeHtml(x) + '</li>').join('')}
        ${lastErr ? '<li>Last script error: <code>' + escapeHtml(lastErr) + '</code></li>' : ''}
      </ul>
      <div class="row"><button type="button" id="atxHelpClose">Close</button></div>`;
    el.classList.add('open');
    panel.querySelector('#atxHelpClose')?.addEventListener('click', () => el.classList.remove('open'));
  }

  function escapeHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function mountBar(tool) {
    if (document.getElementById('atx-pro-bar')) return;
    // Skip inside nested iframes without own chrome? still useful.
    ensureStyles();
    document.body.classList.add('atx-pro-pad');
    if (localStorage.getItem(LS_FOCUS) === '1') document.body.classList.add('atx-focus');
    if (localStorage.getItem(LS_DENSE) === '1') document.body.classList.add('atx-dense');
    if (localStorage.getItem(LS_MINI) === '1') document.body.classList.add('atx-pro-min');

    const bar = document.createElement('div');
    bar.id = 'atx-pro-bar';
    bar.setAttribute('role', 'navigation');
    bar.setAttribute('aria-label', 'Toolbox pro bar');

    const counterparts = (tool.counterparts || [])
      .map((id) => BY_ID[id])
      .filter(Boolean);

    const chips = counterparts.map((c, i) => {
      const href = resolveHref(c);
      const cls = i === 0 ? 'atx-chip primary' : 'atx-chip';
      return href
        ? `<a class="${cls}" href="${href}" title="Open counterpart">${c.emoji || ''} ${escapeHtml(c.title)}</a>`
        : '';
    }).join('');

    const launcher = resolveHref(BY_ID.launcher) || '../Toolbox Launcher.html';

    bar.innerHTML = `
      <span class="atx-brand">${tool.emoji || '🧰'} ${escapeHtml(tool.title)}</span>
      <div class="atx-chips">${chips || '<span style="opacity:.5">No counterparts mapped</span>'}</div>
      <div class="atx-actions">
        <a class="atx-chip" href="${launcher}">🚀 Launcher</a>
        <button type="button" class="atx-chip" data-act="help">Help <span class="atx-kbd">?</span></button>
        <button type="button" class="atx-chip" data-act="back">Back <span class="atx-kbd">B</span></button>
        <button type="button" class="atx-chip" data-act="focus">Focus <span class="atx-kbd">F</span></button>
        <button type="button" class="atx-chip" data-act="dense">Dense <span class="atx-kbd">D</span></button>
        <button type="button" class="atx-chip" data-act="look">Look <span class="atx-kbd">O</span></button>
        <button type="button" class="atx-chip" data-act="report">Report <span class="atx-kbd">R</span></button>
        <button type="button" class="atx-chip" data-act="minibar" title="Tuck the bar away until hover">▾</button>
      </div>`;

    bar.addEventListener('click', async (e) => {
      const btn = e.target.closest('[data-act]');
      if (!btn) return;
      const act = btn.getAttribute('data-act');
      if (act === 'help') openHelp(tool);
      if (act === 'focus') {
        document.body.classList.toggle('atx-focus');
        localStorage.setItem(LS_FOCUS, document.body.classList.contains('atx-focus') ? '1' : '0');
        toast(document.body.classList.contains('atx-focus') ? 'Focus mode on' : 'Focus mode off');
      }
      if (act === 'dense') {
        document.body.classList.toggle('atx-dense');
        const compact = document.body.classList.contains('atx-dense');
        localStorage.setItem(LS_DENSE, compact ? '1' : '0');
        try { global.AIToolboxPrefs?.save({ density: compact ? 'compact' : 'comfortable' }); } catch (_) { /* ignore */ }
        toast(compact ? 'Compact density' : 'Comfortable density');
      }
      if (act === 'look') {
        try {
          if (global.AIToolboxPrefs?.open) global.AIToolboxPrefs.open();
          else toast('Look module still loading — try O in a second');
        } catch (_) { toast('Look panel unavailable'); }
      }
      if (act === 'report') {
        const ok = await copyText(buildReport(tool));
        toast(ok ? 'Report copied to clipboard' : 'Copy failed');
      }
      if (act === 'back') goBack(tool);
      if (act === 'minibar') {
        document.body.classList.toggle('atx-pro-min');
        localStorage.setItem(LS_MINI, document.body.classList.contains('atx-pro-min') ? '1' : '0');
        toast(document.body.classList.contains('atx-pro-min') ? 'Bar tucked — hover to expand' : 'Bar pinned');
      }
    });

    document.body.appendChild(bar);
  }

  function goBack(tool) {
    const rec = loadRecents();
    const prev = rec.find((x) => x && x.id && x.id !== tool.id && x.id !== 'launcher' && x.id !== 'unknown');
    const href = prev ? resolveHref(prev) : resolveHref(BY_ID.launcher);
    if (href) location.href = href;
    else toast('No previous tool yet');
  }

  function bindKeys(tool) {
    document.addEventListener('keydown', (e) => {
      const tag = (e.target && e.target.tagName) || '';
      const typing = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target?.isContentEditable;
      if (e.key === 'Escape') {
        document.getElementById('atx-pro-help')?.classList.remove('open');
      }
      if (typing && e.key !== 'Escape') return;
      if (e.key === '?' || (e.key === '/' && e.ctrlKey)) {
        e.preventDefault();
        openHelp(tool);
        return;
      }
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (tool.id === 'launcher') {
        if (e.key === 'b' || e.key === 'B') goBack(tool);
        return;
      }
      if (e.key === 'f' || e.key === 'F') {
        document.body.classList.toggle('atx-focus');
        localStorage.setItem(LS_FOCUS, document.body.classList.contains('atx-focus') ? '1' : '0');
      } else if (e.key === 'd' || e.key === 'D') {
        document.body.classList.toggle('atx-dense');
        const compact = document.body.classList.contains('atx-dense');
        localStorage.setItem(LS_DENSE, compact ? '1' : '0');
        try { global.AIToolboxPrefs?.save({ density: compact ? 'compact' : 'comfortable' }); } catch (_) { /* ignore */ }
      } else if (e.key === 'b' || e.key === 'B') {
        goBack(tool);
      } else if (e.key === 'l' || e.key === 'L') {
        location.href = resolveHref(BY_ID.launcher) || '../Toolbox Launcher.html';
      } else if (e.key === 'c' || e.key === 'C') {
        const first = (tool.counterparts || []).map((id) => BY_ID[id]).find(Boolean);
        const href = resolveHref(first);
        if (href) location.href = href;
      } else if (e.key === 'r' || e.key === 'R') {
        copyText(buildReport(tool)).then((ok) => toast(ok ? 'Report copied' : 'Copy failed'));
      }
    });
  }

  function installGuard() {
    if (global.__atxGuard) return;
    global.__atxGuard = true;
    const note = (msg) => {
      try { sessionStorage.setItem('atx_last_error', String(msg || 'error').slice(0, 400)); } catch { /* ignore */ }
    };
    window.addEventListener('error', (e) => {
      note((e && (e.message || e.error)) || 'script error');
    });
    window.addEventListener('unhandledrejection', (e) => {
      const r = e && e.reason;
      note((r && (r.message || r)) || 'unhandled rejection');
    });
  }

  function boot() {
    if (global.AITOOLBOX_PRO_DISABLE) return;
    // Don't double-mount inside extension pages without body
    if (!document.body) return;
    try { installGuard(); } catch { /* ignore */ }
    // Launcher has its own chrome — light mode only (recents + help still ok)
    const tool = detectTool();
    pushRecent(tool);
    if (tool.id === 'launcher') {
      ensureStyles();
      bindKeys(tool);
      return;
    }
    mountBar(tool);
    bindKeys(tool);
    try {
      if (global.AIToolboxUI?.initTooltips) global.AIToolboxUI.initTooltips(document.getElementById('atx-pro-bar'));
    } catch { /* ignore */ }
    // Modular layout (resize / reorder / persist) — opt-in via data-fafo-layout-root
    try {
      if (global.AIToolboxLayout?.autoInit) global.AIToolboxLayout.autoInit();
    } catch { /* ignore */ }
  }

  global.AIToolboxPro = {
    REGISTRY,
    BY_ID,
    detectTool,
    resolveHref,
    toast,
    copyText,
    buildReport,
    openHelp,
    loadRecents,
    boot,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})(typeof window !== 'undefined' ? window : globalThis);
