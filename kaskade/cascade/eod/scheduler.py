#!/usr/bin/env python3
"""
cascade_eod_scheduler.py – Background scheduler for 23:30 Europe/Berlin EOD cascade reconcile.

Created: 2026-06-15
Last updated: 2026-06-15
"""

from __future__ import annotations

import logging
import os
import threading
import time
import traceback
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

_scheduler_thread: Optional[threading.Thread] = None


def cascade_eod_enabled() -> bool:
    return (os.getenv("CASCADE_EOD_ENABLED") or "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _eod_tz() -> ZoneInfo:
    name = (os.getenv("CASCADE_EOD_TZ") or "Europe/Berlin").strip()
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("Europe/Berlin")


def _eod_hour_minute() -> tuple[int, int]:
    try:
        hour = int(os.getenv("CASCADE_EOD_HOUR") or "23")
    except ValueError:
        hour = 23
    try:
        minute = int(os.getenv("CASCADE_EOD_MINUTE") or "30")
    except ValueError:
        minute = 30
    return max(0, min(23, hour)), max(0, min(59, minute))


def seconds_until_next_eod() -> float:
    tz = _eod_tz()
    now = datetime.now(tz)
    hour, minute = _eod_hour_minute()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now >= target:
        target = target + timedelta(days=1)
    return max(1.0, (target - now).total_seconds())


def _scheduler_loop(postgres_manager: Any) -> None:
    from kaskade.cascade.eod.reconcile import run_cascade_eod_reconcile, today_episode_date

    last_run_day = ""
    while True:
        try:
            if not cascade_eod_enabled():
                time.sleep(300)
                continue
            wait_sec = seconds_until_next_eod()
            logger.info(
                "cascade_eod_scheduler_sleep",
                extra={"wait_sec": round(wait_sec, 1), "component": "cascade_eod_scheduler"},
            )
            time.sleep(wait_sec)
            day_id = today_episode_date()
            if day_id == last_run_day:
                time.sleep(60)
                continue
            print(f"STEP EOD: Cascade reconcile for {day_id}…", flush=True)
            print("This may take a while, please wait...", flush=True)
            run_cascade_eod_reconcile(day_id=day_id, pg=postgres_manager, dry_run=False)
            last_run_day = day_id
        except Exception:
            logger.error(
                "cascade_eod_scheduler_tick_failed",
                extra={"stack": traceback.format_exc()[:800], "component": "cascade_eod_scheduler"},
            )
            time.sleep(120)


def start_cascade_eod_scheduler(postgres_manager: Any) -> None:
    global _scheduler_thread
    if not cascade_eod_enabled():
        logger.info("cascade_eod_scheduler_disabled")
        return
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        return
    t = threading.Thread(
        target=_scheduler_loop,
        args=(postgres_manager,),
        name="CascadeEodScheduler",
        daemon=True,
    )
    t.start()
    _scheduler_thread = t
    logger.info(
        "cascade_eod_scheduler_started",
        extra={
            "component": "cascade_eod_scheduler",
            "tz": str(_eod_tz()),
            "hour": _eod_hour_minute()[0],
            "minute": _eod_hour_minute()[1],
        },
    )


__all__ = ["seconds_until_next_eod", "start_cascade_eod_scheduler"]
