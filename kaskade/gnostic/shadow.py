#!/usr/bin/env python3
"""
shadow.py – Spark audit: rare spontaneous recall lines (demo implementation).

Created: 2026-08-28
Last updated: 2026-08-28
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_last_spark: Dict[str, float] = {}
COOLDOWN_SEC = 300.0


def spark_enabled() -> bool:
    return (os.getenv("KASKADE_SPARK_ENABLED") or "1").strip().lower() in ("1", "true", "yes", "on")


def maybe_generate_spark(
    *,
    agent_id: str,
    candidates: List[Dict[str, Any]],
    privacy_penalty: float = 1.0,
) -> Optional[Dict[str, Any]]:
    if not spark_enabled() or not candidates:
        return None
    now = time.monotonic()
    if now - _last_spark.get(agent_id, 0) < COOLDOWN_SEC:
        return None
    ranked = sorted(candidates, key=lambda c: float(c.get("score", 0)) / max(0.5, float(c.get("privacy", 3))), reverse=True)
    pick = ranked[0]
    _last_spark[agent_id] = now
    line = str(pick.get("recall_inject_l1") or pick.get("content") or "")[:200]
    out = {"spark_text": line, "memory_id": pick.get("memory_id"), "score": pick.get("score")}
    logger.info(json.dumps({"level": "INFO", "module": "gnostic.shadow", "message": "spark_generated", **out}))
    return out
