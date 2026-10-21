#!/usr/bin/env python3
"""
attribution.py – Explainable "why did this spark?" cards and convergence summaries for EOD.

Cards carry ids, cue types and numbers only. Memory content, spark text and cue keys
(which can be tag or theme names) are deliberately left out so cards are safe to log.

Created: 2026-10-20
Last updated: 2026-10-20
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Sequence

from kaskade.gnostic._log import log_event
from kaskade.gnostic.types import ScoredCandidate

logger = logging.getLogger(__name__)
_MODULE = "kaskade.gnostic.attribution"

CONVERGENT_MIN_TYPES = 2


def build_card(scored: ScoredCandidate, *, trace_id: str) -> Dict[str, Any]:
    """Card: trace_id, memory_id, cue_types (sorted), cue_types_n, kuramoto_r, p_rel, cluster_id, convergent.

    Never includes raw memory content (only the memory_id and cue identities).
    """
    tid = str(trace_id or "")
    if not isinstance(scored, ScoredCandidate):
        log_event(logger, "WARN", _MODULE, "build_card", "invalid_scored", trace_id=tid, error="expected ScoredCandidate")
        return {
            "trace_id": tid,
            "memory_id": "",
            "cue_types": [],
            "cue_types_n": 0,
            "kuramoto_r": 0.0,
            "p_rel": 0.0,
            "cluster_id": "generic",
            "convergent": False,
        }
    cue_types = sorted({str(c.type) for c in (scored.candidate.cues or []) if getattr(c, "type", None)})
    types_n = int(scored.cue_types_n)
    card = {
        "trace_id": tid,
        "memory_id": scored.memory_id,
        "cue_types": cue_types,
        "cue_types_n": types_n,
        "kuramoto_r": round(float(scored.kuramoto_r), 4),
        "p_rel": round(float(scored.p_rel), 4),
        "cluster_id": str(scored.cluster_id),
        "convergent": types_n >= CONVERGENT_MIN_TYPES,
    }
    log_event(logger, "DEBUG", _MODULE, "build_card", "built", **card)
    return card


def convergence_summary(cards: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """{cards_n, convergent_n, convergent_rate, by_cluster: {cluster: n}}."""
    valid = [c for c in (cards or []) if isinstance(c, dict)]
    convergent_n = sum(1 for c in valid if c.get("convergent") is True)
    by_cluster: Dict[str, int] = {}
    for c in valid:
        key = str(c.get("cluster_id") or "generic")
        by_cluster[key] = by_cluster.get(key, 0) + 1
    cards_n = len(valid)
    summary = {
        "cards_n": cards_n,
        "convergent_n": convergent_n,
        "convergent_rate": round(convergent_n / cards_n, 4) if cards_n else 0.0,
        "by_cluster": dict(sorted(by_cluster.items())),
    }
    log_event(
        logger,
        "INFO",
        _MODULE,
        "convergence_summary",
        "summarised",
        skipped_n=len(cards or []) - cards_n,
        **summary,
    )
    return summary


__all__ = ["CONVERGENT_MIN_TYPES", "build_card", "convergence_summary"]
