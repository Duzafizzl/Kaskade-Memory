#!/usr/bin/env python3
"""
context.py – Generic recall policy snapshot (regime rewrite).

Created: 2026-08-28
Last updated: 2026-08-28
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class RecallPolicy:
    time_window_hours: int = 24
    channel_mode: str = "default"
    enrichment_boost: float = 1.0
    relational_boost: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time_window_hours": self.time_window_hours,
            "channel_mode": self.channel_mode,
            "enrichment_boost": self.enrichment_boost,
            "relational_boost": self.relational_boost,
        }


def build_recall_policy(*, channel_id: str = "", message_type: str = "user") -> RecallPolicy:
    boost = 1.2 if channel_id.startswith("dm:") else 1.0
    return RecallPolicy(channel_mode=channel_id or "default", enrichment_boost=boost)
