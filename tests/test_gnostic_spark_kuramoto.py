#!/usr/bin/env python3
"""
test_gnostic_spark_kuramoto.py – Kuramoto phase/order-parameter tests (happy, edge, break).

Created: 2026-10-20
Last updated: 2026-10-20
"""

from __future__ import annotations

import hashlib
import math

from kaskade.gnostic.kuramoto import (
    CUE_TYPE_WEIGHTS,
    UNKNOWN_CUE_WEIGHT,
    count_cue_types,
    cue_phase,
    cue_weight,
    order_parameter,
)
from kaskade.gnostic.types import SPARK_CUE_TYPES, Cue


def test_phase_matches_spec_formula():
    cue = Cue("theme_bucket", "hiking-trail")
    expected = 2 * math.pi * int(hashlib.sha256(b"theme_bucket:hiking-trail").hexdigest()[:8], 16) / 0xFFFFFFFF
    assert math.isclose(cue_phase(cue), expected)
    assert 0.0 <= cue_phase(cue) < 2 * math.pi


def test_phase_deterministic_and_type_sensitive():
    a = Cue("tag", "hiking")
    assert cue_phase(a) == cue_phase(Cue("tag", "hiking"))
    assert cue_phase(a) != cue_phase(Cue("theme_bucket", "hiking"))


def test_single_cue_is_fully_coherent():
    assert order_parameter([Cue("tag", "x")]) == 1.0


def test_identical_cues_coherent_and_range():
    assert order_parameter([Cue("tag", "x"), Cue("tag", "x", weight=2.0)]) == 1.0
    r = order_parameter([Cue("theme_bucket", "a"), Cue("tag", "b"), Cue("day_bucket", "2026-10-20")])
    assert 0.0 <= r <= 1.0
    assert r == round(r, 4)


def test_empty_and_garbage_input():
    assert order_parameter([]) == 0.0
    assert order_parameter(None) == 0.0  # type: ignore[arg-type]
    assert order_parameter(["not-a-cue", 3, None]) == 0.0  # type: ignore[list-item]
    assert count_cue_types([]) == 0
    assert count_cue_types(None) == 0  # type: ignore[arg-type]


def test_weights_cover_all_contract_cue_types_and_unknown_default():
    assert set(CUE_TYPE_WEIGHTS) == set(SPARK_CUE_TYPES)
    assert cue_weight(Cue("made_up_type", "k")) == UNKNOWN_CUE_WEIGHT
    assert cue_weight(Cue("theme_bucket", "k", weight=99.0)) == 2.0
    assert cue_weight(Cue("theme_bucket", "k", weight=-5.0)) == 0.1
    assert cue_weight(Cue("theme_bucket", "k", weight="junk")) == 1.0  # type: ignore[arg-type]


def test_unknown_cue_type_does_not_crash():
    r = order_parameter([Cue("made_up_type", "k"), Cue("tag", "x")])
    assert 0.0 <= r <= 1.0
    assert count_cue_types([Cue("made_up_type", "k"), Cue("tag", "x"), Cue("tag", "y")]) == 2
