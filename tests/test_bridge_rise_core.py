#!/usr/bin/env python3
"""
test_bridge_rise_core.py – Door-B invariants for fragment / tag / weather / guard / render / spread.

Created: 2026-10-20
Last updated: 2026-10-20
"""

from __future__ import annotations

from datetime import datetime, timezone

from kaskade.gnostic.demo_fixture import load_demo_fixture
from kaskade.gnostic.spreading.archival_tag_cues import build_tag_index, match_tags
from kaskade.gnostic.spreading.fragment_index import build_fragment_index, match_fragments, tokenize
from kaskade.gnostic.spreading.inject_guard import PROMPT_MARKER, InjectGuard, strip_stale_blocks
from kaskade.gnostic.spreading.recall import spread
from kaskade.gnostic.spreading.rise_render import assert_no_meta_leak, render_rise
from kaskade.gnostic.spreading.topic_weather import recurring_topics
from kaskade.gnostic.types import MemoryRecord

NOW = datetime(2026, 10, 20, 20, 0, tzinfo=timezone.utc)


def _rec(**kwargs) -> MemoryRecord:
    defaults = dict(memory_id="mem-x", content="plain note", theme_id="theme-x", privacy=2)
    defaults.update(kwargs)
    return MemoryRecord(**defaults)


def test_tokenize_stems_and_drops_stopwords():
    assert tokenize("Should we do the ridge loop this weekend?") == ["ridge", "loop", "weekend"]
    assert tokenize("") == []
    assert tokenize(None) == []  # type: ignore[arg-type]


def test_idf_size_invariant_singleton_is_one():
    from kaskade.gnostic.spreading.distinctiveness import token_idf

    small = {"ridge": ["hiking-trail"]}
    assert token_idf("ridge", small, themes_n=4) == token_idf("ridge", {"ridge": ["hiking-trail"], "other": ["z"]}, themes_n=4)
    assert token_idf("missing", small, themes_n=4) == 0.0
    assert token_idf("ridge", small, themes_n=1) == 0.0


def test_weather_spam_and_future_ignored():
    events = [
        {"ts": "2026-10-20T10:00:00Z", "topics": ["hiking"] * 50},
        {"ts": "2026-10-20T11:00:00Z", "topics": ["hiking"]},
        {"ts": "2026-10-21T10:00:00Z", "topics": ["hiking"]},
        {"ts": "not-a-date", "topics": ["hiking"]},
    ]
    counts = recurring_topics(events, now=NOW, min_count=2)
    assert counts.get("hiking") == 2
    assert recurring_topics(events, now=NOW, min_count=3) == {}


def test_tag_alone_no_fire():
    memories = [_rec(memory_id="m1", content="unrelated loaf", theme_id="sourdough-baking", tags=["starter"])]
    out = spread("starter", channel="dm:alex", memories=memories, events=[], now=NOW)
    assert out.fired is False
    assert out.reason in ("single_signal", "no_signal")


def test_fragment_alone_no_fire():
    memories = [_rec(memory_id="m1", content="ridge loop weekend", theme_id="hiking-trail", tags=[])]
    out = spread("ridge loop weekend", channel="dm:alex", memories=memories, events=[], now=NOW)
    assert out.fired is False
    assert out.reason in ("single_signal", "no_signal")


def test_climate_boost_never_fires_alone():
    memories = [
        _rec(memory_id="m1", content="ridge loop", theme_id="hiking-trail", tags=["ridge"]),
        _rec(memory_id="m2", content="sourdough starter", theme_id="sourdough-baking", tags=["starter"]),
    ]
    weather_only = spread(
        "how was your evening",
        channel="dm:alex",
        memories=memories,
        events=[{"ts": "2026-10-20T08:00:00Z", "topics": ["hiking"]}] * 3,
        now=NOW,
        climate_boost=2.0,
    )
    assert weather_only.fired is False
    assert weather_only.reason in ("single_signal", "no_signal")


def test_same_token_does_not_double_count():
    memories = [
        _rec(memory_id="m1", content="ridge view", theme_id="hiking-trail", tags=["ridge"]),
        _rec(memory_id="m2", content="export bug", theme_id="project-alpha", tags=["export"]),
    ]
    out = spread("ridge", channel="dm:alex", memories=memories, events=[], now=NOW)
    assert out.fired is False
    assert out.reason in ("single_signal", "no_signal")


def test_private_tokens_do_not_vote():
    memories = [
        _rec(memory_id="p5", content="uniquekneephrase after the descent", theme_id="hiking-trail", tags=["uniquekneephrase"], privacy=5),
        _rec(memory_id="p2", content="weekend ridge loop", theme_id="hiking-trail", tags=["weekend"], privacy=2),
        _rec(memory_id="bake", content="sourdough starter", theme_id="sourdough-baking", tags=["starter"], privacy=2),
    ]
    events = [{"ts": "2026-10-20T08:00:00Z", "topics": ["hiking"]}] * 3
    out = spread("uniquekneephrase", channel="dm:alex", memories=memories, events=events, now=NOW)
    assert out.fired is False


def test_channels_cooldown_independent():
    demo = load_demo_fixture()
    guard = InjectGuard(cooldown_s=120)
    turn = "should we do the ridge loop this weekend if my boots arrive?"
    first = spread(turn, channel="dm:alex", memories=demo.memories, events=demo.events, now=demo.now, guard=guard)
    again = spread(turn, channel="dm:alex", memories=demo.memories, events=demo.events, now=demo.now, guard=guard)
    other = spread(turn, channel="work-chat", memories=demo.memories, events=demo.events, now=demo.now, guard=guard)
    assert first.fired is True
    assert again.fired is False and again.reason == "cooldown"
    assert other.fired is True


def test_all_private_leaves_no_eligible():
    memories = [
        _rec(memory_id="p5", content="ridge loop weekend", theme_id="hiking-trail", tags=["ridge", "weekend"], privacy=5),
        _rec(memory_id="other", content="sourdough starter", theme_id="sourdough-baking", tags=["starter"], privacy=2),
        _rec(memory_id="alpha", content="export bug", theme_id="project-alpha", tags=["export"], privacy=2),
    ]
    out = spread("ridge loop weekend", channel="dm:alex", memories=memories, events=[], now=NOW)
    assert out.fired is False
    # P=5 tokens no longer vote (D1), so a private-only theme produces no spontaneous signal.
    assert out.reason in ("no_eligible_leaves", "no_signal", "single_signal")
    assert out.leaves == []


def test_huge_turn_does_not_crash():
    demo = load_demo_fixture()
    out = spread("ridge " * 20000, channel="dm:alex", memories=demo.memories, events=demo.events, now=demo.now)
    assert out.reason != "error"
    assert out.trace_id


def test_render_strips_leaks():
    leaf = _rec(
        memory_id="mem-uuid",
        content="Talked about aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee ERIP P:5 **bold**",
        recall_inject_l1="Ridge trail mem-hike-01 ERIP",
    )
    lines = render_rise([leaf])
    assert all(assert_no_meta_leak(line) for line in lines)
    assert all("ERIP" not in line and "mem-" not in line for line in lines)


def test_strip_stale_blocks():
    prompt = f"hello\n{PROMPT_MARKER}\nold rise\n## Next\nkeep"
    cleaned, n = strip_stale_blocks(prompt)
    assert n == 1
    assert PROMPT_MARKER not in cleaned
    assert "keep" in cleaned
    assert "hello" in cleaned


def test_p5_never_in_demo_fire():
    demo = load_demo_fixture()
    out = spread(
        "should we do the ridge loop this weekend if my boots arrive?",
        channel="dm:alex",
        memories=demo.memories,
        events=demo.events,
        now=demo.now,
    )
    assert out.fired is True
    assert all(leaf.privacy < 5 for leaf in out.leaves)
    assert not any("Knee" in line for line in out.inject_lines)


def test_tag_index_skips_erip_and_place():
    memories = [
        _rec(tags=["E:3", "P:5", "12", "ab", "place", "ridge-trail"], theme_id="hiking-trail"),
    ]
    index = build_tag_index(memories)
    assert "e:3" not in index
    assert "place" not in index
    assert match_tags(["ridge"], index)["hiking-trail"] == 1.0
