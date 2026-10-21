#!/usr/bin/env python3
"""
bayesian_rank.py – Weighted-logit P(relevant) for a Spark candidate (no sampler on the hot path).

P_rel = sigmoid(bias + sum(w_k * x_k) [+ coherence bonus]). Weights are hand-set priors,
documented in docs/GNOSTIC_SPARK.md; they are meant to be refit offline from audit data.

Created: 2026-10-20
Last updated: 2026-10-20
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict

from kaskade.gnostic._log import log_event
from kaskade.gnostic.kuramoto import count_cue_types
from kaskade.gnostic.types import CUE_HIGH_ENGAGEMENT, SparkCandidate

logger = logging.getLogger(__name__)
_MODULE = "kaskade.gnostic.bayesian_rank"

# Feature `repeat_penalty` carries the penalty *amount* (1 - candidate.repeat_penalty),
# so a fresh memory (repeat_penalty=1.0) contributes 0 and a fully repeated one -0.6.
WEIGHTS: Dict[str, float] = {
    "cue_types_n": 0.4,
    "kuramoto_r": 0.5,
    "convergence_hits": 0.3,
    "theme_overlap": 0.2,
    "repeat_penalty": -0.6,
    "high_engagement": 0.15,
}
BIAS = -0.6
COHERENCE_BONUS = 0.25
COHERENCE_MIN_TYPES = 2
COHERENCE_MIN_R = 0.55
THEME_OVERLAP_CAP = 3
_LOGIT_CLAMP = 20.0

CLUSTER_CONVERGENT = "convergent"
CLUSTER_ENGAGED = "engaged"
CLUSTER_SINGLE_CUE = "single_cue"
CLUSTER_GENERIC = "generic"


def _sigmoid(x: float) -> float:
    x = max(-_LOGIT_CLAMP, min(_LOGIT_CLAMP, float(x)))
    return 1.0 / (1.0 + math.exp(-x))


def _num(value: Any, default: float) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(out) else out


def _clamp01(value: Any, default: float) -> float:
    return max(0.0, min(1.0, _num(value, default)))


def _empty_features() -> Dict[str, float]:
    return {k: 0.0 for k in WEIGHTS}


def feature_vector(candidate: SparkCandidate, *, kuramoto_r: float) -> Dict[str, float]:
    """Features: cue_types_n, kuramoto_r, convergence_hits, theme_overlap, repeat_penalty, high_engagement."""
    if not isinstance(candidate, SparkCandidate):
        log_event(
            logger,
            "WARN",
            _MODULE,
            "feature_vector",
            "invalid_candidate",
            error="expected SparkCandidate",
            got=type(candidate).__name__,
        )
        return _empty_features()
    cues = list(candidate.cues or [])
    feats = {
        "cue_types_n": float(count_cue_types(cues)),
        "kuramoto_r": _clamp01(kuramoto_r, 0.0),
        "convergence_hits": float(max(0, int(_num(candidate.convergence_hits, 0.0)))),
        "theme_overlap": float(min(THEME_OVERLAP_CAP, max(0, int(_num(candidate.theme_overlap, 0.0))))),
        "repeat_penalty": round(1.0 - _clamp01(candidate.repeat_penalty, 1.0), 4),
        "high_engagement": 1.0 if any(getattr(c, "type", None) == CUE_HIGH_ENGAGEMENT for c in cues) else 0.0,
    }
    log_event(
        logger,
        "DEBUG",
        _MODULE,
        "feature_vector",
        "computed",
        memory_id=candidate.memory_id,
        features=feats,
    )
    return feats


def _logit(feats: Dict[str, float]) -> float:
    logit = BIAS + sum(w * float(feats.get(k, 0.0)) for k, w in WEIGHTS.items())
    if feats.get("cue_types_n", 0.0) >= COHERENCE_MIN_TYPES and feats.get("kuramoto_r", 0.0) >= COHERENCE_MIN_R:
        logit += COHERENCE_BONUS
    return logit


def score(candidate: SparkCandidate, *, kuramoto_r: float) -> float:
    """P_rel in [0, 1] = sigmoid(bias + w . features)."""
    if not isinstance(candidate, SparkCandidate):
        log_event(logger, "WARN", _MODULE, "score", "invalid_candidate", error="expected SparkCandidate", p_rel=0.0)
        return 0.0
    feats = feature_vector(candidate, kuramoto_r=kuramoto_r)
    logit = _logit(feats)
    p_rel = round(_sigmoid(logit), 4)
    log_event(
        logger,
        "DEBUG",
        _MODULE,
        "score",
        "computed",
        memory_id=candidate.memory_id,
        logit=round(logit, 4),
        p_rel=p_rel,
    )
    return p_rel


def cluster_id(candidate: SparkCandidate, *, kuramoto_r: float) -> str:
    """One of: convergent | single_cue | engaged | generic."""
    if not isinstance(candidate, SparkCandidate):
        log_event(logger, "WARN", _MODULE, "cluster_id", "invalid_candidate", error="expected SparkCandidate")
        return CLUSTER_GENERIC
    feats = feature_vector(candidate, kuramoto_r=kuramoto_r)
    types_n = feats["cue_types_n"]
    if types_n >= 2 and feats["convergence_hits"] >= 1:
        cluster = CLUSTER_CONVERGENT
    elif feats["high_engagement"] >= 1.0:
        cluster = CLUSTER_ENGAGED
    elif types_n <= 1:
        cluster = CLUSTER_SINGLE_CUE
    else:
        cluster = CLUSTER_GENERIC
    log_event(logger, "DEBUG", _MODULE, "cluster_id", "computed", memory_id=candidate.memory_id, cluster_id=cluster)
    return cluster


__all__ = [
    "BIAS",
    "CLUSTER_CONVERGENT",
    "CLUSTER_ENGAGED",
    "CLUSTER_GENERIC",
    "CLUSTER_SINGLE_CUE",
    "COHERENCE_BONUS",
    "WEIGHTS",
    "cluster_id",
    "feature_vector",
    "score",
]
