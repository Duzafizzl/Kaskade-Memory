---
title: SECURITY.md
description: Security policy for Kaskade Memory OSS.
created: 2026-08-28
updated: 2026-08-28
---

# Security Policy

Kaskade Memory is a **demo-oriented memory engine**, not a production secrets vault.

## Reporting

Please report vulnerabilities via [GitHub Security Advisories](https://github.com/Duzafizzl/Kaskade-Memory/security/advisories).

## Do not commit

- `.env` files with real API keys
- Production database dumps or private conversation archives
- Real person identifiers from non-demo datasets

## CI

`scripts/export_check.py` scans for common secret patterns and blocked private identifiers before release.
