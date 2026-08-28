# Kaskade Memory

**Verlinkende Kaskade** — open-source hierarchical memory engine with ERIP tagging, EOD maintainer, Gnostic Search, Spark, Learning Agent hooks, and Time Circle UI.

Repository: [github.com/Duzafizzl/Kaskade-Memory](https://github.com/Duzafizzl/Kaskade-Memory)

## Features

- **Cascade Engine** — archival envelope, significance gate, maintainer queue, vertical rollups
- **EOD Maintainer** — daily reconcile + pluggable coding-agent hook (Cursor, subprocess, noop)
- **ERIP** — E/R/I/**P (Privacy)** scoring on archival memories
- **Core Memory Gates** — include blocks by channel, keywords, message types
- **Gnostic Search** — graph traverse until convergence
- **Spark** — spontaneous recall audit lines
- **Event Enrichment** — generic topic extraction
- **Regime** — recall policy snapshot
- **Learning Agent** — nested core/archival loops
- **Time Circle UI** — `/time-circle` explorer

## Quickstart

```bash
cp example.env .env
docker compose up --build
```

- API: http://localhost:8080/api/health
- Time Circle: http://localhost:8080/time-circle/
- Gnostic Shadow docs: http://localhost:8080/gnostic-shadow/

## ERIP (P = Privacy)

Archival content must include:

```
E:3
R:4
I:4
P:2
```

See [docs/ERIP.md](docs/ERIP.md).

## EOD Agent Hook

```env
KASKADE_EOD_AGENT_PROVIDER=subprocess
KASKADE_EOD_AGENT_CMD="your-agent --file {prompt_path}"
```

## Development

```bash
pip install -e ".[dev]"
pytest
python scripts/export_check.py
python demo/seed.py
uvicorn api.main:app --reload --port 8080
```

## License

Apache-2.0
