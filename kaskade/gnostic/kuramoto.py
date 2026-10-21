#!/usr/bin/env python3
"""
kuramoto.py – Discrete Kuramoto order parameter R in [0, 1] for cue coherence per candidate.

Each cue gets a deterministic phase from its identity (sha256 of "type:key"). R is the
weight-normalised length of the mean phase vector: 1.0 = all cues aligned, ~0 = scattered.
No ODE integration; one closed-form value per candidate.

Created: 2026-10-20
Last updated: 2026-10-20
"""

from __future__ import annotations

import hashlib
import logging
import math
from typing import Any, Dict, Sequence

from kaskade.gnostic._log import log_event
from kaskade.gnostic.types import (
    CUE_DAY_BUCKET,
    CUE_DAY_THEME_BUCKET,
    CUE_GRAPH_REF,
    CUE_HIGH_ENGAGEMENT,
    CUE_TAG,
    CUE_THEME_BUCKET,
    Cue,
)

logger = logging.getLogger(__name__)
_MODULE = "kaskade.gnostic.kuramoto"

CUE_TYPE_WEIGHTS: Dict[str, float] = {
    CUE_THEME_BUCKET: 1.0,
    CUE_DAY_THEME_BUCKET: 0.95,
    CUE_DAY_BUCKET: 0.9,
    CUE_TAG: 0.85,
    CUE_HIGH_ENGAGEMENT: 0.75,
    CUE_GRAPH_REF: 0.55,
}
UNKNOWN_CUE_WEIGHT = 0.5
_STRENGTH_MIN = 0.1
_STRENGTH_MAX = 2.0
_PHASE_SCALE = float(0xFFFFFFFF)


def _is_cue(obj: Any) -> bool:
    return isinstance(obj, Cue)


def cue_weight(cue: Cue) -> float:
    """Type weight times the cue's own strength clamped to [0.1, 2.0]."""
    base = CUE_TYPE_WEIGHTS.get(str(cue.type or ""), UNKNOWN_CUE_WEIGHT)
    try:
        strength = float(cue.weight)
    except (TypeError, ValueError):
        strength = 1.0
    if math.isnan(strength):
        strength = 1.0
    strength = max(_STRENGTH_MIN, min(_STRENGTH_MAX, strength))
    return base * strength


def cue_phase(cue: Cue) -> float:
    """Deterministic phase in [0, 2*pi) from (type, key) via sha256."""
    raw = f"{cue.type}:{cue.key}".encode("utf-8")
    bucket = int(hashlib.sha256(raw).hexdigest()[:8], 16) / _PHASE_SCALE
    phase = 2.0 * math.pi * bucket
    # 0xFFFFFFFF maps to exactly 2*pi; fold it back so the range stays half-open.
    return 0.0 if phase >= 2.0 * math.pi else phase


def order_parameter(cues: Sequence[Cue]) -> float:
    """Weighted |mean(e^{i*theta})| over cues; 0.0 for empty input."""
    valid = [c for c in (cues or []) if _is_cue(c)]
    if not valid:
        log_event(logger, "DEBUG", _MODULE, "order_parameter", "empty_cues", cues_n=0, r=0.0)
        return 0.0
    sum_re = 0.0
    sum_im = 0.0
    weight_sum = 0.0
    for cue in valid:
        w = cue_weight(cue)
        theta = cue_phase(cue)
        sum_re += w * math.cos(theta)
        sum_im += w * math.sin(theta)
        weight_sum += w
    if weight_sum <= 0.0:
        return 0.0
    r = round(max(0.0, min(1.0, math.hypot(sum_re, sum_im) / weight_sum)), 4)
    log_event(
        logger,
        "DEBUG",
        _MODULE,
        "order_parameter",
        "computed",
        cues_n=len(valid),
        skipped_n=len(cues or []) - len(valid),
        r=r,
    )
    return r


def count_cue_types(cues: Sequence[Cue]) -> int:
    """Number of distinct cue types present (independent evidence paths)."""
    n = len({str(c.type) for c in (cues or []) if _is_cue(c) and c.type})
    log_event(logger, "DEBUG", _MODULE, "count_cue_types", "computed", cue_types_n=n)
    return n


__all__ = [
    "CUE_TYPE_WEIGHTS",
    "UNKNOWN_CUE_WEIGHT",
    "count_cue_types",
    "cue_phase",
    "cue_weight",
    "order_parameter",
]
