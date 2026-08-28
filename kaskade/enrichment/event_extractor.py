#!/usr/bin/env python3
"""
event_extractor.py – Generic message enrichment (rule-based demo + LLM hook).

Created: 2026-08-28
Last updated: 2026-08-28
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

TOPICS = ("work", "health", "social", "learning")


def extract_events(text: str) -> List[Dict[str, Any]]:
    low = (text or "").lower()
    events: List[Dict[str, Any]] = []
    for topic in TOPICS:
        if topic in low:
            events.append({"topic": topic, "sentiment": "neutral", "source": "rule"})
    if not events:
        events.append({"topic": "general", "sentiment": "neutral", "source": "fallback"})
    logger.info(json.dumps({"level": "INFO", "module": "enrichment", "message": "extracted", "n": len(events)}))
    return events
