---
title: SECURITY.md
description: Security policy for Kaskade Memory OSS.
created: 2026-08-28
updated: 2026-10-21
---

# Security Policy

Kaskade Memory is a **demo-oriented memory engine**, not a production secrets vault.

## Reporting

Please report vulnerabilities via [GitHub Security Advisories](https://github.com/Duzafizzl/Kaskade-Memory/security/advisories).

## Do not commit

- `.env` files with real API keys
- Production database dumps or private conversation archives
- Real person identifiers from non-demo datasets
- Private host paths, LAN addresses, or chat-platform snowflakes
- Local maintainer notes under `drafts/` (gitignored; reviews and publish audits stay off the public tree)

## Release gate

`scripts/export_check.py` is the CI gate (working tree). It fails on:

- Secret-shaped tokens (`sk-`, `ghp_`, `AKIA`, PEM private keys, …)
- Private identifiers (product names, room names, LAN ranges, local paths)
- Forbidden filenames (`.env`, `*.pem`, database dumps)

History is a separate check for maintainers before a public push:

```bash
python scripts/export_check.py                  # CI / working tree
python scripts/export_check.py --history        # every reachable blob
python scripts/export_check.py --history --range origin/main..HEAD
```

Deleting a string from HEAD does not remove it from git blobs. A history finding
on already-published commits is documented, not silently ignored.
