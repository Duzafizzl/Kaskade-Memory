#!/usr/bin/env python3
"""
test_gnostic_contract.py – Frozen invariants for Gnostic Spark + Bridge Rise (parent-owned acceptance tests).

Created: 2026-10-20
Last updated: 2026-10-20
"""

from __future__ import annotations

from kaskade.gnostic.demo_fixture import load_demo_fixture
from kaskade.gnostic.types import (
    Cue,
    MemoryRecord,
    SparkCandidate,
    clamp_privacy,
    is_spontaneous_allowed,
    privacy_factor,
)


def test_privacy_factor_monotonic_and_p5_blocked():
    factors = [privacy_factor(p) for p in range(1, 6)]
    assert factors == sorted(factors, reverse=True)
    assert privacy_factor(5) == 0.0
    assert not is_spontaneous_allowed(5)
    assert clamp_privacy("garbage") == 3
    assert clamp_privacy(99) == 5


def _cand(mid: str, p: int) -> SparkCandidate:
    rec = MemoryRecord(memory_id=mid, content="same content", theme_id="t", day_id="2026-10-20", tags=["x"], privacy=p)
    cues = [Cue("theme_bucket", "t"), Cue("tag", "x"), Cue("day_bucket", "2026-10-20")]
    return SparkCandidate(record=rec, cues=cues, convergence_hits=1, theme_overlap=1)


def test_privacy_p_demotes_spark():
    from kaskade.gnostic.spark_rank import rank_candidates

    ranked = rank_candidates([_cand("mem-b", 4), _cand("mem-a", 1), _cand("mem-c", 5)])
    ids = [s.memory_id for s in ranked]
    assert ids[0] == "mem-a"
    assert "mem-c" not in ids
    assert ranked[0].final_score > ranked[1].final_score


def test_weather_alone_no_fire():
    from kaskade.gnostic.spreading.recall import spread

    demo = load_demo_fixture()
    out = spread("how was your evening", channel="dm:alex", memories=demo.memories, events=demo.events, now=demo.now)
    assert out.fired is False
    assert out.reason in ("single_signal", "no_signal")


def test_converge_fires_and_respects_privacy():
    from kaskade.gnostic.spreading.recall import spread

    demo = load_demo_fixture()
    out = spread(
        "should we do the ridge loop this weekend if my boots arrive?",
        channel="dm:alex",
        memories=demo.memories,
        events=demo.events,
        now=demo.now,
    )
    assert out.fired is True
    assert "hiking-trail" in out.converged_themes
    assert len({s.name for s in out.signals if s.sharp and "hiking-trail" in s.themes}) >= 2
    assert all(leaf.privacy < 5 for leaf in out.leaves)
    assert not any("Knee" in line for line in out.inject_lines)
    assert 1 <= len(out.inject_lines) <= 2
