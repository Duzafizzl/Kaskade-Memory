#!/usr/bin/env python3
"""
test_gnostic_spark_pool_rank.py – Flashback pool + Spark ranking tests incl. demo end-to-end.

Created: 2026-10-20
Last updated: 2026-10-20
"""

from __future__ import annotations

import pytest

from kaskade.gnostic.demo_fixture import load_demo_fixture
from kaskade.gnostic.flashback_pool import build_pool, is_place_memory
from kaskade.gnostic.spark_rank import DEFAULT_ALPHA, kuramoto_alpha, rank_candidates
from kaskade.gnostic.types import Cue, MemoryRecord, SparkCandidate


@pytest.fixture(scope="module")
def demo():
    return load_demo_fixture()


def _ids(items):
    return [c.memory_id for c in items]


# ----------------------------------------------------------------- pool


def test_pool_theme_seed_happy(demo):
    pool = build_pool(["hiking-trail"], demo.memories, edges=demo.edges)
    ids = _ids(pool)
    assert "mem-hike-01" in ids and "mem-hike-02" in ids
    hike1 = next(c for c in pool if c.memory_id == "mem-hike-01")
    types = {c.type for c in hike1.cues}
    assert {"theme_bucket", "graph_ref"} <= types
    assert hike1.convergence_hits == len(types) - 1
    assert hike1.theme_overlap == 1


def test_pool_prefixed_theme_and_tag_and_day_seeds(demo):
    pool = build_pool(["theme:sourdough-baking", "tag:starter", "2026-10-18"], demo.memories, edges=demo.edges)
    bake2 = next(c for c in pool if c.memory_id == "mem-bake-02")
    assert {c.type for c in bake2.cues} == {"theme_bucket", "day_bucket", "day_theme_bucket", "tag", "graph_ref"}
    assert bake2.convergence_hits == 4
    assert _ids(pool)[0] == "mem-bake-02"


def test_pool_memory_seed_graph_both_directions(demo):
    pool = build_pool(["mem-alpha-01"], demo.memories, edges=demo.edges)
    ids = _ids(pool)
    assert "mem-alpha-01" not in ids  # the seed itself is not a flashback
    alpha2 = next(c for c in pool if c.memory_id == "mem-alpha-02")
    assert Cue("graph_ref", "mem-alpha-01") in alpha2.cues
    assert Cue("tag", "alpha") in alpha2.cues


def test_pool_p5_never_included(demo):
    for seeds in (["hiking-trail"], ["tag:hiking"], ["2026-10-16"], ["mem-hike-01"]):
        assert "mem-hike-03" not in _ids(build_pool(seeds, demo.memories, edges=demo.edges, allow_place=True))


def test_pool_place_gate(demo):
    lake = next(m for m in demo.memories if m.memory_id == "mem-lake-01")
    assert is_place_memory(lake)
    assert "mem-lake-01" not in _ids(build_pool(["hiking-trail"], demo.memories, edges=demo.edges))
    assert "mem-lake-01" not in _ids(build_pool(["place-lake-pier"], demo.memories, edges=demo.edges))
    with_place = build_pool(["hiking-trail"], demo.memories, edges=demo.edges, allow_place=True)
    lake_c = next(c for c in with_place if c.memory_id == "mem-lake-01")
    assert lake_c.cues == [Cue("graph_ref", "mem-hike-01")]


def test_pool_theme_prefix_place_without_tag():
    rec = MemoryRecord(memory_id="m1", content="c", theme_id="place-attic", tags=["box"], privacy=1)
    assert build_pool(["tag:box"], [rec]) == []
    assert _ids(build_pool(["tag:box"], [rec], allow_place=True)) == ["m1"]


def test_pool_empty_and_garbage_inputs(demo):
    assert build_pool([], demo.memories) == []
    assert build_pool(None, demo.memories) == []  # type: ignore[arg-type]
    assert build_pool(["hiking-trail"], []) == []
    assert build_pool(["hiking-trail"], None) == []  # type: ignore[arg-type]
    assert build_pool([None, 5, "", "  ", "theme:", "tag:"], demo.memories) == []  # type: ignore[list-item]
    assert build_pool(["unknown-theme"], demo.memories, edges=demo.edges) == []
    garbage_edges = [None, "x", {"src_node_id": "a"}, {"src_node_id": "a", "dst_node_id": "a"}]
    pool = build_pool(["hiking-trail"], demo.memories + ["junk"], edges=garbage_edges)  # type: ignore[operator]
    assert {"mem-hike-01", "mem-hike-02"} == set(_ids(pool))


def test_pool_max_pool_clamp(demo):
    seeds = ["hiking-trail", "project-alpha", "sourdough-baking"]
    assert len(build_pool(seeds, demo.memories, edges=demo.edges, max_pool=0)) == 1
    assert len(build_pool(seeds, demo.memories, edges=demo.edges, max_pool=-3)) == 1
    assert len(build_pool(seeds, demo.memories, edges=demo.edges, max_pool="junk")) == 6  # type: ignore[arg-type]


def test_pool_deterministic_under_input_permutation(demo):
    seeds = ["hiking-trail", "tag:alpha", "2026-10-18"]
    a = build_pool(seeds, demo.memories, edges=demo.edges)
    b = build_pool(list(reversed(seeds)), list(reversed(demo.memories)), edges=list(reversed(demo.edges)))
    assert [(c.memory_id, c.cues) for c in a] == [(c.memory_id, c.cues) for c in b]


# ----------------------------------------------------------------- rank


def _cand(mid: str, p: int, cues=None, repeat=1.0) -> SparkCandidate:
    rec = MemoryRecord(memory_id=mid, content="body", theme_id="t", day_id="2026-10-20", tags=["x"], privacy=p)
    cues = cues if cues is not None else [Cue("theme_bucket", "t"), Cue("tag", "x"), Cue("day_bucket", "2026-10-20")]
    return SparkCandidate(record=rec, cues=cues, convergence_hits=len({c.type for c in cues}) - 1 if cues else 0, theme_overlap=1, repeat_penalty=repeat)


def test_rank_formula_and_order(monkeypatch):
    monkeypatch.delenv("KASKADE_SPARK_KURAMOTO_ALPHA", raising=False)
    ranked = rank_candidates([_cand("mem-b", 3), _cand("mem-a", 1), _cand("mem-c", 5)])
    assert _ids(ranked) == ["mem-a", "mem-b"]
    top = ranked[0]
    expected = round(top.p_rel * (1 + DEFAULT_ALPHA * top.kuramoto_r) * top.privacy_factor * 1.0, 4)
    assert top.final_score == expected
    assert top.cue_types_n == 3 and top.cluster_id == "convergent"


def test_rank_ties_by_memory_id():
    ranked = rank_candidates([_cand("mem-z", 2), _cand("mem-a", 2), _cand("mem-m", 2)])
    assert _ids(ranked) == ["mem-a", "mem-m", "mem-z"]


def test_rank_min_score_and_repeat_penalty():
    fresh = rank_candidates([_cand("mem-a", 1)])[0].final_score
    tired = rank_candidates([_cand("mem-a", 1, repeat=0.5)])[0].final_score
    assert tired < fresh
    assert rank_candidates([_cand("mem-a", 1)], min_score=fresh + 0.01) == []
    assert len(rank_candidates([_cand("mem-a", 1)], min_score="junk")) == 1  # type: ignore[arg-type]


@pytest.mark.parametrize("raw", ["not-a-number", "nan", "inf", ""])
def test_alpha_broken_env_falls_back(monkeypatch, raw):
    monkeypatch.setenv("KASKADE_SPARK_KURAMOTO_ALPHA", raw)
    assert kuramoto_alpha() == DEFAULT_ALPHA


def test_alpha_clamped(monkeypatch):
    monkeypatch.setenv("KASKADE_SPARK_KURAMOTO_ALPHA", "9")
    assert kuramoto_alpha() == 2.0
    monkeypatch.setenv("KASKADE_SPARK_KURAMOTO_ALPHA", "-1")
    assert kuramoto_alpha() == 0.0
    ranked = rank_candidates([_cand("mem-a", 1)])
    assert ranked[0].final_score == round(ranked[0].p_rel * ranked[0].privacy_factor, 4)


def test_rank_garbage_and_unknown_cue():
    assert rank_candidates([]) == []
    assert rank_candidates(None) == []  # type: ignore[arg-type]
    ranked = rank_candidates([None, "x", _cand("mem-u", 2, cues=[Cue("made_up", "k")])])  # type: ignore[list-item]
    assert ranked == []
    two = rank_candidates([_cand("mem-u", 2, cues=[Cue("made_up", "k"), Cue("tag", "x")])])
    assert _ids(two) == ["mem-u"]


def test_rank_duplicate_memory_keeps_best():
    ranked = rank_candidates([_cand("mem-a", 1, repeat=0.2), _cand("mem-a", 1)])
    assert len(ranked) == 1 and ranked[0].candidate.repeat_penalty == 1.0


# ----------------------------------------------------------------- end-to-end


def test_demo_end_to_end_privacy_and_place(demo):
    plain = rank_candidates(build_pool(["hiking-trail"], demo.memories, edges=demo.edges))
    ids = _ids(plain)
    assert ids and ids[0] in {"mem-hike-01", "mem-hike-02"}
    assert "mem-hike-03" not in ids
    assert "mem-lake-01" not in ids

    placed = rank_candidates(build_pool(["hiking-trail", "place-lake-pier"], demo.memories, edges=demo.edges, allow_place=True))
    placed_ids = _ids(placed)
    assert "mem-lake-01" in placed_ids
    assert "mem-hike-03" not in placed_ids
    assert placed_ids.index("mem-lake-01") > placed_ids.index("mem-hike-01")


def test_demo_end_to_end_deterministic(demo):
    run = lambda: [(s.memory_id, s.final_score, s.kuramoto_r, s.p_rel) for s in rank_candidates(  # noqa: E731
        build_pool(["hiking-trail", "tag:alpha"], demo.memories, edges=demo.edges, allow_place=True)
    )]
    assert run() == run()
