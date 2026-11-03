---
title: README.md
description: Kaskade Memory. Hierarchical recall for coding agents. Root README and docs map.
created: 2026-08-28
updated: 2026-11-03
---

# Kaskade Memory

[![CI](https://github.com/Duzafizzl/Kaskade-Memory/actions/workflows/ci.yml/badge.svg)](https://github.com/Duzafizzl/Kaskade-Memory/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

![Kaskade Memory](docs/assets/kaskade-memory-hero.webp)

## About

Kaskade Memory stores coding-agent memory as a cascade. Days roll into weeks. Weeks roll into months. Themes and people link archival records across those levels.

Spark and Bridge Rise do not call an LLM. Spark emits at most one cooldown-gated line. Bridge Rise injects only when Door-B has at least two independent sharp signals. A memory with privacy score P = 5 never appears in a spontaneous Spark. Time Circle is the demo UI.

This repository is Kaskade Memory: the cascade store, the graph, Spark, Rise, and Time Circle. Your agent still owns core blocks, chat history, tasks, and approval. Map: [docs/README.md](docs/README.md).

## Docs

| Start here | Why |
|------------|-----|
| [docs/README.md](docs/README.md) | Map. This repo versus your agent. |
| [docs/MEMORY_LAYERS.md](docs/MEMORY_LAYERS.md) | Wire Kaskade. Lifetime layers. Propose-only reports and research buckets. |
| [docs/MEMORY_SYSTEM_BLUEPRINT.md](docs/MEMORY_SYSTEM_BLUEPRINT.md) | Full agent loop. History, tasks, approval, live feed. You build that. |
| [docs/GNOSTIC_SPARK.md](docs/GNOSTIC_SPARK.md) · [docs/BRIDGE_RISE.md](docs/BRIDGE_RISE.md) · [docs/ERIP.md](docs/ERIP.md) | How Spark, Rise, and P-scores work. |

## Time Circle

Demo UI. Scroll the ring through months, then days, then hours.

![Time Circle month ring](docs/assets/time-circle-board.webp)

![Time Circle with a day open](docs/assets/time-circle-day-open.webp)

![Gnostic Spark and Bridge Rise overview](docs/assets/gnostic-shadow.webp)

| URL | What |
|-----|------|
| http://localhost:8080/time-circle/ | Time Circle |
| http://localhost:8080/gnostic-shadow/ | Spark and Rise overview |
| http://localhost:8080/api/health | Health |
| http://localhost:8080/docs | OpenAPI |

## Quickstart

Docker and Docker Compose:

```bash
git clone https://github.com/Duzafizzl/Kaskade-Memory.git
cd Kaskade-Memory
cp example.env .env
docker compose up --build
```

The first boot seeds 14 days of demo archival data. Demo persons are `alex`, `sam`, and `agent`.

Without Docker: Postgres with pgvector, `DATABASE_URL` in `.env`, then

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python demo/seed.py
uvicorn api.main:app --reload --host 127.0.0.1 --port 8080
```

## Write and read

Write lands in the cascade. Days roll into weeks and months. Search, Spark, and Rise read from that store.

![Write, cascade, and read](docs/assets/prism-cascade-2d.webp)

Doctrine stays put. Reference loads on cue. Working memory overwrites.

![Doctrine, reference, and working memory](docs/assets/prism-lifetimes-2d.webp)

Spark needs two cue types, Kuramoto R, Bayesian P_rel, and P below 5. Rise needs two sharp Door-B signals. Climate only changes rank. P = 5 stays searchable and never sparks.

![Spark rank path and Bridge Rise Door-B](docs/assets/prism-spark-rise-2d.gif)

Stills and the Spark/Rise loop are [mermaid-prism](https://github.com/Duzafizzl/mermaid-prism) 2D. Stills are captured after the last flow step. Mermaid sources live in [docs/assets/prism/](docs/assets/prism/). How to wire that: [docs/MEMORY_LAYERS.md](docs/MEMORY_LAYERS.md).

## ERIP

Every archival insert should carry four scores from 1 to 5. **P** is privacy. P = 5 never sparks. See [docs/ERIP.md](docs/ERIP.md).

```
E:3   # Emotional intensity
R:4   # Relational density
I:4   # Identity relevance
P:2   # Privacy
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://kaskade:kaskade@localhost:5432/kaskade` | Postgres with pgvector |
| `KASKADE_EOD_AGENT_PROVIDER` | `noop` | `cursor`, `subprocess`, or `noop` |
| `KASKADE_EOD_AGENT_CMD` | unset | Shell. Placeholders `{prompt_path}` `{day_id}` |
| `CASCADE_SIGNIFICANCE_GATE_ENABLED` | `1` | Pre-enqueue archival filter |
| `HIGH_PRIVACY_THRESHOLD` | `4` | High P and no theme: defer to end of day |
| `KASKADE_SPARK_ENABLED` | `1` | Background Spark |

Gates: [`config/core_memory_gates.yaml`](config/core_memory_gates.yaml). Persons: [`config/demo_persons.yaml`](config/demo_persons.yaml).

## API

```
GET  /api/cascade/days
GET  /api/cascade/day/{day_id}
GET  /api/cascade/persons/aliases
POST /api/cascade/archival
POST /api/cascade/gnostic_traverse
POST /api/gnostic/spark/simulate
POST /api/cascade/spread/simulate
POST /api/cascade/eod/{day_id}
GET  /api/memory/core/filter?channel_id=&message=
```

## Layout

```
kaskade/       cascade, memory, erip, gnostic, learning counters
api/           FastAPI
web/           Time Circle, Gnostic Shadow
demo/          seed
docs/          map, layers, blueprint, Spark, Rise, ERIP
tests/
```

`kaskade/learning/loop.py` counts 10 and 50. It does not run an LLM editor.

## Tests

```bash
pytest
python scripts/export_check.py
```

## Scope

Kaskade Memory is a cascade store, a recall API, and a demo UI. Call it from an agent. It is not a hosted chat and it does not ship private conversation dumps.

## License

[Apache-2.0](LICENSE). Issues and PRs: run `pytest` and `scripts/export_check.py`. Vulnerabilities: [SECURITY.md](SECURITY.md).
