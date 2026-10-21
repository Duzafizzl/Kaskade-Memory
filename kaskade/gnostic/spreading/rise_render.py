#!/usr/bin/env python3
"""
rise_render.py – Render 1-2 short recall lines for a Bridge Rise (no ids, no meta leaks).

Lines that still look like metadata after cleaning are dropped (fail closed), never emitted.

Created: 2026-10-20
Last updated: 2026-10-20
"""

from __future__ import annotations

import re
from typing import List, Sequence

from kaskade.gnostic.types import MemoryRecord

# All patterns use single, bounded quantifiers (no nested repetition -> no catastrophic backtracking).
_UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_MEM_ID_RE = re.compile(r"\bmem-[A-Za-z0-9_-]{1,80}")
_ERIP_WORD_RE = re.compile(r"\bERIP\b:?", re.IGNORECASE)
_ERIP_AXIS_RE = re.compile(r"\b[ERIP]:\s?\d\b")
_EMPTY_BRACKETS_RE = re.compile(r"[\[(]\s{0,16}[\])]")
_META_KEY_RE = re.compile(r"\b(?:memory_id|trace_id)\b[^\s,;]{0,80}", re.IGNORECASE)
_MD_MARKER_RE = re.compile(r"\*\*|__|`|^#{1,6}\s?|^>\s?|^[-*]\s")
_SENTENCE_END_RE = re.compile(r"[.!?](?:\s|$)")
_WS_RE = re.compile(r"\s+")

_LEAK_ERIP_RE = re.compile(r"\bERIP\b", re.IGNORECASE)
_LEAK_META_RE = re.compile(r"memory_id|trace_id", re.IGNORECASE)

ELLIPSIS = "..."
MAX_LINES_CAP = 5


def _first_sentence(text: str) -> str:
    match = _SENTENCE_END_RE.search(text)
    return text[: match.start() + 1] if match else text


def _clean(text: str) -> str:
    out = _UUID_RE.sub(" ", text)
    out = _MEM_ID_RE.sub(" ", out)
    out = _ERIP_WORD_RE.sub(" ", out)
    out = _ERIP_AXIS_RE.sub(" ", out)
    out = _EMPTY_BRACKETS_RE.sub(" ", _WS_RE.sub(" ", out))
    out = _META_KEY_RE.sub(" ", out)
    out = _MD_MARKER_RE.sub("", out.strip())
    out = out.replace("##", " ")
    out = _WS_RE.sub(" ", out).strip(" \t-:;,|")
    return out


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    if max_chars <= len(ELLIPSIS):
        return text[:max_chars]
    cut = text[: max_chars - len(ELLIPSIS)].rstrip()
    space = cut.rfind(" ")
    if space >= (max_chars // 2):
        cut = cut[:space].rstrip(" ,;:-")
    return cut + ELLIPSIS


def render_rise(leaves: Sequence[MemoryRecord], *, max_lines: int = 2, max_chars: int = 160) -> List[str]:
    """Prefer recall_inject_l1, else first sentence of content. Strip UUIDs, ERIP blocks, markdown markers."""
    try:
        n_lines = max(1, min(MAX_LINES_CAP, int(max_lines)))
    except (TypeError, ValueError):
        n_lines = 2
    try:
        limit = max(8, int(max_chars))
    except (TypeError, ValueError):
        limit = 160
    lines: List[str] = []
    seen = set()
    for leaf in leaves or ():
        if len(lines) >= n_lines:
            break
        if not isinstance(leaf, MemoryRecord):
            continue
        source = (leaf.recall_inject_l1 or "").strip()
        if not source:
            source = _first_sentence((leaf.content or "").strip())
        line = _truncate(_clean(source), limit)
        if not line or not assert_no_meta_leak(line):
            continue
        dedupe_key = line.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        lines.append(line)
    return lines


def assert_no_meta_leak(line: str) -> bool:
    """True when line contains no UUID, no 'ERIP', no 'memory_id', no 'trace_id'."""
    if not isinstance(line, str):
        return False
    if _UUID_RE.search(line) or _MEM_ID_RE.search(line):
        return False
    if _LEAK_ERIP_RE.search(line) or _LEAK_META_RE.search(line):
        return False
    return True
