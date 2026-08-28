#!/usr/bin/env python3
"""
test_cascade_significance_gate.py – M2 significance gate before cascade enqueue.

Created: 2026-07-18
Last updated: 2026-07-18
"""

from __future__ import annotations

from pathlib import Path

import pytest

import kaskade.cascade.maintainer.queue as q
import kaskade.reflex.significance_gate as gate


def _erip_block(e: int = 3, r: int = 3, i: int = 3, p: int = 3) -> str:
    return f"E:{e}\nR:{r}\nI:{i}\nP:{p}\n"


@pytest.fixture(autouse=True)
def _clean_gate():
    gate.reset_gate_state_for_tests()
    yield
    gate.reset_gate_state_for_tests()


@pytest.fixture
def queue_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "cascade_maintainer_queue.jsonl"
    monkeypatch.setenv("CASCADE_MAINTAINER_QUEUE_PATH", str(p))
    return p


def test_theme_erip_ok_passes():
    content = "Alex and Sam discussed the roadmap.\n" + _erip_block(4, 4, 3, 3)
    out = gate.evaluate_cascade_significance(
        content=content,
        recall_inject_l1="Alex SOCD Mini-1 iBoot abort evening",
        theme_id="mac-socd",
        memory_id="mem-pass-1",
    )
    assert out["decision"] == "pass"
    assert out["reason"] == "theme_erip_ok"


def test_exact_dup_rejects():
    content = "Unique archival body for dup test aaa.\n" + _erip_block()
    l1 = "Unique L1 line for exact dup test alpha"
    first = gate.evaluate_cascade_significance(
        content=content, recall_inject_l1=l1, theme_id="theme_a"
    )
    assert first["decision"] == "pass"
    second = gate.evaluate_cascade_significance(
        content=content,
        recall_inject_l1=l1 + " slightly different",
        theme_id="theme_a",
    )
    assert second["decision"] == "reject"
    assert second["reason"] == "exact_dup"


def test_near_dup_l1_defers():
    base_l1 = "Alex and Agent talked about the Mac SOCD panic at twenty twelve"
    a = gate.evaluate_cascade_significance(
        content="First memory about SOCD.\n" + _erip_block(4, 3, 3, 2),
        recall_inject_l1=base_l1,
        theme_id="mac-socd",
    )
    assert a["decision"] == "pass"
    b = gate.evaluate_cascade_significance(
        content="Second different body about SOCD.\n" + _erip_block(4, 3, 3, 2),
        recall_inject_l1=base_l1 + "!",
        theme_id="mac-socd",
    )
    assert b["decision"] == "defer_eod"
    assert b["reason"] == "near_dup_l1"


def test_missing_theme_defers():
    out = gate.evaluate_cascade_significance(
        content="Memory without theme but solid ERIP.\n" + _erip_block(4, 4, 4, 3),
        recall_inject_l1="Solid L1 Wer Was Wann ohne Theme",
        theme_id=None,
    )
    assert out["decision"] == "defer_eod"
    assert out["reason"] == "missing_theme_id"


def test_low_erip_no_theme_defers():
    out = gate.evaluate_cascade_significance(
        content="Low gravity factoid.\n" + _erip_block(1, 1, 1, 1),
        recall_inject_l1="Low ERIP L1 without theme id here",
        theme_id=None,
    )
    assert out["decision"] == "defer_eod"
    assert out["reason"] == "low_erip_no_theme"


def test_erip_unparseable_rejects():
    out = gate.evaluate_cascade_significance(
        content="No ERIP lines at all in this archival text.",
        recall_inject_l1="Some L1 without ERIP axes lines",
        theme_id="theme_x",
    )
    assert out["decision"] == "reject"
    assert out["reason"] == "erip_unparseable"


def test_kill_switch_off_always_passes(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CASCADE_SIGNIFICANCE_GATE_ENABLED", "false")
    out = gate.evaluate_cascade_significance(
        content="No ERIP and no theme — still pass when disabled.",
        recall_inject_l1="",
        theme_id=None,
    )
    assert out["decision"] == "pass"
    assert out["reason"] == "gate_disabled"


def test_theme_fast_path():
    content1 = "First hit on theme cache.\n" + _erip_block(3, 3, 3, 3)
    a = gate.evaluate_cascade_significance(
        content=content1,
        recall_inject_l1="First L1 for theme fast path cache seed",
        theme_id="nested_learning",
    )
    assert a["decision"] == "pass"
    content2 = "Second hit different body.\n" + _erip_block(3, 3, 3, 3)
    b = gate.evaluate_cascade_significance(
        content=content2,
        recall_inject_l1="Second totally different L1 for fast path",
        theme_id="nested_learning",
    )
    assert b["decision"] == "pass"
    assert b["reason"] == "theme_fast_path"


def test_enqueue_with_initial_status_deferred_eod(queue_tmp: Path) -> None:
    r = q.enqueue_cascade_link(
        memory_id="mem-gate-defer-1",
        episode_date="2026-07-18",
        person_id="alex",
        theme_id=None,
        initial_status="deferred_eod",
        reason="missing_theme_id",
    )
    assert r.get("memory_id") == "mem-gate-defer-1"
    rows = q.read_queue()
    assert len(rows) == 1
    assert rows[0]["status"] == "deferred_eod"
    assert rows[0].get("reason") == "missing_theme_id"
