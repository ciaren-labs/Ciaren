# Ciaren Brand Assets

Generated from the "Flow C" mark — a continuous ring of three nodes that reads
as the initial "C", tying directly into Ciaren's node-and-pipeline canvas.

## Files

### Symbol (icon alone, no text)
- `symbol.svg` — violet (#6D28D9), transparent background, scalable
- `symbol-white.svg` — white version, for dark backgrounds
- `symbol-black.svg` — single-color black, for 1-color/print contexts
- `symbol-512.png`, `symbol-white-512.png`, `symbol-black-512.png` — transparent PNG rasters

### App icon / favicons (symbol on a rounded violet tile)
- `app-icon.svg` — scalable source, rounded-square violet tile + white symbol
- `favicon.svg` — same mark, bolder stroke/node ratio tuned for legibility at tiny sizes
- `favicon-16.png`, `favicon-32.png`, `favicon-48.png` — raster favicons, each re-tuned for its size
- `favicon.ico` — legacy multi-size icon (16/32/48) for older browsers
- `apple-touch-icon-180.png` — iOS home-screen icon (180×180)
- `icon-192.png`, `icon-512.png` — PWA / Android manifest icons

Suggested `<head>` snippet:
```html
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="alternate icon" href="/favicon.ico">
<link rel="apple-touch-icon" href="/apple-touch-icon-180.png">
```

### Wordmark ("Ciaren" — the ring doubles as the C)
- `wordmark-light.svg` — for light backgrounds (dark "iaren", violet ring); scalable, assumes
  the page loads **Space Grotesk 700** (Google Fonts) — same font the marketing site already uses
- `wordmark-dark.svg` — all-white version, for dark backgrounds
- `wordmark-light-800.png` / `wordmark-light-1600.png` — flattened raster, white background,
  for anywhere a font-independent file is needed (README, social, docs, slides)
- `wordmark-dark-800.png` / `wordmark-dark-1600.png` — same, on dark background

## Notes
- Brand violet: `#6D28D9`. Near-black (text/dark bg): `#171717`.
- The two "nodes" at the ring's open ends are intentionally sized asymmetrically
  (smaller = input, larger = output) — this hierarchy holds even in the
  monochrome/1-color version since it's carried by size, not color.
- The wordmark SVGs reference Space Grotesk by name rather than embedding the font file
  (keeps file size small); make sure the page loading them also loads
  `Space Grotesk` (700) from Google Fonts, or substitute the flattened PNGs where that's
  not possible.
