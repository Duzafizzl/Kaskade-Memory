#!/usr/bin/env python3
"""Tests for ERIP parsing (P = Privacy)."""

from kaskade.erip.weighting import ERIPScores, parse_mandatory_erip_from_content


def test_parse_erip():
    content = "Note\nE:4\nR:3\nI:3\nP:5\n"
    scores = parse_mandatory_erip_from_content(content)
    assert scores is not None
    assert scores.P == 5
    assert scores.privacy_risk() == 1.0


def test_composite():
    s = ERIPScores(E=4, R=4, I=4, P=2)
    assert s.composite() == 3.5
