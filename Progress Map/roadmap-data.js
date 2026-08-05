/**
 * FAFO / Toolbox development roadmap — living map of what exists vs what's next.
 * Edit this file (or the in-app editor) as milestones complete.
 */
(function (global) {
  'use strict';

  const NOW = '2026-07';

  /** @type {import('./types').RoadmapData} */
  const ROADMAP = {
    updated: NOW,
    mission:
      'One home for field tools, chrome apps, media pipelines, and clever public mythos — build what earns truck time and client trust.',

    apps: [
      {
        id: 'toolbox',
        name: 'AI HTML Toolbox (FAFO Power Toolbox)',
        path: 'C:\\_Git\\repos\\html\\HTML Toolbox AI tools\\production',
        summary:
          'Local HTML + Python backend for Verifone, media, system diagnostics, launchers, and multi-server companions (S1/S2).',
        status: 'production',
        progress: 82,
        goalsTotal: 12,
        goalsDone: 10,
        milestones: [
          { id: 'tb-s1s2', title: 'S1/S2 multi-server + tray + named bats', done: true, when: '2026-07' },
          { id: 'tb-bar', title: 'Companion bar on every tool (← Toolbox)', done: true, when: '2026-07' },
          { id: 'tb-cine', title: 'Cinematic intro fit/1:1 + folder shuffle', done: true, when: '2026-07' },
          { id: 'tb-progress', title: 'Progress Map + Mythos chamber', done: true, when: '2026-07' },
          { id: 'tb-xero', title: 'Xero OAuth sync (contacts/invoices)', done: false, when: null },
          { id: 'tb-ocr', title: 'POS screenshot OCR → site configs', done: false, when: null },
        ],
        nextFocus: 'Xero read-only money metrics to drive mythos sizes; real sites.json.',
      },
      {
        id: 'local-media',
        name: 'FAFO Local Media (Chrome new tab)',
        path: 'C:\\_Git\\repos\\html\\fafo-chrome-extensions\\FAFO Local Media LOAD THIS',
        summary:
          'Cinema new-tab player with tags, pairs, smart playlists, Explorer metadata companion (S2 :8765).',
        status: 'production',
        progress: 82,
        goalsTotal: 10,
        goalsDone: 8,
        milestones: [
          { id: 'lm-merge', title: 'Ultimate Tab + Local Media merge (LOAD THIS)', done: true, when: '2026-07' },
          { id: 'lm-73', title: 'v7.3 smart dupes / tag clear / cinema scale', done: true, when: '2026-07' },
          { id: 'lm-scrub', title: 'Tag junk scrub (Signature/Comfy dumps)', done: true, when: '2026-07' },
          { id: 'lm-store', title: 'Chrome Web Store package pipeline', done: false, when: null },
        ],
        nextFocus: 'Store packaging + keep tag scrub hardened.',
      },
      {
        id: 'progen',
        name: 'FAFO ProGen Studio',
        path: '…\\fafo-chrome-extensions\\ProGen\\FAFO Progen V6.0 GROK EDIT',
        summary: 'Staged AI prompt compiler with profiles, palette, and export formats.',
        status: 'beta',
        progress: 70,
        goalsTotal: 8,
        goalsDone: 5,
        milestones: [
          { id: 'pg-v6', title: 'V6 Studio UI + command palette', done: true, when: '2026-07' },
          { id: 'pg-xero', title: 'Optional export hooks to job notes', done: false, when: null },
        ],
        nextFocus: 'Stabilize V6; document load path for techs.',
      },
      {
        id: 'comfy',
        name: 'ComfyUI / FlashVSR pipelines',
        path: 'C:\\_Git\\repos\\apps\\comfyui-desktop',
        summary: 'Local gen + VSR pipelines; models on O:/D: via paths/junctions.',
        status: 'production',
        progress: 65,
        goalsTotal: 8,
        goalsDone: 4,
        milestones: [
          { id: 'cf-offload', title: 'Models/media on D/O not cloud', done: true, when: '2026-07' },
          { id: 'cf-share', title: 'Shared model root across apps', done: false, when: null },
        ],
        nextFocus: 'Document shared model junctions for all inference apps.',
      },
      {
        id: 'mythos',
        name: 'Public Mythos (map / skyline / rings)',
        path: 'Progress Map (this tool)',
        summary:
          'Cosmetic growth graphs: letter-color map dots, night skyline, tree rings — impress without spreadsheets.',
        status: 'alpha',
        progress: 25,
        goalsTotal: 10,
        goalsDone: 2,
        milestones: [
          { id: 'my-proto', title: 'Interactive prototypes in Progress Map', done: true, when: '2026-07' },
          { id: 'my-techquest', title: 'TECH QUEST mini-game (adventure off public pages)', done: true, when: '2026-07' },
          { id: 'my-data', title: 'sites.json + letter colors + spend tiers', done: false, when: null },
          { id: 'my-web', title: 'Ship to FAFOPetro.com pages', done: false, when: null },
          { id: 'my-xero', title: 'Dot/tower size from Xero billed', done: false, when: null },
        ],
        nextFocus: 'Wire real site list; keep public view privacy-safe. Adventure laughs → Tech Quest.',
      },
      {
        id: 'xero',
        name: 'Xero accounting bridge',
        path: 'planned',
        summary: 'OAuth2 sync contacts/invoices/items both ways; money feeds mythos + job drafts.',
        status: 'planned',
        progress: 5,
        goalsTotal: 12,
        goalsDone: 0,
        milestones: [
          { id: 'xe-app', title: 'Xero app + OAuth + token store', done: false, when: null },
          { id: 'xe-pull', title: 'Pull contacts + invoices → local DB', done: false, when: null },
          { id: 'xe-push', title: 'Push draft invoices from jobs', done: false, when: null },
        ],
        nextFocus: 'Create Xero developer app when ready for money spine.',
      },
      {
        id: 'ocr',
        name: 'POS photo → site config OCR',
        path: 'planned',
        summary: 'Ingest phone screenshots; OCR into searchable site configs; stop hoarding pics forever.',
        status: 'planned',
        progress: 8,
        goalsTotal: 10,
        goalsDone: 1,
        milestones: [
          { id: 'oc-win', title: 'Windows OCR hook exists in toolbox scripts', done: true, when: '2026-06' },
          { id: 'oc-pipeline', title: 'Drop zone + classify + attach to site', done: false, when: null },
        ],
        nextFocus: 'Drop-zone MVP after Progress Map.',
      },
    ],

    features: {
      installed: [
        { id: 's1', name: 'S1 HTML Toolbox Server :18765', app: 'toolbox', blurb: 'Media, Verifone, system tools API.' },
        { id: 's2', name: 'S2 FAFO Local Media Tagger :8765', app: 'local-media', blurb: 'Explorer tags/ratings companion.' },
        { id: 'tray', name: 'Tray auto-keep + Start/Stop bats', app: 'toolbox', blurb: 'Background companions without folder hunting.' },
        { id: 'cine', name: 'Launch cinematics (fit / 1:1)', app: 'toolbox', blurb: 'Folder shuffle + scale modes.' },
        { id: 'verifone', name: 'Commander console / HUD / punch list', app: 'toolbox', blurb: 'Site dossiers and live probes.' },
        { id: 'media-lib', name: 'Media Library / VSR / pairs', app: 'toolbox', blurb: 'Local media ops with server power.' },
        { id: 'tags', name: 'FAFO tags + pair system + scrub', app: 'local-media', blurb: 'On-play tagging without dump pollution.' },
        { id: 'sticky', name: 'Sticky Notes plain export', app: 'toolbox', blurb: 'Field knowledge backed up as text.' },
        { id: 'playbooks', name: 'Field playbooks 01–07', app: 'toolbox', blurb: 'SOPs from sticky patterns.' },
        { id: 'cloud-org', name: 'OneDrive/GDrive cleanup map', app: 'toolbox', blurb: 'Offload + manuals home.' },
        { id: 'progress-map', name: 'Progress Map + Mythos chamber', app: 'mythos', blurb: 'Roadmap, gems, sealed loot chamber.' },
      ],
      building: [
        { id: 'sites-db', name: 'Sites/customers JSON spine', app: 'mythos', blurb: 'Feeds map, towers, rings, passwords vault keys.' },
      ],
      planned: [
        { id: 'xero-sync', name: 'Xero bidirectional sync', app: 'xero', blurb: 'Money-of-record ↔ field-of-record.' },
        { id: 'web-map', name: 'Public letter-color coverage map', app: 'mythos', blurb: 'Every pin a real site.' },
        { id: 'skyline', name: 'Night skyline (customer towers)', app: 'mythos', blurb: '2 floors/site, windows = avg tanks+dispensers.' },
        { id: 'ocr-pos', name: 'POS screenshot OCR library', app: 'ocr', blurb: 'Search configs without phone archaeology.' },
        { id: 'leaderboard', name: 'Customer block leaderboard', app: 'mythos', blurb: 'Size = volume, no $ labels public.' },
      ],
    },

    history: [
      { when: '2026-07', title: 'Repos home under C:\\_Git\\repos', detail: 'html + apps channels; FAFO chrome monorepo moved.' },
      { when: '2026-07', title: 'S1/S2 servers named + companion bar', detail: 'Auto-keep, manual stop, Windows startup prefs.' },
      { when: '2026-07', title: 'Local Media 7.3 + tag scrub', detail: 'Laptop push merged; junk Signature/Comfy tags filtered.' },
      { when: '2026-07', title: 'Field manuals + sticky export', detail: '866 notes plain text; playbooks drafted.' },
      { when: '2026-07', title: 'Cloud offload + organization', detail: 'D:\\CloudOffload plan; GDrive buckets; docs cleanup.' },
    ],

    /** Mythos unlock — do not put the solution in the public UI. */
    mythos: {
      /** Correct multi-state combination (owner can change) */
      combo: { ring: 'fall', pin: 'cyan', tower: 'landmark' },
      dragonBanMs: 5 * 60 * 1000,
      storagePrefix: 'fafo.mythos.',
    },
  };

  global.FAFO_ROADMAP = ROADMAP;
})(typeof window !== 'undefined' ? window : globalThis);
