---
title: README.md
description: Documentation map. What this repo is versus what your agent still owns.
created: 2026-10-26
updated: 2026-11-03
---

# Docs

Kaskade Memory is one repo. Your agent is a separate program that calls it.

```text
README (this repo)
  |
  +-- THIS REPO   cascade, graph, Spark, Rise, Time Circle
  |
  +-- YOUR AGENT  core blocks, history, tasks, approval, live feed,
                  propose-only reports, research triage
        MEMORY_LAYERS (short) then MEMORY_SYSTEM_BLUEPRINT (long)
```

| If you want | Read |
|-------------|------|
| Clone, run, API | [../README.md](../README.md) |
| How to split core vs archive and where Kaskade sits | [MEMORY_LAYERS.md](MEMORY_LAYERS.md) |
| Propose-only night reports and research buckets | [MEMORY_LAYERS.md](MEMORY_LAYERS.md#propose-is-not-apply) |
| History, tasks, approval, and live feed | [MEMORY_SYSTEM_BLUEPRINT.md](MEMORY_SYSTEM_BLUEPRINT.md) |
| Spark ranking | [GNOSTIC_SPARK.md](GNOSTIC_SPARK.md) |
| Door-B Bridge Rise | [BRIDGE_RISE.md](BRIDGE_RISE.md) |
| Privacy scores E/R/I/P | [ERIP.md](ERIP.md) |
| README screenshots | [assets/README.md](assets/README.md) |

This repo stores days and recalls them. Your agent chooses what enters the prompt, what needs a human, and what a camera just saw. Kaskade does not ship a chat bot, an approval UI, or a device journal.

Read the root README first. Use Memory layers to wire Kaskade. Open the blueprint when you build the rest of the agent.
