// Evopals service worker.
//
// CACHE_VERSION is rewritten by build_pwa.py with a hash of index.html, so
// every deploy produces a new cache name and the old one gets cleaned up.
// Without that, a cache-first worker would serve the stale game forever.
const CACHE_VERSION = 'acf88ebd2edd';
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

// How long to wait for the network before falling back to the cached game.
// Short enough that a weak signal doesn't stall the launch, long enough that
// a normal connection wins the race and serves the newest build. // TUNABLE
const NETWORK_TIMEOUT_MS = 2500;

// Is this a request for the game itself (as opposed to an icon or a font)?
// Those are the only things that change between deploys, so they're the only
// ones worth going to the network for.
function isAppShell(req, url){
  if(req.mode === 'navigate') return true;
  const path = url.pathname;
  return path.endsWith('/') || path.endsWith('/index.html');
}

self.addEventListener('fetch', event => {
  const req = event.request;
  if(req.method !== 'GET') return;

  const url = new URL(req.url);
  const isFont = url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com';
  if(url.origin !== self.location.origin && !isFont) return;

  if(isAppShell(req, url)){
    // Network-first for the game file: during active playtesting, seeing a
    // fresh deploy on the very next launch matters more than shaving a beat
    // off startup. If the network is slow or gone, the cached copy is served
    // instead, so offline play is unaffected.
    event.respondWith(networkFirst(req));
    return;
  }

  // Cache-first for everything else — icons, manifest and fonts don't change
  // between deploys, so there's nothing to gain by re-fetching them.
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
        if(req.mode === 'navigate') return caches.match('./index.html');
        return Response.error();
      });
    })
  );
});

async function networkFirst(req){
  const cached = await caches.match(req) || await caches.match('./index.html');

  let timer;
  const timeout = new Promise(resolve => { timer = setTimeout(() => resolve(null), NETWORK_TIMEOUT_MS); });

  try{
    // Whichever resolves first wins: a real response, or the timeout handing
    // back null so we can fall through to the cache.
    const res = await Promise.race([fetch(req), timeout]);
    clearTimeout(timer);
    if(res && res.ok){
      // Refresh the stored copy so the next offline launch gets this build.
      const copy = res.clone();
      caches.open(CACHE_NAME).then(cache => cache.put('./index.html', copy)).catch(() => {});
      return res;
    }
  }catch(e){
    clearTimeout(timer);
  }

  return cached || Response.error();
}
