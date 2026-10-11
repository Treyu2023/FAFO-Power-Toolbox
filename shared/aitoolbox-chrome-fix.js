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
    '.fafo-layout-float-dock{left:10px!important;bottom:calc(var(--atx-pro-h,48px) + 10px)!important;max-height:min(42vh,280px)!important;pointer-events:none}',
    'body.tb-has-companion-bar .fafo-layout-float-dock,body.atx-pro-pad .fafo-layout-float-dock{bottom:calc(var(--atx-pro-h,48px) + 10px)!important}',
    'body.atx-pro-min .fafo-layout-float-dock{bottom:12px!important}',
    '.fafo-layout-float-host{resize:both!important;overflow:auto!important;min-width:160px!important;min-height:32px!important;max-width:min(72vw,760px)!important;max-height:min(42vh,280px)!important}',
    '.tb-companion-bar,#tbSharedServerBar{flex-wrap:nowrap!important;max-height:42px!important;overflow-x:auto!important;overflow-y:hidden!important;padding:4px 10px!important}',
    '.tb-companion-bar .tb-pill,.tb-companion-bar .tb-btn,.tb-companion-bar .tb-bar-back{flex:0 0 auto!important}',
    '.fafo-layout-rows > .fafo-layout-panel[data-fafo-flex="1"],',
    '.fafo-layout-panel[data-fafo-flex="1"]{flex:1 1 auto!important;min-height:0!important}',
    '.fafo-body-split > [data-fafo-section].fafo-section-flex{flex:1 1 auto!important;min-height:0!important}',
    '[data-fafo-section][data-fafo-resizable="1"]{min-height:36px!important}',
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
    '#tbSharedServerBar .tb-bar-hint,.tb-companion-bar .tb-bar-hint{min-width:min(100%,120px)!important}',
    '#tbSharedServerBar .tb-bar-actions,.tb-companion-bar .tb-bar-actions{flex-wrap:wrap!important;min-width:0!important;max-width:100%!important}',
    '#fafoSkillCtl{flex-wrap:wrap!important;max-width:100%!important;min-width:0!important}',
    /* S7-W0b-2: phone pro bar puts the app name on the counterpart row (no separate brand row). Chips flow in the bar,
       so the bar takes the chips' 6px gap; the action rows keep their 8px distance (6 + 2). */
    '@media (max-width:720px){',
    '#atx-pro-bar{gap:6px!important}',
    '#atx-pro-bar > .atx-chips{display:contents!important}',
    '#atx-pro-bar > .atx-actions{margin-top:2px!important}',
    '}'
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

  function boot() {
    injectCss();
    measure();
    try {
      if (typeof ResizeObserver === 'function') {
        var pro = document.getElementById('atx-pro-bar');
        if (pro) new ResizeObserver(measure).observe(pro);
      }
    } catch (_) {}
    window.addEventListener('resize', measure);
    setTimeout(measure, 50);
    setTimeout(measure, 400);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})(typeof window !== 'undefined' ? window : globalThis);
