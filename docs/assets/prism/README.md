---
title: README.md
description: Mermaid sources for the mermaid-prism 2D stills and Spark/Rise GIF in the root README.
created: 2026-11-03
updated: 2026-11-03
---

# Prism sources

Plain Mermaid for [mermaid-prism](https://github.com/Duzafizzl/mermaid-prism) 2D. Each subgraph is a group.

| File | Still |
|------|-------|
| `cascade.mmd` | `../prism-cascade-2d.webp` |
| `lifetimes.mmd` | `../prism-lifetimes-2d.webp` |
| `spark-rise.mmd` | `../prism-spark-rise-2d.webp` (last step) and `../prism-spark-rise-2d.gif` |

Rebuild:

```bash
MERMAID_PRISM=/path/to/mermaid-prism node scripts/capture_prism_readme.mjs
```
