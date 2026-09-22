/**
 * shared/fafo-pwa.js — register the local shell service worker when served
 * over HTTP(S). Skips file:// so desktop open-from-disk stays unchanged.
 * No analytics, no remote hosts.
 */
(function (global) {
  'use strict';

  if (!global.navigator || !('serviceWorker' in global.navigator)) return;

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

  global.navigator.serviceWorker.register(swUrl, { scope: './' }).catch(function () {
    /* optional layer — ignore unsupported / blocked SW */
  });
})(typeof window !== 'undefined' ? window : this);
