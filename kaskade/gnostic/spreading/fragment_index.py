#!/usr/bin/env python3
"""
fragment_index.py – Token -> themes index over archival memories (signal `fragment`).

The index is a search structure for spontaneous Rise only: memories that are not
spontaneous-allowed (P=5) are omitted so their tokens cannot vote.

Created: 2026-10-20
Last updated: 2026-10-20
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Sequence

from kaskade.gnostic.spreading.distinctiveness import token_idf
from kaskade.gnostic.types import MemoryRecord, is_spontaneous_allowed

# Letters/digits only (underscore is a separator, like '-' and whitespace). Single quantifier, linear time.
_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)

MIN_TOKEN_LEN = 3

STOPWORDS = frozenset(
    {
        "about", "all", "also", "and", "any", "are", "been", "but", "can", "could", "day",
        "did", "does", "evening", "for", "from", "get", "got", "had", "has", "have", "her",
        "here", "his", "how", "into", "its", "just", "like", "more", "much", "not", "now",
        "our", "out", "really", "should", "some", "than", "that", "the", "them", "then",
        "there", "they", "this", "time", "today", "tomorrow", "very", "was", "were", "what",
        "when", "where", "will", "with", "would", "yesterday", "you", "your",
    }
)

_NO_PLURAL_ENDINGS = ("ss", "us", "is")


def stem(token: str) -> str:
    """Tiny suffix stripper shared by index, query, tags and weather topics.

    Plural 's' is removed when the base keeps >= 3 chars ("boots" -> "boot", not "glass", "bus").
    'ing' / 'ed' are removed only when the base keeps >= 4 chars, which avoids mangling short words.
    """
    if token.endswith("ing") and len(token) - 3 >= 4:
        return token[:-3]
    if token.endswith("ed") and len(token) - 2 >= 4:
        return token[:-2]
    if token.endswith("s") and not token.endswith(_NO_PLURAL_ENDINGS) and len(token) - 1 >= MIN_TOKEN_LEN:
        return token[:-1]
    return token


def tokenize(text: str) -> List[str]:
    """Lowercase word tokens (unicode letters/digits, len >= 3), stopwords removed, order kept, deduped."""
    if not isinstance(text, str) or not text:
        return []
    out: List[str] = []
    seen = set()
    for raw in _WORD_RE.findall(text.lower()):
        if len(raw) < MIN_TOKEN_LEN or raw in STOPWORDS:
            continue
        tok = stem(raw)
        if len(tok) < MIN_TOKEN_LEN or tok in STOPWORDS or tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
    return out


def theme_surface_tokens(theme_id: Any) -> List[str]:
    """Tokens of a theme id like 'hiking-trail' or 'sourdough_baking' (same stemming as tokenize)."""
    if not isinstance(theme_id, str):
        return []
    return tokenize(theme_id.replace("-", " ").replace("_", " "))


def _iter_records(memories: Iterable[Any]) -> Iterable[MemoryRecord]:
    for mem in memories or ():
        if isinstance(mem, MemoryRecord):
            yield mem
        elif isinstance(mem, dict):
            yield MemoryRecord.from_dict(mem)


def build_fragment_index(memories: Sequence[MemoryRecord]) -> Dict[str, List[str]]:
    """token -> sorted unique theme_ids, built from content + theme_id surface tokens."""
    acc: Dict[str, set] = {}
    for rec in _iter_records(memories):
        if not is_spontaneous_allowed(rec.privacy):
            continue
        theme = (rec.theme_id or "").strip()
        if not theme:
            continue
        for tok in tokenize(rec.content) + theme_surface_tokens(theme):
            acc.setdefault(tok, set()).add(theme)
    return {tok: sorted(themes) for tok, themes in acc.items()}


def index_theme_count(index: Dict[str, List[str]]) -> int:
    """Number of distinct themes referenced by an index."""
    themes = set()
    for ids in (index or {}).values():
        themes.update(ids)
    return len(themes)


def match_fragments(tokens: Sequence[str], index: Dict[str, List[str]], *, min_idf: float) -> Dict[str, float]:
    """theme_id -> summed IDF of matching tokens; tokens below min_idf (too common) ignored."""
    if not tokens or not index:
        return {}
    try:
        threshold = float(min_idf)
    except (TypeError, ValueError):
        threshold = 0.0
    themes_n = index_theme_count(index)
    scores: Dict[str, float] = {}
    seen = set()
    for tok in tokens:
        if not isinstance(tok, str) or tok in seen:
            continue
        seen.add(tok)
        theme_ids = index.get(tok)
        if not theme_ids:
            continue
        idf = token_idf(tok, index, themes_n=themes_n)
        if idf < threshold or idf <= 0.0:
            continue
        for theme in theme_ids:
            scores[theme] = round(scores.get(theme, 0.0) + idf, 6)
    return scores
