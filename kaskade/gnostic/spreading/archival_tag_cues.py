#!/usr/bin/env python3
"""
archival_tag_cues.py – Match turn tokens against archival tags (signal `archival_tag`).

The tag index maps each normalised tag and each of its segments (split on '-' / '_')
to theme ids, so matching is one dict lookup per token: O(tokens + tags), not O(tokens * tags).

Created: 2026-10-20
Last updated: 2026-10-20
"""

from __future__ import annotations

import re
from typing import Dict, List, Sequence

from kaskade.gnostic.spreading.fragment_index import MIN_TOKEN_LEN, STOPWORDS, stem
from kaskade.gnostic.types import MemoryRecord, is_spontaneous_allowed

# ERIP axis tags written at archival insert, e.g. "E:3", "P:5" (no nested quantifiers).
_ERIP_AXIS_RE = re.compile(r"^[erip]:\d$")
_SEGMENT_SPLIT_RE = re.compile(r"[-_\s]+")

# Tags that describe the kind of memory rather than its subject; they would match everything.
GENERIC_TAGS = frozenset({"place"})

MAX_HITS_CAP = 50


def _normalize_tag(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    norm = tag.strip().lower()
    if not norm or len(norm) < MIN_TOKEN_LEN:
        return ""
    if _ERIP_AXIS_RE.match(norm) or norm.isdigit() or norm in GENERIC_TAGS:
        return ""
    return norm


def _tag_keys(norm: str) -> List[str]:
    """Lookup keys for one tag: the stemmed full tag plus each stemmed segment."""
    keys = [stem(norm)]
    segments = [s for s in _SEGMENT_SPLIT_RE.split(norm) if s]
    if len(segments) > 1:
        for seg in segments:
            if len(seg) < MIN_TOKEN_LEN or seg.isdigit() or seg in STOPWORDS or seg in GENERIC_TAGS:
                continue
            keys.append(stem(seg))
    return keys


def build_tag_index(memories: Sequence[MemoryRecord]) -> Dict[str, List[str]]:
    """normalized tag -> sorted theme_ids. Excludes ERIP axis tags (E:3 ...), numeric ids, tags < 3 chars."""
    acc: Dict[str, set] = {}
    for rec in memories or ():
        if isinstance(rec, dict):
            rec = MemoryRecord.from_dict(rec)
        if not isinstance(rec, MemoryRecord):
            continue
        if not is_spontaneous_allowed(rec.privacy):
            continue
        theme = (rec.theme_id or "").strip()
        if not theme:
            continue
        for tag in rec.tags or ():
            norm = _normalize_tag(tag)
            if not norm:
                continue
            for key in _tag_keys(norm):
                acc.setdefault(key, set()).add(theme)
    return {key: sorted(themes) for key, themes in acc.items()}


def match_tags(tokens: Sequence[str], tag_index: Dict[str, List[str]], *, max_hits: int = 6) -> Dict[str, float]:
    """theme_id -> hit count (exact token==tag or tag split on - / _ contains token). O(tokens + tags)."""
    if not tokens or not isinstance(tag_index, dict) or not tag_index:
        return {}
    try:
        cap = int(max_hits)
    except (TypeError, ValueError):
        cap = 6
    cap = max(1, min(MAX_HITS_CAP, cap))
    hits: Dict[str, float] = {}
    total = 0
    seen = set()
    for tok in tokens:
        if not isinstance(tok, str) or tok in seen:
            continue
        seen.add(tok)
        theme_ids = tag_index.get(tok)
        if not theme_ids:
            continue
        for theme in theme_ids:
            hits[theme] = hits.get(theme, 0.0) + 1.0
            total += 1
            if total >= cap:
                return hits
    return hits
