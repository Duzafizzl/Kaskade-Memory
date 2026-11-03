---
title: README.md
description: Visual assets for the public Kaskade Memory README (hero, live UI, Prism 2D stills and one GIF).
created: 2026-10-21
updated: 2026-11-03
---

# README assets

Tracked images used by the repository root `README.md`. Demo seed, original art, and mermaid-prism 2D stills only.

| File | What |
|------|------|
| `kaskade-memory-hero.webp` | Wordless editorial hero. Dark rings and a cascade. Not a screenshot. |
| `time-circle-board.webp` | Live Time Circle month ring at `/time-circle/` on the demo seed. |
| `time-circle-day-open.webp` | Same UI with a day and the `demo_notes` theme panel open. |
| `gnostic-shadow.webp` | Live Spark and Bridge Rise page at `/gnostic-shadow/`. |
| `prism-cascade-2d.webp` | Write, cascade, and read. |
| `prism-lifetimes-2d.webp` | Doctrine, reference, and working memory. |
| `prism-spark-rise-2d.webp` | Spark rank path and Bridge Rise Door-B, last flow step. |
| `prism-spark-rise-2d.gif` | Same graph playing through. About 150 KB. |

Mermaid sources for the Prism stills are in [`prism/`](prism/). Re-render locally with `MERMAID_PRISM=/path/to/mermaid-prism node scripts/capture_prism_readme.mjs`. Renderer: [mermaid-prism](https://github.com/Duzafizzl/mermaid-prism).

The README uses the GIF for Spark/Rise so the Door-B yes/no edges finish. The webp is the last-step still.
