---
title: README.md
description: What the public test suite covers and why it ships with Kaskade Memory.
created: 2026-10-21
updated: 2026-10-21
---

# Tests

These tests **belong in the public repo**. They are the contract: Door-B, privacy,
export hygiene, ranking, and the demo API. Downstream users and CI run the same suite.

| File | Why it is public |
|------|------------------|
| `test_gnostic_contract.py` | Frozen invariants (P-curve, weather-alone, converge) |
| `test_bridge_rise_core.py` | Door-B, cooldown, render leaks, token collapse |
| `test_gnostic_spark_*.py` | Pool, Kuramoto, logit, attribution, delivery |
| `test_gnostic_traverse.py` | Graph search hub |
| `test_cascade_*.py` / `test_erip_*.py` / `test_eod_*.py` / `test_core_memory_*.py` | Engine gates |
| `test_export_no_secrets.py` | Release leak scan |
| `test_integration_api.py` | Optional Postgres + HTTP smoke (`skip` without `DATABASE_URL`) |

## What does not belong here

- Maintainer reviews and publish audits → `drafts/` (gitignored)
- Private conversation dumps, real person ids, production `.env`
- Assertions that spell old internal product names just to forbid them.
  Prefer a positive check (`"kaskade" in body`) over naming the leftover.

```bash
.venv/bin/python -m pytest -q
```
