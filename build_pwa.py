#!/usr/bin/env python3
"""Turn the working Evopals file into a deployable PWA index.html.

    python3 build_pwa.py ../evopals-prototype.html

Writes index.html next to this script and stamps sw.js with a content hash so
each deploy busts the previous cache.

The PWA plumbing (manifest link, theme colour, noindex, service worker
registration) is injected here rather than living in the working file, so the
Claude artifact preview doesn't log 404s for manifest.json and sw.js — neither
of which exists in that environment.
"""
import hashlib
import pathlib
import sys

HERE = pathlib.Path(__file__).parent

HEAD_INJECT = """<link rel="manifest" href="./manifest.json" />
<meta name="theme-color" content="#3B3F55" />
<meta name="robots" content="noindex, nofollow" />
<meta name="mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
<link rel="apple-touch-icon" href="./icon-192.png" />
<link rel="icon" type="image/png" sizes="192x192" href="./icon-192.png" />
"""

SW_REGISTER = """<script>
  // Registered only over http/https — opening index.html straight off disk
  // (file://) has no service worker support and would throw.
  if('serviceWorker' in navigator && location.protocol.startsWith('http')){
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('./sw.js').catch(err => console.warn('SW registration failed', err));
    });
  }
</script>
"""


def main():
    if len(sys.argv) < 2:
        sys.exit('usage: build_pwa.py <path-to-evopals-html>')

    src = pathlib.Path(sys.argv[1])
    html = src.read_text(encoding='utf-8')

    if 'rel="manifest"' in html:
        sys.exit('error: source file already contains PWA tags — pass the working file, not a built index.html')

    if '</head>' not in html or '</body>' not in html:
        sys.exit('error: could not find </head> and </body> to inject into')

    html = html.replace('</head>', HEAD_INJECT + '</head>', 1)
    html = html.replace('</body>', SW_REGISTER + '</body>', 1)

    out = HERE / 'index.html'
    out.write_text(html, encoding='utf-8')

    # Stamp the worker with a hash of what it's caching.
    version = hashlib.sha256(html.encode('utf-8')).hexdigest()[:12]
    sw_src = HERE / 'sw.js'
    sw = sw_src.read_text(encoding='utf-8')
    marker = "const CACHE_VERSION = '"
    start = sw.index(marker) + len(marker)
    end = sw.index("'", start)
    sw_src.write_text(sw[:start] + version + sw[end:], encoding='utf-8')

    print(f'wrote {out} ({out.stat().st_size / 1_000_000:.2f} MB)')
    print(f'stamped sw.js cache version: {version}')


if __name__ == '__main__':
    main()
