/**
 * shared/fafo-chrome.js — optional helper for FAFO shared chrome kit
 * Cite: UI-M / MOBILE KIT (PET-UI-M). Shared kit ONLY — no per-app HTML.
 *
 * CSS (fafo-chrome.css) alone is enough for look. This script adds:
 *   - collapse open/closed persistence (localStorage)
 *   - optional sheen class ensure (no-op if markup already correct)
 *   - typewell-first class ensure for [data-fafo-primary]
 *   - pointer / narrow hints on <html> for host CSS (data-fafo-pointer, data-fafo-narrow)
 *
 * Opt-in:
 *   <script src="shared/fafo-chrome.js"></script>
 *   Or call window.FafoChrome.init(root?) after dynamic markup insert.
 *
 * Collapse targets (default CLOSED; Advanced stays closed unless persisted open):
 *   details.fafo-collapse
 *   details.ui-advanced
 *
 * Persistence key: fafo-collapse:<id|data-fafo-collapse-key|path>
 * Viewport meta: docs note only in CSS — this script does not mass-edit <head>.
 * No CDN / no dependencies.
 */
(function (global) {
  'use strict';

  var STORAGE_PREFIX = 'fafo-collapse:';
  var SELECTOR = 'details.fafo-collapse, details.ui-advanced';

  /** UI-M / MOBILE KIT mirrors (CSS --fafo-bp-* / --fafo-touch-min) */
  var MOBILE = {
    bpStack: 900,
    bpNarrow: 640,
    touchMin: 44,
    kit: 'UI-M',
    pet: 'PET-UI-M'
  };

  function storageKey(el, index) {
    var custom = el.getAttribute('data-fafo-collapse-key');
    if (custom) return STORAGE_PREFIX + custom;
    if (el.id) return STORAGE_PREFIX + el.id;
    var summary = el.querySelector('summary');
    var label = summary ? String(summary.textContent || '').trim().slice(0, 80) : '';
    var advanced = el.classList.contains('ui-advanced') ? 'adv' : 'col';
    return STORAGE_PREFIX + advanced + ':' + (label || 'i' + index);
  }

  function readWantOpen(key) {
    try {
      return global.localStorage.getItem(key);
    } catch (e) {
      return null;
    }
  }

  function writeWantOpen(key, open) {
    try {
      if (open) global.localStorage.setItem(key, '1');
      else global.localStorage.removeItem(key);
    } catch (e) { /* ignore quota / private mode */ }
  }

  function bindCollapse(el, index) {
    if (el.getAttribute('data-fafo-collapse-bound') === '1') return;
    el.setAttribute('data-fafo-collapse-bound', '1');

    var key = storageKey(el, index);
    var saved = readWantOpen(key);

    // Advanced / chrome collapses default CLOSED.
    // Restore only when user previously opened (saved === '1').
    if (saved === '1') el.setAttribute('open', '');
    else el.removeAttribute('open');

    el.addEventListener('toggle', function () {
      writeWantOpen(key, !!el.open);
    });
  }

  function initCollapse(root) {
    var scope = root && root.querySelectorAll ? root : document;
    var list = scope.querySelectorAll(SELECTOR);
    for (var i = 0; i < list.length; i++) bindCollapse(list[i], i);
  }

  function initSheen(root) {
    // Optional: mark panels that opt in via data-fafo-sheen without requiring a class in HTML builders.
    var scope = root && root.querySelectorAll ? root : document;
    var list = scope.querySelectorAll('[data-fafo-sheen]');
    for (var i = 0; i < list.length; i++) {
      list[i].classList.add('fafo-sheen');
    }
  }

  function initPrimary(root) {
    // Typewell-first helper: ensure class for [data-fafo-primary] opted nodes.
    // Does not touch Trainer #promptWrap logic.
    var scope = root && root.querySelectorAll ? root : document;
    var list = scope.querySelectorAll('[data-fafo-primary]');
    for (var i = 0; i < list.length; i++) {
      list[i].classList.add('fafo-primary-surface');
    }
  }

  function matchMq(query) {
    try {
      return !!(global.matchMedia && global.matchMedia(query).matches);
    } catch (e) {
      return false;
    }
  }

  function syncViewportHints() {
    var docEl = global.document && document.documentElement;
    if (!docEl) return;

    var coarse = matchMq('(pointer: coarse)');
    var narrow = matchMq('(max-width: ' + MOBILE.bpStack + 'px)');
    var tight = matchMq('(max-width: ' + MOBILE.bpNarrow + 'px)');

    docEl.setAttribute('data-fafo-pointer', coarse ? 'coarse' : 'fine');
    if (narrow) docEl.setAttribute('data-fafo-narrow', tight ? '640' : '900');
    else docEl.removeAttribute('data-fafo-narrow');

    // Coarse: mark split handles non-interactive (CSS also hides). Fine desktop keeps drag.
    if (global.document.querySelectorAll) {
      var handles = document.querySelectorAll('.fafo-split-handle');
      for (var i = 0; i < handles.length; i++) {
        if (coarse || narrow) {
          handles[i].setAttribute('data-fafo-split-disabled', '1');
          handles[i].setAttribute('aria-hidden', 'true');
        } else {
          handles[i].removeAttribute('data-fafo-split-disabled');
          handles[i].removeAttribute('aria-hidden');
        }
      }
    }
  }

  function initViewport() {
    syncViewportHints();
    if (initViewport._bound) return;
    initViewport._bound = true;
    if (!global.matchMedia) return;
    try {
      var qStack = global.matchMedia('(max-width: ' + MOBILE.bpStack + 'px)');
      var qNarrow = global.matchMedia('(max-width: ' + MOBILE.bpNarrow + 'px)');
      var qPointer = global.matchMedia('(pointer: coarse)');
      var onChange = function () { syncViewportHints(); };
      if (qStack.addEventListener) {
        qStack.addEventListener('change', onChange);
        qNarrow.addEventListener('change', onChange);
        qPointer.addEventListener('change', onChange);
      } else if (qStack.addListener) {
        qStack.addListener(onChange);
        qNarrow.addListener(onChange);
        qPointer.addListener(onChange);
      }
    } catch (e) { /* older hosts */ }
    if (global.addEventListener) {
      global.addEventListener('resize', syncViewportHints, { passive: true });
      global.addEventListener('orientationchange', syncViewportHints, { passive: true });
    }
  }

  function init(root) {
    initCollapse(root);
    initSheen(root);
    initPrimary(root);
    initViewport();
    return api;
  }

  var api = {
    init: init,
    initCollapse: initCollapse,
    initSheen: initSheen,
    initPrimary: initPrimary,
    initViewport: initViewport,
    syncViewportHints: syncViewportHints,
    STORAGE_PREFIX: STORAGE_PREFIX,
    MOBILE: MOBILE
  };

  global.FafoChrome = api;

  function boot() {
    init(document);
  }

  if (global.document) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', boot);
    } else {
      boot();
    }
  }
})(typeof window !== 'undefined' ? window : globalThis);
