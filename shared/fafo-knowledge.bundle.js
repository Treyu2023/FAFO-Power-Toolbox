/**
 * AUTO-GENERATED — do not edit.
 * Source: docs/knowledge/fafo-knowledge.json
 * Rebuild: node tools/compile-fafo-knowledge.js
 * Generated: 2026-08-05T11:44:17.835Z
 */
(function (global) {
  'use strict';
  var DATA = {"schema":"fafo-knowledge/v1","app":"FAFO Ultimate Tab","package":"FAFO Local Media LOAD THIS","version":"1.1.1","updated":"2026-08-05","manifestTarget":"6.4.23","description":"Canonical QoL tidbits, shortcuts, and UX rules for humans and machines. Compiled into GUIDE.md + fafo-knowledge.bundle.js. Context map powers location-aware Help (F1).","contexts":{"newtab":{"label":"New tab · player","app":"ultimate-tab","priority":10,"detect":{"selectorsAny":["#scene-root","body.fafo-ready"],"pathIncludes":["newtab"]},"sections":["player","commands","session","layout"],"items":["player.space","player.next-prev","player.tags-panel","player.help","cmd.palette","cmd.chips","session.resume","layout.stick","layout.memory"]},"newtab.tags":{"label":"Tags panel","app":"ultimate-tab","priority":50,"parent":"newtab","detect":{"selectorsAny":["#meta-panel:not(.collapsed)","#meta-dock .meta-toolbar","#meta-library"],"bodyClassNone":[]},"sections":["tags","commands"],"items":["tag.click-apply","tag.dblclick-remove","tag.right-click-menu","tag.chip-x","tag.keyboard-toggle","tag.colors","tag.themes","tag.undo","player.tags-panel","layout.sliders","explorer.sync","explorer.auto-sync"]},"newtab.sprint":{"label":"Sprint Tag","app":"ultimate-tab","priority":60,"parent":"newtab.tags","detect":{"bodyClassAny":["fafo-sprint-mode"],"selectorsAny":["#meta-sprint-body:not(.hidden)"]},"sections":["tags"],"items":["tag.click-apply","tag.dblclick-remove","tag.keyboard-toggle","player.next-prev"]},"newtab.guide":{"label":"Guide open","app":"ultimate-tab","priority":5,"detect":{"bodyClassAny":["fafo-guide-open"]},"sections":["commands"],"items":["cmd.palette","player.help"]},"options":{"label":"Options","app":"ultimate-tab","priority":20,"detect":{"pathIncludes":["options.html"],"selectorsAny":["#view-library",".nav-items"]},"sections":["library","session","commands"],"items":["lib.restore-access","lib.doctor","session.intro-daily","intro.promos","cmd.palette"]},"options.library":{"label":"Options · Visual Library","app":"ultimate-tab","priority":55,"parent":"options","detect":{"selectorsAny":["#view-library.active","#view-library:not([style*='display: none'])"],"dataView":"view-library"},"sections":["library"],"items":["lib.restore-access","lib.doctor","lib.next-up"]},"options.tag-themes":{"label":"Options · Tag Themes","app":"ultimate-tab","priority":55,"parent":"options","detect":{"dataView":"view-tag-themes"},"sections":["tags"],"items":["tag.themes","tag.colors","tag.click-apply"]},"options.session":{"label":"Options · Session & QoL","app":"ultimate-tab","priority":55,"parent":"options","detect":{"dataView":"view-session"},"sections":["session","commands"],"items":["session.resume","session.intro-daily","cmd.palette","tag.undo"]},"options.intro-promos":{"label":"Options · Intro Promos","app":"ultimate-tab","priority":55,"parent":"options","detect":{"dataView":"view-intro-promos"},"sections":["session"],"items":["intro.promos","session.intro-daily"]},"options.chrome-art":{"label":"Options · Chrome Art","app":"ultimate-tab","priority":55,"parent":"options","detect":{"dataView":"view-chrome-art"},"sections":["layout"],"items":["layout.sliders","layout.stick","layout.memory"]},"options.knowledge":{"label":"Options · Knowledge","app":"ultimate-tab","priority":55,"parent":"options","detect":{"dataView":"view-knowledge"},"sections":["commands"],"items":["cmd.palette","player.help"]},"toolbox":{"label":"AI HTML Toolbox","app":"toolbox","priority":15,"detect":{"pathIncludes":["Toolbox Launcher","AI HTML TOOLBOX"]},"sections":["servers","commands"],"items":["srv.s1-s2","cmd.palette"]},"toolbox.servers":{"label":"Toolbox · Servers / Watchdog","app":"toolbox","priority":50,"parent":"toolbox","detect":{"selectorsAny":["#watchdogPanel","#launchPrefsPanel","#btnWatchdogStart"]},"sections":["servers"],"items":["srv.s1-s2"]},"toolbox.tax":{"label":"Toolbox · TaxForge","app":"toolbox","priority":50,"parent":"toolbox","detect":{"pathIncludes":["TaxForge","Business Tax","Mileage Log","Write-Off"]},"sections":["servers"],"items":["srv.s1-s2"]},"global":{"label":"General","app":"any","priority":1,"detect":{},"sections":["commands","player"],"items":["cmd.palette","player.help","tag.undo"]}},"sections":[{"id":"tags","title":"Tags & ratings","order":10,"items":[{"id":"tag.click-apply","title":"Single click applies only","tip":"Click = apply only. Lists shift under the cursor — single click never removes a tag.","body":"When the tag list reorders (counts, session, filters), a single mis-click used to toggle tags off. From 6.4.20, a single click only applies a tag if it is not already on the file. If it is already on, the status line tells you how to remove it.","selectors":["#meta-library .meta-lib-tag","#meta-recent-tags [data-tag]",".meta-hotkey-slot",".meta-sprint-tag"],"since":"6.4.20","keywords":["click","apply","toggle","misclick","shift"]},{"id":"tag.dblclick-remove","title":"Double-click removes from this file","tip":"Double-click a tag (or chip / hotkey slot) to remove it from the current file only.","body":"Double-click is the fast remove gesture. It does not purge the tag from the library or other files.","selectors":["#meta-library .meta-lib-tag","#meta-recent-tags [data-tag]",".meta-chip[data-tag]",".meta-hotkey-slot"],"since":"6.4.20","keywords":["double-click","remove","file"]},{"id":"tag.right-click-menu","title":"Right-click full tag menu","tip":"Right-click any tag for edit, delete, color, hide, and hotkey assign.","body":"Context menu includes: Edit/rename everywhere, Remove from this file, Hide from list, Remove from library list only, Delete from ALL media, color swatches + picker, and hotkey slot assign.","selectors":["#meta-library .meta-lib-tag","#meta-recent-tags [data-tag]",".meta-chip[data-tag]"],"since":"6.4.19","keywords":["context","menu","rename","purge","color"]},{"id":"tag.chip-x","title":"Chip × needs double-click","tip":"The × on a current-file chip needs a double-click to remove (single-click only reminds you).","body":"Prevents accidental strip when chips reflow after applying another tag.","selectors":[".meta-chip button[data-i]"],"since":"6.4.20","keywords":["chip","remove","×"]},{"id":"tag.keyboard-toggle","title":"Keyboard hotkeys still toggle","tip":"` then 1–0 (or modifier+digit) still toggles on second press — intentional, not a miss-click.","body":"Mouse = apply-only. Keyboard chord hotkeys keep toggle-off so power users can clear quickly.","keys":["`","1-0","Shift+digit"],"since":"6.4.20","keywords":["hotkey","keyboard","toggle"]},{"id":"tag.colors","title":"Per-tag custom colors","tip":"Right-click a tag → Color: swatches, picker, or Clear color.","body":"Colors live in chrome.storage (fafoTagColors). They follow renames and clear on purge.","since":"6.4.19","keywords":["color","swatch"]},{"id":"tag.themes","title":"Tag theme packs","tip":"Options → Tag Themes, top Theme chip, or Ctrl+K → Cycle tag theme.","body":"Packs: Cyan Ops, Amber Field, Violet Night, Hard Edge, Soft Glass. Affects chip font, radius, glow, selected/last styles.","since":"6.4.18","keywords":["theme","pack","style"]},{"id":"tag.undo","title":"Undo last tag/rating","tip":"Ctrl+Z or top Undo chip · undoes last tag/rating mutation (not purge-all).","keys":["Ctrl+Z"],"since":"6.4.18","keywords":["undo"]}]},{"id":"commands","title":"Command palette & chips","order":20,"items":[{"id":"cmd.palette","title":"Command palette","tip":"Ctrl+K or / — search commands, tags, nearby clips, Resume, Doctor, Theme.","keys":["Ctrl+K","/"],"selectors":["[data-act=cmd]","#fafo-status-chips"],"since":"6.4.18","keywords":["palette","search"]},{"id":"cmd.chips","title":"Top status chips","tip":"⌘K · Undo · Resume · Doctor · Theme · S2 — quick access without hunting menus.","selectors":["#fafo-status-chips"],"since":"6.4.18","keywords":["chips","status"]}]},{"id":"session","title":"Session & intro","order":30,"items":[{"id":"session.resume","title":"Resume last clip","tip":"Session autosaves clip + time. Use Resume chip or Ctrl+K → Resume last session.","since":"6.4.18","keywords":["resume","session"]},{"id":"session.intro-daily","title":"Daily intro (default)","tip":"Options → Session & QoL: daily / always / after-update / never. Quiet splash shortens the title card.","since":"6.4.18","keywords":["intro","daily","quiet"]},{"id":"intro.promos","title":"Intro promo videos","tip":"Options → Intro Promos: 4 folder slots, shuffle residual queue, play full video once, Skip · Esc. Slot 4 = BOFA Deez Teas sponsor.","since":"6.4.17","keywords":["promo","bofa","shuffle"]}]},{"id":"library","title":"Library & next-up","order":40,"items":[{"id":"lib.doctor","title":"Library doctor","tip":"Doctor chip / Ctrl+K → re-grant only folders that lost permission (no full re-pick).","since":"6.4.18","keywords":["restore","permission","folder"]},{"id":"lib.next-up","title":"Up next strip","tip":"Bottom strip shows upcoming clips with thumbs — click to jump.","selectors":["#fafo-next-up"],"since":"6.4.18","keywords":["next","preview","queue"]},{"id":"lib.restore-access","title":"Restore Access after browser restart","tip":"Chrome revokes folder grants on restart — use Restore Access, not delete-and-relink.","since":"6.2.0","keywords":["permission","restart"]}]},{"id":"layout","title":"Layout & scale","order":50,"items":[{"id":"layout.stick","title":"Stick layout","tip":"Stick ON keeps free-float panels from jumping on scale/open. You can always drag ⋮⋮ headers.","selectors":["#meta-stick-layout"],"since":"6.4.0","keywords":["stick","panels"]},{"id":"layout.memory","title":"Layout memory (reload / resize / fullscreen)","tip":"Panel place + size are remembered. Windowed and fullscreen keep separate layouts. Stick remaps proportionally on resize.","body":"From 6.4.23: dual slots (windowed vs fullscreen), normalized coordinates, preferred size that survives temporary shrinks, and scale-safe capture (CSS scale no longer inflates saved width). Save defaults / presets also store this.","selectors":["#meta-layout-save-defaults","#meta-stick-layout","#meta-layout-preset-select"],"since":"6.4.23","keywords":["memory","remember","fullscreen","resize","reload","position","size"]},{"id":"layout.sliders","title":"UI / video sliders in tags panel","tip":"Tags toolbar has UI/tags and Video range sliders (+ ↺ reset) — no need for Options for everyday scale.","selectors":["#meta-scale-sliders","#meta-slider-ui","#meta-slider-video"],"since":"6.4.16","keywords":["scale","slider"]},{"id":"layout.undock","title":"Undock for move","tip":"Undock forces free-float and pulls panels on-screen so headers are draggable.","selectors":["#meta-undock-move"],"since":"6.4.0","keywords":["undock","drag"]}]},{"id":"explorer","title":"Explorer companion (S2)","order":60,"items":[{"id":"explorer.sync","title":"Explorer vs library access","tip":"Explorer Sync writes Tags/Rating into files. Library folders use Options → Restore Access — different systems.","selectors":["#meta-explorer-status","#meta-explorer-sync"],"since":"6.0.0","keywords":["explorer","s2","8765"]},{"id":"explorer.auto-sync","title":"Auto-sync disk writes","tip":"Auto-sync ON queues continuous Explorer metadata writes when the companion server is running.","selectors":["#meta-auto-disk-sync"],"since":"6.4.0","keywords":["auto-sync","disk"]}]},{"id":"player","title":"Player shortcuts","order":70,"items":[{"id":"player.space","title":"Play / pause","tip":"Space — play/pause (or restart looped clip).","keys":["Space"],"since":"1.0.0","keywords":["playback"]},{"id":"player.next-prev","title":"Next / previous","tip":"D / → next · A / ← previous. Untagged clips loop until you press Next (tagging does not advance).","keys":["A","D","ArrowLeft","ArrowRight"],"since":"1.0.0","keywords":["next","prev","loop"]},{"id":"player.tags-panel","title":"Tags panel","tip":"T toggles the tags panel.","keys":["T"],"since":"1.0.0","keywords":["panel"]},{"id":"player.help","title":"Shortcut help & contextual Guide","tip":"F1 opens Help for this screen. ? toggles shortcut overlay. Top Help chip = contextual; Guide chip = all topics.","keys":["F1","?","Shift+?"],"since":"6.4.22","keywords":["help","f1","guide","context"]}]},{"id":"servers","title":"Servers (toolbox)","order":80,"items":[{"id":"srv.s1-s2","title":"S1 vs S2","tip":"S1 HTML Toolbox 127.0.0.87:18765 · S2 FAFO Tagger 127.0.0.1:8765. Watchdog auto-heals; listening≠healthy uses soft retries.","since":"1.10.0","keywords":["watchdog","s1","s2"]}]}]};

  function byId(id) {
    if (!id || !DATA.sections) return null;
    for (var s = 0; s < DATA.sections.length; s++) {
      var items = DATA.sections[s].items || [];
      for (var i = 0; i < items.length; i++) {
        if (items[i].id === id) return items[i];
      }
    }
    return null;
  }

  function tip(id) {
    var it = byId(id);
    return it ? (it.tip || it.title || '') : '';
  }

  function title(id) {
    var it = byId(id);
    return it ? (it.title || it.id) : '';
  }

  function allItems() {
    var out = [];
    (DATA.sections || []).forEach(function (sec) {
      (sec.items || []).forEach(function (it) {
        out.push(Object.assign({ section: sec.id, sectionTitle: sec.title }, it));
      });
    });
    return out;
  }

  /** Apply tip strings to [data-fafo-tip] elements (and optional title). */
  function applyTooltips(root) {
    var scope = root || document;
    if (!scope || !scope.querySelectorAll) return 0;
    var n = 0;
    scope.querySelectorAll('[data-fafo-tip]').forEach(function (el) {
      var id = el.getAttribute('data-fafo-tip');
      var t = tip(id);
      if (!t) return;
      el.setAttribute('title', t);
      el.setAttribute('data-tip', t);
      n++;
    });
    // selector-based tips from knowledge
    allItems().forEach(function (it) {
      (it.selectors || []).forEach(function (sel) {
        try {
          scope.querySelectorAll(sel).forEach(function (el) {
            if (el.getAttribute('data-fafo-tip-locked') === '1') return;
            // Prefer longer explicit title if author set data-fafo-tip
            if (el.hasAttribute('data-fafo-tip')) return;
            var existing = el.getAttribute('title') || '';
            // Don't stomp rich titles that already mention double-click if same tip
            if (!existing || existing.length < 12) {
              el.setAttribute('title', it.tip || it.title);
              n++;
            }
          });
        } catch (e) { /* invalid selector */ }
      });
    });
    return n;
  }

  function ensureGuide() {
    var el = document.getElementById('fafo-knowledge-guide');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'fafo-knowledge-guide';
    el.className = 'fafo-knowledge-guide hidden';
    el.innerHTML =
      '<div class="fkg-backdrop" data-close="1"></div>' +
      '<div class="fkg-panel" role="dialog" aria-label="FAFO guide">' +
      '<div class="fkg-head"><h2>FAFO Guide</h2>' +
      '<input type="search" class="fkg-search" placeholder="Search tips…" />' +
      '<button type="button" class="fkg-close" data-close="1" title="Close">×</button></div>' +
      '<div class="fkg-context-bar"></div>' +
      '<div class="fkg-meta"></div>' +
      '<div class="fkg-body"></div>' +
      '<div class="fkg-foot">F1 contextual help · docs/knowledge · compile tools/compile-fafo-knowledge.js</div>' +
      '</div>';
    document.body.appendChild(el);
    el.querySelectorAll('[data-close]').forEach(function (b) {
      b.addEventListener('click', closeGuide);
    });
    el.querySelector('.fkg-search').addEventListener('input', function (e) {
      if (global.FAFOHelp && global.FAFOHelp.getLastContext && global.FAFOHelp.getLastContext() !== 'global') {
        try {
          global.FAFOHelp.summon({ context: global.FAFOHelp.getLastContext(), q: e.target.value || '' });
          return;
        } catch (err) {}
      }
      renderGuide(e.target.value || '');
    });
    return el;
  }

  function renderGuide(q) {
    var el = ensureGuide();
    var body = el.querySelector('.fkg-body');
    var meta = el.querySelector('.fkg-meta');
    var query = (q || '').trim().toLowerCase();
    if (meta) {
      meta.textContent =
        'v' + (DATA.version || '') + ' · updated ' + (DATA.updated || '') +
        ' · target ' + (DATA.manifestTarget || '');
    }
    var html = '';
    (DATA.sections || []).forEach(function (sec) {
      var items = (sec.items || []).filter(function (it) {
        if (!query) return true;
        var hay = [it.id, it.title, it.tip, it.body, (it.keywords || []).join(' ')].join(' ').toLowerCase();
        return hay.indexOf(query) >= 0;
      });
      if (!items.length) return;
      html += '<section class="fkg-sec"><h3>' + esc(sec.title || sec.id) + '</h3>';
      items.forEach(function (it) {
        html +=
          '<article class="fkg-item" data-id="' + esc(it.id) + '">' +
          '<h4>' + esc(it.title || it.id) + '</h4>' +
          '<p class="fkg-tip">' + esc(it.tip || '') + '</p>' +
          (it.body ? '<p class="fkg-body-text">' + esc(it.body) + '</p>' : '') +
          (it.keys && it.keys.length
            ? '<p class="fkg-keys">' + it.keys.map(function (k) { return '<kbd>' + esc(k) + '</kbd>'; }).join(' ') + '</p>'
            : '') +
          '<code class="fkg-id">' + esc(it.id) + '</code>' +
          '</article>';
      });
      html += '</section>';
    });
    body.innerHTML = html || '<p class="fkg-empty">No matches.</p>';
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function openGuide(q) {
    var el = ensureGuide();
    el.classList.remove('hidden');
    document.body.classList.add('fafo-guide-open');
    renderGuide(q || '');
    setTimeout(function () {
      var s = el.querySelector('.fkg-search');
      if (s) s.focus();
    }, 30);
  }

  function closeGuide() {
    var el = document.getElementById('fafo-knowledge-guide');
    if (el) el.classList.add('hidden');
    document.body.classList.remove('fafo-guide-open');
  }

  function init() {
    try { applyTooltips(document); } catch (e) {}
    setInterval(function () {
      if (document.hidden) return;
      try { applyTooltips(document); } catch (e) {}
    }, 4000);
  }

  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', init);
    } else {
      init();
    }
  }

  global.FAFOKnowledge = {
    data: DATA,
    byId: byId,
    tip: tip,
    title: title,
    allItems: allItems,
    applyTooltips: applyTooltips,
    openGuide: openGuide,
    closeGuide: closeGuide,
    renderGuide: renderGuide,
    ensureGuide: ensureGuide,
    contexts: function () { return DATA.contexts || {}; },
  };
})(typeof window !== 'undefined' ? window : globalThis);
