#!/usr/bin/env python3
"""
cascade_envelope.py – Archival envelope validation and temporal stamping for cascade pipeline.

Created: 2026-06-15
Last updated: 2026-08-24
"""

from __future__ import annotations

import logging
import os
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

_DAY_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PERSON_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,48}$")
# Bare KW39 or KW39_2026 — calendar buckets, not semantic themes.
_KW_LABEL_RE = re.compile(r"^KW(\d{1,2})(?:_(\d{4}))?$", re.IGNORECASE)
_DAYPART_LABELS = frozenset(
    {
        "vormittag",
        "mittag",
        "nachmittag",
        "abend",
        "nacht",
        "frueh",
        "früh",
        "morning",
        "noon",
        "afternoon",
        "evening",
        "night",
    }
)

KNOWN_PERSON_IDS = frozenset({"alex", "sam", "agent"})


def _person_id_aliases() -> Dict[str, str]:
    """YAML-backed aliases (config/person_aliases.yaml); fallback für Legacy-Imports."""
    try:
        from kaskade.config import person_alias_map as alias_map

        return alias_map()
    except Exception as exc:
        logger.warning(
            "person_id_aliases_fallback",
            extra={"level": "WARN", "component": "cascade_envelope", "error": str(exc)},
        )
        return {"assistant": "agent", "user": "alex"}


# Discord handles / mining nicknames → canonical archival person_id (siehe person_aliases.yaml)
PERSON_ID_ALIASES: Dict[str, str] = _person_id_aliases()


def archival_episode_timezone() -> ZoneInfo:
    name = (os.getenv("ARCHIVAL_EPISODE_TZ") or os.getenv("CASCADE_EOD_TZ") or "Europe/Berlin").strip()
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("Europe/Berlin")


def iso_week_id(d: date) -> str:
    iso = d.isocalendar()
    return f"KW{iso.week:02d}_{iso.year}"


def resolve_episode_date(metadata: Optional[Dict[str, Any]] = None) -> str:
    """Episode calendar day (YYYY-MM-DD), default today in archival timezone."""
    meta = metadata or {}
    override = str(meta.get("episode_date") or "").strip()[:10]
    if _DAY_ID_RE.fullmatch(override):
        return override
    tz = archival_episode_timezone()
    return datetime.now(tz).date().isoformat()


def resolve_week_id(episode_date: str) -> str:
    y, m, d = map(int, episode_date.split("-"))
    return iso_week_id(date(y, m, d))


def normalize_person_id(raw: Optional[str]) -> str:
    from kaskade.config import normalize_person_id as _norm

    return _norm(raw)


def normalize_mentioned_persons(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        return []
    out: List[str] = []
    seen: set[str] = set()
    for item in raw:
        pid = normalize_person_id(str(item))
        if not pid or pid in seen:
            continue
        if not _PERSON_ID_RE.fullmatch(pid):
            continue
        seen.add(pid)
        out.append(pid)
    return out


def validate_person_id(person_id: Optional[str]) -> Tuple[bool, str, str]:
    """
    Validate person_id for archival insert.
    Returns (ok, normalized_id, error_code).
    """
    pid = normalize_person_id(person_id)
    if not pid:
        return False, "", "ARCHIVE_PERSON_ID_REQUIRED"
    if not _PERSON_ID_RE.fullmatch(pid):
        return False, "", "ARCHIVE_PERSON_ID_INVALID"
    if pid in KNOWN_PERSON_IDS:
        return True, pid, ""
    pending_ok = (os.getenv("ARCHIVAL_PERSON_PENDING_REVIEW_ALLOWED") or "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if pending_ok:
        logger.info(
            "archival_person_pending_review",
            extra={"person_id": pid, "level": "INFO", "module": "cascade_envelope"},
        )
        return True, pid, ""
    return False, "", "ARCHIVE_PERSON_ID_NOT_ALLOWLISTED"


def is_kw_calendar_label(raw: Optional[str]) -> bool:
    """True for KW39 / kw39_2026 style calendar-week labels."""
    return bool(_KW_LABEL_RE.fullmatch(str(raw or "").strip()))


def is_daypart_label(raw: Optional[str]) -> bool:
    """True for pure dayparts (Nachmittag, Abend) — not kebab themes like Pause-Nachmittag."""
    t = str(raw or "").strip().lower()
    if not t or "-" in t or "_" in t:
        return False
    return t in _DAYPART_LABELS


def is_temporal_theme_label(raw: Optional[str]) -> bool:
    """Labels that must not become cascade theme_id (week/daypart/calendar day)."""
    t = str(raw or "").strip()
    if not t:
        return False
    if is_kw_calendar_label(t) or is_daypart_label(t):
        return True
    return bool(_DAY_ID_RE.fullmatch(t))


def normalize_archival_temporal_scope(
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    """
    Rewrite wrong KW tags to episode week_id; clear temporal theme_id.

    week_id / episode_date must already be stamped on metadata.
    """
    meta = dict(metadata or {})
    week_id = str(meta.get("week_id") or "").strip()
    episode_date = str(meta.get("episode_date") or "").strip()[:10]
    if not week_id and _DAY_ID_RE.fullmatch(episode_date):
        week_id = resolve_week_id(episode_date)
        meta["week_id"] = week_id

    raw_tags = [str(t).strip() for t in (tags or []) if str(t).strip()]
    out_tags: List[str] = []
    seen: set[str] = set()
    wrong_kws: List[str] = []
    had_kw = False

    for tag in raw_tags:
        key = tag.lower()
        if is_kw_calendar_label(tag):
            had_kw = True
            if week_id and tag.upper().replace(" ", "") != week_id.upper():
                wrong_kws.append(tag)
            continue
        if key in seen:
            continue
        seen.add(key)
        out_tags.append(tag)

    if had_kw and week_id and week_id.lower() not in seen:
        out_tags.append(week_id)
        seen.add(week_id.lower())

    tid = str(meta.get("theme_id") or "").strip()
    if tid and is_temporal_theme_label(tid):
        meta["theme_id_rewritten_from"] = tid
        meta["theme_id_rewrite_reason"] = (
            "temporal_kw_not_theme" if is_kw_calendar_label(tid) else "temporal_daypart_not_theme"
        )
        meta.pop("theme_id", None)
        logger.info(
            "archival_theme_id_cleared_temporal",
            extra={
                "level": "INFO",
                "module": "cascade_envelope",
                "from_theme_id": tid[:64],
                "week_id": week_id,
                "episode_date": episode_date,
            },
        )

    if wrong_kws:
        logger.info(
            "archival_kw_tags_rewritten",
            extra={
                "level": "INFO",
                "module": "cascade_envelope",
                "wrong_kws": wrong_kws[:8],
                "week_id": week_id,
                "episode_date": episode_date,
            },
        )

    return out_tags, meta


def stamp_archival_metadata(
    metadata: Optional[Dict[str, Any]],
    *,
    person_id: str,
    mentioned_persons: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Merge person + temporal fields into archival metadata."""
    meta = dict(metadata or {})
    meta["person_id"] = person_id
    episode_date = resolve_episode_date(meta)
    meta["episode_date"] = episode_date
    meta["week_id"] = resolve_week_id(episode_date)
    if mentioned_persons is not None:
        meta["mentioned_persons"] = normalize_mentioned_persons(mentioned_persons)
        meta["participant_ids"] = meta["mentioned_persons"]
    elif meta.get("mentioned_persons"):
        meta["mentioned_persons"] = normalize_mentioned_persons(meta.get("mentioned_persons"))
        meta["participant_ids"] = meta["mentioned_persons"]
    return meta


__all__ = [
    "KNOWN_PERSON_IDS",
    "PERSON_ID_ALIASES",
    "archival_episode_timezone",
    "iso_week_id",
    "is_daypart_label",
    "is_kw_calendar_label",
    "is_temporal_theme_label",
    "normalize_archival_temporal_scope",
    "normalize_mentioned_persons",
    "normalize_person_id",
    "resolve_episode_date",
    "resolve_week_id",
    "stamp_archival_metadata",
    "validate_person_id",
]
