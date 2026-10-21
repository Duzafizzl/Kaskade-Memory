---
title: BRIDGE_RISE.md
description: How Bridge Rise surfaces older episodes when several independent signals agree on the current topic.
created: 2026-10-20
updated: 2026-10-20
---

# Bridge Rise

Bridge Rise answers: *"we are talking about X right now; is there an older episode worth bringing back?"*
It only fires when **at least two independent sharp signals** agree on the same theme (Door-B).

## Signals

| Signal | Module | Sharp? |
|--------|--------|--------|
| `fragment` | `spreading/fragment_index.py` + `distinctiveness.py` (size-invariant IDF) | yes |
| `archival_tag` | `spreading/archival_tag_cues.py` | yes |
| `topic_weather` | `spreading/topic_weather.py` (recurring topics in recent events) | yes |
| `climate` | `climate_boost` argument | no, rank-only |

Any single signal, climate included, never fires on its own.

## Flow

```
turn text -> signals -> Door-B converge (>= 2 sharp on one theme) -> leaves (privacy-filtered)
          -> InjectGuard cooldown per agent|channel -> rise_render (1-2 lines, no ids)
```

## Implementation (2026-10-20)

`spread()` is deterministic. Topic weather counts enrichment events in a lookback
window (one count per topic per event). Climate is a rank multiplier only.

| Env | Default | Role |
|-----|---------|------|
| `KASKADE_SPREAD_MIN_IDF` | `0.35` | Tokens weaker than this never drive `fragment` |

Reason codes: `converged` | `single_signal` | `no_signal` | `no_eligible_leaves` | `cooldown` | `error`.
Inject lines come from `rise_render` (no UUIDs, no ERIP, no `mem-` ids). Cooldown is per `agent|channel`.
