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
    '[data-fafo-section][data-fafo-resizable="1"]{min-height:36px!important}'
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
        bottom = Math.min(48, Math.max(0, h));
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
