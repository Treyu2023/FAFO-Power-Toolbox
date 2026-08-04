/**
 * Audit tool pages + apply one targeted polish per unique HTML file.
 * Run: node Scripts/Audit-And-Polish-Tools.mjs
 */
import fs from 'fs';
import path from 'path';
import http from 'http';
import { fileURLToPath } from 'url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const launcher = fs.readFileSync(path.join(ROOT, 'Toolbox Launcher.html'), 'utf8');
const i = launcher.indexOf('const TOOLS = [');
let depth = 0;
const j = launcher.indexOf('[', i);
let end = -1;
for (let k = j; k < launcher.length; k++) {
  if (launcher[k] === '[') depth++;
  else if (launcher[k] === ']') {
    depth--;
    if (depth === 0) {
      end = k;
      break;
    }
  }
}
const TOOLS = eval('(' + launcher.slice(j, end + 1) + ')');

function get(url) {
  return new Promise((res) => {
    const req = http.get(url, { timeout: 8000 }, (r) => {
      let d = '';
      r.on('data', (c) => (d += c));
      r.on('end', () => res({ status: r.statusCode, body: d, len: d.length }));
    });
    req.on('error', (e) => res({ status: 0, err: e.message, body: '', len: 0 }));
    req.on('timeout', () => {
      req.destroy();
      res({ status: 0, err: 'timeout', body: '', len: 0 });
    });
  });
}

/** One unique improvement per relative HTML path */
const POLISH = {
  'Verifone Tools/Commander Site Console.html': {
    id: 'commander-site-console',
    note: 'Add offline reconnect banner + keyboard focus ring on primary actions',
    apply(html) {
      if (html.includes('data-polish="commander-site"')) return null;
      let out = html;
      if (!out.includes('outline: 2px solid var(--accent)')) {
        out = out.replace(
          '</style>',
          `/* polish */ button:focus-visible, .ui-btn:focus-visible, a.ui-btn:focus-visible { outline: 2px solid #00f3ff; outline-offset: 2px; }
    .tb-offline-banner { display:none; padding:10px 14px; background:rgba(255,77,106,.12); border-bottom:1px solid rgba(255,77,106,.35); color:#ffb4c0; font-size:12px; text-align:center; }
    .tb-offline-banner.show { display:block; }
    </style>`
        );
      }
      if (!out.includes('id="tbOfflineBanner"')) {
        out = out.replace(
          /<body([^>]*)>/i,
          `<body$1>
  <div class="tb-offline-banner" id="tbOfflineBanner" data-polish="commander-site">○ S1 offline — Commander needs the toolbox server. <button type="button" class="ui-btn" id="tbOfflineStart" style="margin-left:8px">▶ Start Server</button></div>`
        );
      }
      if (!out.includes('tbOfflineBanner') || !out.includes('tbOfflineStart?.onclick')) {
        // inject script near end
        const snip = `
<script data-polish="commander-site">
(function(){
  async function tick(){
    const el=document.getElementById('tbOfflineBanner');
    if(!el) return;
    let on=false;
    try{ on=await window.AIToolboxAPI?.isOnline?.(true,1500); }catch(_){}
    el.classList.toggle('show', !on);
  }
  document.getElementById('tbOfflineStart')?.addEventListener('click',()=>{
    try{ window.AIToolboxAPI?.startServer?.({mode:'tray'}); }catch(_){}
    setTimeout(tick, 2000);
  });
  tick(); setInterval(tick, 6000);
})();
</script>`;
        if (!out.includes('data-polish="commander-site"') || !out.includes('tbOfflineStart')) {
          out = out.replace(/<\/body>/i, snip + '\n</body>');
        }
      }
      return out;
    },
  },
};

// Simpler generic polish applied per-file with unique markers
function genericPolish(rel, html, toolMeta) {
  const marker = `data-tool-polish="${toolMeta.id}"`;
  if (html.includes(marker)) return { html, changed: false, note: 'already polished' };

  const notes = [];
  let out = html;

  // 1) Ensure viewport meta
  if (!/<meta[^>]+viewport/i.test(out)) {
    out = out.replace(/<head([^>]*)>/i, `<head$1>\n  <meta name="viewport" content="width=device-width, initial-scale=1.0">`);
    notes.push('viewport');
  }

  // 2) Document title includes tool name if generic
  if (/<title>\s*(Untitled|Document)?\s*<\/title>/i.test(out) || !/<title>/i.test(out)) {
    if (/<title>/i.test(out)) {
      out = out.replace(/<title>[^<]*<\/title>/i, `<title>${toolMeta.name} — FAFO Toolbox</title>`);
    } else {
      out = out.replace(/<head([^>]*)>/i, `<head$1>\n  <title>${toolMeta.name} — FAFO Toolbox</title>`);
    }
    notes.push('title');
  } else if (/<title>/i.test(out) && !out.includes(toolMeta.name.split(' ')[0]) && !out.includes('FAFO') && !out.includes('Toolbox')) {
    out = out.replace(/<title>([^<]*)<\/title>/i, `<title>$1 · ${toolMeta.name}</title>`);
    notes.push('title-tag');
  }

  // 3) Esc-to-launcher + polish marker script (unique per tool via id)
  const escScript = `
<script ${marker}>
/* Tool polish: ${toolMeta.id} — Esc → launcher, load toast, error surface */
(function(){
  if (window.__tbToolPolish) return; window.__tbToolPolish = true;
  const TOOL_ID = ${JSON.stringify(toolMeta.id)};
  const TOOL_NAME = ${JSON.stringify(toolMeta.name)};
  function launcherHref(){
    try {
      if (window.AIToolboxUI?.launcherHref) return AIToolboxUI.launcherHref();
      if (location.hostname === '127.0.0.87' || location.port === '18765')
        return 'http://127.0.0.87:18765/toolbox/Toolbox%20Launcher.html';
    } catch(_){}
    const a = document.querySelector('a[href*="Toolbox Launcher"], a.toolbox-back');
    if (a?.href) return a.href;
    return '../Toolbox Launcher.html';
  }
  document.addEventListener('keydown', function(e){
    if (e.key !== 'Escape') return;
    const t = e.target;
    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)) return;
    if (t?.closest?.('[role="dialog"], .modal, .overlay, .ui-modal')) return;
    location.href = launcherHref();
  }, true);
  // One soft status toast so launch failures are visible
  window.addEventListener('load', function(){
    try {
      if (sessionStorage.getItem('tb_launch_toast_'+TOOL_ID)) return;
      sessionStorage.setItem('tb_launch_toast_'+TOOL_ID, '1');
      if (window.AIToolboxUI?.toast) AIToolboxUI.toast(TOOL_NAME + ' ready · Esc = launcher', 'ok');
    } catch(_){}
  });
  // Surface failed module loads
  window.addEventListener('error', function(ev){
    if (!ev?.filename || !/\\.js($|\\?)/i.test(ev.filename)) return;
    try { window.AIToolboxUI?.toast?.('Script failed: ' + (ev.message||'error').slice(0,80), 'warn'); } catch(_){}
  });
})();
</script>`;

  if (!out.includes(marker)) {
    if (/<\/body>/i.test(out)) out = out.replace(/<\/body>/i, escScript + '\n</body>');
    else out += escScript;
    notes.push('esc+launch-toast');
  }

  // 4) Tool-specific micro-improvements
  const id = toolMeta.id;
  if (id === 'phone-assist-navigator' && !/Toolbox Launcher/i.test(out)) {
    out = out.replace(
      /<body([^>]*)>/i,
      `<body$1>\n  <a class="toolbox-back" href="../Toolbox Launcher.html" style="position:fixed;top:10px;left:12px;z-index:9999;color:#00f3ff;text-decoration:none;font:600 12px system-ui;padding:6px 10px;border-radius:8px;background:rgba(5,5,12,.9);border:1px solid rgba(0,243,255,.3)">← Toolbox</a>`
    );
    notes.push('back-link');
  }
  if (id === 'investor-portal' && !/Toolbox Launcher/i.test(out)) {
    out = out.replace(
      /<body([^>]*)>/i,
      `<body$1>\n  <a class="toolbox-back" href="Toolbox Launcher.html" style="position:fixed;top:10px;left:12px;z-index:9999;color:#7dffc8;text-decoration:none;font:600 12px system-ui;padding:6px 10px;border-radius:8px;background:rgba(5,5,12,.9);border:1px solid rgba(125,255,200,.35)">← Toolbox</a>`
    );
    notes.push('back-link');
  }
  if (id === 'event-deep-dive' && !/Toolbox Launcher/i.test(out)) {
    out = out.replace(
      /<body([^>]*)>/i,
      `<body$1>\n  <a class="toolbox-back" href="../Toolbox Launcher.html" style="position:fixed;top:10px;left:12px;z-index:9999;color:#00f3ff;text-decoration:none;font:600 12px system-ui;padding:6px 10px;border-radius:8px;background:rgba(5,5,12,.9);border:1px solid rgba(0,243,255,.3)">← Toolbox</a>`
    );
    notes.push('back-link');
  }
  if (id === 'hardware-board-map' && !/Toolbox Launcher/i.test(out)) {
    out = out.replace(
      /<body([^>]*)>/i,
      `<body$1>\n  <a class="toolbox-back" href="../Toolbox Launcher.html" style="position:fixed;top:10px;left:12px;z-index:9999;color:#00f3ff;text-decoration:none;font:600 12px system-ui;padding:6px 10px;border-radius:8px;background:rgba(5,5,12,.9);border:1px solid rgba(0,243,255,.3)">← Toolbox</a>`
    );
    notes.push('back-link');
  }
  if ((id === 'pc-reports-log-viewer' || id === 'log-viewer') && !/Toolbox Launcher/i.test(out)) {
    out = out.replace(
      /<body([^>]*)>/i,
      `<body$1>\n  <a class="toolbox-back" href="../../Toolbox Launcher.html" style="position:fixed;top:10px;left:12px;z-index:9999;color:#00f3ff;text-decoration:none;font:600 12px system-ui;padding:6px 10px;border-radius:8px;background:rgba(5,5,12,.9);border:1px solid rgba(0,243,255,.3)">← Toolbox</a>`
    );
    notes.push('back-link');
  }

  // Media hub: number keys 1-3 for tabs
  if (id === 'media-hub' && !out.includes('hubTabKeys')) {
    out = out.replace(
      /showTab\(tabFromHash\(\), true\);/,
      `showTab(tabFromHash(), true);
      // polish: number keys switch tabs
      document.addEventListener('keydown', function hubTabKeys(e){
        if (e.target && /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
        const map = { '1':'library', '2':'duplicates', '3':'organizer' };
        if (map[e.key]) showTab(map[e.key], true);
      });`
    );
    notes.push('num-keys');
  }
  if (id === 'compare-hub' && !out.includes('hubTabKeys')) {
    out = out.replace(
      /showTab\(tabFromHash\(\), true\);/,
      `showTab(tabFromHash(), true);
      document.addEventListener('keydown', function hubTabKeys(e){
        if (e.target && /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
        const map = { '1':'pairs', '2':'video', '3':'image' };
        if (map[e.key]) showTab(map[e.key], true);
      });`
    );
    notes.push('num-keys');
  }

  // Loan calculator filename typo note in title polish already; add currency default hint
  if (id === 'loan-calc' && !out.includes('data-tool-polish="loan-calc"')) {
    notes.push('esc');
  }

  // Ghost: auto-run already exists
  if (id === 'ghost-device-cleaner') notes.push('native-launch');

  // Typing trainer: ensure esc doesn't break mid-test - polish script already skips inputs
  // Empire seed: skip if canvas focused - ok

  if (notes.length === 0) notes.push('esc+launch-toast');

  return { html: out, changed: out !== html, note: notes.join('+') };
}

// Map path → primary tool meta (first TOOLS entry wins)
const byPath = new Map();
for (const t of TOOLS) {
  const p = (t.path || '').split('#')[0].split('?')[0];
  if (!byPath.has(p)) byPath.set(p, t);
}

const report = [];
const base = 'http://127.0.0.87:18765/toolbox/';

console.log('=== HTTP LAUNCH AUDIT ===');
for (const [rel, t] of byPath) {
  const url = base + rel.split('/').map(encodeURIComponent).join('/');
  const r = await get(url);
  const ok = r.status === 200 && r.len > 500;
  report.push({
    id: t.id,
    path: rel,
    status: r.status,
    bytes: r.len,
    ok,
    err: r.err || '',
    native: t.nativeLaunch || '',
  });
  console.log(`${ok ? 'OK' : 'FAIL'}\t${r.status}\t${t.id}\t${rel}\t${r.len}`);
}

console.log('\n=== APPLY ONE POLISH PER PAGE ===');
for (const [rel, t] of byPath) {
  const full = path.join(ROOT, rel);
  if (!fs.existsSync(full)) {
    console.log('MISS_FILE', rel);
    continue;
  }
  let html = fs.readFileSync(full, 'utf8');
  // special-case commander
  if (rel === 'Verifone Tools/Commander Site Console.html') {
    // still apply generic
  }
  const res = genericPolish(rel, html, t);
  if (res.changed) {
    fs.writeFileSync(full, res.html, 'utf8');
    console.log('POLISH', t.id, '→', res.note);
  } else {
    console.log('SKIP', t.id, res.note);
  }
}

// Extra hand polishes for high-value tools
function injectOnce(rel, marker, transform) {
  const full = path.join(ROOT, rel);
  if (!fs.existsSync(full)) return;
  let html = fs.readFileSync(full, 'utf8');
  if (html.includes(marker)) {
    console.log('EXTRA skip', rel);
    return;
  }
  const next = transform(html);
  if (next && next !== html) {
    fs.writeFileSync(full, next, 'utf8');
    console.log('EXTRA', rel);
  }
}

// VSR: warn when offline on load more clearly
injectOnce('Movie File Manager/VSR Pipeline Manager.html', 'data-extra-polish="vsr"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="vsr">
(async function(){
  try {
    const on = await window.AIToolboxAPI?.isOnline?.(true, 2000);
    if (!on && window.AIToolboxUI?.toast) AIToolboxUI.toast('VSR needs S1 server — use ▶ Start Server', 'warn');
  } catch(_){}
})();
</script>
</body>`
  );
});

// Disk analyzer: offline toast
injectOnce('System Tools/Disk Space Analyzer.html', 'data-extra-polish="disk"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="disk">
(async function(){
  try {
    const on = await window.AIToolboxAPI?.isOnline?.(true, 2000);
    if (!on && window.AIToolboxUI?.toast) AIToolboxUI.toast('Disk Analyzer needs S1 — Start Server for live scan', 'warn');
  } catch(_){}
})();
</script>
</body>`
  );
});

// Hosts blocker offline toast
injectOnce('System Tools/Hosts DNS Blocker.html', 'data-extra-polish="hosts"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="hosts">
(async function(){
  try {
    const on = await window.AIToolboxAPI?.isOnline?.(true, 2000);
    if (!on && window.AIToolboxUI?.toast) AIToolboxUI.toast('Hosts tool needs S1 (elevated writes)', 'warn');
  } catch(_){}
})();
</script>
</body>`
  );
});

// REG tweaks offline
injectOnce('REG Tweak AI Bat Files/Windows REG QoL Tweaks.html', 'data-extra-polish="reg"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="reg">
(async function(){
  try {
    const on = await window.AIToolboxAPI?.isOnline?.(true, 2000);
    if (!on && window.AIToolboxUI?.toast) AIToolboxUI.toast('REG tweaks apply best with S1 online', 'warn');
  } catch(_){}
})();
</script>
</body>`
  );
});

// Media library: show hub link in title area already has menus
injectOnce('Movie File Manager/Media Library Manager.html', 'data-extra-polish="mlib"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="mlib">
(function(){
  // Ctrl+D opens duplicates in Media Hub
  document.addEventListener('keydown', function(e){
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'd' && !/INPUT|TEXTAREA/.test(e.target?.tagName||'')) {
      e.preventDefault();
      location.href = 'Media Hub.html#duplicates';
    }
  });
})();
</script>
</body>`
  );
});

// Duplicate manager: open hub library link if missing polish
injectOnce('File Tools/Duplicate File Manager.html', 'data-extra-polish="dup"', (html) => {
  if (html.includes('Media Hub.html')) return html;
  return html.replace(
    /href="\.\.\/Movie File Manager\/Media Library Manager\.html"/g,
    'href="../Movie File Manager/Media Hub.html#duplicates"'
  ).replace(
    /<\/body>/i,
    `<script data-extra-polish="dup"></script></body>`
  );
});

// Video wall: mute by default note
injectOnce('Video Tools/GEMPlayHTML.html', 'data-extra-polish="vwall"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="vwall">
(function(){
  // Ensure any autoplay videos stay muted (browser policy + living-room safe)
  document.addEventListener('DOMContentLoaded', function(){
    document.querySelectorAll('video').forEach(function(v){ v.muted = true; v.defaultMuted = true; });
    const obs = new MutationObserver(function(){
      document.querySelectorAll('video').forEach(function(v){ if(!v.muted) v.muted = true; });
    });
    obs.observe(document.body, { childList:true, subtree:true });
  });
})();
</script>
</body>`
  );
});

// Batch converter offline
injectOnce('System Tools/Batch Media Converter.html', 'data-extra-polish="bconv"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="bconv">
(async function(){
  try {
    const on = await window.AIToolboxAPI?.isOnline?.(true, 2000);
    if (!on && window.AIToolboxUI?.toast) AIToolboxUI.toast('Batch convert needs S1 + ffmpeg', 'warn');
  } catch(_){}
})();
</script>
</body>`
  );
});

// Fix typo in loan calc page title if present
injectOnce('Accounting Tools and calculators/Amoritization loan calculator2.html', 'data-extra-polish="loan"', (html) => {
  let out = html.replace(/Amoritization/gi, 'Amortization');
  if (out === html) out = html; // still mark
  return out.replace(/<\/body>/i, `<script data-extra-polish="loan"></script>\n</body>`);
});

// Startup manager offline
injectOnce('System Tools/Startup Service Manager.html', 'data-extra-polish="startup"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="startup">
(async function(){
  try {
    const on = await window.AIToolboxAPI?.isOnline?.(true, 2000);
    if (!on && window.AIToolboxUI?.toast) AIToolboxUI.toast('Startup Manager needs S1 for live service data', 'warn');
  } catch(_){}
})();
</script>
</body>`
  );
});

// Malware defender offline
injectOnce('System Tools/Malware Defender.html', 'data-extra-polish="mal"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="mal">
(async function(){
  try {
    const on = await window.AIToolboxAPI?.isOnline?.(true, 2000);
    if (!on && window.AIToolboxUI?.toast) AIToolboxUI.toast('Malware Defender needs S1 for scans', 'warn');
  } catch(_){}
})();
</script>
</body>`
  );
});

// FAFO Task Manager Pro offline
injectOnce('System Tools/FAFO Task Manager Pro.html', 'data-extra-polish="ftm"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="ftm">
(async function(){
  try {
    const on = await window.AIToolboxAPI?.isOnline?.(true, 2000);
    if (!on && window.AIToolboxUI?.toast) AIToolboxUI.toast('Task Manager Pro needs S1 for live process list', 'warn');
  } catch(_){}
})();
</script>
</body>`
  );
});

// LAN Task Manager offline
injectOnce('System Tools/LAN Task Manager.html', 'data-extra-polish="lan"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="lan">
(async function(){
  try {
    const on = await window.AIToolboxAPI?.isOnline?.(true, 2000);
    if (!on && window.AIToolboxUI?.toast) AIToolboxUI.toast('LAN tools need S1 for discovery / ping', 'warn');
  } catch(_){}
})();
</script>
</body>`
  );
});

// Health dashboard offline
injectOnce('System Tools/System Health Dashboard.html', 'data-extra-polish="health"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="health">
(async function(){
  try {
    const on = await window.AIToolboxAPI?.isOnline?.(true, 2000);
    if (!on && window.AIToolboxUI?.toast) AIToolboxUI.toast('Health Dashboard needs S1 for live metrics', 'warn');
  } catch(_){}
})();
</script>
</body>`
  );
});

// Event viewer offline
injectOnce('System Tools/Event Viewer.html', 'data-extra-polish="ev"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="ev">
(async function(){
  try {
    const on = await window.AIToolboxAPI?.isOnline?.(true, 2000);
    if (!on && window.AIToolboxUI?.toast) AIToolboxUI.toast('Event Viewer needs S1 to read Windows logs', 'warn');
  } catch(_){}
})();
</script>
</body>`
  );
});

// PC diagnostics offline
injectOnce('System Tools/PC Diagnostics HUD.html', 'data-extra-polish="pcd"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="pcd">
(async function(){
  try {
    const on = await window.AIToolboxAPI?.isOnline?.(true, 2000);
    if (!on && window.AIToolboxUI?.toast) AIToolboxUI.toast('PC Diagnostics needs S1 for probes', 'warn');
  } catch(_){}
})();
</script>
</body>`
  );
});

// Git manager offline
injectOnce('Developer Tools/Git Repository Manager.html', 'data-extra-polish="git"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="git">
(async function(){
  try {
    const on = await window.AIToolboxAPI?.isOnline?.(true, 2000);
    if (!on && window.AIToolboxUI?.toast) AIToolboxUI.toast('Git Manager needs S1 for repo scan/actions', 'warn');
  } catch(_){}
})();
</script>
</body>`
  );
});

// Pair review: open compare hub link
injectOnce('Movie File Manager/Pair Review Queue.html', 'data-extra-polish="pairs"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="pairs">
(function(){
  // Tip once per session
  try {
    if (!sessionStorage.getItem('pair_hub_tip') && window.AIToolboxUI?.toast) {
      sessionStorage.setItem('pair_hub_tip','1');
      AIToolboxUI.toast('Tip: Compare Hub groups Pair Review + sliders', 'ok');
    }
  } catch(_){}
})();
</script>
</body>`
  );
});

// Video comparator tip
injectOnce('Video Tools/Video Comparison Slider Tool.html', 'data-extra-polish="vc"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="vc">
(function(){
  try {
    if (!sessionStorage.getItem('vc_hub_tip') && window.AIToolboxUI?.toast) {
      sessionStorage.setItem('vc_hub_tip','1');
      AIToolboxUI.toast('Video Comparator · also in Compare Hub', 'ok');
    }
  } catch(_){}
})();
</script>
</body>`
  );
});

// Image comparator tip
injectOnce('Image tools/Image Comparitor With Slider.html', 'data-extra-polish="ic"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="ic">
(function(){
  try {
    if (!sessionStorage.getItem('ic_hub_tip') && window.AIToolboxUI?.toast) {
      sessionStorage.setItem('ic_hub_tip','1');
      AIToolboxUI.toast('Image Comparator · also in Compare Hub', 'ok');
    }
  } catch(_){}
})();
</script>
</body>`
  );
});

// Image cropper: preserve aspect hint toast
injectOnce('Image tools/image Converter_Cropper for chrome store resolution.html', 'data-extra-polish="crop"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="crop">
(function(){
  try {
    if (!sessionStorage.getItem('crop_tip') && window.AIToolboxUI?.toast) {
      sessionStorage.setItem('crop_tip','1');
      AIToolboxUI.toast('Cropper: pick a store preset, then export', 'ok');
    }
  } catch(_){}
})();
</script>
</body>`
  );
});

// File organizer hub tip
injectOnce('Movie File Manager/File Organizer.html', 'data-extra-polish="org"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="org">
(function(){
  try {
    if (!sessionStorage.getItem('org_hub_tip') && window.AIToolboxUI?.toast) {
      sessionStorage.setItem('org_hub_tip','1');
      AIToolboxUI.toast('Organizer is also under Media Hub → Organizer', 'ok');
    }
  } catch(_){}
})();
</script>
</body>`
  );
});

// Tax tools: offline-ok already — add esc already via generic
// Universal converter: fix if BODY_ERR was false positive
injectOnce('Accounting Tools and calculators/Universal Converter.html', 'data-extra-polish="uc"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="uc">
(function(){
  try {
    if (!sessionStorage.getItem('uc_tip') && window.AIToolboxUI?.toast) {
      sessionStorage.setItem('uc_tip','1');
      AIToolboxUI.toast('Universal Converter ready · Esc returns to launcher', 'ok');
    }
  } catch(_){}
})();
</script>
</body>`
  );
});

// Solar debris
injectOnce('Solar System Debris Tracker.html', 'data-extra-polish="solar"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="solar">
(function(){
  try {
    if (!sessionStorage.getItem('solar_tip') && window.AIToolboxUI?.toast) {
      sessionStorage.setItem('solar_tip','1');
      AIToolboxUI.toast('Debris Tracker · drag to orbit · Esc = launcher', 'ok');
    }
  } catch(_){}
})();
</script>
</body>`
  );
});

// Games / fun
injectOnce('Bloodmoon Survivor.html', 'data-extra-polish="blood"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="blood">
(function(){
  // Don't steal Esc during gameplay if paused UI open — only when not in canvas lock
  document.addEventListener('keydown', function(e){
    if (e.key === 'Escape' && document.pointerLockElement) {
      // let game handle unlock first
    }
  }, true);
})();
</script>
</body>`
  );
});

injectOnce('Empire Seed.html', 'data-extra-polish="empire"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="empire">
(function(){
  try {
    if (!sessionStorage.getItem('empire_tip') && window.AIToolboxUI?.toast) {
      sessionStorage.setItem('empire_tip','1');
      AIToolboxUI.toast('Empire Seed 3D · Esc returns to launcher', 'ok');
    }
  } catch(_){}
})();
</script>
</body>`
  );
});

injectOnce('Typing Assistant Trainer.html', 'data-extra-polish="type"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="type">
(function(){
  // Esc should not leave mid-run if finished banner is open — polish already skips inputs
  // Add Tab restart hint once
  try {
    if (!sessionStorage.getItem('type_tab_tip') && window.AIToolboxUI?.toast) {
      sessionStorage.setItem('type_tab_tip','1');
      // delay so it doesn't fight ready toast
      setTimeout(function(){ AIToolboxUI.toast('Tip: Tab restarts · Esc = launcher (when not in a field)', 'ok'); }, 1200);
    }
  } catch(_){}
})();
</script>
</body>`
  );
});

// Setup / startup boards
injectOnce('Setup Configurator.html', 'data-extra-polish="setup"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="setup">
(async function(){
  try {
    const on = await window.AIToolboxAPI?.isOnline?.(true, 2000);
    if (!on && window.AIToolboxUI?.toast) AIToolboxUI.toast('Setup pack build needs S1 online', 'warn');
  } catch(_){}
})();
</script>
</body>`
  );
});

injectOnce('Startup Command Board.html', 'data-extra-polish="scb"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="scb">
(async function(){
  try {
    const on = await window.AIToolboxAPI?.isOnline?.(true, 2000);
    if (!on && window.AIToolboxUI?.toast) AIToolboxUI.toast('Command Board needs S1 for live server control', 'warn');
  } catch(_){}
})();
</script>
</body>`
  );
});

injectOnce('System Tools/IP Profile Switcher.html', 'data-extra-polish="ip"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="ip">
(async function(){
  try {
    const on = await window.AIToolboxAPI?.isOnline?.(true, 2000);
    if (!on && window.AIToolboxUI?.toast) AIToolboxUI.toast('IP Profile Switcher needs S1 (may require elevation)', 'warn');
  } catch(_){}
})();
</script>
</body>`
  );
});

// Verifone tools
injectOnce('Verifone Tools/Commander Status HUD.html', 'data-extra-polish="csh"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="csh">
(async function(){
  try {
    const on = await window.AIToolboxAPI?.isOnline?.(true, 2000);
    if (!on && window.AIToolboxUI?.toast) AIToolboxUI.toast('Status HUD needs S1 for live probes', 'warn');
  } catch(_){}
})();
</script>
</body>`
  );
});

injectOnce('Verifone Tools/Pre-Reload Punch List.html', 'data-extra-polish="prpl"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="prpl">
(function(){
  try {
    if (!sessionStorage.getItem('prpl_tip') && window.AIToolboxUI?.toast) {
      sessionStorage.setItem('prpl_tip','1');
      AIToolboxUI.toast('Punch list · check off items before reload · Esc = launcher', 'ok');
    }
  } catch(_){}
})();
</script>
</body>`
  );
});

injectOnce('Verifone Tools/Phone Assist Navigator.html', 'data-extra-polish="pan"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="pan">
(function(){
  try {
    if (!sessionStorage.getItem('pan_tip') && window.AIToolboxUI?.toast) {
      sessionStorage.setItem('pan_tip','1');
      AIToolboxUI.toast('Phone Assist · follow the flow · Esc = launcher', 'ok');
    }
  } catch(_){}
})();
</script>
</body>`
  );
});

// Tax suite tips
for (const [rel, tip] of [
  ['Business Tax Preparedness/TaxForge Hub.html', 'TaxForge Hub · pick a desk to start'],
  ['Business Tax Preparedness/LedgerLink Console.html', 'LedgerLink · Xero bridge desk'],
  ['Business Tax Preparedness/Compliance Pulse.html', 'Compliance Pulse · readiness score'],
  ['Business Tax Preparedness/Write-Off Workshop.html', 'Write-Off Workshop · triage spend'],
  ['Business Tax Preparedness/Year-End War Room.html', 'Year-End War Room · close checklist'],
  ['Business Tax Preparedness/Partner Period Desk.html', 'Partner Period Desk · reimb windows'],
]) {
  injectOnce(rel, `data-extra-polish="tax-${path.basename(rel)}"`, (html) => {
    const m = `data-extra-polish="tax-${path.basename(rel)}"`;
    return html.replace(
      /<\/body>/i,
      `<script ${m}>
(function(){
  try {
    if (!sessionStorage.getItem(${JSON.stringify('tip_' + rel)}) && window.AIToolboxUI?.toast) {
      sessionStorage.setItem(${JSON.stringify('tip_' + rel)},'1');
      AIToolboxUI.toast(${JSON.stringify(tip + ' · Esc = launcher')}, 'ok');
    }
  } catch(_){}
})();
</script>
</body>`
    );
  });
}

// Event deep dive + hardware
injectOnce('System Tools/Event Deep Dive.html', 'data-extra-polish="edd"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="edd">
(async function(){
  try {
    const on = await window.AIToolboxAPI?.isOnline?.(true, 2000);
    if (!on && window.AIToolboxUI?.toast) AIToolboxUI.toast('Event Deep Dive needs S1', 'warn');
  } catch(_){}
})();
</script>
</body>`
  );
});

injectOnce('System Tools/Hardware Board Map.html', 'data-extra-polish="hbm"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="hbm">
(async function(){
  try {
    const on = await window.AIToolboxAPI?.isOnline?.(true, 2000);
    if (!on && window.AIToolboxUI?.toast) AIToolboxUI.toast('Hardware Map needs S1 for device inventory', 'warn');
  } catch(_){}
})();
</script>
</body>`
  );
});

// PC reports
injectOnce('System Tools/PC Reports and Log Viewer/index.html', 'data-extra-polish="pcr"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="pcr">
(function(){
  try {
    if (!sessionStorage.getItem('pcr_tip') && window.AIToolboxUI?.toast) {
      sessionStorage.setItem('pcr_tip','1');
      AIToolboxUI.toast('PC Reports · use #logs for log tab · Esc = launcher', 'ok');
    }
  } catch(_){}
})();
</script>
</body>`
  );
});

// Investor portal careful toast
injectOnce('Investor Portal.html', 'data-extra-polish="inv"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="inv">
(function(){
  try {
    if (!sessionStorage.getItem('inv_tip') && window.AIToolboxUI?.toast) {
      sessionStorage.setItem('inv_tip','1');
      AIToolboxUI.toast('Investor Portal · private Sumran desk · Esc = launcher', 'ok');
    }
  } catch(_){}
})();
</script>
</body>`
  );
});

// Commander site console offline already in generic - add extra reconnect
injectOnce('Verifone Tools/Commander Site Console.html', 'data-extra-polish="csc"', (html) => {
  return html.replace(
    /<\/body>/i,
    `<script data-extra-polish="csc">
(async function(){
  try {
    const on = await window.AIToolboxAPI?.isOnline?.(true, 2000);
    if (!on && window.AIToolboxUI?.toast) AIToolboxUI.toast('Commander Console needs S1 — Start Server', 'warn');
  } catch(_){}
})();
</script>
</body>`
  );
});

const fails = report.filter((r) => !r.ok);
console.log('\n=== SUMMARY ===');
console.log('pages', byPath.size, 'fail', fails.length);
if (fails.length) console.log(fails);
fs.writeFileSync(
  path.join(ROOT, 'docs', 'tool-launch-audit.json'),
  JSON.stringify({ at: new Date().toISOString(), report, fails }, null, 2)
);
console.log('Wrote docs/tool-launch-audit.json');
