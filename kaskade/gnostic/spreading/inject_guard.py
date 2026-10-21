#!/usr/bin/env python3
"""
inject_guard.py – Cooldown per (agent, channel) and stale prompt-block stripping for Bridge Rise inject.

Created: 2026-10-20
Last updated: 2026-10-20
"""

from __future__ import annotations

import time
from typing import Dict, Optional, Tuple

PROMPT_MARKER = "## Bridge rise (recalled context)"

_HEADING_PREFIX = "## "


def _key(agent_id: object, channel: object) -> str:
    return f"{agent_id if agent_id is not None else ''}|{channel if channel is not None else ''}"


class InjectGuard:
    """In-process cooldown keyed on f"{agent_id}|{channel}" (one channel never mutes another)."""

    def __init__(self, cooldown_s: float = 120.0) -> None:
        self.cooldown_s = cooldown_s
        self._last: Dict[str, float] = {}

    def _cooldown(self) -> float:
        try:
            return max(0.0, float(self.cooldown_s))
        except (TypeError, ValueError):
            return 120.0

    def allow(self, agent_id: str, channel: str, *, now: Optional[float] = None) -> bool:
        last = self._last.get(_key(agent_id, channel))
        if last is None:
            return True
        current = time.monotonic() if now is None else float(now)
        return current - last >= self._cooldown()

    def mark(self, agent_id: str, channel: str, *, now: Optional[float] = None) -> None:
        self._last[_key(agent_id, channel)] = time.monotonic() if now is None else float(now)


def strip_stale_blocks(prompt: str) -> Tuple[str, int]:
    """Remove previous PROMPT_MARKER blocks (marker line up to next '## ' heading or end). Returns (prompt, n_removed)."""
    if not isinstance(prompt, str) or PROMPT_MARKER not in prompt:
        return (prompt if isinstance(prompt, str) else "", 0)
    kept = []
    removed = 0
    in_block = False
    for line in prompt.splitlines(keepends=True):
        stripped = line.strip()
        if stripped == PROMPT_MARKER:
            in_block = True
            removed += 1
            continue
        if in_block and line.startswith(_HEADING_PREFIX):
            in_block = False
        if not in_block:
            kept.append(line)
    return ("".join(kept), removed)
