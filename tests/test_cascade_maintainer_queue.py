#!/usr/bin/env python3
"""
test_cascade_maintainer_queue.py – M1 queue attempts/retry for cascade maintainer.

Created: 2026-07-01
Last updated: 2026-07-01
"""

from __future__ import annotations

from pathlib import Path

import pytest

import kaskade.cascade.maintainer.queue as q


@pytest.fixture
def queue_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "cascade_maintainer_queue.jsonl"
    monkeypatch.setenv("CASCADE_MAINTAINER_QUEUE_PATH", str(p))
    monkeypatch.setenv("CASCADE_MAINTAINER_MAX_ATTEMPTS", "3")
    return p


def test_enqueue_has_attempts_zero(queue_tmp: Path) -> None:
    r = q.enqueue_cascade_link(
        memory_id="mem-test-0001",
        episode_date="2026-07-01",
        person_id="alex",
        theme_id="theme_test",
    )
    assert r.get("memory_id") == "mem-test-0001"
    rows = q.read_queue()
    assert len(rows) == 1
    assert rows[0]["attempts"] == 0
    assert rows[0]["status"] == "pending"


def test_record_link_failure_retries_then_needs_human(queue_tmp: Path) -> None:
    q.enqueue_cascade_link(
        memory_id="mem-test-0002",
        episode_date="2026-07-01",
        person_id="alex",
        theme_id="theme_test",
    )
    item = q.read_queue()[0]
    item_id = item["id"]

    assert q.record_link_failure(item_id, item, error="e1") == "pending"
    item = q.read_queue(status="pending")[0]
    assert item["attempts"] == 1

    q.record_link_failure(item_id, item, error="e2")
    item = q.read_queue(status="pending")[0]
    assert item["attempts"] == 2

    final = q.record_link_failure(item_id, item, error="e3")
    assert final == "needs_human"
    nh = q.read_queue(status="needs_human")
    assert len(nh) == 1
    assert nh[0]["attempts"] == 3


def test_list_pending_includes_linking(queue_tmp: Path) -> None:
    q.enqueue_cascade_link(
        memory_id="mem-test-0003",
        episode_date="2026-07-01",
        person_id="alex",
        theme_id="theme_test",
    )
    item = q.read_queue()[0]
    q.update_queue_item(item["id"], status="linking")
    pending = q.list_pending()
    assert len(pending) == 1
    assert pending[0]["status"] == "linking"
