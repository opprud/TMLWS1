# Slide decks

Lecture slides authored in **[Marp](https://marp.app/)** (Markdown → slides).
The `.md` files here are the source of truth; the rendered `.pptx` binaries are
**not** committed (they're rebuildable — see below).

| Deck | Topic | Day |
|---|---|---|
| `01-intro-tinyml-ml-basics.md` | Intro to TinyML & ML basics | 1 |
| `02-embedded-hardware-rak4631.md` | Embedded hardware & board bring-up | 1 |
| `03-data-acquisition.md` | Data acquisition | 1 |
| `04-fan-data-acquisition-lab.md` | Fan data-acquisition lab | 2 |
| `05-feature-engineering.md` | Feature engineering | 2 |
| `06-ml-frameworks-mcu.md` | ML frameworks for MCUs | 2 |
| `07-build-and-deploy-models.md` | Build & deploy models | 3 |
| `08-anomaly-detection.md` | Anomaly detection | 3 |
| `09-optimisation-quantisation-pruning.md` | Optimisation: quantisation & pruning | 3 |

- `themes/tinyml-clean.css` — the course Marp theme (referenced by every deck's
  front-matter `theme: tinyml-clean`).
- `assets/` — figures embedded in the decks.
- `inject_notes.py` — post-processor that copies speaker notes from the Marp
  markdown into the rendered PowerPoint presenter-notes (the editable exporter
  drops them).

## Rendering

Preview live while editing (from the repo root):

```bash
npx --yes @marp-team/marp-cli -s decks/
```

Render one deck to an **editable** PowerPoint (needs LibreOffice installed), then
re-inject speaker notes:

```bash
cd decks
npx --yes @marp-team/marp-cli 01-*.md --theme themes/tinyml-clean.css \
  --allow-local-files --pptx-editable -o rendered/01-intro-editable.pptx
python3 inject_notes.py 01-*.md rendered/01-intro-editable.pptx
```

Notes:
- `--allow-local-files` is **mandatory** — without it, images silently vanish.
- Use `--pptx-editable` (not plain `--pptx`, which rasterises the slides).
- Always run `inject_notes.py` **after** rendering — the editable exporter
  strips presenter notes.
- Quick raster preview: swap `--pptx-editable` for `--images png`.

## A note on excluded figures

A handful of lecture figures come from the **TinyML on edX (HarvardX)** course
(V.J. Reddi et al.), used with permission for *delivery of this course only*.
Those images are **not redistributed** in this public repo, so the corresponding
`![](assets/reddi/…)` links in some decks will not resolve here. The slides
still carry the attribution caption. To render the full decks, drop the licensed
figures into `decks/assets/reddi/` from your own licensed copy.

See [`../ATTRIBUTION.md`](../ATTRIBUTION.md) for full credits.
