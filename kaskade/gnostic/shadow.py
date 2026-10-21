#!/usr/bin/env python3
"""
shadow.py – Spark audit: rare spontaneous recall via flashback pool + rank + delivery.

Created: 2026-08-28
Last updated: 2026-10-20
"""

from __future__ import annotations

import logging
import math
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence

from kaskade.gnostic._log import log_event
from kaskade.gnostic.delivery import get_delivery
from kaskade.gnostic.flashback_pool import build_pool
from kaskade.gnostic.spark_rank import rank_candidates
from kaskade.gnostic.types import Cue, MemoryRecord, SparkCandidate, SparkResult

logger = logging.getLogger(__name__)
_MODULE = "kaskade.gnostic.shadow"

_last_spark: Dict[str, float] = {}
COOLDOWN_ENV = "KASKADE_SPARK_COOLDOWN_SEC"
DEFAULT_COOLDOWN_SEC = 300.0


def spark_enabled() -> bool:
    return (os.getenv("KASKADE_SPARK_ENABLED") or "1").strip().lower() in ("1", "true", "yes", "on")


def spark_cooldown_sec() -> float:
    raw = os.getenv(COOLDOWN_ENV)
    if raw is None or not str(raw).strip():
        return DEFAULT_COOLDOWN_SEC
    try:
        val = float(str(raw).strip())
    except ValueError:
        return DEFAULT_COOLDOWN_SEC
    if not math.isfinite(val) or val < 0:
        return DEFAULT_COOLDOWN_SEC
    return val


def reset_spark_cooldown_for_tests() -> None:
    _last_spark.clear()


def _on_cooldown(agent_id: str, now: float) -> bool:
    last = _last_spark.get(agent_id, 0.0)
    return now - last < spark_cooldown_sec()


def _candidates_from_dicts(rows: Sequence[Dict[str, Any]]) -> List[SparkCandidate]:
    out: List[SparkCandidate] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        rec = MemoryRecord.from_dict(row)
        if not rec.memory_id:
            continue
        raw_cues = row.get("cues") if isinstance(row.get("cues"), list) else []
        cues = []
        for item in raw_cues:
            if isinstance(item, Cue):
                cues.append(item)
            elif isinstance(item, dict) and item.get("type") and item.get("key"):
                cues.append(Cue(type=str(item["type"]), key=str(item["key"]), weight=float(item.get("weight") or 1.0)))
        if not cues:
            cues = [Cue("graph_ref", rec.memory_id)]
        out.append(
            SparkCandidate(
                record=rec,
                cues=cues,
                convergence_hits=int(row.get("convergence_hits") or 0),
                theme_overlap=int(row.get("theme_overlap") or 0),
                repeat_penalty=float(row.get("repeat_penalty") or 1.0),
            )
        )
    return out


def _line_for(rec: MemoryRecord) -> str:
    return (rec.recall_inject_l1 or rec.content or "").strip()[:200]


def maybe_generate_spark(
    *,
    agent_id: str,
    candidates: List[Dict[str, Any]],
    privacy_penalty: float = 1.0,
    delivery: str = "",
    now: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Rank dict-shaped candidates, apply cooldown, deliver, return a public spark dict."""
    if not spark_enabled() or not candidates:
        return None
    current = time.monotonic() if now is None else float(now)
    if _on_cooldown(agent_id, current):
        log_event(logger, "DEBUG", _MODULE, "maybe_generate_spark", "cooldown", agent_id=agent_id)
        return None
    ranked = rank_candidates(_candidates_from_dicts(candidates))
    if not ranked:
        return None
    top = ranked[0]
    line = _line_for(top.candidate.record)
    if not line:
        return None
    result = SparkResult(
        trace_id=str(uuid.uuid4()),
        memory_id=top.memory_id,
        spark_text=line,
        score=top.final_score * (float(privacy_penalty) if privacy_penalty else 1.0),
        delivery=(delivery or os.getenv("KASKADE_SPARK_DELIVERY") or "log"),
        cue_types_n=top.cue_types_n,
        kuramoto_r=top.kuramoto_r,
        p_rel=top.p_rel,
    )
    hook = get_delivery(delivery)
    hook.deliver(result, agent_id=agent_id)
    result.delivery = hook.name
    _last_spark[agent_id] = current
    out = result.to_dict()
    log_event(
        logger,
        "INFO",
        _MODULE,
        "maybe_generate_spark",
        "spark_generated",
        agent_id=agent_id,
        memory_id=result.memory_id,
        score=result.score,
        delivery=result.delivery,
        cue_types_n=result.cue_types_n,
    )
    return out


def generate_spark_from_graph(
    *,
    agent_id: str,
    seeds: Sequence[str],
    memories: Sequence[MemoryRecord],
    edges: Optional[Sequence[Dict[str, Any]]] = None,
    allow_place: bool = False,
    delivery: str = "",
) -> Optional[Dict[str, Any]]:
    """Pool from the graph, then reuse maybe_generate_spark ranking/delivery."""
    pool = build_pool(seeds, memories, edges=edges, allow_place=allow_place)
    rows = [
        {
            "memory_id": c.memory_id,
            "content": c.record.content,
            "theme_id": c.record.theme_id,
            "day_id": c.record.day_id,
            "tags": c.record.tags,
            "privacy": c.record.privacy,
            "recall_inject_l1": c.record.recall_inject_l1,
            "cues": [{"type": cue.type, "key": cue.key, "weight": cue.weight} for cue in c.cues],
            "convergence_hits": c.convergence_hits,
            "theme_overlap": c.theme_overlap,
            "repeat_penalty": c.repeat_penalty,
        }
        for c in pool
    ]
    return maybe_generate_spark(agent_id=agent_id, candidates=rows, delivery=delivery)
