#!/usr/bin/env python3
"""
distinctiveness.py – Size-invariant token/theme IDF so common words never drive a Bridge Rise.

IDF is normalised by log1p(themes_n), so a token found in a single theme scores 1.0
regardless of archive size, and a token found in every theme scores log(2)/log1p(n).

Created: 2026-10-20
Last updated: 2026-10-20
"""

from __future__ import annotations

import math
from typing import Dict, List


def token_idf(token: str, index: Dict[str, List[str]], *, themes_n: int) -> float:
    """log1p(themes_n / df) / log1p(themes_n), in [0, 1]; 0.0 for unknown token or themes_n <= 1."""
    try:
        n = int(themes_n)
    except (TypeError, ValueError):
        return 0.0
    if n <= 1 or not isinstance(index, dict):
        return 0.0
    theme_ids = index.get(token) if isinstance(token, str) else None
    if not theme_ids:
        return 0.0
    df = min(len(set(theme_ids)), n)
    val = math.log1p(n / df) / math.log1p(n)
    return max(0.0, min(1.0, val))
