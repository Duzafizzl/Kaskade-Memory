#!/usr/bin/env python3
"""
test_gnostic_spark_delivery.py – Spark delivery hooks and shadow cooldown.

Created: 2026-10-20
Last updated: 2026-10-20
"""

from __future__ import annotations

from kaskade.gnostic.delivery import drain_next_turn, get_delivery, reset_next_turn_for_tests
from kaskade.gnostic.demo_fixture import load_demo_fixture
from kaskade.gnostic.shadow import generate_spark_from_graph, maybe_generate_spark, reset_spark_cooldown_for_tests
from kaskade.gnostic.types import SparkResult


def setup_function() -> None:
    reset_spark_cooldown_for_tests()
    reset_next_turn_for_tests()


def test_next_turn_queues_and_drains():
    hook = get_delivery("next_turn")
    result = SparkResult(trace_id="t1", memory_id="mem-a", spark_text="hello", score=0.5, delivery="next_turn")
    assert hook.deliver(result, agent_id="agent") is True
    queued = drain_next_turn("agent")
    assert [q.memory_id for q in queued] == ["mem-a"]
    assert drain_next_turn("agent") == []


def test_unknown_mode_falls_back_to_log():
    assert get_delivery("telepathy").name == "log"


def test_webhook_rejects_non_https_remote():
    hook = get_delivery("webhook")
    # No URL / private http host: fail closed, never raise.
    result = SparkResult(trace_id="t", memory_id="m", spark_text="x", score=0.1, delivery="webhook")
    assert hook.deliver(result, agent_id="agent") is False


def test_webhook_rejects_private_https(monkeypatch):
    from kaskade.gnostic.delivery import WEBHOOK_ENV, WebhookDelivery
    from kaskade.gnostic.types import SparkResult

    monkeypatch.setenv(WEBHOOK_ENV, "https://10.0.0.1/hook")
    hook = WebhookDelivery()
    result = SparkResult(trace_id="t", memory_id="m", spark_text="x", score=0.1, delivery="webhook")
    assert hook.deliver(result, agent_id="agent") is False


def test_shadow_cooldown_and_p5_excluded():
    demo = load_demo_fixture()
    first = generate_spark_from_graph(agent_id="agent", seeds=["hiking-trail"], memories=demo.memories, edges=demo.edges)
    assert first is not None
    assert first["memory_id"] != "mem-hike-03"
    second = generate_spark_from_graph(agent_id="agent", seeds=["hiking-trail"], memories=demo.memories, edges=demo.edges)
    assert second is None


def test_place_only_when_allowed():
    from kaskade.gnostic.flashback_pool import build_pool

    demo = load_demo_fixture()
    denied_ids = {c.memory_id for c in build_pool(["place-lake-pier"], demo.memories, edges=demo.edges, allow_place=False)}
    allowed_ids = {c.memory_id for c in build_pool(["place-lake-pier"], demo.memories, edges=demo.edges, allow_place=True)}
    assert "mem-lake-01" not in denied_ids
    assert "mem-lake-01" in allowed_ids


def test_empty_candidates_none():
    assert maybe_generate_spark(agent_id="agent", candidates=[]) is None


def test_single_cue_does_not_spark():
    reset_spark_cooldown_for_tests()
    spark = maybe_generate_spark(
        agent_id="agent",
        candidates=[
            {
                "memory_id": "mem-one",
                "content": "only one cue",
                "privacy": 1,
                "recall_inject_l1": "one cue",
                "cues": [{"type": "graph_ref", "key": "mem-one"}],
            }
        ],
    )
    assert spark is None


def test_webhook_refuses_redirect(monkeypatch):
    import os
    import urllib.error

    from kaskade.gnostic.delivery import WEBHOOK_ENV, WebhookDelivery, _WEBHOOK_OPENER
    from kaskade.gnostic.types import SparkResult

    monkeypatch.setenv(WEBHOOK_ENV, "https://example.invalid/hook")

    def _open(_req, timeout=3.0):
        raise urllib.error.HTTPError("https://example.invalid/hook", 302, "redirect_refused", {}, None)

    monkeypatch.setattr(_WEBHOOK_OPENER, "open", _open)
    hook = WebhookDelivery()
    result = SparkResult(trace_id="t", memory_id="m", spark_text="x", score=0.1, delivery="webhook")
    assert hook.deliver(result, agent_id="agent") is False
    assert os.getenv(WEBHOOK_ENV).startswith("https://")
