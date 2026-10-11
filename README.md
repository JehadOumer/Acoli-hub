# ACoLi Lab Hub · GitHub Pages demo

Static demo of the Lab Hub tools homepage, **Sentence Reader**, and **Dictionary**.
All API responses are precomputed and baked under `docs/api/` so the site runs on GitHub Pages without a Python server.

## What’s included

- Hub: `docs/index.html`
- Sentence Reader: `docs/sentence_reader/` (spread sample, ≥50 sentences per source when available, varied sizes)
- Dictionary: `docs/dict_graph_reader/` (~64 language pairs, ~46k bilingual rows, 36 languages across freedict/apertium/dbnary/omw/muse; precomputed induced bridges for house/water/amour/love/…)
- Offline API shim: `docs/shared/static_api.js`

## License note

This demo redistributes **subsets** for non-commercial lab / teaching preview.
Some corpora are NC or scholarly-use; keep the site non-commercial and retain source attribution in the apps.
Do not treat this as a full public dump of gated resources.

## Rebuild from the Augsburg lab tree

```powershell
$py = "C:\Users\Pc\AppData\Local\Programs\Python\Python315\python.exe"
& $py scripts\build_static_demo.py
```

Requires the sibling Augsburg checkout with `_labhub/apps` indexes and source CoNLL / `acoli-dicts` files.

## Publish on GitHub Pages

1. Create a GitHub repo (e.g. `acoli-labhub-demo`).
2. Push this project.
3. Settings → Pages → Source: **Deploy from a branch** → branch `main` → folder **`/docs`**.
4. Open `https://<you>.github.io/acoli-labhub-demo/`.

## Local preview

```powershell
$py = "C:\Users\Pc\AppData\Local\Programs\Python\Python315\python.exe"
& $py -m http.server 8767 --directory docs
```

Then open http://127.0.0.1:8767/
