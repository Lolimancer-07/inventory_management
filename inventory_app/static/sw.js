// Stockroom Service Worker — required for PWA installability
// Passes all requests straight to the network (no offline caching needed
// since this is a local-WiFi-only app with a live server).

const CACHE = 'stockroom-v1';

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));

self.addEventListener('fetch', event => {
  event.respondWith(fetch(event.request));
});
