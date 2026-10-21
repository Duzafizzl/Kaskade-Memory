#!/usr/bin/env python3
"""
recall.py – Bridge Rise entry point `spread()`: collect signals, Door-B converge, guard, render.

Created: 2026-10-20
Last updated: 2026-10-20
"""

from __future__ import annotations

import logging
import math
import os
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from kaskade.gnostic._log import log_event
from kaskade.gnostic.spreading.archival_tag_cues import build_tag_index
from kaskade.gnostic.spreading.distinctiveness import token_idf
from kaskade.gnostic.spreading.fragment_index import build_fragment_index, index_theme_count, tokenize
from kaskade.gnostic.spreading.inject_guard import InjectGuard
from kaskade.gnostic.spreading.rise_render import render_rise
from kaskade.gnostic.spreading.topic_weather import match_weather_to_themes, recurring_topics
from kaskade.gnostic.types import (
    MIN_CONVERGE,
    SHARP_SIGNALS,
    SIGNAL_ARCHIVAL_TAG,
    SIGNAL_FRAGMENT,
    SIGNAL_TOPIC_WEATHER,
    MemoryRecord,
    SpreadResult,
    SpreadSignal,
    is_spontaneous_allowed,
    privacy_factor,
)

logger = logging.getLogger(__name__)
_MODULE = "kaskade.gnostic.spreading.recall"

TURN_MAX_CHARS = 4000
MIN_IDF_ENV = "KASKADE_SPREAD_MIN_IDF"
DEFAULT_MIN_IDF = 0.35
K_MIN, K_MAX = 1, 5
CLIMATE_MIN, CLIMATE_MAX = 0.5, 2.0


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        val = float(str(raw).strip())
    except ValueError:
        return default
    return val if math.isfinite(val) else default


def _clamp_k(k: Any) -> int:
    try:
        return max(K_MIN, min(K_MAX, int(k)))
    except (TypeError, ValueError):
        return 3


def _clamp_climate(value: Any) -> float:
    try:
        val = float(value)
    except (TypeError, ValueError):
        return 1.0
    if not math.isfinite(val):
        return 1.0
    return max(CLIMATE_MIN, min(CLIMATE_MAX, val))


def _as_records(memories: Sequence[Any]) -> List[MemoryRecord]:
    out: List[MemoryRecord] = []
    for mem in memories or ():
        if isinstance(mem, MemoryRecord):
            out.append(mem)
        elif isinstance(mem, dict):
            out.append(MemoryRecord.from_dict(mem))
    return out


def _emit(name: str, scores: Dict[str, float]) -> Optional[SpreadSignal]:
    themes = [t for t, s in scores.items() if t and s > 0]
    if not themes:
        return None
    return SpreadSignal(name=name, themes=sorted(themes), strength=round(sum(scores.get(t, 0.0) for t in themes), 6))


def _converged_themes(signals: Sequence[SpreadSignal]) -> List[str]:
    counts: Dict[str, int] = {}
    for sig in signals:
        if sig.name not in SHARP_SIGNALS:
            continue
        for theme in set(sig.themes):
            counts[theme] = counts.get(theme, 0) + 1
    return sorted(t for t, n in counts.items() if n >= MIN_CONVERGE)


def _theme_strength(theme: str, signals: Sequence[SpreadSignal]) -> float:
    return sum(s.strength for s in signals if theme in s.themes)


def _rank_leaves(
    memories: Sequence[MemoryRecord],
    themes: Sequence[str],
    signals: Sequence[SpreadSignal],
    climate: float,
    k: int,
) -> List[MemoryRecord]:
    theme_set = set(themes)
    scored: List[Tuple[float, str, str, MemoryRecord]] = []
    for rec in memories:
        if rec.theme_id not in theme_set or not is_spontaneous_allowed(rec.privacy):
            continue
        score = _theme_strength(rec.theme_id, signals) * privacy_factor(rec.privacy) * climate
        scored.append((score, rec.day_id or "", rec.memory_id, rec))
    # Highest score, then newest day (empty last), then memory_id.
    scored.sort(key=lambda row: (-row[0], row[1] == "", "".join(chr(155 - ord(c)) for c in row[1]) if row[1] else "", row[2]))
    return [row[3] for row in scored[:k]]


def _fragment_token_themes(tokens: Sequence[str], index: Dict[str, List[str]], min_idf: float) -> Dict[str, set]:
    themes_n = index_theme_count(index)
    out: Dict[str, set] = {}
    seen = set()
    for tok in tokens:
        if not isinstance(tok, str) or tok in seen:
            continue
        seen.add(tok)
        theme_ids = index.get(tok)
        if not theme_ids:
            continue
        idf = token_idf(tok, index, themes_n=themes_n)
        if idf < min_idf or idf <= 0.0:
            continue
        out[tok] = set(theme_ids)
    return out


def _score_from_token_themes(token_themes: Dict[str, set]) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    for themes in token_themes.values():
        for theme in themes:
            scores[theme] = scores.get(theme, 0.0) + 1.0
    return scores


def _collect_signals(
    turn_text: str,
    memories: Sequence[MemoryRecord],
    events: Optional[Sequence[Dict[str, Any]]],
    now: datetime,
) -> List[SpreadSignal]:
    tokens = tokenize(turn_text)
    min_idf = _env_float(MIN_IDF_ENV, DEFAULT_MIN_IDF)
    fragment_index = build_fragment_index(memories)
    tag_index = build_tag_index(memories)
    weather = recurring_topics(events or [], now=now)
    theme_ids = sorted({m.theme_id for m in memories if m.theme_id})
    weather_themes = match_weather_to_themes(weather, theme_ids)
    weather_scores = {t: 1.0 for t in weather_themes}

    frag_map = _fragment_token_themes(tokens, fragment_index, min_idf)
    tag_map: Dict[str, set] = {}
    seen = set()
    for tok in tokens:
        if not isinstance(tok, str) or tok in seen:
            continue
        seen.add(tok)
        hit = tag_index.get(tok)
        if not hit:
            continue
        leftover = set(hit) - frag_map.get(tok, set())
        if leftover:
            tag_map[tok] = leftover

    signals: List[SpreadSignal] = []
    for name, scores in (
        (SIGNAL_FRAGMENT, _score_from_token_themes(frag_map)),
        (SIGNAL_ARCHIVAL_TAG, _score_from_token_themes(tag_map)),
        (SIGNAL_TOPIC_WEATHER, weather_scores),
    ):
        sig = _emit(name, scores)
        if sig:
            signals.append(sig)
    return signals


def _empty(
    trace_id: str,
    reason: str,
    *,
    started: float,
    signals: Optional[List[SpreadSignal]] = None,
    themes: Optional[List[str]] = None,
) -> SpreadResult:
    return SpreadResult(
        trace_id=trace_id,
        fired=False,
        reason=reason,
        signals=list(signals or []),
        converged_themes=list(themes or []),
        duration_ms=int((time.monotonic() - started) * 1000),
    )


def spread(
    turn_text: str,
    *,
    channel: str,
    memories: Sequence[MemoryRecord],
    events: Optional[Sequence[Dict[str, Any]]] = None,
    agent_id: str = "agent",
    now: Optional[datetime] = None,
    guard: Optional[InjectGuard] = None,
    climate_boost: float = 1.0,
    k: int = 3,
) -> SpreadResult:
    """Bridge Rise. Door-B: fire only when >= MIN_CONVERGE sharp signals share a theme."""
    started = time.monotonic()
    trace_id = str(uuid.uuid4())
    turn = (turn_text if isinstance(turn_text, str) else "")[:TURN_MAX_CHARS]
    try:
        records = _as_records(memories)
        when = now or datetime.now(timezone.utc)
        climate = _clamp_climate(climate_boost)
        leaf_k = _clamp_k(k)
        signals = _collect_signals(turn, records, events, when)
        if not signals:
            result = _empty(trace_id, "no_signal", started=started)
        else:
            themes = _converged_themes(signals)
            if not themes:
                result = _empty(trace_id, "single_signal", started=started, signals=signals)
            else:
                leaves = _rank_leaves(records, themes, signals, climate, leaf_k)
                if not leaves:
                    result = _empty(trace_id, "no_eligible_leaves", started=started, signals=signals, themes=themes)
                elif guard is not None and not guard.allow(agent_id, channel):
                    result = _empty(trace_id, "cooldown", started=started, signals=signals, themes=themes)
                else:
                    lines = render_rise(leaves)
                    if guard is not None:
                        guard.mark(agent_id, channel)
                    result = SpreadResult(
                        trace_id=trace_id,
                        fired=True,
                        reason="converged",
                        signals=signals,
                        converged_themes=themes,
                        leaves=leaves,
                        inject_lines=lines,
                        duration_ms=int((time.monotonic() - started) * 1000),
                    )
        log_event(
            logger,
            "INFO",
            _MODULE,
            "spread",
            "spread_done",
            trace_id=result.trace_id,
            fired=result.fired,
            reason=result.reason,
            signals=[s.name for s in result.signals],
            converged_themes=result.converged_themes,
            leaf_ids=[leaf.memory_id for leaf in result.leaves],
            duration_ms=result.duration_ms,
            turn_chars=len(turn),
            tokens_n=len(tokenize(turn)),
        )
        return result
    except Exception as exc:
        log_event(
            logger,
            "ERROR",
            _MODULE,
            "spread",
            "spread_error",
            trace_id=trace_id,
            error=type(exc).__name__,
            error_message=str(exc)[:200],
            stack_trace=traceback.format_exc(limit=6),
        )
        return SpreadResult(trace_id=trace_id, fired=False, reason="error", duration_ms=int((time.monotonic() - started) * 1000))
