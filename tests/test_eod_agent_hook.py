#!/usr/bin/env python3
"""Tests for generic EOD agent hook."""

from kaskade.cascade.eod.agent_hook import NoOpAdapter, SubprocessAdapter


def test_noop_adapter():
    hook = NoOpAdapter()
    r = hook.run_maintainer_pass(day_id="2026-08-01", prompt="hi", allowed_paths=[], timeout_sec=5)
    assert r.ok


def test_subprocess_echo(monkeypatch):
    monkeypatch.setenv("KASKADE_EOD_AGENT_CMD", "echo ok")
    hook = SubprocessAdapter()
    r = hook.run_maintainer_pass(day_id="2026-08-01", prompt="hi", allowed_paths=[], timeout_sec=5)
    assert r.ok
