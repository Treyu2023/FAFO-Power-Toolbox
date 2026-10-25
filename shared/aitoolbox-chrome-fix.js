/**
 * FAFO toolbox chrome clamp — loaded by aitoolbox-ui.js
 * Keeps the shared top S1/S2 bar and bottom LAYOUT/pro dock from
 * reserving a third of the viewport on every tool page.
 */
(function (global) {
  if (global.__fafoChromeFix) return;
  global.__fafoChromeFix = true;

  var CSS = [
    '#atx-pro-bar{display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important;align-items:center!important;gap:8px!important;max-height:48px!important;height:48px!important;overflow-x:auto!important;overflow-y:hidden!important;padding:4px 10px!important}',
    'html[data-atx-layout="phone"] #atx-pro-bar{flex-direction:row!important;align-items:center!important}',
    '#atx-pro-bar .atx-brand{flex:0 0 auto!important;max-width:16ch!important;overflow:hidden!important;text-overflow:ellipsis!important;white-space:nowrap!important}',
    '#atx-pro-bar .atx-chips,#atx-pro-bar .atx-actions{display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important;align-items:center!important;gap:6px!important;min-width:0!important;overflow-x:auto!important;overflow-y:hidden!important}',
    '#atx-pro-bar .atx-chips{flex:1 1 auto!important}',
    '#atx-pro-bar .atx-actions{flex:0 1 auto!important}',
    '#atx-pro-bar a.atx-chip,#atx-pro-bar button.atx-chip{flex:0 0 auto!important;position:relative!important;z-index:1!important;min-height:28px!important;height:28px!important;padding:0 10px!important;white-space:nowrap!important}',
    'body.atx-pro-pad{padding-bottom:var(--atx-pro-h,48px)!important}',
    'body.atx-pro-min #atx-pro-bar{transform:translateY(calc(100% - 8px))!important}',
    'body.atx-pro-min.atx-pro-pad{padding-bottom:8px!important}',
    '.fafo-layout-float-dock{left:10px!important;bottom:calc(var(--atx-pro-h,48px) + 10px)!important;max-height:none!important;overflow:visible!important;pointer-events:none}',
    'body.tb-has-companion-bar .fafo-layout-float-dock,body.atx-pro-pad .fafo-layout-float-dock{bottom:calc(var(--atx-pro-h,48px) + 10px)!important}',
    'body.atx-pro-min .fafo-layout-float-dock{bottom:12px!important}',
    '.fafo-layout-float-host{resize:both!important;overflow:auto!important;min-width:160px!important;min-height:32px!important;max-width:min(72vw,760px)!important;max-height:min(70vh,560px)!important}',
    '.tb-companion-bar,#tbSharedServerBar{flex-wrap:nowrap!important;max-height:42px!important;overflow-x:auto!important;overflow-y:hidden!important;padding:4px 10px!important}',
    '.tb-companion-bar .tb-pill,.tb-companion-bar .tb-btn,.tb-companion-bar .tb-bar-back{flex:0 0 auto!important}',
    '.fafo-layout-rows > .fafo-layout-panel[data-fafo-flex="1"],',
    '.fafo-layout-panel[data-fafo-flex="1"]{flex:1 1 auto!important;min-height:0!important}',
    '.fafo-body-split > [data-fafo-section].fafo-section-flex:not(.fafo-section-fit){flex:1 0 auto!important;min-height:0!important}',
    '.fafo-body-split > [data-fafo-section].fafo-section-fit,[data-fafo-section].fafo-section-fit{flex:0 0 auto!important;height:auto!important;max-height:none!important;overflow:visible!important}',
    '[data-fafo-section][data-fafo-resizable="1"]:not([data-fafo-user-sized="1"]){min-height:0!important;height:auto!important;max-height:none!important;overflow:visible!important}',
    '[data-fafo-section][data-fafo-resizable="1"][data-fafo-user-sized="1"]{min-height:36px!important}',
    '@media (max-width:720px){',
    'html,body{max-width:100%!important;overflow-x:clip!important}',
    'html:not(:has(body.run-active)),html:not(:has(body.run-active)) body{height:auto!important;max-height:none!important;overflow-y:auto!important}',
    '#atx-pro-bar{height:auto!important;max-height:none!important;flex-wrap:wrap!important;overflow:visible!important;padding-top:6px!important;padding-bottom:max(6px,env(safe-area-inset-bottom,0px))!important}',
    '#atx-pro-bar .atx-chips,#atx-pro-bar .atx-actions{flex-wrap:wrap!important;overflow:visible!important;width:100%!important}',
    '#atx-pro-bar a.atx-chip,#atx-pro-bar button.atx-chip{min-height:44px!important;height:auto!important;padding:8px 12px!important}',
    '#atx-pro-bar .atx-kbd{display:none!important}',
    '.tb-companion-bar,#tbSharedServerBar{max-height:none!important;height:auto!important;flex-wrap:wrap!important;overflow:visible!important;row-gap:6px!important}',
    '.tb-bar-back{min-height:44px!important;display:inline-flex!important;align-items:center!important;padding:10px 12px!important}',
    '.fafo-chrome-btn{min-width:44px!important;min-height:44px!important;width:auto!important;height:auto!important;padding:8px 10px!important}',
    '.fafo-layout-float-dock{left:max(8px,env(safe-area-inset-left,0px))!important;right:max(8px,env(safe-area-inset-right,0px))!important;max-width:none!important;max-height:none!important;overflow:visible!important}',
    '.fafo-layout-float-host{resize:none!important;overflow:visible!important;max-height:none!important;max-width:100%!important;width:100%!important;min-height:0!important}',
    '.fafo-layout-dock-toggle{min-height:44px!important}',
    'body:not(.run-active) .fafo-layout-panel,body:not(.run-active) .fafo-layout-panel[data-fafo-flex="1"],body:not(.run-active) .fafo-layout-panel[data-fafo-sized="1"]{flex:0 0 auto!important;width:100%!important;max-width:100%!important;height:auto!important;max-height:none!important;min-height:0!important;overflow:visible!important}',
    'body:not(.run-active) .fafo-panel-body,body:not(.run-active) .fafo-scroll-pane,body:not(.run-active) .fafo-section-body,body:not(.run-active) .fafo-body-split > [data-fafo-section],body:not(.run-active) .fafo-body-split > [data-fafo-section].fafo-section-flex,body:not(.run-active) .fafo-body-split > [data-fafo-section] > .fafo-section-body{flex:0 0 auto!important;height:auto!important;max-height:none!important;min-height:0!important;overflow:visible!important}',
    '[data-fafo-section].fafo-section-collapsed > .fafo-section-body{display:none!important;overflow:hidden!important}',
    '.fafo-split-handle,.fafo-corner-resize,.fafo-section-resize{display:none!important}',
    '}',
    /* S7-W0b un-clip (look unchanged whenever the content already fits):
       - pro bar above 720px: stays one 48px row while brand + actions fit; counterpart chips take only leftover width
         (basis 0, they keep their own scroll; capped at the 39px content row of the 48px bar so their scrollbar cannot grow the bar); actions size to their content (prefs' phone-layout width:100% made them claim
         a whole row even though chrome-fix keeps the bar a row above 720px). When brand + actions cannot fit, actions wrap to a second row instead of
         running off-screen (SC-2); --atx-pro-h follows the real height so body padding / scroll-padding reserve it.
       - shared server bar: wraps instead of clipping at 42px (SC-4); the hint gets a min width so it wraps to its own
         line rather than collapsing into a one-word column; the actions group (incl. #fafoSkillCtl) wraps at every width
         so the skill control fits on a phone (SC-5). */
    '@media (min-width:721px){',
    '#atx-pro-bar{flex-wrap:wrap!important;height:auto!important;min-height:48px!important;max-height:none!important}',
    '#atx-pro-bar .atx-chips{flex:1 1 0%!important;max-height:39px!important}',
    '#atx-pro-bar .atx-actions{flex-wrap:wrap!important;width:auto!important}',
    '.tb-companion-bar,#tbSharedServerBar{flex-wrap:wrap!important;max-height:none!important}',
    '}',
    '#tbSharedServerBar .tb-bar-hint,.tb-companion-bar .tb-bar-hint{min-width:min(100%,200px)!important}',
    '#tbSharedServerBar .tb-bar-actions,.tb-companion-bar .tb-bar-actions{flex-wrap:wrap!important;min-width:0!important;max-width:100%!important}',
    '#fafoSkillCtl{flex-wrap:wrap!important;max-width:100%!important;min-width:0!important}',
    /* Short sections show in full. Tall ones that have no parent scroller scroll once at 70vh. */
    '.fafo-fit-content{max-height:none!important;height:auto!important;flex:0 0 auto!important;min-height:0!important;min-width:0!important;overflow:auto!important;overflow-wrap:break-word}',
    'pre.fafo-fit-content,.fafo-fit-content pre{white-space:pre-wrap!important;overflow-wrap:anywhere!important}',
    '.fafo-scroll-cap{max-height:min(70dvh,720px)!important;height:auto!important;flex:0 0 auto!important;overflow:auto!important}',
    '[data-fafo-section].fafo-section-collapsed>.fafo-section-body{display:none!important;overflow:hidden!important;height:0!important;max-height:0!important}'
  ].join('\n');

  function injectCss() {
    if (document.getElementById('fafo-chrome-fix-css')) return;
    var s = document.createElement('style');
    s.id = 'fafo-chrome-fix-css';
    s.textContent = CSS;
    (document.head || document.documentElement).appendChild(s);
  }

  function cap(name, px) {
    try { document.documentElement.style.setProperty(name, px + 'px'); } catch (_) {}
  }

  function measure() {
    var pro = document.getElementById('atx-pro-bar');
    var bottom = 0;
    if (pro && pro.style.display !== 'none' && !document.body.classList.contains('atx-pro-min')) {
      try {
        var h = Math.ceil(pro.getBoundingClientRect().height) || 0;
        var capPx = 160; // S7-W0b: a wrapped (2-row) bar must be fully reserved; was 48 when the bar was forced to 48px
        try { if (window.matchMedia('(max-width: 720px)').matches) capPx = 320; } catch (_) {}
        bottom = Math.min(capPx, Math.max(0, h));
      } catch (_) { bottom = 44; }
    } else if (document.body.classList.contains('atx-pro-min')) {
      bottom = 8;
    }
    cap('--atx-pro-h', bottom);
    cap('--fafo-chrome-bottom', bottom);
  }

  /**
   * Section scroll fit.
   * If a section's content is small enough to show fully (about 70% of the
   * viewport), drop its scroll cage so it grows. A tall block with no parent
   * scroller keeps one scrollbar at 70vh. Opt out with data-fafo-keep-scroll="1".
   * Collapsed sections stay collapsed. User-dragged sizes (data-fafo-user-sized)
   * are left alone.
   */
  var FIT_SKIP = '[data-fafo-keep-scroll], dialog, [role="dialog"], [role="menu"], [role="listbox"], .ui-modal, .modal, .modal-bg, .atx-pick-list, #autocomplete-menu, .command-palette, .command-palette-list, .dbg-panel, #atx-pro-bar, .tb-companion-bar, #tbSharedServerBar, .menu-pop, .tag-suggestions, .fafo-layout-float-dock, .fafo-layout-float-host, textarea, select, canvas, svg, .fafo-section-collapsed';
  var FIT_NODES = 'div, section, aside, ul, ol, pre, main, article, nav, form, fieldset, li, details';
  var fitTimer = 0;
  var fitObs = null;

  function fitCapPx() {
    var vh = window.innerHeight || 800;
    return Math.max(480, Math.round(vh * 0.7));
  }

  function hasLargeScrollParent(el) {
    var p = el.parentElement;
    while (p && p !== document.body && p !== document.documentElement) {
      if (p.classList.contains('fafo-scroll-cap') || p.classList.contains('fafo-fit-content')) return true;
      if (p.classList.contains('fafo-panel-body') || p.classList.contains('fafo-viewport-pin')) {
        try {
          var cs = getComputedStyle(p);
          var oy = cs.overflowY;
          if ((oy === 'auto' || oy === 'scroll' || oy === 'hidden') && p.clientHeight >= 240) return true;
        } catch (e) { /* ignore */ }
      }
      p = p.parentElement;
    }
    return false;
  }

  function markSectionFit(el) {
    var sec = el.closest && el.closest('[data-fafo-section]');
    if (!sec || sec.getAttribute('data-fafo-user-sized') === '1') return;
    if (sec.getAttribute('data-fafo-collapsed') === '1' || sec.classList.contains('fafo-section-collapsed')) return;
    if (el === sec || el.classList.contains('fafo-section-body')) sec.classList.add('fafo-section-fit');
  }

  function tuneScrollBox(el) {
    if (!el || el.nodeType !== 1) return;
    if (el === document.body || el === document.documentElement) return;
    try { if (el.closest(FIT_SKIP)) return; } catch (e) { return; }
    var cs;
    try { cs = getComputedStyle(el); } catch (e2) { return; }
    if (cs.display === 'none' || cs.visibility === 'hidden') return;
    if (cs.position === 'fixed' || cs.position === 'absolute') return;
    var oy = cs.overflowY;
    if (oy !== 'auto' && oy !== 'scroll') {
      if (!el.classList.contains('fafo-fit-content') && !el.classList.contains('fafo-scroll-cap')) return;
      el.classList.remove('fafo-fit-content', 'fafo-scroll-cap');
      return;
    }
    if (el.getAttribute('data-fafo-user-sized') === '1') return;
    if (el.classList.contains('fafo-section-body')) {
      var parentSec = el.parentElement;
      if (parentSec && parentSec.getAttribute('data-fafo-user-sized') === '1') return;
    }
    var natural = el.scrollHeight;
    var visible = el.clientHeight;
    if (visible <= 0 || natural <= 0) return;
    // A column / pinned panel body that already has room is the one scroller.
    if (el.classList.contains('fafo-panel-body') && visible >= 240) {
      el.classList.remove('fafo-fit-content', 'fafo-scroll-cap');
      return;
    }
    var capPx = fitCapPx();
    var inPort = hasLargeScrollParent(el);
    if (el.classList.contains('fafo-fit-content') && (natural <= capPx + 8 || inPort)) return;
    if (el.classList.contains('fafo-scroll-cap') && natural > capPx) return;
    if (natural <= visible + 4) return;
    var maxPx = cs.maxHeight === 'none' ? 0 : (parseFloat(cs.maxHeight) || 0);
    if (natural <= capPx || inPort) {
      el.classList.add('fafo-fit-content');
      el.classList.remove('fafo-scroll-cap');
      markSectionFit(el);
      return;
    }
    var smallCage = (maxPx > 0 && maxPx < Math.min(capPx - 8, 480)) || visible < 240;
    if (smallCage && !inPort) {
      el.classList.add('fafo-scroll-cap');
      el.classList.remove('fafo-fit-content');
    }
  }

  function refreshFit(root) {
    var scope = root && root.querySelectorAll ? root : document;
    var nodes;
    try { nodes = scope.querySelectorAll(FIT_NODES); }
    catch (e) { return; }
    var list = [];
    for (var i = 0; i < nodes.length; i++) list.push(nodes[i]);
    if (scope.nodeType === 1) list.push(scope);
    list.sort(function (a, b) {
      var da = 0;
      var db = 0;
      var n = a;
      while (n) { da++; n = n.parentElement; }
      n = b;
      while (n) { db++; n = n.parentElement; }
      return db - da;
    });
    for (var j = 0; j < list.length; j++) tuneScrollBox(list[j]);
  }

  function scheduleFit(root) {
    if (fitTimer) clearTimeout(fitTimer);
    var target = root || document;
    fitTimer = setTimeout(function () {
      fitTimer = 0;
      try {
        if (fitObs) fitObs.disconnect();
        refreshFit(target);
      } catch (e) { /* ignore */ }
      try {
        if (fitObs && document.documentElement) {
          fitObs.observe(document.documentElement, { childList: true, subtree: true });
        }
      } catch (e2) { /* ignore */ }
    }, 200);
  }

  function foldAppId(el) {
    var host = el.closest ? el.closest('[data-fafo-layout-app],[data-fafo-app]') : null;
    var id = host ? (host.getAttribute('data-fafo-layout-app') || host.getAttribute('data-fafo-app')) : '';
    if (!id && document.documentElement) id = document.documentElement.getAttribute('data-fafo-app') || '';
    if (!id) {
      try {
        var p = String((location && location.pathname) || '');
        id = decodeURIComponent(p.split('/').pop() || '').replace(/\.html?$/i, '');
      } catch (e) { id = ''; }
    }
    return id || 'app';
  }

  function bindFolds(root) {
    if (global.FafoChrome && typeof global.FafoChrome.initFold === 'function') {
      try { global.FafoChrome.initFold(root || document); return; } catch (e) { /* own binder */ }
    }
    var scope = root && root.querySelectorAll ? root : document;
    var list;
    try { list = scope.querySelectorAll('details.fafo-fold:not(.fafo-collapse):not(.ui-advanced)'); }
    catch (e2) { return; }
    for (var i = 0; i < list.length; i++) {
      var el = list[i];
      if (el.getAttribute('data-fafo-fold-bound') === '1') continue;
      el.setAttribute('data-fafo-fold-bound', '1');
      if (!el.getAttribute('data-fafo-fold') && !el.id) el.setAttribute('data-fafo-fold', 'i' + i);
      var section = el.getAttribute('data-fafo-fold') || el.id;
      var key = 'fafo-fold:' + foldAppId(el) + ':' + section;
      var defOpen = !el.hasAttribute('data-collapsed-default');
      var saved = null;
      try { saved = localStorage.getItem(key); } catch (e3) { saved = null; }
      var open = saved === '1' ? true : (saved === '0' ? false : defOpen);
      if (open) el.setAttribute('open', '');
      else el.removeAttribute('open');
      var summary = el.querySelector('summary');
      if (summary) summary.setAttribute('aria-expanded', open ? 'true' : 'false');
      el.addEventListener('toggle', function onFoldToggle() {
        var s = this.querySelector('summary');
        if (s) s.setAttribute('aria-expanded', this.open ? 'true' : 'false');
        var sec = this.getAttribute('data-fafo-fold') || this.id;
        var k = 'fafo-fold:' + foldAppId(this) + ':' + sec;
        var def = !this.hasAttribute('data-collapsed-default');
        try {
          if (!!this.open === def) localStorage.removeItem(k);
          else localStorage.setItem(k, this.open ? '1' : '0');
        } catch (err) { /* quota */ }
        scheduleFit(this);
      });
    }
  }

  global.FafoFitSections = {
    refresh: refreshFit,
    schedule: scheduleFit,
    bindFolds: bindFolds
  };

  function boot() {
    injectCss();
    measure();
    bindFolds(document);
    refreshFit(document);
    scheduleFit(document);
    try {
      if (typeof ResizeObserver === 'function') {
        var pro = document.getElementById('atx-pro-bar');
        if (pro) new ResizeObserver(measure).observe(pro);
      }
    } catch (_) {}
    window.addEventListener('resize', measure);
    window.addEventListener('resize', function () { scheduleFit(document); });
    document.addEventListener('toggle', function (ev) { scheduleFit(ev.target); }, true);
    try {
      fitObs = new MutationObserver(function (records) {
        var scope = document;
        if (records && records.length === 1 && records[0].target && records[0].target.querySelectorAll) {
          scope = records[0].target;
        }
        scheduleFit(scope);
      });
      fitObs.observe(document.documentElement, { childList: true, subtree: true });
    } catch (e) { /* ignore */ }
    setTimeout(measure, 50);
    setTimeout(measure, 400);
    setTimeout(function () { refreshFit(document); }, 350);
    setTimeout(function () { refreshFit(document); }, 1200);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})(typeof window !== 'undefined' ? window : globalThis);
