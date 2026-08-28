---
title: SECURITY.md
description: Security policy for Kaskade Memory OSS.
created: 2026-08-28
updated: 2026-08-28
---

# Security Policy

Kaskade Memory is a **demo-oriented memory engine**, not a production secrets vault.

## Reporting

Please report vulnerabilities via GitHub Security Advisories on this repository.

## Do not commit

- `.env` files with real API keys
- Production database dumps
- Private conversation archives

## CI

`scripts/export_check.py` blocks common secret patterns and private person identifiers before release.
