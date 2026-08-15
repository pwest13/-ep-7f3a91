// Evopals service worker.
//
// CACHE_VERSION is rewritten by build_pwa.py with a hash of index.html, so
// every deploy produces a new cache name and the old one gets cleaned up.
// Without that, a cache-first worker would serve the stale game forever.
const CACHE_VERSION = '447a4bcb8ddd';
const CACHE_NAME = `evopals-${CACHE_VERSION}`;

// Everything the game needs to run with no network at all. The game itself is
// a single self-contained file with all art embedded, so this list is short.
const PRECACHE = [
  './',
  './index.html',
  './manifest.json',
  './icon-192.png',
  './icon-512.png',
  './icon-maskable-512.png',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      // addAll is all-or-nothing; a single 404 would abort the whole install,
      // so each entry is added individually and failures are tolerated.
      .then(cache => Promise.all(PRECACHE.map(url => cache.add(url).catch(() => {}))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(names => Promise.all(names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const req = event.request;
  if(req.method !== 'GET') return;

  const url = new URL(req.url);
  const isFont = url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com';
  if(url.origin !== self.location.origin && !isFont) return;

  // Cache-first: this is a game, not a news site — instant offline launches
  // matter more than picking up a redeploy the moment it lands. A new deploy
  // changes CACHE_VERSION, so the next launch installs the new worker and the
  // one after that runs the new build.
  event.respondWith(
    caches.match(req).then(hit => {
      if(hit) return hit;
      return fetch(req).then(res => {
        // Opaque cross-origin font responses are still worth storing so the
        // typography survives going offline.
        if(res && (res.ok || res.type === 'opaque')){
          const copy = res.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(req, copy)).catch(() => {});
        }
        return res;
      }).catch(() => {
        // Offline and uncached: fall back to the app shell for navigations so
        // a cold launch still opens the game rather than a browser error page.
        if(req.mode === 'navigate') return caches.match('./index.html');
        return Response.error();
      });
    })
  );
});
