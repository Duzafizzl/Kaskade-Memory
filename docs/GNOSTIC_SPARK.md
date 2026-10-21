---
title: GNOSTIC_SPARK.md
description: How Gnostic Spark picks a rare, privacy-aware spontaneous recall line from the memory graph.
created: 2026-10-20
updated: 2026-10-20
---

# Gnostic Spark

Spark is a *rare* spontaneous recall: at most one short line, behind a cooldown, chosen
because several independent cues point at the same memory, and never for sensitive memories.

## Pipeline

```
seeds -> flashback_pool.build_pool -> spark_rank.rank_candidates -> shadow.maybe_generate_spark -> SparkDelivery
                                         |                                  |
                               kuramoto R + bayesian P_rel        audit row -> spark_day (EOD)
```

| Stage | Module | What it does |
|-------|--------|--------------|
| Pool | `kaskade/gnostic/flashback_pool.py` | Cascade-first buckets (theme, day, day+theme, tag, graph neighbours) |
| Coherence | `kaskade/gnostic/kuramoto.py` | Order parameter R: do the cues phase-align on one memory? |
| Relevance | `kaskade/gnostic/bayesian_rank.py` | Weighted logit P(relevant) from cue/convergence features |
| Combine | `kaskade/gnostic/spark_rank.py` | `p_rel * (1 + alpha*R) * privacy_factor(P) * repeat_penalty` |
| Explain | `kaskade/gnostic/attribution.py` | Cards: which cue types made this spark |
| Deliver | `kaskade/gnostic/delivery.py` | `log` / `next_turn` / `webhook` |
| EOD | `kaskade/gnostic/cascade_day_summary.py` | `spark_day` signal layer |

## Privacy

ERIP **P** (1..5) scales every spontaneous score (`kaskade/gnostic/types.py::privacy_factor`).
P=5 memories are never surfaced spontaneously; they remain searchable explicitly.

## Implementation (2026-10-20)

Ranking is deterministic and local: no LLM, no network. A candidate needs **at least
two cue types** to rank. Cue type `high_engagement` is reserved for a session-intensity
flag the pool does not emit yet. Place memories (`place` tag or `place-` theme prefix)
enter the pool only when `allow_place=True`.

### Bayesian weights

`P_rel = sigmoid(bias + w·x [+ coherence bonus])`.

| Feature | Weight |
|---------|--------|
| `cue_types_n` | 0.4 |
| `kuramoto_r` | 0.5 |
| `convergence_hits` | 0.3 |
| `theme_overlap` | 0.2 |
| `repeat_penalty` (as `1 - freshness`) | -0.6 |
| `high_engagement` | 0.15 |

Bias `-0.6`. Coherence bonus `+0.25` when `cue_types_n >= 2` and `R >= 0.55`.

| Env | Default | Role |
|-----|---------|------|
| `KASKADE_SPARK_ENABLED` | `1` | Master switch for `maybe_generate_spark` |
| `KASKADE_SPARK_KURAMOTO_ALPHA` | `0.35` | Coherence boost; clamped to `[0, 2]` |
| `KASKADE_SPARK_DELIVERY` | `log` | `log` / `next_turn` / `webhook` |
| `KASKADE_SPARK_WEBHOOK_URL` | unset | HTTPS only (localhost HTTP allowed) |

`spark_day` in the EOD registry is the real rollup (`cascade_day_summary.spark_day_summary`):
counts only, never spark text. Cards from `attribution.build_card` omit content and cue keys.
