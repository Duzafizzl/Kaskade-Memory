#!/usr/bin/env python3
"""
test_gnostic_spark_bayesian.py – Weighted-logit P_rel and cluster tests (happy, edge, break).

Created: 2026-10-20
Last updated: 2026-10-20
"""

from __future__ import annotations

from kaskade.gnostic.bayesian_rank import BIAS, cluster_id, feature_vector, score
from kaskade.gnostic.types import Cue, MemoryRecord, SparkCandidate


def _cand(cues, *, hits=0, overlap=0, repeat=1.0, mid="mem-x") -> SparkCandidate:
    rec = MemoryRecord(memory_id=mid, content="secret body", theme_id="t", privacy=2)
    return SparkCandidate(record=rec, cues=list(cues), convergence_hits=hits, theme_overlap=overlap, repeat_penalty=repeat)


THREE = [Cue("theme_bucket", "t"), Cue("tag", "x"), Cue("day_bucket", "2026-10-20")]


def test_feature_vector_keys_and_values():
    f = feature_vector(_cand(THREE + [Cue("high_engagement", "s")], hits=3, overlap=1), kuramoto_r=0.6)
    assert set(f) == {"cue_types_n", "kuramoto_r", "convergence_hits", "theme_overlap", "repeat_penalty", "high_engagement"}
    assert f["cue_types_n"] == 4.0
    assert f["high_engagement"] == 1.0
    assert f["repeat_penalty"] == 0.0


def test_more_evidence_scores_higher():
    weak = score(_cand([Cue("tag", "x")]), kuramoto_r=1.0)
    strong = score(_cand(THREE, hits=2, overlap=1), kuramoto_r=0.7)
    assert 0.0 <= weak < strong <= 1.0


def test_repeat_penalty_lowers_score():
    fresh = score(_cand(THREE, hits=2, overlap=1, repeat=1.0), kuramoto_r=0.5)
    repeated = score(_cand(THREE, hits=2, overlap=1, repeat=0.2), kuramoto_r=0.5)
    assert repeated < fresh


def test_no_cues_is_below_half():
    assert score(_cand([]), kuramoto_r=0.0) < 0.5
    assert BIAS < 0


def test_clusters():
    assert cluster_id(_cand(THREE, hits=2), kuramoto_r=0.5) == "convergent"
    assert cluster_id(_cand([Cue("high_engagement", "s")]), kuramoto_r=1.0) == "engaged"
    assert cluster_id(_cand([Cue("tag", "x")]), kuramoto_r=1.0) == "single_cue"
    assert cluster_id(_cand(THREE, hits=0), kuramoto_r=0.5) == "generic"


def test_garbage_inputs_no_crash():
    assert score(None, kuramoto_r=0.5) == 0.0  # type: ignore[arg-type]
    assert cluster_id("nope", kuramoto_r=0.5) == "generic"  # type: ignore[arg-type]
    c = _cand(THREE, hits="x", overlap=None, repeat="bad")  # type: ignore[arg-type]
    f = feature_vector(c, kuramoto_r="broken")  # type: ignore[arg-type]
    assert f["kuramoto_r"] == 0.0 and f["convergence_hits"] == 0.0 and f["repeat_penalty"] == 0.0
    assert 0.0 <= score(c, kuramoto_r=float("nan")) <= 1.0


def test_unknown_cue_type_counts_as_type_but_not_engagement():
    f = feature_vector(_cand([Cue("made_up", "k")]), kuramoto_r=1.0)
    assert f["cue_types_n"] == 1.0 and f["high_engagement"] == 0.0


def test_deterministic():
    c = _cand(THREE, hits=2, overlap=1)
    assert score(c, kuramoto_r=0.42) == score(c, kuramoto_r=0.42)
