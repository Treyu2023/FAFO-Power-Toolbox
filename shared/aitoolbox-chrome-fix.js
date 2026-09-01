/**
 * FAFO toolbox chrome clamp — loaded by aitoolbox-ui.js
 * Keeps the shared top S1/S2 bar and bottom LAYOUT/pro dock from
 * reserving a third of the viewport on every tool page.
 */
(function (global) {
  if (global.__fafoChromeFix) return;
  global.__fafoChromeFix = true;

  var CSS = [
    '#atx-pro-bar{flex-wrap:nowrap!important;max-height:44px!important;overflow-x:auto!important;overflow-y:hidden!important;padding:4px 10px!important}',
    '#atx-pro-bar .atx-chips,#atx-pro-bar .atx-actions{flex-wrap:nowrap!important}',
    'body.atx-pro-pad{padding-bottom:var(--atx-pro-h,44px)!important}',
    'body.atx-pro-min #atx-pro-bar{transform:translateY(calc(100% - 8px))!important}',
    'body.atx-pro-min.atx-pro-pad{padding-bottom:8px!important}',
    '.fafo-layout-float-dock{max-height:min(36vh,220px)!important;pointer-events:none}',
    '.tb-companion-bar,#tbSharedServerBar{flex-wrap:nowrap!important;max-height:42px!important;overflow-x:auto!important;overflow-y:hidden!important;padding:4px 10px!important}',
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
        bottom = Math.min(56, Math.max(0, h));
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
