#!/usr/bin/env python3
"""
Build the GitHub Pages / PWA bundle from the single-file prototype.

Reads  : ../evopals-prototype.html
Writes : dist/index.html, dist/sw.js, dist/manifest.webmanifest,
         dist/icon-192.png, dist/icon-512.png, dist/icon-maskable-512.png

Everything is referenced with RELATIVE paths ('./'), so the same build works
whether the repo is served from a user root (user.github.io) or a project
subdirectory (user.github.io/evopals/) without any rewriting.

The cache name embeds a hash of the built HTML, so every deploy that actually
changes the game invalidates the old cache automatically — no manual version
bumping, and no stale build pinned on someone's phone after an update.
"""
import base64, hashlib, io, os, re, subprocess, sys
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(HERE, '..', 'evopals-prototype.html')
DIST = os.path.join(HERE, 'dist')
OXI  = os.path.join(HERE, '..', 'node_modules', '.bin', 'oxipng')

APP_NAME  = 'Evopals'
SHORT     = 'Evopals'
THEME     = '#3B3F55'   # --topbar-bg, so the status bar matches the game's chrome
BG        = '#E7E9EF'   # --bg, so the splash screen matches the app background

os.makedirs(DIST, exist_ok=True)
html = open(SRC, encoding='utf-8').read()

# ---------------------------------------------------------------- icons
# Built from the starter's card art on the app background, so the home-screen
# icon matches what the player sees on first open.
def creature_art(species, role):
    i = html.find(species + ': { card:')
    m = re.search(role + r":\s*'data:image/png;base64,([A-Za-z0-9+/=]+)'", html[i:i + 900000])
    return Image.open(io.BytesIO(base64.b64decode(m.group(1)))).convert('RGBA')

def write_icon(path, size, art, pad):
    canvas = Image.new('RGBA', (size, size), BG)
    inner  = round(size * (1 - 2 * pad))
    sprite = art.resize((inner, inner), Image.LANCZOS)
    canvas.alpha_composite(sprite, (round((size - inner) / 2), round((size - inner) / 2)))
    # flat cartoon art on a flat background — a small palette is visually
    # lossless here and cuts the 512px icons by ~4x
    canvas.convert('RGB').quantize(colors=128, method=Image.FASTOCTREE,
                                   dither=Image.Dither.NONE).save(path, 'PNG', optimize=True)
    if os.path.exists(OXI):
        subprocess.run([OXI, '-o', '4', '--strip', 'safe', '-q', path], capture_output=True)

art = creature_art('cinderkit', 'card')
write_icon(os.path.join(DIST, 'icon-192.png'), 192, art, 0.06)
write_icon(os.path.join(DIST, 'icon-512.png'), 512, art, 0.06)
# maskable needs the art inside the safe zone or launchers will crop its edges
write_icon(os.path.join(DIST, 'icon-maskable-512.png'), 512, art, 0.18)

# ---------------------------------------------------------------- manifest
manifest = ('{\n'
  f'  "name": "{APP_NAME}",\n'
  f'  "short_name": "{SHORT}",\n'
  '  "start_url": "./",\n'
  '  "scope": "./",\n'
  '  "display": "standalone",\n'
  '  "orientation": "portrait",\n'
  f'  "background_color": "{BG}",\n'
  f'  "theme_color": "{THEME}",\n'
  '  "icons": [\n'
  '    { "src": "./icon-192.png", "sizes": "192x192", "type": "image/png" },\n'
  '    { "src": "./icon-512.png", "sizes": "512x512", "type": "image/png" },\n'
  '    { "src": "./icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }\n'
  '  ]\n'
  '}\n')
open(os.path.join(DIST, 'manifest.webmanifest'), 'w', encoding='utf-8').write(manifest)

# ---------------------------------------------------------------- index.html
head = f'''<link rel="manifest" href="./manifest.webmanifest">
<meta name="theme-color" content="{THEME}">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="{SHORT}">
<link rel="apple-touch-icon" href="./icon-192.png">
'''
anchor = '<link rel="preconnect" href="https://fonts.googleapis.com">'
if html.count(anchor) != 1:
    sys.exit('head anchor not found exactly once')
out = html.replace(anchor, head + anchor, 1)

sw_reg = '''
<script>
// Service worker registration. Deliberately deferred to 'load' so it never
// competes with first paint, and wrapped because a failed registration
// (file:// testing, unsupported browser) must not break the game.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('./sw.js').then(function (reg) {
      // If an update is waiting, take it on the NEXT launch rather than
      // swapping the page out from under someone mid-run.
      reg.addEventListener('updatefound', function () {
        var sw = reg.installing;
        if (sw) sw.addEventListener('statechange', function () {
          if (sw.state === 'installed' && navigator.serviceWorker.controller) {
            try { window.__evopalsUpdateReady = true; } catch (e) {}
          }
        });
      });
    }).catch(function () { /* offline support is optional; play on */ });
  });
}
</script>
'''
if out.count('</body>') != 1:
    sys.exit('body anchor not found exactly once')
out = out.replace('</body>', sw_reg + '</body>', 1)

index_path = os.path.join(DIST, 'index.html')
open(index_path, 'w', encoding='utf-8').write(out)

# ---------------------------------------------------------------- sw.js
digest = hashlib.sha256(out.encode('utf-8')).hexdigest()[:12]
assets = ['./', './index.html', './manifest.webmanifest',
          './icon-192.png', './icon-512.png', './icon-maskable-512.png']
sw = '''/* Evopals service worker — generated by build_pwa.py, do not edit by hand.
   Cache name is derived from a hash of the built HTML, so publishing a changed
   build automatically retires the previous cache. */
const CACHE = 'evopals-%s';
const ASSETS = %s;

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  // Only ever serve our own origin from cache. Analytics and fonts must go to
  // the network untouched, or a cached failure would persist across launches.
  if (url.origin !== self.location.origin) return;

  // Navigations: cache-first so the game opens instantly and works offline,
  // with a network fallback for the very first visit.
  if (req.mode === 'navigate') {
    e.respondWith(
      caches.match('./index.html').then(hit => hit || fetch(req).catch(() => caches.match('./')))
    );
    return;
  }

  e.respondWith(
    caches.match(req).then(hit => hit || fetch(req).then(res => {
      if (res && res.status === 200 && res.type === 'basic') {
        const copy = res.clone();
        caches.open(CACHE).then(c => c.put(req, copy));
      }
      return res;
    }).catch(() => hit))
  );
});
''' % (digest, str(assets).replace("'", '"'))
open(os.path.join(DIST, 'sw.js'), 'w', encoding='utf-8').write(sw)

print('cache version: evopals-%s' % digest)
for f in sorted(os.listdir(DIST)):
    print('  %-26s %8.1f KB' % (f, os.path.getsize(os.path.join(DIST, f)) / 1024))
