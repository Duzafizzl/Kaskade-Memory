#!/usr/bin/env python3
"""
test_gnostic_spark_attribution.py – Attribution cards and spark_day EOD rollup.

Created: 2026-10-20
Last updated: 2026-10-20
"""

from __future__ import annotations

from kaskade.cascade.eod.signals import build_signal_layers
from kaskade.gnostic.attribution import build_card, convergence_summary
from kaskade.gnostic.cascade_day_summary import spark_day_summary
from kaskade.gnostic.types import Cue, MemoryRecord, ScoredCandidate, SparkCandidate


def _scored(mid: str, types: list[str], *, cluster: str = "convergent") -> ScoredCandidate:
    cues = [Cue(t, f"k-{t}") for t in types]
    rec = MemoryRecord(memory_id=mid, content="SECRET LOAF RECIPE", theme_id="t", privacy=2)
    return ScoredCandidate(
        candidate=SparkCandidate(record=rec, cues=cues, convergence_hits=1),
        kuramoto_r=0.7,
        cue_types_n=len(types),
        p_rel=0.8,
        cluster_id=cluster,
        privacy_factor=0.9,
        final_score=0.8,
    )


def test_card_has_ids_not_content():
    card = build_card(_scored("mem-a", ["theme_bucket", "tag"]), trace_id="tr-1")
    blob = str(card)
    assert card["memory_id"] == "mem-a"
    assert card["convergent"] is True
    assert "SECRET" not in blob
    assert "LOAF" not in blob
    assert "k-theme" not in blob


def test_card_invalid_input_is_empty():
    card = build_card("nope", trace_id="tr-2")  # type: ignore[arg-type]
    assert card["memory_id"] == ""
    assert card["convergent"] is False


def test_convergence_summary_empty_and_rate():
    empty = convergence_summary([])
    assert empty == {"cards_n": 0, "convergent_n": 0, "convergent_rate": 0.0, "by_cluster": {}}
    cards = [
        build_card(_scored("a", ["theme_bucket", "tag"], cluster="convergent"), trace_id="t"),
        build_card(_scored("b", ["tag"], cluster="single_cue"), trace_id="t"),
        "skip-me",
    ]
    summary = convergence_summary(cards)
    assert summary["cards_n"] == 2
    assert summary["convergent_n"] == 1
    assert summary["convergent_rate"] == 0.5
    assert summary["by_cluster"]["convergent"] == 1


def test_spark_day_from_audits_never_leaks_text():
    audits = [
        {"agent_id": "agent", "extra": {"convergent": True}, "spark_text": "Ridge trail at sunset"},
        {"agent_id": "agent", "extra": {"cue_types_n": 1}, "spark_text": "SECRET"},
        {"agent_id": "other", "extra": {"convergent": True}},
    ]
    layer = spark_day_summary("2026-10-20", agent_id="agent", audits=audits)
    assert layer["layer"] == "spark"
    assert layer["has_data"] is True
    assert layer["sparks_n"] == 2
    assert layer["convergent_n"] == 1
    assert "SECRET" not in layer["gist"]
    assert "Ridge" not in layer["gist"]


def test_spark_day_invalid_day_and_db_miss_never_raise():
    bad = spark_day_summary("not-a-day")
    assert bad["has_data"] is False
    miss = spark_day_summary("1999-01-01")
    assert miss["has_data"] is False
    assert miss["source"] in ("unavailable", "postgres")


def test_eod_registry_uses_real_spark_day():
    layers = build_signal_layers(day_id="not-a-day")
    spark = layers["spark"]
    assert spark["theme_id"] == "spark_day"
    assert spark["has_data"] is False
