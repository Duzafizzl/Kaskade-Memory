#!/usr/bin/env python3
"""
types.py – Frozen shared contract for Gnostic Spark and Bridge Rise (dataclasses, cue names, privacy curve).

Every gnostic/* and gnostic/spreading/* module imports its shared shapes from here.
Changing a name or field in this file is a contract change owned by the parent integrator.

Created: 2026-10-20
Last updated: 2026-10-20
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Cue types (Spark ranking). `high_engagement` is a neutral session-intensity cue.
# ---------------------------------------------------------------------------
CUE_THEME_BUCKET = "theme_bucket"
CUE_DAY_BUCKET = "day_bucket"
CUE_DAY_THEME_BUCKET = "day_theme_bucket"
CUE_TAG = "tag"
CUE_GRAPH_REF = "graph_ref"
CUE_HIGH_ENGAGEMENT = "high_engagement"

SPARK_CUE_TYPES = (
    CUE_THEME_BUCKET,
    CUE_DAY_BUCKET,
    CUE_DAY_THEME_BUCKET,
    CUE_TAG,
    CUE_GRAPH_REF,
    CUE_HIGH_ENGAGEMENT,
)

# ---------------------------------------------------------------------------
# Bridge Rise signals. Door-B: fire only when >= MIN_CONVERGE distinct SHARP
# signals agree on at least one theme. Climate is rank-only and never counts.
# ---------------------------------------------------------------------------
SIGNAL_FRAGMENT = "fragment"
SIGNAL_ARCHIVAL_TAG = "archival_tag"
SIGNAL_TOPIC_WEATHER = "topic_weather"
SIGNAL_CLIMATE = "climate"

SHARP_SIGNALS = (SIGNAL_FRAGMENT, SIGNAL_ARCHIVAL_TAG, SIGNAL_TOPIC_WEATHER)
RANK_ONLY_SIGNALS = (SIGNAL_CLIMATE,)
MIN_CONVERGE = 2

# ---------------------------------------------------------------------------
# Privacy (ERIP P axis, 1..5). Higher P = more sensitive = less spontaneous.
# P >= PRIVACY_NEVER_SPONTANEOUS_P is never surfaced by Spark or Bridge Rise.
# ---------------------------------------------------------------------------
PRIVACY_DEFAULT_P = 3
PRIVACY_NEVER_SPONTANEOUS_P = 5
_PRIVACY_FACTORS: Dict[int, float] = {1: 1.0, 2: 0.9, 3: 0.7, 4: 0.35, 5: 0.0}


def clamp_privacy(p: Any) -> int:
    """Coerce any input into the 1..5 ERIP P range; unknown -> default."""
    try:
        val = int(p)
    except (TypeError, ValueError):
        return PRIVACY_DEFAULT_P
    return max(1, min(5, val))


def privacy_factor(p: Any) -> float:
    """Multiplicative rank factor in [0, 1] for spontaneous surfacing."""
    return _PRIVACY_FACTORS[clamp_privacy(p)]


def is_spontaneous_allowed(p: Any) -> bool:
    return clamp_privacy(p) < PRIVACY_NEVER_SPONTANEOUS_P


# ---------------------------------------------------------------------------
# Shared records
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Cue:
    type: str
    key: str
    weight: float = 1.0


@dataclass
class MemoryRecord:
    memory_id: str
    content: str
    theme_id: str = ""
    day_id: str = ""
    person_id: str = ""
    tags: List[str] = field(default_factory=list)
    privacy: int = PRIVACY_DEFAULT_P
    recall_inject_l1: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryRecord":
        erip = data.get("erip") if isinstance(data.get("erip"), dict) else {}
        return cls(
            memory_id=str(data.get("memory_id") or data.get("id") or ""),
            content=str(data.get("content") or ""),
            theme_id=str(data.get("theme_id") or ""),
            day_id=str(data.get("day_id") or data.get("episode_date") or ""),
            person_id=str(data.get("person_id") or ""),
            tags=[str(t) for t in (data.get("tags") or [])],
            privacy=clamp_privacy(data.get("privacy", erip.get("P", PRIVACY_DEFAULT_P))),
            recall_inject_l1=str(data.get("recall_inject_l1") or ""),
        )


@dataclass
class SparkCandidate:
    record: MemoryRecord
    cues: List[Cue] = field(default_factory=list)
    convergence_hits: int = 0
    theme_overlap: int = 0
    repeat_penalty: float = 1.0

    @property
    def memory_id(self) -> str:
        return self.record.memory_id


@dataclass
class ScoredCandidate:
    candidate: SparkCandidate
    kuramoto_r: float
    cue_types_n: int
    p_rel: float
    cluster_id: str
    privacy_factor: float
    final_score: float

    @property
    def memory_id(self) -> str:
        return self.candidate.memory_id


@dataclass
class SparkResult:
    trace_id: str
    memory_id: str
    spark_text: str
    score: float
    delivery: str
    cue_types_n: int = 0
    kuramoto_r: float = 0.0
    p_rel: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SpreadSignal:
    name: str
    themes: List[str]
    strength: float = 1.0

    @property
    def sharp(self) -> bool:
        return self.name in SHARP_SIGNALS


@dataclass
class SpreadResult:
    trace_id: str
    fired: bool
    reason: str
    signals: List[SpreadSignal] = field(default_factory=list)
    converged_themes: List[str] = field(default_factory=list)
    leaves: List[MemoryRecord] = field(default_factory=list)
    inject_lines: List[str] = field(default_factory=list)
    duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "fired": self.fired,
            "reason": self.reason,
            "signals": [{"name": s.name, "themes": list(s.themes), "strength": s.strength} for s in self.signals],
            "converged_themes": list(self.converged_themes),
            "leaf_ids": [leaf.memory_id for leaf in self.leaves],
            "inject_lines": list(self.inject_lines),
            "duration_ms": self.duration_ms,
        }


__all__ = [
    "CUE_DAY_BUCKET",
    "CUE_DAY_THEME_BUCKET",
    "CUE_GRAPH_REF",
    "CUE_HIGH_ENGAGEMENT",
    "CUE_TAG",
    "CUE_THEME_BUCKET",
    "Cue",
    "MIN_CONVERGE",
    "MemoryRecord",
    "PRIVACY_DEFAULT_P",
    "PRIVACY_NEVER_SPONTANEOUS_P",
    "RANK_ONLY_SIGNALS",
    "SHARP_SIGNALS",
    "SIGNAL_ARCHIVAL_TAG",
    "SIGNAL_CLIMATE",
    "SIGNAL_FRAGMENT",
    "SIGNAL_TOPIC_WEATHER",
    "SPARK_CUE_TYPES",
    "ScoredCandidate",
    "SparkCandidate",
    "SparkResult",
    "SpreadResult",
    "SpreadSignal",
    "clamp_privacy",
    "is_spontaneous_allowed",
    "privacy_factor",
]
