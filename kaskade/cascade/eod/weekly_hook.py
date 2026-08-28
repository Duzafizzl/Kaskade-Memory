#!/usr/bin/env python3
"""
weekly_hook.py – After EOD on Sunday, trigger weekly rollup hook (demo).

Created: 2026-08-28
Last updated: 2026-08-28
"""

from __future__ import annotations

import json
import logging
from datetime import date

logger = logging.getLogger(__name__)


def iso_week_key(day_id: str) -> str:
    d = date.fromisoformat(day_id[:10])
    iso = d.isocalendar()
    return f"KW{iso.week:02d}_{iso.year}"


def is_iso_week_end_day(day_id: str) -> bool:
    try:
        return date.fromisoformat((day_id or "")[:10]).weekday() == 6
    except ValueError:
        return False


def maybe_run_weekly_rollup_hook(*, day_id: str) -> dict:
    if not is_iso_week_end_day(day_id):
        return {"skipped": True, "reason": "not_sunday"}
    week = iso_week_key(day_id)
    logger.info(json.dumps({"level": "INFO", "module": "weekly_hook", "message": "weekly_rollup_trigger", "week": week}))
    return {"skipped": False, "week_id": week, "status": "scheduled"}
