#!/usr/bin/env python3
"""Assemble the app: dist/pwa (installable, offline) and dist/wolff-dictionary.html (preview page)."""
import base64, gzip, json, os, hashlib, sys
from PIL import Image, ImageDraw, ImageFont

src = os.path.dirname(os.path.abspath(__file__))
dist = os.path.join(src, 'dist'); pwa = os.path.join(dist, 'pwa')
os.makedirs(pwa, exist_ok=True)

raw = open(os.path.join(src, 'db.json'), 'rb').read()
b64 = base64.b64encode(gzip.compress(raw, 9, mtime=0)).decode()
app = open(os.path.join(src, 'app.html'), encoding='utf-8').read().replace('@@DATA@@', b64)
ver = hashlib.sha1(app.encode()).hexdigest()[:10]

# preview page (artifact skeleton adds doctype/head)
open(os.path.join(dist, 'wolff-dictionary.html'), 'w', encoding='utf-8').write(app)

head = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0c6a6e">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Wolff">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="icon-192.png">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<style>:root{{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}}body{{margin:0}}[hidden]{{display:none!important}}</style>
</head>
<body>
'''
tail = f'''
<script>
if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost')) navigator.serviceWorker.register('sw.js');
</script>
</body>
</html>
'''
open(os.path.join(pwa, 'index.html'), 'w', encoding='utf-8').write(head + app + tail)

json.dump({
    "name": "Wolff Cebuano Dictionary",
    "short_name": "Wolff",
    "description": "John U. Wolff, A Dictionary of Cebuano Visayan (1972), searchable offline.",
    "start_url": "./",
    "scope": "./",
    "display": "standalone",
    "background_color": "#f3f5f4",
    "theme_color": "#0c6a6e",
    "icons": [
        {"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
        {"src": "icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}
    ]
}, open(os.path.join(pwa, 'manifest.webmanifest'), 'w'), indent=2)

sw = f'''// Offline cache for the Wolff dictionary. Bump VERSION to ship an update.
const VERSION = 'wolff-{ver}';
const FILES = ['./', './index.html', './manifest.webmanifest', './icon-192.png', './icon-512.png',
  './icon-maskable-512.png', './apple-touch-icon.png'];
self.addEventListener('install', e => {{
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(FILES)).then(() => self.skipWaiting()));
}});
self.addEventListener('activate', e => {{
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
}});
self.addEventListener('fetch', e => {{
  if (e.request.method !== 'GET') return;
  e.respondWith(caches.match(e.request, {{ ignoreSearch: true }}).then(r => r ||
    fetch(e.request).catch(() => caches.match('./index.html'))));
}});
'''
open(os.path.join(pwa, 'sw.js'), 'w').write(sw)

# icons: a dictionary-page glyph, the letters "Wf" in serif on lagoon teal
def font(size):
    for p in ['/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf',
              '/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf']:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def icon(size, pad, path):
    im = Image.new('RGB', (size, size), (12, 106, 110))
    d = ImageDraw.Draw(im)
    inner = size - 2 * pad
    f = font(int(inner * 0.5))
    txt = 'Wf'
    bb = d.textbbox((0, 0), txt, font=f)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    x = (size - w) / 2 - bb[0]; y = (size - h) / 2 - bb[1] - inner * 0.04
    d.text((x, y), txt, font=f, fill=(243, 245, 244))
    # rule under the letters, like a headword line
    ly = (size + h) / 2 + inner * 0.06
    d.rectangle([size * 0.5 - inner * 0.28, ly, size * 0.5 + inner * 0.28, ly + max(2, inner * 0.03)], fill=(253, 233, 166))
    im.save(path)

icon(192, 14, os.path.join(pwa, 'icon-192.png'))
icon(512, 36, os.path.join(pwa, 'icon-512.png'))
icon(512, 96, os.path.join(pwa, 'icon-maskable-512.png'))
icon(180, 14, os.path.join(pwa, 'apple-touch-icon.png'))
print('version', ver, 'index.html', os.path.getsize(os.path.join(pwa, 'index.html')))
