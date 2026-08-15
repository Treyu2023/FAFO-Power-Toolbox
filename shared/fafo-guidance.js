/**
 * FAFO Guidance — PC component scores + skill-aware tooltips.
 *
 * - Scores GPU/CPU/RAM/storage/network from identity (no benchmarks).
 * - User skill: auto | beginner | intermediate | advanced (independent of PC).
 * - Tooltips pick basic / mid / pro wording and add efficiency vs performance flavor.
 */
(function (global) {
  'use strict';

  const LS_SKILL = 'fafo_user_skill_v1';
  const LS_HW = 'fafo_hw_score_cache_v1';
  const CACHE_MS = 6 * 60 * 60 * 1000;

  /** @type {{ overall: number, tier: string, components: object, labels: object } | null} */
  let hwProfile = null;
  /** @type {'auto'|'beginner'|'intermediate'|'advanced'} */
  let skillPref = 'auto';

  try {
    const s = localStorage.getItem(LS_SKILL);
    if (s === 'auto' || s === 'beginner' || s === 'intermediate' || s === 'advanced') skillPref = s;
  } catch (_) { /* ignore */ }

  // ── Component scoring (catalog tiers, not live benchmarks) ───────────

  const GPU_RULES = [
    { re: /\b(rtx\s*)?5090\b|h100|b200|mi300|a100/i, score: 99, tier: 'flagship' },
    { re: /\b(rtx\s*)?4090\b|a6000|l40s?\b|rtx\s*6000/i, score: 96, tier: 'flagship' },
    { re: /\b(rtx\s*)?4080\b|\b3090\b|a5000/i, score: 90, tier: 'high' },
    { re: /\b(rtx\s*)?4070\s*ti\b|\b3080\b|7900\s*xtx/i, score: 84, tier: 'high' },
    { re: /\b(rtx\s*)?4070\b|\b3070\b|7800\s*xt|6900\s*xt/i, score: 78, tier: 'high' },
    { re: /\b(rtx\s*)?4060\b|\b3060\b|6700\s*xt|arc\s*a770/i, score: 68, tier: 'mid' },
    { re: /\brtx\s*20|gtx\s*16|1660|1650|5600|6600/i, score: 52, tier: 'mid' },
    { re: /\bgtx\s*10|1050|1060|rx\s*5[0-9]{2}\b/i, score: 40, tier: 'entry' },
    { re: /\brtx\b|gtx\b|radeon\s*rx|arc\s*a/i, score: 62, tier: 'mid' },
    { re: /\bintel\s*(uhd|iris)|radeon\s*graphics|vega\s*[0-9]|apple\s*m[1-4]/i, score: 28, tier: 'igpu' },
  ];

  const CPU_RULES = [
    { re: /\b(i9|ultra\s*9|ryzen\s*9|threadripper|xeon\s*w|epyc|m[234]\s*(max|ultra|pro)?)\b/i, score: 92 },
    { re: /\b(i7|ultra\s*7|ryzen\s*7)\b/i, score: 80 },
    { re: /\b(i5|ultra\s*5|ryzen\s*5)\b/i, score: 68 },
    { re: /\b(i3|ryzen\s*3|celeron|pentium|atom)\b/i, score: 42 },
  ];

  function matchScore(name, rules, fallback) {
    const n = String(name || '');
    for (const r of rules) {
      if (r.re.test(n)) return { score: r.score, tier: r.tier || null, matched: r.re.source };
    }
    return { score: fallback, tier: null, matched: null };
  }

  function scoreGpuList(gpus) {
    const list = Array.isArray(gpus) ? gpus : [];
    if (!list.length) {
      return { score: 35, label: 'Unknown GPU', detail: 'No graphics adapter reported' };
    }
    let best = { score: 0, label: '', detail: '' };
    for (const g of list) {
      const name = g.name || g || '';
      const m = matchScore(name, GPU_RULES, 48);
      // Prefer discrete over iGPU when both present
      const isIgpu = /intel\s*(uhd|iris)|radeon\s*graphics/i.test(name);
      const adj = isIgpu ? Math.min(m.score, 40) : m.score;
      if (adj >= best.score) {
        best = {
          score: adj,
          label: name,
          detail: m.tier ? `Tier: ${m.tier}` : 'General-purpose GPU',
        };
      }
    }
    // 4090 stays near top even if 5090 exists — already handled by scores 96 vs 99
    return best;
  }

  function scoreCpu(cpu) {
    const name = (cpu && (cpu.name || cpu.Name)) || '';
    const cores = Number(cpu?.cores || cpu?.logical || 0) || 0;
    const m = matchScore(name, CPU_RULES, 55);
    let score = m.score;
    if (cores >= 16) score = Math.min(100, score + 6);
    else if (cores >= 8) score = Math.min(100, score + 3);
    else if (cores > 0 && cores <= 4) score = Math.max(25, score - 8);
    return {
      score,
      label: name || (cores ? `${cores}-core CPU` : 'Unknown CPU'),
      detail: cores ? `${cores} cores` : 'Core count unknown',
    };
  }

  function scoreRam(identity, nav) {
    // Prefer deviceMemory (GB, Chromium) — identity may not include RAM
    let gb = 0;
    if (nav && typeof nav.deviceMemory === 'number') gb = nav.deviceMemory;
    if (identity?.memoryGb) gb = Number(identity.memoryGb) || gb;
    if (identity?.ramGb) gb = Number(identity.ramGb) || gb;
    let score = 50;
    if (gb >= 64) score = 95;
    else if (gb >= 32) score = 85;
    else if (gb >= 16) score = 72;
    else if (gb >= 8) score = 55;
    else if (gb > 0) score = 35;
    return {
      score,
      label: gb ? `${gb} GB RAM` : 'RAM unknown',
      detail: gb ? 'From browser/OS report' : 'Open PC Diagnostics for exact RAM',
    };
  }

  function scoreStorage(disks) {
    const list = Array.isArray(disks) ? disks : [];
    if (!list.length) {
      return { score: 50, label: 'Storage unknown', detail: 'No disk inventory yet' };
    }
    let best = 45;
    let labels = [];
    for (const d of list) {
      const media = String(d.media || d.MediaType || '').toLowerCase();
      const name = String(d.name || d.FriendlyName || '');
      const bus = String(d.bus || '').toLowerCase();
      let s = 50;
      if (/ssd|nvme|solid/i.test(media + name) || /nvme/i.test(bus)) s = 88;
      else if (/hdd|mechanical|spindle/i.test(media + name)) s = 40;
      if (/nvme/i.test(name + bus + media)) s = 92;
      best = Math.max(best, s);
      labels.push(name || media || 'disk');
    }
    return {
      score: best,
      label: labels.slice(0, 2).join(', '),
      detail: best >= 85 ? 'Fast SSD/NVMe present' : 'Consider SSD for media tools',
    };
  }

  function scoreNetwork(nets) {
    const list = Array.isArray(nets) ? nets : [];
    if (!list.length) return { score: 50, label: 'Network unknown', detail: '' };
    const names = list.map((n) => n.name || '').join(' ');
    let score = 55;
    if (/wifi\s*6|802\.11ax|ethernet|2\.5g|10g|killer|intel\s*i\d{3}/i.test(names)) score = 80;
    if (/wifi\s*7|thunderbolt/i.test(names)) score = 90;
    return { score, label: list[0]?.name || 'Network', detail: `${list.length} adapter(s)` };
  }

  function tierFromOverall(n) {
    if (n >= 80) return 'high';
    if (n >= 50) return 'mid';
    return 'low';
  }

  function buildProfileFromIdentity(identity) {
    const id = identity || {};
    const gpu = scoreGpuList(id.gpus || []);
    const cpu = scoreCpu(id.cpu || {});
    const ram = scoreRam(id, typeof navigator !== 'undefined' ? navigator : null);
    const storage = scoreStorage(id.disks || []);
    const network = scoreNetwork(id.net || []);
    // Weights lean toward GPU/CPU for media/AI toolbox
    const overall = Math.round(
      gpu.score * 0.34 +
      cpu.score * 0.26 +
      ram.score * 0.20 +
      storage.score * 0.14 +
      network.score * 0.06
    );
    return {
      overall: clamp(overall, 1, 100),
      tier: tierFromOverall(overall),
      components: { gpu, cpu, ram, storage, network },
      labels: {
        computer: id.computer || id.systemModel || 'This PC',
        summary: `PC score ${overall}/100 · GPU ${gpu.score} · CPU ${cpu.score} · RAM ${ram.score}`,
      },
      at: Date.now(),
    };
  }

  function clamp(n, a, b) { return Math.max(a, Math.min(b, n)); }

  function browserFallbackProfile() {
    const cores = (typeof navigator !== 'undefined' && navigator.hardwareConcurrency) || 4;
    const mem = (typeof navigator !== 'undefined' && navigator.deviceMemory) || 0;
    const cpu = {
      score: cores >= 12 ? 78 : cores >= 8 ? 68 : cores >= 4 ? 55 : 40,
      label: `${cores} logical cores`,
      detail: 'Browser-reported (no full inventory)',
    };
    const ram = scoreRam({ ramGb: mem }, typeof navigator !== 'undefined' ? navigator : null);
    const gpu = { score: 50, label: 'GPU unknown', detail: 'Start S1 for hardware identity' };
    const storage = { score: 50, label: 'Storage unknown', detail: '' };
    const network = { score: 50, label: 'Network unknown', detail: '' };
    const overall = Math.round(gpu.score * 0.2 + cpu.score * 0.35 + ram.score * 0.3 + 15);
    return {
      overall: clamp(overall, 1, 100),
      tier: tierFromOverall(overall),
      components: { gpu, cpu, ram, storage, network },
      labels: { computer: 'This browser', summary: `Approx score ${overall}/100 (limited data)` },
      at: Date.now(),
      partial: true,
    };
  }

  async function refreshHardware(force) {
    try {
      if (!force) {
        const raw = localStorage.getItem(LS_HW);
        if (raw) {
          const cached = JSON.parse(raw);
          if (cached && cached.at && Date.now() - cached.at < CACHE_MS && cached.overall) {
            hwProfile = cached;
            return hwProfile;
          }
        }
      }
    } catch (_) { /* ignore */ }

    let identity = null;
    try {
      const API = global.AIToolboxAPI;
      if (API?.isOnline && (await API.isOnline(false, 1500))) {
        // Prefer hardware identity endpoint
        const base = API.getApiBase ? API.getApiBase() : (global.AITOOLBOX_CONFIG?.API_BASE || '');
        if (base) {
          const r = await fetch(base.replace(/\/$/, '') + '/hardware/identity', { cache: 'no-store' });
          if (r.ok) identity = await r.json();
        }
      }
    } catch (_) { /* offline */ }

    hwProfile = identity && identity.supported !== false
      ? buildProfileFromIdentity(identity)
      : browserFallbackProfile();
    try { localStorage.setItem(LS_HW, JSON.stringify(hwProfile)); } catch (_) { /* ignore */ }
    dispatchChange();
    return hwProfile;
  }

  function getHardware() {
    return hwProfile || browserFallbackProfile();
  }

  function getSkillPref() { return skillPref; }

  function setSkillPref(level) {
    if (!['auto', 'beginner', 'intermediate', 'advanced'].includes(level)) return skillPref;
    skillPref = level;
    try { localStorage.setItem(LS_SKILL, level); } catch (_) { /* ignore */ }
    dispatchChange();
    return skillPref;
  }

  /** Effective tip language level (not the same as PC tier when user overrides). */
  function effectiveLevel() {
    if (skillPref === 'beginner' || skillPref === 'intermediate' || skillPref === 'advanced') {
      return skillPref;
    }
    // auto: soft map from PC score
    const o = getHardware().overall;
    if (o >= 78) return 'advanced';
    if (o >= 48) return 'intermediate';
    return 'beginner';
  }

  function pcTier() {
    return getHardware().tier; // low | mid | high
  }

  /**
   * Resolve tooltip text for an element.
   * Supports:
   *  data-tip (default)
   *  data-tip-basic / data-tip-mid / data-tip-pro
   *  data-tip-title
   *  title= fallback
   * Appends short efficiency/performance note from PC tier.
   */
  function resolveTip(el) {
    if (!el) return { title: '', text: '' };
    const level = effectiveLevel();
    const title = el.getAttribute('data-tip-title') || el.dataset.tipTitle || '';
    let text = '';
    if (level === 'beginner') {
      text = el.getAttribute('data-tip-basic') || el.dataset.tipBasic
        || el.getAttribute('data-tip') || el.dataset.tip || '';
    } else if (level === 'advanced') {
      text = el.getAttribute('data-tip-pro') || el.dataset.tipPro
        || el.getAttribute('data-tip') || el.dataset.tip || '';
    } else {
      text = el.getAttribute('data-tip-mid') || el.dataset.tipMid
        || el.getAttribute('data-tip') || el.dataset.tip || '';
    }
    if (!text && el.title && !el.dataset.tipBound) {
      text = el.title;
    }
    // PC flavor (short, non-duplicative)
    const flavor = pcFlavorLine(el, level);
    if (flavor && text && !text.includes(flavor.slice(0, 20))) {
      text = text + '\n\n' + flavor;
    } else if (flavor && !text) {
      text = flavor;
    }
    return { title, text };
  }

  function pcFlavorLine(el, level) {
    const hw = getHardware();
    const tier = hw.tier;
    // Prefer data-tip-perf / data-tip-efficient if authors set them
    if (tier === 'high') {
      const p = el.getAttribute('data-tip-perf') || el.dataset.tipPerf;
      if (p) return p;
      if (level === 'advanced') {
        return '⚙ This PC can favor higher quality / parallel settings when you have headroom.';
      }
      return '⚙ Your PC is strong — quality presets are usually fine.';
    }
    if (tier === 'low') {
      const e = el.getAttribute('data-tip-efficient') || el.dataset.tipEfficient;
      if (e) return e;
      return '💡 Tip: prefer smaller batches and lower quality first to save time and heat.';
    }
    return '⚖ Balance quality and speed — raise settings only if the tool stays responsive.';
  }

  function dispatchChange() {
    try {
      global.dispatchEvent(new CustomEvent('fafo-guidance', {
        detail: { skill: skillPref, level: effectiveLevel(), hardware: getHardware() },
      }));
    } catch (_) { /* ignore */ }
  }

  /**
   * Auto-fill missing tips on common controls (does not overwrite author tips).
   */
  function tip(el, title, basic, mid, pro, perf, efficient) {
    if (!el || el.getAttribute('data-tip') || el.dataset.tip) return;
    el.setAttribute('data-tip-title', title);
    el.setAttribute('data-tip', basic);
    el.setAttribute('data-tip-basic', basic);
    el.setAttribute('data-tip-mid', mid || basic);
    el.setAttribute('data-tip-pro', pro || mid || basic);
    if (perf) el.setAttribute('data-tip-perf', perf);
    if (efficient) el.setAttribute('data-tip-efficient', efficient);
  }

  function autoAnnotate(root) {
    root = root || document;
    const map = [
      { sel: '#btnStart, #btnEmptyStart', title: 'Start', basic: 'Begin the main action for this tool.', pro: 'Run primary workflow / queue.' },
      { sel: '#btnScan, #btnEmptyScan, #btnNoDupRescan', title: 'Scan', basic: 'Look through a folder and list results.', pro: 'Index/hash files (I/O heavy on big trees).', efficient: 'Scan a smaller subfolder first if the drive is spinning rust.' },
      { sel: '#btnRefresh, #btnRefreshLearn', title: 'Refresh', basic: 'Reload the latest data.', pro: 'Re-fetch state without full restart.' },
      { sel: '#btnMerge, #btnMergeAllLowest', title: 'Merge', basic: 'Keep one file and send extras to Recycle Bin.', pro: 'Destructive de-dupe — verify keeper (lowest copy #).' },
      { sel: '#btnDeleteSelected, #btnDelete, [id*="btnDelete"]', title: 'Delete', basic: 'Remove selected items (usually Recycle Bin).', pro: 'Irreversible if not using trash — double-check selection.' },
      { sel: '#btnYes, .ui-btn.match, #btnAccept', title: 'Accept / Match', basic: 'Yes — keep this choice / lock the pair.', pro: 'Commit decision to catalog or queue.' },
      { sel: '#btnNo, .ui-btn.nomatch, #btnReject', title: 'Reject', basic: 'No — skip this option.', pro: 'Reject candidate; continue elimination.' },
      { sel: '#btnSkip', title: 'Skip', basic: 'Skip this item and move on.', pro: 'Leave pending / advance without decision.' },
      { sel: '#btnUndo, #btnUndoDone', title: 'Undo', basic: 'Go back one step.', pro: 'Restore prior queue state from history.' },
      { sel: '#btnRedo, #btnRedoDone', title: 'Redo', basic: 'Go forward again after undo.', pro: 'Re-apply next history entry.' },
      { sel: '#btnPlay', title: 'Play', basic: 'Play or pause previews.', pro: 'Toggle synchronized preview playback.' },
      { sel: '#tabOverlay, #btnViewOverlay', title: 'Overlay', basic: 'Stack both images and wipe a line to compare.', pro: 'Clip-path before/after sweeper (content-width aware).' },
      { sel: '#tabSide', title: 'Side by side', basic: 'Show both files next to each other.', pro: 'Dual-pane compare layout.' },
      { sel: '#optPip', title: 'PiP zoom', basic: 'Zoomed window of the same spot on both sides.', pro: 'Canvas loupe with shared focus/zoom.' },
      { sel: '#optMeta', title: 'Meta table', basic: 'Show or hide the side-by-side file details.', pro: 'Toggle uniform field comparison grid.' },
      { sel: '#beforeDir, #btnPickBefore', title: 'Before folder', basic: 'Folder with original / source files.', pro: 'Anchor dir_id for guided pairing.' },
      { sel: '#afterDir, #btnPickAfter', title: 'After folder', basic: 'Folder with finished / upscaled files.', pro: 'Candidate dir_id — prefer larger files only.' },
      { sel: '#btnPickFolder, #btnEmptyPick, #btnNoDupPick', title: 'Pick folder', basic: 'Choose a folder on this PC.', pro: 'Native folder picker via S1.' },
      { sel: '#btnOpenFolder', title: 'Open folder', basic: 'Open the scanned folder in Explorer.', pro: 'Shell-open folder path.' },
      { sel: '#btnClearScan, #btnClear', title: 'Clear', basic: 'Clear results from the screen (files stay on disk).', pro: 'Drop session/localStorage scan cache.' },
      { sel: '#btnCompare, #btnOpenCompare', title: 'Compare', basic: 'Open a closer look at two files.', pro: 'Launch comparator / side-by-side preview.' },
      { sel: '#btnSave, #btnSaveHs, #btnSavePairs, #btnSaveCfg', title: 'Save', basic: 'Save your work.', pro: 'Persist to catalog / localStorage / config.' },
      { sel: '#btnExportSession, #btnDupReport, #btnCopyReport, #btnCopyLog, #btnOrgReport', title: 'Report', basic: 'Copy a text summary to the clipboard.', pro: 'Export session diagnostics for notes or tickets.' },
      { sel: '#btnDebug', title: 'Debug', basic: 'Show extra technical details for troubleshooting.', pro: 'Toggle AIToolboxDebug overlay / logging.' },
      { sel: '#btnLoad, #btnEmptyLoad', title: 'Load queue', basic: 'Load items to review.', pro: 'Fetch VSR/catalog candidates into the queue.' },
      { sel: '#btnApplyAccepted, #btnApplyS1, #btnApplyS2, #btnRenameApply', title: 'Apply', basic: 'Write the accepted changes to disk.', pro: 'Execute renames/patches (confirm carefully).' },
      { sel: '#btnDryAccepted, #btnDryS1', title: 'Dry run', basic: 'Preview what would change without writing files.', pro: 'No-op apply for safety check.' },
      { sel: '#btnPreview', title: 'Preview', basic: 'Show matches before applying.', pro: 'Run matcher and render stage tables.' },
      { sel: '#btnRescan, #btnEmptyRescan', title: 'Rescan', basic: 'Scan folders again for new files.', pro: 'Re-index catalog directories.' },
      { sel: '#btnConvert', title: 'Convert', basic: 'Start converting selected files.', pro: 'FFmpeg batch stream — needs S1 + ffmpeg on PATH.', efficient: 'Convert a few files first to check quality/size.' },
      { sel: '#btnStop', title: 'Stop', basic: 'Stop the running job.', pro: 'Abort EventSource / worker mid-batch.' },
      { sel: '#btnPopout', title: 'Pop out', basic: 'Open this tab in its own window.', pro: 'Detached window for dual-monitor workflows.' },
      { sel: '#tbBtnStartServer, #btnStartServer', title: 'Start servers', basic: 'Turn on the toolbox backend.', pro: 'Start S1 (+ S2 companions) via tray/API.' },
      { sel: '#tbPillS1', title: 'S1 Toolbox', basic: 'Main toolbox server for media and system tools.', pro: '127.0.0.87:18765 health / API root.' },
      { sel: '#tbPillS2', title: 'S2 Tagger', basic: 'FAFO Local Media tagger server.', pro: '127.0.0.1:8765 tags/ratings companion.' },
    ];
    map.forEach(({ sel, title, basic, pro, mid, perf, efficient }) => {
      root.querySelectorAll(sel).forEach((el) => {
        tip(el, title, basic, mid, pro, perf, efficient);
      });
    });

    // Page-specific packs (path fragment → tips)
    const path = (location.pathname || location.href || '').toLowerCase();
    applyPageTips(root, path);
  }

  function applyPageTips(root, path) {
    const q = (id) => root.querySelector(id);

    // Duplicate File Manager
    if (path.includes('duplicate')) {
      tip(q('#matchMode'), 'Match mode',
        'Quick is faster. Full checks every byte (slower, stricter).',
        'Quick = size + partial hash. Full = SHA-256 exact.',
        'Full mode is expensive on huge trees; use after Quick narrows suspects.');
      tip(q('#fileTypes'), 'File types',
        'Limit which kinds of files to scan.',
        'Filter extensions to speed up scanning.',
        'Narrow types to cut I/O when hunting media dups only.');
      tip(q('#deepVideo'), 'Deep video',
        'Extra careful video matching (slower).',
        'First-frame hash for near-dup videos.',
        'Requires ffmpeg; use when Quick video groups look wrong.');
      tip(q('#btnMergeAllLowest'), 'Merge all → lowest #',
        'In every group, keep the file with the lowest copy number (no # first).',
        'Batch merge using (1)<(2) ranking; sends extras to Recycle Bin.',
        'Bulk delete of non-keepers — review “likely” provisional groups first.');
    }
    // Guided pair / pair review
    if (path.includes('guided') || path.includes('pair match')) {
      tip(q('#maxTries'), 'Max tries',
        'How many candidates to try per source file.',
        'Elimination depth per anchor.',
        'Raise on strong PCs when Min score is low.');
      tip(q('#minPct'), 'Min score %',
        'Ignore weak name matches below this percent.',
        'Confidence floor for candidates_for_media.',
        'Lower = more recall, more false positives.');
      tip(q('#requireLarger'), 'After larger only',
        'Finished files should be bigger than sources. Same size = duplicate, not a pair.',
        'Reject after_size <= before_size.',
        'Enforces VSR size heuristic; disable only for same-size edge cases.');
      tip(q('#preferSources'), 'Sources first',
        'Work through original-looking names before upscaled names.',
        'Sort anchors by non-upscale markers first.',
        'Pairs with looks_like_source_before ranking.');
      tip(q('#kindFilter'), 'Kind filter',
        'Only queue videos, only images, or both.',
        'type filter for unpaired anchors.',
        'Use video-only when pairing VSR outputs.');
      tip(q('#btnExportSession'), 'Export session',
        'Copy a text report of this match session.',
        'Clipboard dump of counters + log.',
        'Useful for handoff notes after a long queue.');
    }
    if (path.includes('pair review')) {
      tip(q('#btnApplyAccepted'), 'Apply accepted renames',
        'Rename files you accepted to the proposed names.',
        'vsrApplySelected on accept+renameNeeded rows.',
        'Prefer dry-run first if scores were mixed.');
      tip(q('#btnSavePairs'), 'Save accepted pairs',
        'Store accepted before/after links in the catalog.',
        'savePair / savePairFromPaths for accepted rows.',
        'Pins pairs for Compare Hub.');
      tip(q('#btnDeleteRejected'), 'Delete rejected pair links',
        'Remove bad pair links from the catalog (files stay).',
        'deletePair for rejected catalog pairs.',
        'Does not delete media files on disk.');
      tip(q('#chkAutoNext'), 'Auto-play next',
        'When After ends, jump to the next pair and play.',
        'Queue auto-advance on video ended.',
        'Turn off if you need more time per decision.');
      tip(q('#chkUpdateFiles'), 'Update files on next',
        'Write the previous item’s tags/rating into the real files when you leave it.',
        'Flush tags to disk on advance.',
        'Keeps Explorer tags in sync with the queue.');
    }
    // VSR
    if (path.includes('vsr')) {
      tip(q('#btnPreview'), 'Preview matches',
        'See how Stage I / II files line up before renaming.',
        'Run pipeline preview matcher.',
        'Always preview; then Review queue if scores look mixed.');
      tip(q('#btnApplyS1'), 'Apply Stage I',
        'Rename Stage I (upscale) files to the proposed names.',
        'Bulk vsrApply stage 1.',
        'Trust checkbox skips future confirms — use carefully.');
      tip(q('#btnApplyS2'), 'Apply Stage II',
        'Rename Stage II (interpolation) files.',
        'Bulk vsrApply stage 2.',
        'Stage II names often include fps — pair 1↔3 elsewhere.');
      tip(q('#btnReviewS1'), 'Review queue',
        'Check each match with keyboard before renaming.',
        'Opens Pair Review for safer accept/reject.',
        'Best when matcher confidence is mixed.');
      tip(q('#btnLearn'), 'Teach matcher',
        'Show a few known pairs so future matches get smarter.',
        'vsrLearn strip prefixes/suffixes.',
        'Feed 3–5 solid pairs when VSR names are chaotic.');
      tip(q('#btnDupScan'), 'Scan duplicates',
        'Find duplicate videos in a folder.',
        'Hash / deep frame scan under VSR tools.',
        'Deep mode needs ffmpeg and more CPU.');
      tip(q('#btnSaveCfg'), 'Save config',
        'Remember folder paths and naming templates.',
        'Persist VSR config to server storage.',
        'Save after setting three folders so you do not retype.');
    }
    // Media library
    if (path.includes('media library')) {
      tip(q('#btnAddDir'), 'Watch folder',
        'Add a folder to the library index. Files are not moved.',
        'Register directory + scan into catalog.',
        'Add Before and After folders separately for pairing.');
      tip(q('#btnNativeDir'), 'Pick folder',
        'Windows folder picker (needs server green).',
        'Native pick via S1.',
        'Use when paste-path is awkward.');
      tip(q('#btnRescan'), 'Rescan',
        'Re-index folders for new/moved/deleted files.',
        'Rescan + reimport Explorer tags + relink UP-#### pairs.',
        'Run after VSR writes new outputs.');
      tip(q('#btnPair'), 'Pair two files',
        'Select exactly 2 files (1st=source, 2nd=upscaled) and lock a pair.',
        'savePair + open comparator + stamp UP tags.',
        'Order matters: first selected is Before.');
      tip(q('#btnSuggest'), 'Pair Studio',
        'Get multi-signal pair suggestions and assign sides when names are messy.',
        'Stem/tail/digit/folder suggestion UI.',
        'Use when bulk auto-pair is too aggressive.');
      tip(q('#btnTwoDirPairs'), 'Two-folder pairs',
        'Match files between a Before folder and an After folder.',
        'Cross-dir pairing workflow.',
        'Best for VSR source vs output trees.');
      tip(q('#btnAutoPair'), 'Auto-link upscale pairs',
        'Automatically link files that look like source↔upscale.',
        'auto_pair_upscaled with confidence floor.',
        'Review with Pair Health after a large auto-link.');
      tip(q('#btnRelinkPairs'), 'Relink from tags',
        'Reconnect pairs using UP-#### tags after files moved.',
        'Tag-based pair relink.',
        'Use after renaming/moving already-paired files.');
      tip(q('#btnPairHealth'), 'Pair health',
        'Find broken pairs and leftovers.',
        'pair_health_report.',
        'Cleanup step after big renames.');
      tip(q('#btnFindDup'), 'Inline duplicates',
        'Quick duplicate scan in the current view.',
        'In-library dup scan.',
        'For full merge/delete UI open Find Duplicates Here.');
      tip(q('#btnDupHere'), 'Find Duplicates Here',
        'Open the full Duplicate Manager for this folder.',
        'Deep-link Duplicate File Manager with folder.',
        'Preferred for merge-all and live scan tallies.');
      tip(q('#btnViewList'), 'List view', 'Show files as a list.', 'Table layout.', 'Best for dense metadata.');
      tip(q('#btnViewGrid'), 'Grid view', 'Show thumbnail tiles.', 'Card grid layout.', 'Best for visual scanning.');
      tip(q('#btnViewGroup'), 'Group view', 'Group related files together.', 'Grouped virtual folders.', 'Useful with pair codes.');
      tip(q('#btnNewPlaylist'), 'New playlist', 'Create a playlist from selection or empty.', 'Playlist create API.', 'Build review sets without tags.');
      tip(q('#btnBuildSmart'), 'Smart list', 'Save a smart filter (tags + rules).', 'Smart search builder.', 'Reusable queries across sessions.');
    }
    // Batch converter
    if (path.includes('batch') && path.includes('convert') || path.includes('batch media')) {
      tip(q('#preset'), 'Preset',
        'Choose the output style (quality vs size).',
        'FFmpeg preset id from /convert/presets.',
        'Pick smaller presets first on limited disks/GPUs.');
      tip(q('#outDir'), 'Output folder',
        'Where converted files are written (keep sources safe).',
        'output_dir for convert stream.',
        'Always use a dedicated folder — never overwrite sources blindly.');
      tip(q('#btnEmptyStartSrv'), 'Start server',
        'Start the toolbox backend for convert jobs.',
        'S1 start for ffmpeg stream.',
        'Convert needs S1 + ffmpeg on PATH.');
    }
    // Hubs
    if (path.includes('media hub') || path.includes('compare hub')) {
      tip(q('#btnPopout'), 'Pop out',
        'Open the current tab full-window.',
        'Detached window for dual monitors.',
        'Useful when reviewing long queues.');
      tip(q('#btnCopyReport'), 'Report',
        'Copy a short hub status summary.',
        'Clipboard session report.',
        'Handy for tickets / handoff notes.');
    }
    // Video comparator
    if (path.includes('video comparison') || path.includes('comparison slider')) {
      tip(q('#btn-play'), 'Play', 'Play or pause both sides together.', 'Synced transport.', 'Use with A-B loop for detail.');
      tip(q('#btn-sweep'), 'Sweep', 'Animate the compare slider back and forth.', 'Auto wipe for differences.', 'Great for spotting upscale detail.');
      tip(q('#btn-save-pair'), 'Save pair', 'Lock this before/after as a catalog pair.', 'savePair from comparator.', 'Pins for later review.');
      tip(q('#btn-swap'), 'Swap', 'Swap left and right sources.', 'Invert A/B.', 'When you loaded sides backwards.');
      tip(q('#btn-fit'), 'Fit', 'Fit both videos in the window.', 'Contain scale.', 'Default for overview.');
      tip(q('#btn-100'), '1:1', 'Show true pixels (no scale).', 'Native resolution pan.', 'Best for sharpness checks.');
      tip(q('#btn-fullscreen'), 'Fullscreen', 'Fill the screen for review.', 'Fullscreen stage.', 'Use Esc to exit.');
      tip(q('#btn-screenshot'), 'Screenshot', 'Capture the current compare frame.', 'Frame grab.', 'Good for tickets.');
      tip(q('#btn-mirror-ab'), 'Mirror / sync', 'Center slider and re-sync timelines.', 'Reset A/B alignment.', 'After seeking one side alone.');
      tip(q('#btn-prev-pair'), 'Previous pair', 'Load the previous locked pair.', 'Pair list navigation.', 'Keyboard-friendly review.');
      tip(q('#btn-next-pair'), 'Next pair', 'Load the next locked pair and play.', 'Pair list + autoplay.', 'Speed through a catalog.');
    }
    // Video wall / GEMPlay
    if (path.includes('gemplay') || path.includes('video wall')) {
      tip(q('#btnPick'), 'Folder', 'Pick a media folder for the wall.', 'Load directory into slots.', 'Many simultaneous decodes — heavy on GPU/CPU.');
      tip(q('#btnShuffle'), 'Shuffle', 'Reshuffle which files are in the slots.', 'Random reassign.', 'Fun + sampling.');
      tip(q('#btnMute'), 'Mute', 'Mute or unmute wall audio.', 'Global mute toggle.', 'Keep muted when multitasking.');
      tip(q('#loadDirectoryBtn'), 'Select directory', 'Choose the folder that fills the wall.', 'Primary load action.', 'Start small on weaker PCs.');
    }
    // FAFO VID TRIM
    if (path.includes('vid_trim') || path.includes('vid trim') || path.includes('fafo_vid')) {
      tip(q('#tabVideo'), 'Video tab', 'Max-side resize + batch queue (never upscales).', 'Video encode panel.', 'MP4 needs S1 + ffmpeg + real paths.');
      tip(q('#tabImage'), 'Image tab', 'Resize, crop, and export images.', 'Image shop panel.', 'Use cover/contain carefully for store assets.');
      tip(q('#srcPath'), 'Source path', 'Real disk path for S1/ffmpeg MP4 encode.', 'Server-side source.', 'Browser pick alone cannot write MP4 via S1.');
      tip(q('#btnPickSrc'), 'Browse source', 'Pick a source file path (needs S1).', 'Native path pick.', 'Prefer real paths for queue jobs.');
      tip(q('#outDir'), 'Output directory', 'Where S1 writes exports. Keep separate from sources.', 'output_dir for encode jobs.', 'Required for queue/MP4 writes.');
      tip(q('#btnPickOut'), 'Browse out', 'Pick the output folder via S1.', 'Native folder pick.', 'Save recent dirs for reuse.');
      tip(q('#maxSide'), 'Max side', 'Longest-edge cap in pixels. Never upscales.', 'Downscale only when larger.', '4K max = 3840 is a common default.');
      tip(q('#vidQuality'), 'Encode quality', 'Match source bitrate keeps detail when CRF looks too small.', 'Quality / bitrate strategy.', 'Archive is slowest highest detail.');
      tip(q('#bitrateMode'), 'Bitrate mode', 'Retain same Mbps vs scale with resolution.', 'Match-source bitrate policy.', 'Retain gives more bits/pixel after crop.');
      tip(q('#vidCrf'), 'CRF override', 'Lower CRF = higher quality/larger file. Ignored for match-bitrate.', 'CRF override.', 'Leave Auto unless you know the ladder.');
      tip(q('#vidFps'), 'Cap FPS', 'Leave Source unless you need a hard cap.', 'FPS limit.', 'Forcing 30 from 60 halves motion data.');
      tip(q('#btnVidExport'), 'Export one', 'Encode/export the current video with these settings.', 'Single-job export.', 'Watch free disk on long encodes.');
      tip(q('#btnQAdd'), 'Add to queue', 'Add current path/file to the live batch queue.', 'Queue append.', 'Queue accepts more jobs while running.');
      tip(q('#btnVidFfmpeg'), 'Copy ffmpeg', 'Copy the generated ffmpeg one-liner.', 'Clipboard command.', 'Handy for manual CLI runs.');
      tip(q('#btnQStart'), 'Run queue', 'Process the queue with current encode settings.', 'Batch encode stream.', 'Needs S1 + out dir for MP4.');
      tip(q('#btnQStop'), 'Stop after current', 'Finish the current job, then stop.', 'Soft stop.', 'Does not kill mid-encode unless force tools used.');
      tip(q('#btnImgExport'), 'Export image', 'Write the resized/cropped image.', 'Image export.', 'ICO packs multiple sizes.');
    }
    // Disk analyzer
    if (path.includes('disk space') || path.includes('disk-space')) {
      tip(q('#btnScan'), 'Scan', 'Measure what is using space under a path.', 'Tree size walk.', 'Large trees take time; start at a drive root only if needed.');
      tip(q('#btnStop'), 'Stop', 'Stop the space scan.', 'Cancel walker.', 'Safe anytime.');
      tip(q('#btnExportFiles'), 'Export CSV', 'Download large-file list as CSV.', 'Export findings.', 'Open in Excel for cleanup planning.');
      tip(q('#btnRefreshDrives'), 'Refresh drives', 'Reload drive free-space list.', 'Re-enumerate volumes.', 'After plugging external disks.');
    }
    // Event viewer / deep dive
    if (path.includes('event viewer')) {
      tip(q('#btnRefresh'), 'Refresh', 'Reload recent Windows events.', 'Fetch timeline/summary.', 'Narrow hours if the list is huge.');
      tip(q('#btnExportJson'), 'Export JSON', 'Save the current summary as JSON.', 'Machine-readable export.', 'For tickets or scripts.');
      tip(q('#btnExportCsv'), 'Export CSV', 'Save the timeline as CSV.', 'Spreadsheet export.', 'Filter first for smaller files.');
      tip(q('#btnDeepDiveCtx'), 'Deep dive', 'Open ranked analysis with current filters.', 'Hand off to Event Deep Dive.', 'Best after spotting a theme.');
    }
    if (path.includes('event deep')) {
      tip(q('#btnRun'), 'Run deep dive', 'Analyze events and rank likely fixes.', 'Deep dive pipeline.', 'Longer window = more data, slower run.');
      tip(q('#btnExport'), 'Export JSON', 'Export findings as JSON.', 'Findings dump.', 'Share with support.');
      tip(q('#btnCopy'), 'Copy summary', 'Copy plain-English summary.', 'Clipboard handoff.', 'Good for chat/email.');
    }
    // Malware
    if (path.includes('malware')) {
      tip(q('#btnScan'), 'Run scan', 'Scan with the configured engine/DB.', 'Malware scan job.', 'Update DB first if definitions look stale.');
      tip(q('#btnUpdateOnly'), 'Update DB', 'Update virus definitions only.', 'DB update without full scan.', 'Do this before a big scan.');
      tip(q('#btnQuarantineSel'), 'Quarantine', 'Move selected findings to quarantine.', 'Safe isolate.', 'Prefer quarantine over permanent delete at first.');
      tip(q('#btnDeleteSel'), 'Delete permanently', 'Permanently remove selected findings.', 'Destructive delete.', 'Only after quarantine review.');
      tip(q('#btnSaveKey'), 'Save key', 'Store API/license key for the defender integration.', 'Persist secret presence.', 'Never share the key.');
    }
    // Ops stats
    if (path.includes('ops stats')) {
      tip(q('#btnRefresh'), 'Refresh', 'Reload tallies and charts.', 'Re-read localStorage ledger.', 'Updates after other tools record activity.');
      tip(q('#btnCopy'), 'Copy report', 'Copy a text report of lifetime stats.', 'Clipboard ops report.', 'Good for weekly cleanup notes.');
      tip(q('#btnReset'), 'Clear tallies', 'Erase all lifetime/session stats on this browser.', 'resetAll ledger.', 'Cannot undo — only local tallies, not files.');
    }
    // Health dashboard
    if (path.includes('health dashboard') || path.includes('system health')) {
      tip(q('#btnRefresh'), 'Refresh hub', 'Reload live sections for this PC.', 'Section collectors.', 'Light refresh vs full scan.');
      tip(q('#btnFullScan'), 'Full scan', 'Run deeper diagnostics (longer).', 'Invoke-FAFOSystemDiagnostics.', 'Use sparingly; prefer section re-run.');
      tip(q('#btnGenReport'), 'English report', 'Save a plain-language health report.', 'health_report.generate.', 'Share with non-technical readers.');
      tip(q('#btnExportJson'), 'JSON export', 'Download machine-readable snapshot.', 'Hub JSON.', 'For automation/scripts.');
      tip(q('#btnCopySummary'), 'Copy summary', 'Copy plain-English summary.', 'Clipboard.', 'Quick handoff.');
    }
    // PC diagnostics
    if (path.includes('pc diagnostics') || path.includes('diagnostics hud')) {
      tip(q('#btnRun'), 'Run diagnostics', 'Collect system status for this PC.', 'diagnostics run/pack.', 'Needs S1 online.');
      tip(q('#btnRunTop'), 'Run diagnostics', 'Collect a fresh system status pack (needs S1).', 'Top-bar run.', 'Prefer quick first, then full.');
      tip(q('#btnRunQuick'), 'Quick run', 'Fast diagnostics pass with light sections.', 'Quick pack.', 'Good daily check.');
      tip(q('#btnReloadLatest'), 'Reload latest', 'Load the newest diagnostics pack from disk.', 'Pack reload.', 'After another tool wrote a pack.');
      tip(q('#btnCopySummary'), 'Copy summary', 'Copy plain-English summary for chat or tickets.', 'Clipboard handoff.', 'Also available at top of page.');
      tip(q('#btnExportJson'), 'Export JSON', 'Download the full pack as machine-readable JSON.', 'Pack export.', 'For automation/scripts.');
      tip(q('#btnRescan'), 'Rescan', 'Re-collect live hardware/status signals.', 'Live rescan.', 'After plugging devices.');
      tip(q('#btnHudView'), 'HUD view', 'Dense diagnostics HUD layout.', 'View mode.', 'Best for power users.');
      tip(q('#btnSimpleView'), 'Simple view', 'Simplified plain-language view.', 'View mode.', 'Best for non-technical readers.');
      tip(q('#btnActionsView'), 'Actions view', 'Show recommended fix actions.', 'View mode.', 'Start here when something is red.');
    }
    // Task Manager Pro
    if (path.includes('task manager pro') || path.includes('fafo task manager')) {
      tip(q('#btnReloadProcs'), 'Refresh processes', 'Reload the live process list (R).', 'Process snapshot.', 'Sort by CPU/mem to find hogs.');
      tip(q('#btnExportProcsCsv'), 'Export CSV', 'Download the process table as CSV.', 'Process export.', 'Useful for weekly intel.');
      tip(q('#btnSeedCommonHogs'), 'Seed common hogs', 'Add common optional apps to M2/M3 mode lists.', 'Mode list seed.', 'Review before running a mode.');
      tip(q('#modeSkipUnsafe'), 'Skip unsafe', 'Do not kill system-critical processes in efficiency modes.', 'Safety gate.', 'Leave on unless you know the target.');
      tip(q('#modeForceKill'), 'Force kill', 'Use force-terminate for mode targets.', 'Aggressive kill.', 'Prefer graceful End first.');
      tip(q('#btnKill'), 'End process', 'Gracefully end the selected process.', 'Terminate.', 'Prefer this over Force.');
      tip(q('#btnForce'), 'Force kill', 'Force-terminate the selected process.', 'Force kill.', 'Last resort for hung apps.');
      tip(q('#btnDoRefresh'), 'Run refresh', 'Apply refresh settings and re-sample.', 'Refresh pipeline.', 'Tune interval if list is noisy.');
    }
    // Startup / hosts / IP / LAN / secrets / hardware
    if (path.includes('startup command') || path.includes('startup command board')) {
      tip(q('#btnStartAll'), 'Start allowed', 'Start services allowed by Windows-startup policy.', 'Fleet start.', 'Respects Win-startup checkboxes.');
      tip(q('#btnForceAll'), 'Force start all', 'Force-start every service on the board.', 'Force fleet start.', 'Use carefully on shared PCs.');
      tip(q('#btnStopAll'), 'Stop all', 'Stop all managed FAFO services.', 'Fleet stop.', 'Use when shutting down for the day.');
      tip(q('#btnRestartAll'), 'Restart allowed', 'Restart services allowed to auto-start.', 'Fleet restart.', 'After updates or hung API.');
      tip(q('#btnRefresh'), 'Refresh', 'Re-probe which services are up or down.', 'Fleet probe.', 'Run after start/stop.');
      tip(q('#btnCopyFleet'), 'Copy fleet', 'Copy a text summary of service states.', 'Clipboard fleet.', 'Good for tickets.');
      tip(q('#chkWinServers'), 'Win startup · servers', 'Register/unregister server processes for Windows startup.', 'Autostart servers.', 'Needs privileges on first set.');
      tip(q('#chkWinApp'), 'Win startup · app', 'Register/unregister the app launcher for Windows startup.', 'Autostart app.', 'Optional convenience.');
    }
    if (path.includes('startup service')) {
      tip(q('#btnRefresh'), 'Refresh', 'Reload startup programs and services inventory.', 'Startup inventory.', 'Compare before/after installs.');
      tip(q('#btnExportCsv'), 'Export CSV', 'Download startup inventory as CSV.', 'Startup export.', 'Audit bloatware over time.');
      tip(q('#filter'), 'Filter', 'Filter startup items and services by name.', 'Client filter.', 'Narrow before disable actions.');
    }
    if (path.includes('hosts') || path.includes('dns blocker')) {
      tip(q('#btnEnable'), 'Enable blocklist', 'Apply the selected hosts blocklist.', 'Hosts apply.', 'Needs admin/S1 privileges.');
      tip(q('#btnDisable'), 'Disable blocklist', 'Remove FAFO hosts blocklist entries.', 'Hosts restore.', 'Use if sites break unexpectedly.');
      tip(q('#btnRefresh'), 'Refresh', 'Reload hosts status and block counts.', 'Hosts status.', 'After manual hosts edits.');
      tip(q('#btnAdd'), 'Add host', 'Add a custom host entry to the list.', 'Custom block/allow.', 'Typos can break sites — double-check.');
      tip(q('#btnCopyStatus'), 'Copy status', 'Copy hosts/blocklist status summary.', 'Clipboard.', 'For support notes.');
    }
    if (path.includes('ip profile')) {
      tip(q('#btnApplyForm'), 'Apply profile', 'Apply this IP config to the selected adapter.', 'NIC apply.', 'Needs privileges; DHCP vs static matters.');
      tip(q('#btnSave'), 'Save profile', 'Save this profile for later apply.', 'Profile persist.', 'Name by site or role.');
      tip(q('#btnCapture'), 'Capture current', 'Capture the current adapter config into a draft.', 'Capture live NIC.', 'Fastest way to clone a working setup.');
      tip(q('#btnRefreshAdapters'), 'Refresh adapters', 'Re-enumerate network adapters.', 'NIC list.', 'After docking/undocking.');
      tip(q('#btnExport'), 'Export profiles', 'Export IP profiles for backup or another PC.', 'Profile export.', 'Keep secrets out of shared copies.');
      tip(q('#profMode'), 'IP mode', 'DHCP or static configuration.', 'Addressing mode.', 'Static needs IP/mask/gw/DNS.');
    }
    if (path.includes('lan task')) {
      tip(q('#btnDiscover'), 'Discover LAN', 'Scan the subnet for live hosts.', 'LAN discovery.', 'Stay on networks you own/admin.');
      tip(q('#btnPing'), 'Ping', 'ICMP ping the host.', 'Ping tool.', 'First check when something is “down”.');
      tip(q('#btnTelnet'), 'Port check', 'Test if a TCP port is open.', 'TCP probe.', 'Good for 80/443/22/3389.');
      tip(q('#btnTrace'), 'Traceroute', 'Trace hops to the host.', 'Path discovery.', 'Find where the path dies.');
      tip(q('#btnDns'), 'DNS lookup', 'Resolve DNS records.', 'DNS tool.', 'Check A/AAAA/CNAME mismatches.');
      tip(q('#btnScan'), 'Port scan', 'Scan listed ports on the host.', 'Port scan.', 'Use narrow ranges; avoid hostile networks.');
      tip(q('#btnRefreshProcs'), 'Refresh processes', 'Reload process list.', 'Process snapshot.', 'Pair with kill carefully.');
      tip(q('#btnKillProc'), 'End process', 'End the selected process.', 'Terminate.', 'Prefer graceful over force.');
    }
    if (path.includes('hardware board') || path.includes('hardware board map')) {
      tip(q('#btnRefresh'), 'Refresh', 'Reload hardware inventory and port map.', 'HW inventory.', 'After plugging USB/display devices.');
      tip(q('#btnCopyHw'), 'Copy hardware', 'Copy hardware summary to clipboard.', 'Clipboard HW.', 'Good for tickets.');
      tip(q('#btnExportHw'), 'Export hardware', 'Export hardware inventory.', 'HW export.', 'Archive before major upgrades.');
    }
    if (path.includes('secrets presence')) {
      tip(q('#btnRefresh'), 'Refresh', 'Reload which secrets/keys are present (not values).', 'Presence only.', 'Never displays secret values.');
      tip(q('#btnCopy'), 'Copy status', 'Copy presence checklist (never secret values).', 'Clipboard presence.', 'Safe to share in tickets.');
      tip(q('#btnStartServer'), 'Start server', 'Start S1 to read secure-store presence.', 'S1 required.', 'Presence APIs need backend.');
    }
    if (path.includes('transfer monitor')) {
      tip(q('#btnRun'), 'Run monitor', 'Start watching transfers and partial downloads.', 'Monitor loop.', 'Keep window open while copying.');
      tip(q('#btnFolder'), 'Watch folder', 'Pick a folder to watch for partial downloads.', 'Folder watch.', 'Browser temp dirs vary by app.');
      tip(q('#btnCopyTip'), 'Copy tip', 'Copy a status tip for the current transfer.', 'Clipboard.', 'Quick handoff.');
      tip(q('#btnOfflineStart'), 'Start server', 'Start S1 when offline banner shows.', 'Backend start.', 'Prefer companion bar when present.');
    }
    // Commander / Phone / Punch
    if (path.includes('commander status') || path.includes('status hud')) {
      tip(q('#btnProbe'), 'Probe', 'Talk to the Commander site and collect status.', 'Live probe + gather.', 'Save profile first for reuse.');
      tip(q('#btnSaveProfile'), 'Save profile', 'Remember this site for next time.', 'Profile persist.', 'Name sites clearly (store #).');
      tip(q('#btnJournalLogin'), 'Journal login', 'Open CGILink and load journal periods.', 'Session bootstrap.', 'Required before Get Data.');
      tip(q('#btnJGetData'), 'Get Data', 'Download journal data for the selected period.', 'Journal fetch.', 'Force reload if cache looks stale.');
      tip(q('#btnJExport'), 'Export CSV', 'Export the current journal view.', 'CSV export.', 'Apply filters first for smaller files.');
    }
    if (path.includes('phone assist')) {
      tip(q('#btnHome'), 'Root', 'Jump to the top of the call tree.', 'Nav root.', 'Start each new call from Root.');
      tip(q('#btnBack'), 'Back', 'Go up one step in the tree.', 'Nav back.', 'Does not hang up the call.');
      tip(q('#btnSsh'), 'SSH / resetpw', 'Show password-reset / SSH SOP helpers.', 'SOP panel.', 'Copy full SOP when escalating.');
      tip(q('#btnCopySay'), 'Copy say-this', 'Copy the suggested agent script.', 'Clipboard phrase.', 'Primary call-flow action.');
      tip(q('#btnCopyPath'), 'Copy path', 'Copy where you are in the tree.', 'Path clipboard.', 'Useful for notes.');
      tip(q('#btnCopySession'), 'Session summary', 'Copy a summary of this call session.', 'Session report.', 'End-of-call notes.');
    }
    if (path.includes('pre-reload') || path.includes('punch')) {
      tip(q('#btnCreateOpen'), 'Create & open', 'Create the punch list and open it for editing.', 'Punch list create.', 'Fill site fields first.');
      tip(q('#btnOpenConsole'), 'Commander Console', 'Open site console / dossiers.', 'Cross-link.', 'For deeper site intel.');
      tip(q('#btnOpenPhone'), 'Phone Assist', 'Open the call navigator.', 'Cross-link.', 'Use during live phone support.');
      tip(q('#btnCopyPunchStatus'), 'Copy status', 'Copy punch-list status summary.', 'Clipboard.', 'Quick handoff.');
    }
    // Commander Site Console
    if (path.includes('commander site') || path.includes('site console')) {
      tip(q('#btnQuickStart'), 'Quick start', 'Jump to the guided site-setup checklist.', 'Onboarding path.', 'Start here on a new site.');
      tip(q('#btnSync'), 'Sync', 'Sync site data from disk/watch paths.', 'Site sync.', 'After Import-Export drops files.');
      tip(q('#btnSetRoot'), 'Set root', 'Set the Commander sites root folder on disk.', 'Root path.', 'One root for all store dossiers.');
      tip(q('#btnLiveHud'), 'Live HUD', 'Open Commander Status HUD for this site.', 'Cross-link HUD.', 'Live probe + journal tools.');
      tip(q('#btnPhoneAssist'), 'Phone Assist', 'Open the phone call navigator.', 'Cross-link phone.', 'Use during live support calls.');
      tip(q('#btnPreReload'), 'Pre-Reload punch', 'Open the pre-reload punch list.', 'Cross-link punch.', 'Before risky reloads.');
      tip(q('#btnCopySiteSummary'), 'Copy site summary', 'Copy a text summary of the selected site.', 'Clipboard site.', 'Good for tickets/handoffs.');
      tip(q('#btnJLogin'), 'Journal login', 'Log into journal CGI and refresh periods.', 'Journal session.', 'Required before Get Data.');
      tip(q('#btnJGetData'), 'Get Data', 'Download journal data for the selected period.', 'Journal fetch.', 'Force reload if cache looks stale.');
      tip(q('#btnJExport'), 'Export journal CSV', 'Export the current journal view as CSV.', 'Journal export.', 'Apply filters first.');
      tip(q('#btnIeExport'), 'Export DB', 'Run Import-Export export for selected DBs.', 'IE export.', 'Confirm path and site # first.');
      tip(q('#btnIeImport'), 'Import DB', 'Run Import-Export import for selected DBs.', 'IE import.', 'Destructive — verify backup first.');
      tip(q('#btnPluApply'), 'Apply PLU', 'Apply staged PLU changes to Commander.', 'PLU apply.', 'Verify staged diffs first.');
      tip(q('#btnMpRotate'), 'Rotate passwords', 'Advance the password rotation cycle.', 'MP rotation.', 'Mark changed after on-site work.');
      tip(q('#btnShareRedacted'), 'Share redacted', 'Share a redacted site pack (no secrets).', 'Safe share.', 'Prefer this over full share.');
      tip(q('#btnPreflight'), 'Preflight', 'Run site preflight checks before reload/work.', 'Preflight pack.', 'Catch missing backups early.');
      tip(q('#btnOcrRun'), 'Run OCR', 'OCR screenshots/notes into structured fields.', 'OCR pipeline.', 'Review before applying fields.');
      tip(q('#btnSaveLayout'), 'Save layout', 'Save store layout positions.', 'Layout persist.', 'Seed a template if empty.');
    }
    // TaxForge family
    if (path.includes('taxforge') || path.includes('business tax') || path.includes('write-off')
        || path.includes('mileage') || path.includes('ledger') || path.includes('quarterly')
        || path.includes('partner period') || path.includes('year-end') || path.includes('compliance')) {
      tip(q('#btnRefresh'), 'Refresh', 'Reload statuses from stored tax data.', 'Store re-read.', 'After imports.');
      tip(q('#btnExport'), 'Export', 'Export CSV/JSON for your preparer.', 'Export pack.', 'Prefer redacted expert packs when sharing.');
      tip(q('#btnPack'), 'Preparer pack', 'Download a JSON pack for your tax preparer.', 'Year-end pack.', 'Review before sending.');
      tip(q('#btnCopyBrief'), 'Copy brief', 'Copy the expert brief text.', 'Clipboard brief.', 'Paste into email.');
      tip(q('#btnCopyEmail'), 'Copy email', 'Copy a ready email draft.', 'Email template.', 'Edit site-specific details.');
      tip(q('#btnAuto'), 'Auto-suggest', 'Suggest write-off codes from descriptions.', 'Heuristic coding.', 'Always review before apply.');
      tip(q('#btnApplySugs'), 'Apply suggestions', 'Apply suggested codes to lines.', 'Bulk apply.', 'Undo by re-import if needed.');
      tip(q('#btnSaveSettings'), 'Save settings', 'Remember desk settings.', 'Local store.', 'Per-browser on this PC.');
      tip(q('#btnBridgeCommit'), 'Commit to desk', 'Move preview lines into the working desk.', 'Commit import.', 'Clear selection first if unsure.');
      tip(q('#btnAssistCopyPrompt'), 'Copy Expert prompt', 'Copy an AI-ready expert prompt with redacted context.', 'Assist prompt.', 'Do not include secrets.');
      tip(q('#saveBtn'), 'Save trip', 'Save or update this mileage row.', 'Mileage save.', 'Purpose + miles matter for audits.');
      tip(q('#importMileIQ'), 'Import MileIQ', 'Import trips from a MileIQ export file.', 'Mileage import.', 'Review business % after import.');
      tip(q('#exportCsv'), 'Export CSV', 'Download as CSV for your preparer.', 'CSV export.', 'Filter year first.');
      tip(q('#exportJson'), 'Export JSON', 'Download as JSON for tools/backups.', 'JSON export.', 'Pair with expert pack when sharing.');
      tip(q('#saveAll'), 'Save all', 'Persist quarterly estimate entries for this year.', 'Quarterly save.', 'Update after each estimated payment.');
      tip(q('#btnRecalc'), 'Recalc pulse', 'Recalculate compliance scores from stored data.', 'Compliance recalc.', 'Run after big imports.');
      tip(q('#btnQCalc'), 'Calc quarterly', 'Estimate remaining quarterly payment.', 'Safe-harbor helper.', 'Not tax advice — verify with preparer.');
      tip(q('#btnOAuth'), 'OAuth connect', 'Start OAuth flow to the bookkeeping provider.', 'Ledger OAuth.', 'Store secret via presence store, not plain notes.');
      tip(q('#btnLiveSync'), 'Live sync', 'Pull live transactions after OAuth is connected.', 'Ledger sync.', 'Demo mode first if testing.');
      tip(q('#btnCreateGo'), 'Create in ledger', 'Push confirmed rows to the connected ledger.', 'Ledger create.', 'Confirm selection first.');
      tip(q('#btnPartnerAssistCopy'), 'Copy assist prompt', 'Copy redacted expert prompt for partner questions.', 'Partner assist.', 'Strip secrets before pasting into AI.');
      tip(q('#btnRollup'), 'Rollup', 'Compute period rollups by kind and partner.', 'Partner rollup.', 'Export after rollup for review.');
    }
    // Typing trainer
    if (path.includes('typing')) {
      tip(q('#btnStart'), 'New test', 'Start a fresh typing run with current mode/options.', 'Start run.', 'Focus the typing area after start.');
      tip(q('#btnRestart'), 'Restart', 'Restart this run (Tab). Does not change mode settings.', 'Reset run.', 'Tab also restarts in many modes.');
      tip(q('#playerName'), 'Name', 'Name for high scores and Ops Stats (default Ryan Key).', 'Actor id for stats.', 'Can also set after the run.');
      tip(q('#resultName'), 'High-score name', 'Confirm or edit your name after a run, then Save.', 'Post-run HS name.', 'Uses field value unless you change it.');
      tip(q('#btnSaveHs'), 'Save high score', 'Save this run to the high-score board.', 'HS persist.', 'Name required.');
      tip(q('#btnAgain'), 'Try again', 'Start another run with the same mode settings.', 'Retry.', 'Great for improvement loops.');
      tip(q('#duration'), 'Duration', 'How long the timed test runs.', 'Timed length.', 'No limit = open-ended practice.');
      tip(q('#difficulty'), 'Difficulty', 'Harder passages use longer words and denser punctuation.', 'Passage difficulty.', 'Raise after accuracy is solid.');
      tip(q('#optNoCaps'), 'No capitals', 'Practice without capital letters.', 'Simplifies target text.', 'Good for beginners.');
      tip(q('#optNoPunct'), 'No punctuation', 'Practice without punctuation.', 'Letters/spaces only.', 'Builds speed before accuracy on symbols.');
      tip(q('#btnNovelStart'), 'Open book', 'Load the selected novel chapter and start typing.', 'Novel mode.', 'Enable auto-next for long sessions.');
      tip(q('#btnCampStart'), 'Attack Territory', 'Start the campaign map battle for the selected territory.', 'Campaign run.', 'Story progresses with wins.');
      tip(q('#btnExportHs'), 'Export high scores', 'Download your high-score board.', 'HS export.', 'Back up before Clear.');
      tip(q('#btnClearHs'), 'Clear high scores', 'Erase the local high-score board. Cannot undo.', 'HS reset.', 'Export first if you care about history.');
      tip(q('#btnClearLib'), 'Clear library', 'Remove imported PDF/TXT passages.', 'Library clear.', 'Does not delete original files on disk.');
    }
    // Image comparator
    if (path.includes('image comparitor') || path.includes('image comparator') || path.includes('comparitor with slider')) {
      tip(q('#btn-swap'), 'Swap', 'Swap left and right image sources.', 'Invert A/B.', 'When you loaded sides backwards.');
      tip(q('#btn-fit'), 'Fit', 'Fit both images in the window.', 'Contain scale.', 'Default for overview.');
      tip(q('#btn-100'), '1:1', 'Show true pixels (no scale).', 'Native resolution pan.', 'Best for sharpness checks.');
      tip(q('#btn-save-pair'), 'Save pair', 'Lock this before/after as a catalog pair.', 'savePair from comparator.', 'Pins for later review.');
      tip(q('#btn-loupe'), 'Loupe', 'Toggle magnifier for detail checks.', 'Loupe tool.', 'Great for upscale inspection.');
      tip(q('#btn-export'), 'Export', 'Export the current compare view/frame.', 'Frame/export.', 'Good for tickets.');
    }
    // Ops / FAFO stats already covered
    // Launcher
    if (path.includes('toolbox launcher') || path.endsWith('/toolbox/') || path.includes('launcher.html')) {
      tip(q('#btnStartServer'), 'Start all servers',
        'Start the toolbox backend servers in the background.',
        'S1 + optional S2 tray start.',
        'Prefer Start All once, then leave tray running.');
      tip(q('#btnStopAllServers'), 'Stop all',
        'Stop toolbox servers until you start them again.',
        'Manual stop S1/S2.',
        'Use when shutting down for the day.');
      tip(q('#btnRelaunchServers'), 'Relaunch',
        'Force restart servers.',
        'Hard restart S1/S2.',
        'Use after updates or hung API.');
      tip(q('#btnCompleteSetup'), 'Install FAFO Toolbox',
        'Install missing pieces for this PC (no UAC by default).',
        'Install-FAFOToolbox flow.',
        'Run once per machine after clone.');
      tip(q('#btnOneClickLaunch'), 'One-click launch',
        'Setup if needed, start servers, open the app window.',
        'Full launch pipeline.',
        'Best daily entrypoint.');
      tip(q('#btnWatchdogStart'), 'Start watchdog',
        'Background monitor that restarts servers if they die.',
        'Watchdog service.',
        'Install auto-start for reboot survival.');
      tip(q('#btnSettings'), 'Settings',
        'Shortcuts, recents, visibility, intros.',
        'Launcher prefs.',
        'Ctrl+, also opens settings.');
      tip(q('#btnGetStarted'), 'Get Started',
        'Replay the walkthrough or show the quick-start panel.',
        'Tutorial entry.',
        'Good for new users on this PC.');
      tip(q('#btnCommandPalette'), 'Command palette',
        'Jump to any tool by typing its name.',
        'Cmd-K style navigation.',
        'Fastest way around a large toolbox.');
    }
  }

  function ensurePanelCss() {
    if (document.getElementById('fafoPcScoreCss')) return;
    const s = document.createElement('style');
    s.id = 'fafoPcScoreCss';
    s.textContent = `
      #fafoSkillCtl{display:inline-flex;align-items:center;gap:6px;font:600 11px system-ui;color:#9aa3ad;margin-left:8px;position:relative}
      #fafoPcScoreChip{
        cursor:pointer;padding:3px 9px;border-radius:999px;font-weight:700;
        border:1px solid rgba(0,243,255,.35);background:rgba(0,243,255,.1);color:#7df9ff;
        white-space:nowrap;
      }
      #fafoPcScoreChip:hover{box-shadow:0 0 12px rgba(0,243,255,.35);color:#fff}
      #fafoPcScorePanel{
        display:none;position:fixed;z-index:100010;width:min(320px,calc(100vw - 24px));
        background:rgba(8,8,14,.98);border:1px solid rgba(0,243,255,.35);border-radius:14px;
        box-shadow:0 0 28px rgba(0,243,255,.12),0 16px 48px rgba(0,0,0,.55);
        padding:12px 14px;color:#e8e8ec;font:500 12px/1.45 system-ui,Segoe UI,sans-serif;
      }
      #fafoPcScorePanel.open{display:block}
      #fafoPcScorePanel h3{margin:0 0 4px;font-size:13px;color:#00f3ff;font-weight:700;letter-spacing:.02em}
      #fafoPcScorePanel .sub{color:#8b95a5;font-size:11px;margin-bottom:10px}
      #fafoPcScorePanel .overall{
        display:flex;align-items:center;gap:12px;margin-bottom:12px;padding:10px;
        background:rgba(0,243,255,.06);border:1px solid rgba(0,243,255,.18);border-radius:10px;
      }
      #fafoPcScorePanel .big{font-size:28px;font-weight:800;color:#00f3ff;line-height:1}
      #fafoPcScorePanel .tier{
        display:inline-block;padding:2px 8px;border-radius:999px;font-size:10px;font-weight:800;
        text-transform:uppercase;letter-spacing:.06em;border:1px solid rgba(255,255,255,.15);
      }
      #fafoPcScorePanel .tier.high{color:#00ff88;border-color:rgba(0,255,136,.4)}
      #fafoPcScorePanel .tier.mid{color:#fbbf24;border-color:rgba(251,191,36,.4)}
      #fafoPcScorePanel .tier.low{color:#ff8fab;border-color:rgba(255,143,171,.4)}
      #fafoPcScorePanel .rows{display:flex;flex-direction:column;gap:7px}
      #fafoPcScorePanel .row{display:grid;grid-template-columns:64px 1fr 36px;gap:8px;align-items:center}
      #fafoPcScorePanel .row .k{font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:#7a8494;font-weight:700}
      #fafoPcScorePanel .bar{height:7px;border-radius:99px;background:rgba(255,255,255,.08);overflow:hidden}
      #fafoPcScorePanel .bar > i{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#00f3ff,#7c5cff)}
      #fafoPcScorePanel .bar.low > i{background:linear-gradient(90deg,#ff6b8a,#fbbf24)}
      #fafoPcScorePanel .bar.mid > i{background:linear-gradient(90deg,#fbbf24,#00f3ff)}
      #fafoPcScorePanel .n{font:700 11px Consolas,monospace;color:#c8d0d8;text-align:right}
      #fafoPcScorePanel .hint{margin-top:10px;font-size:11px;color:#8b95a5;line-height:1.4}
      #fafoPcScorePanel .actions{display:flex;gap:6px;margin-top:10px;flex-wrap:wrap}
      #fafoPcScorePanel button{
        font:600 11px system-ui;padding:5px 10px;border-radius:8px;cursor:pointer;
        border:1px solid rgba(0,243,255,.35);background:rgba(0,243,255,.1);color:#00f3ff;
      }
      #fafoPcScorePanel button.ghost{background:transparent;border-color:rgba(255,255,255,.15);color:#9aa3ad}
    `;
    document.head.appendChild(s);
  }

  function installSkillControl() {
    if (document.getElementById('fafoSkillCtl')) {
      updateScoreChip();
      return;
    }
    const bar = document.getElementById('tbSharedServerBar') || document.getElementById('atx-pro-bar');
    if (!bar) return;
    ensurePanelCss();
    const wrap = document.createElement('label');
    wrap.id = 'fafoSkillCtl';
    wrap.title = 'Tooltip language & guidance depth (independent of PC score)';
    wrap.innerHTML = `Guidance
      <select id="fafoSkillSelect" style="background:#0a0a10;color:#00f3ff;border:1px solid rgba(0,243,255,.35);border-radius:6px;padding:3px 6px;font:600 11px system-ui">
        <option value="auto">Auto (from PC)</option>
        <option value="beginner">Beginner</option>
        <option value="intermediate">Intermediate</option>
        <option value="advanced">Advanced</option>
      </select>
      <button type="button" id="fafoPcScoreChip" title="Open PC score panel">PC …</button>`;
    const actions = bar.querySelector('.tb-bar-actions') || bar.querySelector('.atx-actions') || bar;
    actions.appendChild(wrap);
    const sel = wrap.querySelector('#fafoSkillSelect');
    if (sel) {
      sel.value = skillPref;
      sel.addEventListener('change', () => {
        setSkillPref(sel.value);
        const UI = global.AIToolboxUI;
        if (UI?.toast) {
          UI.toast('Guidance: ' + sel.value + ' · tips refresh on next hover', 'ok');
        }
        updateScoreChip();
        renderScorePanel();
      });
    }
    const chip = document.getElementById('fafoPcScoreChip');
    chip?.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      toggleScorePanel();
    });
    // Close panel on outside click
    if (!document._fafoPanelCloseBound) {
      document._fafoPanelCloseBound = true;
      document.addEventListener('click', (e) => {
        const panel = document.getElementById('fafoPcScorePanel');
        if (!panel || !panel.classList.contains('open')) return;
        if (e.target.closest('#fafoPcScorePanel') || e.target.closest('#fafoPcScoreChip')) return;
        panel.classList.remove('open');
      });
    }
    updateScoreChip();
  }

  function barClass(score) {
    if (score >= 80) return 'high';
    if (score >= 50) return 'mid';
    return 'low';
  }

  function renderScorePanel() {
    ensurePanelCss();
    let panel = document.getElementById('fafoPcScorePanel');
    if (!panel) {
      panel = document.createElement('div');
      panel.id = 'fafoPcScorePanel';
      panel.setAttribute('role', 'dialog');
      panel.setAttribute('aria-label', 'PC score');
      document.body.appendChild(panel);
    }
    const hw = getHardware();
    const c = hw.components || {};
    const rows = [
      ['GPU', c.gpu],
      ['CPU', c.cpu],
      ['RAM', c.ram],
      ['Disk', c.storage],
      ['Net', c.network],
    ];
    const tier = hw.tier || 'mid';
    const tip = tier === 'high'
      ? 'Strong box — tooltips lean toward quality/performance when Guidance is Auto.'
      : tier === 'low'
        ? 'Modest box — tooltips lean toward efficiency and smaller batches when Guidance is Auto.'
        : 'Balanced box — tooltips stay in the middle unless you set Guidance manually.';
    panel.innerHTML = `
      <h3>PC score</h3>
      <div class="sub">${escHtml(hw.labels?.computer || 'This PC')} · inventory only (no benchmarks)</div>
      <div class="overall">
        <div class="big">${hw.overall ?? '—'}</div>
        <div>
          <div class="tier ${tier}">${tier} tier</div>
          <div style="margin-top:6px;font-size:11px;color:#8b95a5">Tips level: <strong style="color:#e8e8ec">${escHtml(effectiveLevel())}</strong>
            (skill: ${escHtml(skillPref)})</div>
        </div>
      </div>
      <div class="rows">
        ${rows.map(([k, v]) => {
          const sc = v?.score ?? 0;
          return `<div class="row">
            <span class="k">${k}</span>
            <div class="bar ${barClass(sc)}" title="${escHtml(v?.label || '')}"><i style="width:${clamp(sc, 0, 100)}%"></i></div>
            <span class="n">${sc}</span>
          </div>
          <div style="font-size:10px;color:#6a7380;margin:-4px 0 2px 72px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escHtml(v?.label || '—')}</div>`;
        }).join('')}
      </div>
      <div class="hint">${escHtml(tip)}</div>
      <div class="actions">
        <button type="button" id="fafoPcRefresh">↻ Rescan hardware</button>
        <button type="button" class="ghost" id="fafoPcClose">Close</button>
      </div>`;
    panel.querySelector('#fafoPcRefresh')?.addEventListener('click', async () => {
      const btn = panel.querySelector('#fafoPcRefresh');
      if (btn) btn.textContent = '…';
      await refreshHardware(true);
      renderScorePanel();
      updateScoreChip();
      global.AIToolboxUI?.toast?.('PC inventory refreshed', 'ok');
    });
    panel.querySelector('#fafoPcClose')?.addEventListener('click', () => panel.classList.remove('open'));
    positionScorePanel();
  }

  function escHtml(s) {
    return String(s || '').replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }

  function positionScorePanel() {
    const panel = document.getElementById('fafoPcScorePanel');
    const chip = document.getElementById('fafoPcScoreChip');
    if (!panel || !chip) return;
    const r = chip.getBoundingClientRect();
    const pw = panel.offsetWidth || 320;
    let left = r.right - pw;
    let top = r.bottom + 8;
    if (left < 8) left = 8;
    if (left + pw > window.innerWidth - 8) left = window.innerWidth - pw - 8;
    if (top + 360 > window.innerHeight) top = Math.max(8, r.top - 360);
    panel.style.left = left + 'px';
    panel.style.top = top + 'px';
  }

  function toggleScorePanel() {
    renderScorePanel();
    const panel = document.getElementById('fafoPcScorePanel');
    if (!panel) return;
    panel.classList.toggle('open');
    if (panel.classList.contains('open')) positionScorePanel();
  }

  function updateScoreChip() {
    const chip = document.getElementById('fafoPcScoreChip');
    if (!chip) return;
    const hw = getHardware();
    const lvl = effectiveLevel();
    chip.textContent = `PC ${hw.overall} · ${lvl.slice(0, 3)}`;
    chip.title = (hw.labels?.summary || '') + ' — click for component scores';
  }

  function patchTooltips() {
    const UI = global.AIToolboxUI;
    if (!UI || UI._guidancePatched) return;
    UI._guidancePatched = true;
    const orig = UI.initTooltips;
    if (typeof orig !== 'function') return;
    UI.initTooltips = function (root) {
      try { autoAnnotate(root || document); } catch (_) { /* ignore */ }
      // Bind with resolved tips: temporarily rewrite dataset on enter
      const scope = root || document;
      // Use native init for data-tip elements first
      orig.call(UI, scope);
      // Re-bind mouseenter to inject resolved multi-level text
      scope.querySelectorAll('[data-tip], [data-tip-basic], [data-tip-pro], [title]').forEach((el) => {
        if (el._guideTipBound) return;
        el._guideTipBound = true;
        el.addEventListener('mouseenter', () => {
          const r = resolveTip(el);
          if (r.title) el.setAttribute('data-tip-title', r.title);
          if (r.text) el.setAttribute('data-tip', r.text);
        }, true);
      });
    };
  }

  async function boot() {
    patchTooltips();
    await refreshHardware(false);
    installSkillControl();
    try {
      autoAnnotate(document);
      global.AIToolboxUI?.initTooltips?.(document);
    } catch (_) { /* ignore */ }
    updateScoreChip();
  }

  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => { setTimeout(boot, 50); }, { once: true });
    } else {
      setTimeout(boot, 50);
    }
  }

  global.FAFOGuidance = {
    refreshHardware,
    getHardware,
    getSkillPref,
    setSkillPref,
    effectiveLevel,
    pcTier,
    resolveTip,
    autoAnnotate,
    buildProfileFromIdentity,
    installSkillControl,
    toggleScorePanel,
    renderScorePanel,
    openScorePanel: () => { renderScorePanel(); document.getElementById('fafoPcScorePanel')?.classList.add('open'); positionScorePanel(); },
  };
})(typeof window !== 'undefined' ? window : globalThis);
