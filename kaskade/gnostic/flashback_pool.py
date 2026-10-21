#!/usr/bin/env python3
"""
flashback_pool.py – Cascade-first candidate pool for Gnostic Spark (theme/day/tag/graph buckets).

Seeds are plain strings: a theme id (`hiking-trail` or `theme:hiking-trail`), a tag
(`tag:sourdough`), a day (`2026-10-20`) or a memory id that exists in `memories`.
Every memory collects one cue per independent bucket it matched; the number of distinct
cue types is the convergence signal that spark_rank later requires (>= 2).
`high_engagement` is reserved and is never emitted by this pool.

Created: 2026-10-20
Last updated: 2026-10-20
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from kaskade.gnostic._log import log_event
from kaskade.gnostic.types import (
    CUE_DAY_BUCKET,
    CUE_DAY_THEME_BUCKET,
    CUE_GRAPH_REF,
    CUE_TAG,
    CUE_THEME_BUCKET,
    Cue,
    MemoryRecord,
    SparkCandidate,
    is_spontaneous_allowed,
)

logger = logging.getLogger(__name__)
_MODULE = "kaskade.gnostic.flashback_pool"

DEFAULT_MAX_POOL = 24
PLACE_TAG = "place"
PLACE_THEME_PREFIX = "place-"
THEME_SEED_PREFIX = "theme:"
TAG_SEED_PREFIX = "tag:"
_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CUE_ORDER = {t: i for i, t in enumerate((CUE_THEME_BUCKET, CUE_DAY_THEME_BUCKET, CUE_DAY_BUCKET, CUE_TAG, CUE_GRAPH_REF))}


@dataclass
class _Seeds:
    themes: Set[str] = field(default_factory=set)
    days: Set[str] = field(default_factory=set)
    tags: Set[str] = field(default_factory=set)
    memory_ids: Set[str] = field(default_factory=set)
    ignored_n: int = 0


def is_place_memory(record: MemoryRecord) -> bool:
    """Place memories carry the `place` tag or a `place-` theme prefix."""
    tags = {str(t).strip().lower() for t in (record.tags or [])}
    return PLACE_TAG in tags or str(record.theme_id or "").strip().lower().startswith(PLACE_THEME_PREFIX)


def _admissible(record: MemoryRecord, *, allow_place: bool) -> bool:
    if not record.memory_id:
        return False
    if not is_spontaneous_allowed(record.privacy):
        return False
    if is_place_memory(record) and not allow_place:
        return False
    return True


def _parse_seeds(seeds: Sequence[Any], records_by_id: Dict[str, MemoryRecord]) -> _Seeds:
    out = _Seeds()
    if isinstance(seeds, str):
        seeds = [seeds]
    for raw in seeds or []:
        if not isinstance(raw, str) or not raw.strip():
            out.ignored_n += 1
            continue
        seed = raw.strip()
        if seed.startswith(THEME_SEED_PREFIX):
            theme = seed[len(THEME_SEED_PREFIX):].strip()
            if theme:
                out.themes.add(theme)
            else:
                out.ignored_n += 1
        elif seed.startswith(TAG_SEED_PREFIX):
            tag = seed[len(TAG_SEED_PREFIX):].strip().lower()
            if tag:
                out.tags.add(tag)
            else:
                out.ignored_n += 1
        elif _DAY_RE.match(seed):
            out.days.add(seed)
        elif seed in records_by_id:
            out.memory_ids.add(seed)
            out.tags.update(str(t).strip().lower() for t in records_by_id[seed].tags if str(t).strip())
        else:
            out.themes.add(seed)
    return out


def _edge_pairs(edges: Optional[Sequence[Any]]) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    for edge in edges or []:
        if not isinstance(edge, dict):
            continue
        src = str(edge.get("src_node_id") or edge.get("src") or "").strip()
        dst = str(edge.get("dst_node_id") or edge.get("dst") or "").strip()
        if src and dst and src != dst:
            pairs.append((src, dst))
    return pairs


def _anchor_nodes(parsed: _Seeds, records: Sequence[MemoryRecord], *, allow_place: bool) -> Set[str]:
    """Graph nodes whose 1-hop neighbours earn a graph_ref cue.

    Cascade-first: explicit seed nodes plus the admissible members of every seeded theme
    bucket. Inadmissible memories (P5, gated place) never act as anchors.
    """
    nodes: Set[str] = set(parsed.memory_ids) | set(parsed.days)
    nodes.update(f"{THEME_SEED_PREFIX}{t}" for t in parsed.themes)
    nodes.update(parsed.themes)
    nodes.update(f"{TAG_SEED_PREFIX}{t}" for t in parsed.tags)
    for rec in records:
        if rec.theme_id and rec.theme_id in parsed.themes and _admissible(rec, allow_place=allow_place):
            nodes.add(rec.memory_id)
    return nodes


def _neighbour_index(pairs: Sequence[Tuple[str, str]], anchors: Set[str]) -> Dict[str, Set[str]]:
    """node -> anchors it touches (both edge directions)."""
    index: Dict[str, Set[str]] = {}
    for src, dst in pairs:
        if src in anchors:
            index.setdefault(dst, set()).add(src)
        if dst in anchors:
            index.setdefault(src, set()).add(dst)
    return index


def _cues_for(record: MemoryRecord, parsed: _Seeds, neighbours: Dict[str, Set[str]]) -> List[Cue]:
    cues: List[Cue] = []
    theme_hit = bool(record.theme_id) and record.theme_id in parsed.themes
    day_hit = bool(record.day_id) and record.day_id in parsed.days
    if theme_hit:
        cues.append(Cue(CUE_THEME_BUCKET, record.theme_id))
    if day_hit:
        cues.append(Cue(CUE_DAY_BUCKET, record.day_id))
    if theme_hit and day_hit:
        cues.append(Cue(CUE_DAY_THEME_BUCKET, f"{record.day_id}|{record.theme_id}"))
    for tag in sorted({str(t).strip().lower() for t in record.tags if str(t).strip()} & parsed.tags):
        cues.append(Cue(CUE_TAG, tag))
    for anchor in sorted(neighbours.get(record.memory_id, set()) - {record.memory_id}):
        cues.append(Cue(CUE_GRAPH_REF, anchor))
    cues.sort(key=lambda c: (_CUE_ORDER.get(c.type, 99), c.key))
    return cues


def _clamp_max_pool(max_pool: Any) -> int:
    try:
        return max(1, int(max_pool))
    except (TypeError, ValueError):
        return DEFAULT_MAX_POOL


def build_pool(
    seeds: Sequence[str],
    memories: Sequence[MemoryRecord],
    *,
    edges: Optional[Sequence[Dict[str, Any]]] = None,
    allow_place: bool = False,
    max_pool: int = 24,
) -> List[SparkCandidate]:
    """Collect candidates whose theme/day/tags/graph neighbourhood match `seeds`.

    - One SparkCandidate per memory; cues = every independent bucket that matched.
    - Memories with P >= PRIVACY_NEVER_SPONTANEOUS_P are excluded.
    - Memories tagged `place` / theme prefix `place-` only when allow_place=True.
    - Deterministic order for equal inputs; at most `max_pool` results.
    """
    limit = _clamp_max_pool(max_pool)
    records: List[MemoryRecord] = []
    seen: Set[str] = set()
    for rec in memories or []:
        if isinstance(rec, MemoryRecord) and rec.memory_id and rec.memory_id not in seen:
            seen.add(rec.memory_id)
            records.append(rec)
    records_by_id = {r.memory_id: r for r in records}
    parsed = _parse_seeds(seeds, records_by_id)
    log_event(
        logger,
        "DEBUG",
        _MODULE,
        "build_pool",
        "start",
        memories_n=len(records),
        seed_themes_n=len(parsed.themes),
        seed_days_n=len(parsed.days),
        seed_tags_n=len(parsed.tags),
        seed_memories_n=len(parsed.memory_ids),
        seeds_ignored_n=parsed.ignored_n,
        allow_place=bool(allow_place),
        max_pool=limit,
    )
    if not records or not (parsed.themes or parsed.days or parsed.tags or parsed.memory_ids):
        log_event(logger, "INFO", _MODULE, "build_pool", "empty_pool", reason="no_seeds_or_memories", pool_n=0)
        return []

    anchors = _anchor_nodes(parsed, records, allow_place=bool(allow_place))
    neighbours = _neighbour_index(_edge_pairs(edges), anchors)

    pool: List[SparkCandidate] = []
    excluded_privacy = 0
    excluded_place = 0
    for rec in records:
        if rec.memory_id in parsed.memory_ids:
            continue
        if not is_spontaneous_allowed(rec.privacy):
            excluded_privacy += 1
            continue
        if is_place_memory(rec) and not allow_place:
            excluded_place += 1
            continue
        cues = _cues_for(rec, parsed, neighbours)
        if not cues:
            continue
        types_n = len({c.type for c in cues})
        pool.append(
            SparkCandidate(
                record=rec,
                cues=cues,
                convergence_hits=max(0, types_n - 1),
                theme_overlap=1 if rec.theme_id in parsed.themes else 0,
            )
        )

    pool.sort(key=lambda c: (-len({cue.type for cue in c.cues}), -c.theme_overlap, -len(c.cues), c.memory_id))
    truncated_n = max(0, len(pool) - limit)
    pool = pool[:limit]
    log_event(
        logger,
        "INFO",
        _MODULE,
        "build_pool",
        "done",
        pool_n=len(pool),
        pool_ids=[c.memory_id for c in pool],
        excluded_privacy_n=excluded_privacy,
        excluded_place_n=excluded_place,
        truncated_n=truncated_n,
    )
    return pool


__all__ = ["DEFAULT_MAX_POOL", "build_pool", "is_place_memory"]
