# Kaskade Memory

**Hierarchical memory for coding agents** — time-compressed core blocks, theme-linked archival graph, end-of-day maintenance, and graph-native recall (Gnostic Search + Spark).

[![CI](https://github.com/Duzafizzl/Kaskade-Memory/actions/workflows/ci.yml/badge.svg)](https://github.com/Duzafizzl/Kaskade-Memory/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

Most agent memory is either a flat vector dump or a single “summary” blob. **Kaskade** treats memory as a **linked cascade**: days compress into weeks, weeks into months; episodic facts link horizontally through themes and people. Reflex gates keep the hot path fast; a maintainer worker and optional EOD agent keep the graph honest overnight.

---

## Why Kaskade?

| Problem | Kaskade approach |
|--------|------------------|
| Everything in one context window | **Core** (always-on blocks) + **Archival** (long-term, graph-linked) |
| Keyword search misses “vibe” and structure | **Gnostic Search** — BFS on the memory graph until paths converge |
| Random injection feels creepy | **Spark** — rare, cooldown-gated recall lines with privacy-aware ranking |
| Agents forget to file things | **Significance gate** + **maintainer queue** on every archival insert |
| Overnight drift | **EOD reconcile** + pluggable **coding-agent hook** (Cursor, CLI, or noop) |

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

**Vertical cascade** = time compression in core memory.  
**Horizontal cascade** = theme / person / day linking in archival + graph edges.

---

## Features

- **Cascade engine** — envelope stamping, significance gate, JSONL maintainer queue, EOD scheduler
- **ERIP tagging** — four axes per memory; **P = Privacy** (high P → stricter recall / defer to EOD)
- **Core memory gates** — include blocks only when channel, keyword, or content cues match
- **EOD maintainer** — gap scan, signal layers, generic agent hook (`cursor` \| `subprocess` \| `noop`)
- **Gnostic Search** — graph traverse until a convergence hub (“gnostic moment”)
- **Spark** — background audit rows; optional spontaneous 1–2 line inject
- **Event enrichment** — lightweight topic extraction (demo rule-based; LLM hook ready)
- **Regime** — recall policy snapshot (time window, channel mode, boosts)
- **Learning agent** — nested triggers (core every 10 msgs, archival mini-loop every 50)
- **Time Circle UI** — scrollable day/theme explorer at `/time-circle/`

---

## Quickstart

**Requirements:** Docker + Docker Compose

```bash
git clone https://github.com/Duzafizzl/Kaskade-Memory.git
cd Kaskade-Memory
cp example.env .env
docker compose up --build
```

| URL | What |
|-----|------|
| http://localhost:8080/api/health | API health |
| http://localhost:8080/time-circle/ | Time Circle explorer |
| http://localhost:8080/gnostic-shadow/ | Gnostic Search / Spark overview |

The stack seeds **14 days** of demo archival data on first boot.

### Local dev (no Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Postgres with pgvector required — set DATABASE_URL in .env
python demo/seed.py
uvicorn api.main:app --reload --port 8080
```

---

## ERIP (P = Privacy)

Every archival insert should include four scores (1–5):

```
E:3   # Emotional intensity
R:4   # Relational density
I:4   # Identity relevance
P:2   # Privacy — higher = more sensitive; affects gate, spark, recall
```

Details: [docs/ERIP.md](docs/ERIP.md)

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://kaskade:kaskade@localhost:5432/kaskade` | Postgres + pgvector |
| `KASKADE_EOD_AGENT_PROVIDER` | `noop` | `cursor`, `subprocess`, or `noop` |
| `KASKADE_EOD_AGENT_CMD` | — | Shell command; `{prompt_path}` and `{day_id}` placeholders |
| `CASCADE_SIGNIFICANCE_GATE_ENABLED` | `1` | Pre-enqueue archival filter |
| `HIGH_PRIVACY_THRESHOLD` | `4` | P ≥ threshold without theme → defer EOD |
| `KASKADE_SPARK_ENABLED` | `1` | Background spark generation |

Person aliases and core-memory gates: [`config/demo_persons.yaml`](config/demo_persons.yaml), [`config/core_memory_gates.yaml`](config/core_memory_gates.yaml).

---

## API (selection)

```
GET  /api/cascade/days
GET  /api/cascade/day/{day_id}
GET  /api/cascade/persons/aliases
POST /api/cascade/archival
POST /api/cascade/gnostic_traverse
POST /api/gnostic/spark/simulate
POST /api/cascade/eod/{day_id}
GET  /api/memory/core/filter?channel_id=&message=
```

OpenAPI docs: http://localhost:8080/docs (when server is running).

---

## Project layout

```
kaskade/
  cascade/     # envelope, maintainer, eod, rollup
  memory/      # postgres store, prompt gates
  erip/        # scoring & parsing
  gnostic/     # traverse + spark
  learning/    # sleep-time loops
  enrichment/  # event extraction
  regime/      # recall policy
  reflex/      # significance gate
api/           # FastAPI app
web/           # Time Circle + Gnostic Shadow static UI
demo/          # seed script & sample cascade trees
migrations/    # SQL schema
tests/         # pytest suite
```

---

## Tests & release hygiene

```bash
pytest
python scripts/export_check.py   # blocks private names / secret patterns
```

CI runs on every push to `main`.

---

## What this repo is / isn't

**Is:** a portable memory engine + demo UI you can plug into any agent harness.  
**Isn't:** a hosted product, a Discord bot, or a dump of private conversation data. Demo persons are `alex`, `sam`, `agent` only.

---

## Contributing

Issues and PRs welcome. Run `pytest` and `scripts/export_check.py` before opening a PR. See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

---

## License

[Apache-2.0](LICENSE)
