#!/usr/bin/env python3
"""
loop.py – Learning agent nested triggers (core every 10 msgs, archival every 50).

Created: 2026-08-28
Last updated: 2026-08-28
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CORE_INTERVAL = 10
ARCHIVAL_INTERVAL = 50
FORBIDDEN_LABELS = frozenset({"weekly_summary", "monthly_summary", "yearly_essence", "ABOUT ME"})


@dataclass
class LearningState:
    message_count: int = 0

    def on_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        self.message_count += 1
        triggers: List[str] = []
        if self.message_count % CORE_INTERVAL == 0:
            triggers.append("core_loop")
        if self.message_count % ARCHIVAL_INTERVAL == 0 and len(str(message.get("content") or "")) > 80:
            triggers.append("archival_mini_loop")
        return {"message_count": self.message_count, "triggers": triggers}


def run_core_loop(*, recent_messages: List[Dict[str, Any]], core_blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    editable = [b for b in core_blocks if str(b.get("label")) not in FORBIDDEN_LABELS]
    logger.info(json.dumps({"level": "INFO", "module": "learning.loop", "message": "core_loop", "editable_n": len(editable)}))
    return {"status": "ok", "editable_blocks": len(editable), "tool_budget": 5}


def run_archival_mini_loop(*, recent_messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    logger.info(json.dumps({"level": "INFO", "module": "learning.loop", "message": "archival_mini_loop"}))
    return {"status": "ok", "archival_review": True}
