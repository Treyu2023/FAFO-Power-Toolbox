/* FAFO Toolbox service worker — cache the phone shell only. No phone-home. */
/* eslint-disable no-restricted-globals */
'use strict';

var CACHE = 'fafo-shell-v1';
var SHELL = [
  './',
  './index.html',
  './manifest.webmanifest',
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

self.addEventListener('fetch', function (event) {
  var request = event.request;
  if (request.method !== 'GET') return;
  var url;
  try { url = new URL(request.url); } catch (e) { return; }
  if (url.origin !== self.location.origin) return;

  event.respondWith(
    caches.match(request).then(function (cached) {
      if (cached) return cached;
      return fetch(request);
    })
  );
});
