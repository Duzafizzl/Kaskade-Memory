---
title: README.md
description: Kaskade Memory. Hierarchical recall for coding agents. Cascade, Spark, and Bridge Rise.
created: 2026-08-28
updated: 2026-10-21
---

# Kaskade Memory

[![CI](https://github.com/Duzafizzl/Kaskade-Memory/actions/workflows/ci.yml/badge.svg)](https://github.com/Duzafizzl/Kaskade-Memory/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

![Kaskade Memory](docs/assets/kaskade-memory-hero.webp)

Kaskade Memory stores coding-agent memory as a cascade. Days roll into weeks. Weeks roll into months. Themes and people link archival records across those levels.

Spark ranking and Bridge Rise call no LLM. Both paths are deterministic. A Spark is one rare cooldown-gated line. Bridge Rise injects only when Door-B has at least two independent sharp signals. Privacy score P = 5 never appears in a spontaneous Spark. You can still search that memory on purpose.

---

## Time Circle

Time Circle is the demo UI at `/time-circle/`. Scroll the ring to move through months, then days, then hours. The demo seed fills the theme and archival panels.

![Time Circle month ring](docs/assets/time-circle-board.webp)

Month ring on the demo seed. The focused slice is OCT. Scroll rotates the ring. Zoom opens days, then hours.

![Time Circle with a day open](docs/assets/time-circle-day-open.webp)

A day opened on the demo seed. Theme `demo_notes` and one archival. Demo persons are `alex`, `sam`, and `agent`.

![Gnostic Spark and Bridge Rise overview](docs/assets/gnostic-shadow.webp)

Gnostic Spark and Bridge Rise overview at `/gnostic-shadow/`. The page matches the Spark ranker and the Door-B implementation.

| URL | What |
|-----|------|
| http://localhost:8080/time-circle/ | Time Circle explorer |
| http://localhost:8080/gnostic-shadow/ | Spark and Bridge Rise overview |
| http://localhost:8080/api/health | API health |

---

## Recall rules

Most agent memory is one vector index or one summary file. Kaskade splits working memory from archival memory.

Gnostic Search walks the memory graph until paths meet.

Spark may emit one cooldown-gated line. It ranks with privacy scores and never calls an LLM.

Bridge Rise may emit one or two lines only when Door-B has at least two sharp signals. Climate is rank-only and never fires alone.

P = 5 never appears in a spontaneous Spark. That memory stays searchable on purpose.

A significance gate and a maintainer queue run on every archival insert. End-of-day reconcile can call a coding-agent hook. Set the hook to `cursor`, `subprocess`, or `noop`.

---

## Architecture

```mermaid
flowchart TB
  subgraph write [Write path]
    Insert[Archival insert]
    ERIP[ERIP parse E/R/I/P]
    Gate[Significance gate]
    Queue[Maintainer queue]
    Worker[Maintainer worker]
    Graph[(Postgres graph)]
    Insert --> ERIP --> Gate --> Queue --> Worker --> Graph
  end

  subgraph vertical [Vertical cascade]
    Day[rolling_days]
    Week[weekly_summary]
    Month[monthly_summary]
    Year[yearly_essence]
    Day --> Week --> Month --> Year
  end

  subgraph read [Read path]
    Search[cascade_search / Gnostic traverse]
    Spark[Spark audit]
    Recall[Regime + auto-recall policy]
    Graph --> Search
    Graph --> Spark
    Recall --> Search
  end

  subgraph sleep [Sleep-time]
    LA[Learning agent loop]
    LA --> Day
    LA --> Insert
  end
```

The vertical cascade compresses time in core memory. The horizontal cascade links themes, people, and days in archival records and graph edges.

---

## Modules

The cascade engine stamps envelopes, applies the significance gate, writes a JSONL maintainer queue, and runs the end-of-day scheduler.

ERIP tags each archival on four axes. P is privacy. A high P score tightens recall and can defer work to end of day.

A core-memory gate keeps a block out of the prompt unless a channel, keyword, or content cue matches.

The end-of-day maintainer scans gaps, builds signal layers, and can run an agent hook. Set `KASKADE_EOD_AGENT_PROVIDER` to `cursor`, `subprocess`, or `noop`.

Gnostic Search traverses the graph until paths converge.

Spark draws one rare cooldown-gated line from a multi-cue pool. Ranking is privacy-aware and deterministic.

Bridge Rise injects one or two lines only when at least two sharp signals agree.

Event enrichment extracts topics with a rule-based demo. An LLM hook is optional and unused in Spark rank.

Regime stores a recall-policy snapshot. It holds the time window, channel mode, and boosts.

The learning agent runs nested triggers. Core memory every 10 messages. Archival mini-loop every 50.

Time Circle is the scrollable day and theme explorer at `/time-circle/`.

---

## Quickstart

You need Docker and Docker Compose.

```bash
git clone https://github.com/Duzafizzl/Kaskade-Memory.git
cd Kaskade-Memory
cp example.env .env
docker compose up --build
```

The first boot seeds 14 days of demo archival data.

### Local dev without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Postgres with pgvector required. Set DATABASE_URL in .env
python demo/seed.py
uvicorn api.main:app --reload --host 127.0.0.1 --port 8080
```

---

## ERIP privacy scores

Every archival insert should include four scores from 1 to 5.

```
E:3   # Emotional intensity
R:4   # Relational density
I:4   # Identity relevance
P:2   # Privacy. Higher is more sensitive. Affects gate, Spark, and recall.
```

P = 5 is a hard stop for spontaneous Spark. Details: [docs/ERIP.md](docs/ERIP.md). Spark: [docs/GNOSTIC_SPARK.md](docs/GNOSTIC_SPARK.md). Rise: [docs/BRIDGE_RISE.md](docs/BRIDGE_RISE.md).

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://kaskade:kaskade@localhost:5432/kaskade` | Postgres with pgvector |
| `KASKADE_EOD_AGENT_PROVIDER` | `noop` | `cursor`, `subprocess`, or `noop` |
| `KASKADE_EOD_AGENT_CMD` | unset | Shell command. Placeholders are `{prompt_path}` and `{day_id}`. |
| `CASCADE_SIGNIFICANCE_GATE_ENABLED` | `1` | Pre-enqueue archival filter |
| `HIGH_PRIVACY_THRESHOLD` | `4` | If P is at or above the threshold and the row has no theme, defer to end of day. |
| `KASKADE_SPARK_ENABLED` | `1` | Background Spark generation |

Person aliases and core-memory gates live in [`config/demo_persons.yaml`](config/demo_persons.yaml) and [`config/core_memory_gates.yaml`](config/core_memory_gates.yaml).

---

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

OpenAPI is at http://localhost:8080/docs when the server is running.

---

## Project layout

```
kaskade/
  cascade/     # envelope, maintainer, eod, rollup
  memory/      # postgres store, prompt gates
  erip/        # scoring and parsing
  gnostic/     # traverse, Spark rank, Bridge Rise in spreading/
  learning/    # sleep-time loops
  enrichment/  # event extraction
  regime/      # recall policy
  reflex/      # significance gate
api/           # FastAPI app
web/           # Time Circle and Gnostic Shadow static UI
demo/          # seed script and sample cascade trees
migrations/    # SQL schema
tests/         # pytest suite
docs/assets/   # README hero and live UI captures
```

---

## Tests and release hygiene

```bash
pytest
python scripts/export_check.py   # blocks private names and secret patterns
```

CI runs on every push to `main`.

---

## Scope

This repo is a memory engine and a demo UI. You can call it from an agent loop.

It is not a hosted product, not a hosted chat bot, and not a dump of private conversation data. Demo persons are `alex`, `sam`, and `agent`.

---

## Contributing

Issues and PRs are welcome. Run `pytest` and `scripts/export_check.py` before you open a PR. See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

---

## License

[Apache-2.0](LICENSE)
