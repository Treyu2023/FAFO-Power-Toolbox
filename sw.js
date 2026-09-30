/* FAFO Toolbox service worker — cache the phone shell only. No phone-home. */
/* Shell = entry, manifest, icons, and this site's install helper.          */
/* Tool HTML/JS beyond that stays on the network.                           */
/* eslint-disable no-restricted-globals */
'use strict';

var CACHE = 'fafo-shell-v3';
var SHELL = [
  './',
  './index.html',
  './404.html',
  './Phone Launcher.html',
  './manifest.webmanifest',
  './shared/fafo-pwa.js',
  './shared/fafo-qr.js',
  './shared/pwa/icon-192.png',
  './shared/pwa/icon-512.png',
  './shared/pwa/icon-180.png',
  './shared/pwa/icon.svg'
];

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(CACHE).then(function (cache) {
      return cache.addAll(SHELL);
    }).then(function () {
      return self.skipWaiting();
    }).catch(function () {
      return self.skipWaiting();
    })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (key) {
        return key !== CACHE;
      }).map(function (key) {
        return caches.delete(key);
      }));
    }).then(function () {
      return self.clients.claim();
    })
  );
});

function sameOrigin(url) {
  return url.origin === self.location.origin;
}

self.addEventListener('fetch', function (event) {
  var request = event.request;
  if (request.method !== 'GET') return;
  var url;
  try { url = new URL(request.url); } catch (e) { return; }
  if (!sameOrigin(url)) return;

  event.respondWith(
    caches.match(request).then(function (cached) {
      if (cached) return cached;
      return fetch(request).catch(function () {
        if (request.mode === 'navigate') return caches.match('./index.html');
        return Promise.reject(new Error('offline'));
      });
    })
  );
});
