---
title: ERIP.md
description: ERIP tagging for Kaskade Memory archival entries (P = Privacy).
created: 2026-08-28
updated: 2026-10-26
---

# ERIP tagging

Four axes on a scale from 1 to 5, required in archival content:

| Axis | Meaning |
|------|---------|
| **E** | Emotional intensity |
| **R** | Relational density |
| **I** | Identity relevance |
| **P** | Privacy. Higher P means stricter recall and inject. |

## Format

```
E:3
R:4
I:4
P:2
```

Inline fallback: `ERIP: E:3 R:4 I:4 P:2`

## Behavior

- Parsed at archival insert as tags `E:3`, `R:4`, and so on.
- The significance gate defers a high P row without `theme_id` to end of day (`defer_eod`).
- Higher P lowers the spontaneous Spark rank.
