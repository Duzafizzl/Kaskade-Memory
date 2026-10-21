#!/usr/bin/env python3
"""
signals.py – Signal fetcher registry + demo plugins for EOD.

Created: 2026-08-28
Last updated: 2026-10-20
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Protocol

logger = logging.getLogger(__name__)


class SignalFetcher(Protocol):
    theme_id: str

    def fetch_day_summary(self, *, day_id: str, agent_id: str = "") -> Dict[str, Any]: ...


def demo_activity_day(day_id: str, agent_id: str = "") -> Dict[str, Any]:
    return {
        "layer": "demo_activity",
        "theme_id": "demo_activity_day",
        "container_hint": "signal:demo_activity",
        "has_data": True,
        "gist": f"Demo activity on {day_id}",
        "events_n": 3,
    }


def demo_heartbeat_day(day_id: str, agent_id: str = "") -> Dict[str, Any]:
    return {
        "layer": "demo_heartbeat",
        "theme_id": "demo_heartbeat_day",
        "container_hint": "signal:demo_heartbeat",
        "has_data": True,
        "gist": "Heartbeat ticks stable",
        "ticks_n": 12,
    }


from kaskade.gnostic.cascade_day_summary import spark_day_summary


_REGISTRY: Dict[str, Callable[..., Dict[str, Any]]] = {
    "demo_activity_day": demo_activity_day,
    "demo_heartbeat_day": demo_heartbeat_day,
    "spark_day": spark_day_summary,
}


def build_signal_layers(*, day_id: str, agent_id: str = "") -> Dict[str, Any]:
    layers: Dict[str, Any] = {}
    for key, fn in _REGISTRY.items():
        try:
            layers[key.replace("_day", "")] = fn(day_id, agent_id)
        except Exception as exc:
            logger.warning(json.dumps({"level": "WARN", "message": "signal_fetch_failed", "layer": key, "error": str(exc)}))
    return layers
