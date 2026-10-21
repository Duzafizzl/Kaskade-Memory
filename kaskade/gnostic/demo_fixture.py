#!/usr/bin/env python3
"""
demo_fixture.py – Load the synthetic Gnostic demo graph (memories, edges, events, now).

Created: 2026-10-20
Last updated: 2026-10-20
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from kaskade.gnostic.types import MemoryRecord

DEFAULT_FIXTURE = Path(__file__).resolve().parents[2] / "demo" / "fixtures" / "gnostic_demo.json"


@dataclass
class DemoGraph:
    memories: List[MemoryRecord]
    edges: List[Dict[str, Any]]
    events: List[Dict[str, Any]]
    now: datetime


def load_demo_fixture(path: Optional[Path] = None) -> DemoGraph:
    raw = json.loads((path or DEFAULT_FIXTURE).read_text(encoding="utf-8"))
    return DemoGraph(
        memories=[MemoryRecord.from_dict(m) for m in raw.get("memories", [])],
        edges=list(raw.get("edges", [])),
        events=list(raw.get("events", [])),
        now=datetime.fromisoformat(str(raw["now"]).replace("Z", "+00:00")),
    )
