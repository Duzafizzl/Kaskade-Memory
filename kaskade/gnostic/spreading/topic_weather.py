#!/usr/bin/env python3
"""
topic_weather.py – Recurring-topic frequency over recent memory_events (signal `topic_weather`).

Deterministic only: counts enrichment topics in a lookback window. Weather alone never fires.
Each event counts a topic at most once, so a single spammy event cannot create weather.

Created: 2026-10-20
Last updated: 2026-10-20
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from kaskade.gnostic.spreading.fragment_index import theme_surface_tokens, tokenize

MAX_TOPICS_PER_EVENT = 64
MAX_LOOKBACK_H = 24 * 365


def _as_utc(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value.strip():
        raw = value.strip()
        if raw.endswith(("Z", "z")):
            raw = raw[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _positive_int(value: Any, default: int, upper: int) -> int:
    try:
        val = int(value)
    except (TypeError, ValueError):
        return default
    if val < 1:
        return default
    return min(val, upper)


def recurring_topics(
    events: Sequence[Dict[str, Any]],
    *,
    now: datetime,
    lookback_h: int = 24,
    min_count: int = 3,
) -> Dict[str, int]:
    """topic -> count for topics seen >= min_count times in (now - lookback_h, now].

    Event shape: {"ts": ISO-8601 str | datetime, "topics": [str, ...]}. Malformed events skipped.
    """
    now_utc = _as_utc(now)
    if now_utc is None or not events:
        return {}
    hours = _positive_int(lookback_h, 24, MAX_LOOKBACK_H)
    threshold = _positive_int(min_count, 3, 10_000)
    start = now_utc - timedelta(hours=hours)
    counts: Dict[str, int] = {}
    for ev in events:
        if not isinstance(ev, dict):
            continue
        ts = _as_utc(ev.get("ts"))
        if ts is None or ts <= start or ts > now_utc:
            continue
        topics = ev.get("topics")
        if not isinstance(topics, (list, tuple)):
            continue
        per_event = set()
        for topic in topics[:MAX_TOPICS_PER_EVENT]:
            if isinstance(topic, str):
                norm = topic.strip().lower()
                if norm:
                    per_event.add(norm)
        for topic in per_event:
            counts[topic] = counts.get(topic, 0) + 1
    return {topic: n for topic, n in sorted(counts.items()) if n >= threshold}


def match_weather_to_themes(topics: Dict[str, int], theme_ids: Sequence[str]) -> List[str]:
    """Theme ids whose surface tokens (split on - _ space) overlap any recurring topic token. Sorted."""
    if not isinstance(topics, dict) or not topics or not theme_ids:
        return []
    topic_tokens = set()
    for topic in topics:
        topic_tokens.update(tokenize(topic.replace("-", " ").replace("_", " ")) if isinstance(topic, str) else [])
    if not topic_tokens:
        return []
    out = set()
    for theme in theme_ids:
        if not isinstance(theme, str):
            continue
        if topic_tokens.intersection(theme_surface_tokens(theme)):
            out.add(theme)
    return sorted(out)
