#!/usr/bin/env python3
"""
agent_scope_guard.py – Write-scope guard for maintainer agent runs.

Created: 2026-08-28
Last updated: 2026-08-28
"""

from __future__ import annotations

from pathlib import Path
from typing import List


def resolve_allowed_write_paths(repo_root: Path, day_id: str) -> List[str]:
    base = repo_root / "demo" / "cascade" / day_id
    return [
        str(base / "PROPOSAL.md"),
        str(base / "THEME_GRAPH.md"),
        str(base / "CASCADE_EOD_REPORT.json"),
    ]


def build_scope_prompt_section(allowed_paths: List[str]) -> str:
    lines = ["## Allowed write paths", ""]
    for p in allowed_paths:
        lines.append(f"- `{p}`")
    return "\n".join(lines)
