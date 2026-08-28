---
title: ERIP.md
description: ERIP tagging for Kaskade Memory archival entries (P = Privacy).
created: 2026-08-28
updated: 2026-08-28
---

# ERIP Tagging

Four axes on a **1–5** scale, required in archival content:

| Axis | Meaning |
|------|---------|
| **E** | Emotional intensity |
| **R** | Relational density |
| **I** | Identity relevance |
| **P** | **Privacy** — sensitivity of the content (high = stricter recall/inject) |

## Format

```
E:3
R:4
I:4
P:2
```

Inline fallback: `ERIP: E:3 R:4 I:4 P:2`

## Behavior

- Parsed at archival insert → tags `E:3`, `R:4`, …
- Significance gate: high **P** without `theme_id` → `defer_eod`
- Gnostic Spark: higher **P** lowers spontaneous inject rank
