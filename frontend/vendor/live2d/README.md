# 看板娘 Live2D vendor tree

Same-origin static assets for the site-wide 看板娘 overlay (Cubism 2 blog widget).
Webpack copies this directory to `frontend/dist/live2d/` (URL prefix `/static/live2d/`).

## Layout

- `runtime/live2d.min.js` — Cubism 2 runtime
- `runtime/live2dcubismcore.min.js` — Cubism 3/4 runtime
- `widget/waifu.css`, `widget/waifu-tips.js`, `widget/waifu-tips.json`
- `widget/chunk/` — Cubism 2 and Cubism 3/4 widget loaders
- `widget/autoload.js` — patched to `/static/live2d/` (no CDN at runtime)
- `models/<id>/` — live2d-widget-model-* demo packs
- `catalog.json` — Stream C fetches this; `entry` is relative to `/static/live2d/`

## Licenses

- Widget JS/CSS: GPL-3.0 (`widget/LICENSE`)
- Demo models: GPL-2.0 (`models/<id>/LICENSE`)
- Cubism 2 runtime: Live2D Inc. proprietary (`runtime/LICENSE.txt`)

Demo faces, not club-owned 看板娘 IP. Replacing models is a directory swap.
