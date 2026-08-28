#!/usr/bin/env python3
"""
weighting.py – ERIP memory scoring (E/R/I/P; P = Privacy).

Created: 2026-08-28
Last updated: 2026-08-28
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

ERIP_MARKDOWN_MARKER = "**ERIP (required):**"
_ERIP_INLINE_AXIS = re.compile(r"\b([ERIP])\s*:\s*([1-5])\b", re.IGNORECASE)


@dataclass
class ERIPScores:
    """E/R/I/P on 1–5 scale. P = Privacy (higher = more sensitive)."""

    E: int = 3
    R: int = 3
    I: int = 3
    P: int = 3

    def __post_init__(self) -> None:
        for name, value in (("E", self.E), ("R", self.R), ("I", self.I), ("P", self.P)):
            if not 1 <= int(value) <= 5:
                raise ValueError(f"ERIP {name} must be 1-5, got {value}")

    def composite(self) -> float:
        return (self.E + self.R + self.I + self.P) / 4.0

    def privacy_risk(self) -> float:
        """Higher P reduces spontaneous recall weight."""
        return self.P / 5.0

    def to_dict(self) -> Dict[str, int]:
        return {"E": self.E, "R": self.R, "I": self.I, "P": self.P}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ERIPScores":
        return cls(
            E=int(data.get("E", 3)),
            R=int(data.get("R", 3)),
            I=int(data.get("I", 3)),
            P=int(data.get("P", 3)),
        )


def _extract_erip_values_from_content(content: str) -> Dict[str, int]:
    vals: Dict[str, int] = {}
    for raw in content.splitlines():
        line = raw.strip()
        if len(line) < 3 or line[1] != ":":
            continue
        axis = line[0].upper()
        if axis not in ("E", "R", "I", "P"):
            continue
        rest = line[2:].strip()
        if rest.isdigit():
            vals[axis] = max(1, min(5, int(rest)))
    for axis, num in _ERIP_INLINE_AXIS.findall(content):
        vals[axis.upper()] = max(1, min(5, int(num)))
    return vals


def parse_mandatory_erip_from_content(content: str) -> Optional[ERIPScores]:
    if not content:
        return None
    vals = _extract_erip_values_from_content(content)
    if not all(k in vals for k in ("E", "R", "I", "P")):
        return None
    return ERIPScores(E=vals["E"], R=vals["R"], I=vals["I"], P=vals["P"])


def merge_erip_tags(tags: list[str], scores: ERIPScores) -> list[str]:
    out = [t for t in tags if not re.match(r"^[ERIP]:\d$", str(t), re.I)]
    for axis, val in scores.to_dict().items():
        out.append(f"{axis}:{val}")
    return out


def archival_erip_suffix_block(e: int, r: int, i: int, p: int) -> str:
    return f"\n\n{ERIP_MARKDOWN_MARKER}\nE:{e}\nR:{r}\nI:{i}\nP:{p}\n"
