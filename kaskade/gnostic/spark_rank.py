#!/usr/bin/env python3
"""
spark_rank.py – Combine Kuramoto coherence, Bayesian P_rel and ERIP privacy into one Spark ranking.

final_score = p_rel * (1 + alpha * R) * privacy_factor(P) * repeat_penalty, with alpha from
KASKADE_SPARK_KURAMOTO_ALPHA (default 0.35, clamped to [0, 2]).

Created: 2026-10-20
Last updated: 2026-10-20
"""

from __future__ import annotations

import logging
import math
import os
from typing import Any, Dict, List, Sequence

from kaskade.gnostic import bayesian_rank
from kaskade.gnostic._log import log_event
from kaskade.gnostic.kuramoto import count_cue_types, order_parameter
from kaskade.gnostic.types import ScoredCandidate, SparkCandidate, privacy_factor

logger = logging.getLogger(__name__)
_MODULE = "kaskade.gnostic.spark_rank"

ALPHA_ENV = "KASKADE_SPARK_KURAMOTO_ALPHA"
DEFAULT_ALPHA = 0.35
ALPHA_MIN = 0.0
ALPHA_MAX = 2.0


def kuramoto_alpha() -> float:
    """Coherence boost strength; malformed or non-finite env values fall back to the default."""
    raw = os.getenv(ALPHA_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_ALPHA
    try:
        val = float(raw.strip())
    except ValueError:
        val = float("nan")
    if not math.isfinite(val):
        log_event(logger, "WARN", _MODULE, "kuramoto_alpha", "invalid_env", env=ALPHA_ENV, error="not a finite float", fallback=DEFAULT_ALPHA)
        return DEFAULT_ALPHA
    return max(ALPHA_MIN, min(ALPHA_MAX, val))


def _clamp01(value: Any, default: float) -> float:
    try:
        val = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(val):
        return default
    return max(0.0, min(1.0, val))


def _min_score(value: Any) -> float:
    """final_score can exceed 1.0 (coherence boost), so only negatives and garbage are reset."""
    try:
        val = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, val) if math.isfinite(val) else 0.0


def _score_one(cand: SparkCandidate, alpha: float) -> ScoredCandidate:
    r = order_parameter(cand.cues)
    p_rel = bayesian_rank.score(cand, kuramoto_r=r)
    pf = privacy_factor(cand.record.privacy)
    repeat = _clamp01(cand.repeat_penalty, 1.0)
    final = round(p_rel * (1.0 + alpha * r) * pf * repeat, 4)
    return ScoredCandidate(
        candidate=cand,
        kuramoto_r=r,
        cue_types_n=count_cue_types(cand.cues),
        p_rel=p_rel,
        cluster_id=bayesian_rank.cluster_id(cand, kuramoto_r=r),
        privacy_factor=pf,
        final_score=final,
    )


def rank_candidates(candidates: Sequence[SparkCandidate], *, min_score: float = 0.0) -> List[ScoredCandidate]:
    """final_score = p_rel * (1 + alpha * kuramoto_r) * privacy_factor(P) * repeat_penalty.

    - Sorted by final_score desc, ties by memory_id asc (deterministic).
    - Candidates with cue_types_n < 2, privacy_factor == 0 or final_score < min_score are dropped.
    """
    alpha = kuramoto_alpha()
    floor = _min_score(min_score)
    best: Dict[str, ScoredCandidate] = {}
    invalid_n = 0
    dropped_privacy = 0
    dropped_floor = 0
    for cand in candidates or []:
        if not isinstance(cand, SparkCandidate) or not cand.memory_id:
            invalid_n += 1
            continue
        scored = _score_one(cand, alpha)
        if scored.cue_types_n < 2:
            invalid_n += 1
            continue
        if scored.privacy_factor <= 0.0:
            dropped_privacy += 1
            continue
        if scored.final_score < floor:
            dropped_floor += 1
            continue
        prev = best.get(scored.memory_id)
        if prev is None or scored.final_score > prev.final_score:
            best[scored.memory_id] = scored
    ranked = sorted(best.values(), key=lambda s: (-s.final_score, s.memory_id))
    log_event(
        logger,
        "INFO",
        _MODULE,
        "rank_candidates",
        "ranked",
        alpha=alpha,
        min_score=floor,
        ranked_n=len(ranked),
        invalid_n=invalid_n,
        dropped_privacy_n=dropped_privacy,
        dropped_floor_n=dropped_floor,
        top=[{"memory_id": s.memory_id, "final_score": s.final_score} for s in ranked[:5]],
    )
    return ranked


__all__ = ["ALPHA_ENV", "DEFAULT_ALPHA", "kuramoto_alpha", "rank_candidates"]
