/**
 * shared/fafo-pwa.js — register the local shell service worker when served
 * over HTTP(S). Skips file:// so desktop open-from-disk stays unchanged.
 * Shows the browser install prompt (Add to Home screen / desktop install)
 * when Chrome fires beforeinstallprompt. No analytics, no remote hosts.
 */
(function (global) {
  'use strict';

  if (!global.navigator || !global.document) return;

  var DISMISS_KEY = 'fafo-a2hs-dismissed';
  var deferred = null;

  function standalone() {
    try {
      if (global.matchMedia && (
        global.matchMedia('(display-mode: standalone)').matches ||
        global.matchMedia('(display-mode: fullscreen)').matches
      )) return true;
    } catch (e) { /* ignore */ }
    return global.navigator.standalone === true;
  }

  function dismissed() {
    try { return global.localStorage.getItem(DISMISS_KEY) === '1'; }
    catch (e) { return false; }
  }

  function ensureStyles() {
    if (document.getElementById('fafo-a2hs-css')) return;
    var css = document.createElement('style');
    css.id = 'fafo-a2hs-css';
    css.textContent = [
      '#fafo-a2hs{position:fixed;z-index:100000;left:max(12px,env(safe-area-inset-left,0px));right:max(12px,env(safe-area-inset-right,0px));bottom:calc(var(--fafo-chrome-bottom,var(--atx-pro-h,0px)) + max(12px,env(safe-area-inset-bottom,0px)));display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:0 auto;max-width:520px;padding:10px 12px;border-radius:var(--fafo-radius,12px);background:var(--fafo-panel,var(--panel,var(--bg,#0a0e16)));color:var(--fafo-text,var(--text,#e8eef4));border:1px solid var(--fafo-border,var(--border,rgba(255,255,255,.24)));box-shadow:var(--fafo-shadow,0 8px 28px rgba(0,0,0,.45));font:600 15px/1.35 system-ui,sans-serif}',
      '#fafo-a2hs .fafo-a2hs-label{flex:1 1 160px;min-width:0}',
      '#fafo-a2hs button{appearance:none;min-height:44px;min-width:44px;padding:10px 14px;border-radius:10px;font:inherit;font-weight:700;cursor:pointer}',
      '#fafo-a2hs .fafo-a2hs-go{background:var(--fafo-accent,var(--accent,#00f3ff));color:var(--fafo-on-accent,#061018);border:1px solid var(--fafo-accent,var(--accent,#00f3ff))}',
      '#fafo-a2hs .fafo-a2hs-no{background:transparent;color:var(--fafo-text,var(--text,#e8eef4));border:1px solid var(--fafo-border,var(--border,rgba(255,255,255,.24)))}',
      'body.run-active #fafo-a2hs,body.tat-stage #fafo-a2hs{display:none!important}',
      '@media (display-mode:standalone),(display-mode:fullscreen){#fafo-a2hs{display:none!important}}'
    ].join('\n');
    (document.head || document.documentElement).appendChild(css);
  }

  function hideBar() {
    var el = document.getElementById('fafo-a2hs');
    if (el && el.parentNode) el.parentNode.removeChild(el);
  }

  function showBar() {
    if (standalone() || dismissed() || !deferred) return;
    if (document.getElementById('fafo-a2hs')) return;
    if (!document.body) return;
    ensureStyles();
    var bar = document.createElement('div');
    bar.id = 'fafo-a2hs';
    bar.setAttribute('role', 'region');
    bar.setAttribute('aria-label', 'Install FAFO Toolbox');
    var label = document.createElement('span');
    label.className = 'fafo-a2hs-label';
    label.textContent = 'Install FAFO Toolbox on this phone or desktop.';
    var go = document.createElement('button');
    go.type = 'button';
    go.className = 'fafo-a2hs-go';
    go.textContent = 'Install';
    var no = document.createElement('button');
    no.type = 'button';
    no.className = 'fafo-a2hs-no';
    no.textContent = 'Not now';
    bar.appendChild(label);
    bar.appendChild(go);
    bar.appendChild(no);
    document.body.appendChild(bar);
    go.addEventListener('click', function () {
      var promptEvent = deferred;
      deferred = null;
      hideBar();
      if (!promptEvent || !promptEvent.prompt) return;
      try { promptEvent.prompt(); } catch (e) { return; }
      if (promptEvent.userChoice && promptEvent.userChoice.then) {
        promptEvent.userChoice.then(function () { /* browser owns the dialog */ });
      }
    });
    no.addEventListener('click', function () {
      try { global.localStorage.setItem(DISMISS_KEY, '1'); } catch (e) { /* private mode */ }
      deferred = null;
      hideBar();
    });
  }

  global.addEventListener('beforeinstallprompt', function (event) {
    if (standalone() || dismissed()) return;
    event.preventDefault();
    deferred = event;
    showBar();
  });

  global.addEventListener('appinstalled', function () {
    deferred = null;
    hideBar();
  });

  if (!('serviceWorker' in global.navigator)) return;

  var loc = global.location;
  if (!loc || loc.protocol === 'file:') return;

  var host = String(loc.hostname || '');
  var isLoopback = host === 'localhost' || host === '127.0.0.1' || host === '::1';
  var isPrivateLan = /^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)/.test(host);
  var isHttps = loc.protocol === 'https:';
  if (!isHttps && !isLoopback && !isPrivateLan) return;

  var script = document.currentScript;
  var swUrl = 'sw.js';
  if (script && script.src) {
    try {
      swUrl = new URL('../sw.js', script.src).href;
    } catch (e) { /* keep relative sw.js */ }
  }

  function register() {
    global.navigator.serviceWorker.register(swUrl, { scope: './' }).catch(function () {
      /* optional layer — ignore unsupported / blocked SW */
    });
  }

  if (document.readyState === 'complete') register();
  else global.addEventListener('load', register);
})(typeof window !== 'undefined' ? window : this);
