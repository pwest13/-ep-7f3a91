# Evopals — PWA deploy

Installs to an Android home screen as a fullscreen, portrait, offline-capable app.

## Files

| File | Purpose |
| --- | --- |
| `index.html` | The game, built from the working file with PWA tags injected |
| `manifest.json` | App name, icon, portrait lock, standalone display |
| `sw.js` | Service worker — caches everything for offline play |
| `icon-192.png` / `icon-512.png` / `icon-maskable-512.png` | Home screen icons (Scorch) |
| `robots.txt` | Keeps the site out of search results |
| `build_pwa.py` | Regenerates `index.html` from the working file |

## First deploy

1. Create a repo — call it something non-obvious, e.g. `ep-7f3a91`. Private is fine: the repo stays hidden, the published site is public either way.
2. Upload every file in this folder to the repo root.
3. Settings → Pages → Source: `Deploy from a branch`, branch `main`, folder `/ (root)`.
4. Wait a minute, then open the URL it gives you (`https://<user>.github.io/ep-7f3a91/`).
5. On Android Chrome: menu → **Add to Home screen** / **Install app**.

The URL is unlisted, not private — anyone who has it can play. `robots.txt` and the `noindex` tag keep it out of search results.

## Shipping an update

```bash
python3 build_pwa.py /path/to/evopals-prototype.html
```

Then upload the new `index.html` **and** `sw.js` — the script stamps `sw.js` with a hash of the build, and that changed hash is what tells installed copies to refresh. Upload only `index.html` and phones will keep serving the old cached game forever.

Because the worker is cache-first, an update lands on the *second* launch after you deploy: the first launch fetches and installs it in the background, the next one runs it.

## Notes

- **Saves are per-device.** Storage is local to the browser, so your phone and your desktop keep separate profiles. Clearing Chrome's site data for the origin wipes the save — there's no cloud backup.
- **Fonts** load from Google's CDN on first run and are cached by the worker afterwards. Before that first online load, the game falls back to system fonts.
- **The source is readable.** Anyone with the URL can view-source and pull out the embedded creature art.
