#!/usr/bin/env python3
"""
cascade_day_summary.py – EOD signal plugin `spark_day`: roll up a day's Spark audit rows.

Pure when `audits` is passed. Without it, rows are read from Postgres
(recall_gnostic_shadow_audit); any failure degrades to has_data=False and never raises.
The gist is English and built from counts only, never from spark text.

Created: 2026-10-20
Last updated: 2026-10-20
"""

from __future__ import annotations

import json
import logging
import re
import time
import traceback
from typing import Any, Dict, List, Optional, Sequence, Tuple

from kaskade.gnostic._log import log_event

logger = logging.getLogger(__name__)
_MODULE = "kaskade.gnostic.cascade_day_summary"

_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CONVERGENT_MIN_TYPES = 2


def _extra(row: Dict[str, Any]) -> Dict[str, Any]:
    raw = row.get("extra")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (str, bytes)):
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _is_convergent(row: Dict[str, Any]) -> bool:
    extra = _extra(row)
    flag = extra.get("convergent")
    if isinstance(flag, bool):
        return flag
    try:
        return int(extra.get("cue_types_n") or 0) >= CONVERGENT_MIN_TYPES
    except (TypeError, ValueError):
        return False


def _layer(day_id: str, *, sparks_n: int, convergent_n: int, source: str) -> Dict[str, Any]:
    rate = round(convergent_n / sparks_n, 4) if sparks_n else 0.0
    if sparks_n:
        noun = "spark" if sparks_n == 1 else "sparks"
        gist = f"{sparks_n} {noun} on {day_id}, {convergent_n} convergent ({rate:.0%})"
    elif source == "unavailable":
        gist = f"Spark audits unavailable for {day_id}"
    else:
        gist = f"No sparks on {day_id}"
    return {
        "layer": "spark",
        "theme_id": "spark_day",
        "container_hint": "signal:spark",
        "has_data": sparks_n > 0,
        "gist": gist,
        "sparks_n": sparks_n,
        "convergent_n": convergent_n,
        "convergent_rate": rate,
        "source": source,
    }


def _load_from_postgres(day_id: str) -> Tuple[Optional[List[Dict[str, Any]]], str]:
    """Return (rows, error). rows is None when the DB path failed."""
    try:
        from kaskade.memory.postgres_store import connect, list_spark_audits_for_day

        with connect() as conn:
            return list(list_spark_audits_for_day(conn, day_id)), ""
    except Exception as exc:  # DB down, driver missing, schema absent: EOD must still run.
        log_event(
            logger,
            "WARN",
            _MODULE,
            "spark_day_summary",
            "postgres_unavailable",
            day_id=day_id,
            error=type(exc).__name__,
            error_message=str(exc)[:200],
            stack_trace=traceback.format_exc(limit=3),
        )
        return None, type(exc).__name__


def spark_day_summary(
    day_id: str,
    agent_id: str = "",
    *,
    audits: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Return an EOD signal layer:

    {layer: "spark", theme_id: "spark_day", container_hint: "signal:spark",
     has_data, gist, sparks_n, convergent_n, convergent_rate}

    `audits` = rows like recall_gnostic_shadow_audit (extra.convergent bool). When None,
    load rows for day_id from Postgres; if the DB is unreachable return has_data=False (never raise).
    """
    started = time.monotonic()
    day = str(day_id or "").strip()
    agent = str(agent_id or "").strip()
    if not _DAY_RE.match(day):
        log_event(logger, "WARN", _MODULE, "spark_day_summary", "invalid_day_id", error="day_id must be YYYY-MM-DD")
        return _layer(day or "unknown day", sparks_n=0, convergent_n=0, source="unavailable")

    if audits is None:
        loaded, _err = _load_from_postgres(day)
        if loaded is None:
            return _layer(day, sparks_n=0, convergent_n=0, source="unavailable")
        rows, source = loaded, "postgres"
    else:
        try:
            rows = [] if isinstance(audits, (str, bytes, dict)) else list(audits)
        except TypeError:
            rows = []
        source = "audits"

    valid = [r for r in rows if isinstance(r, dict)]
    if agent:
        valid = [r for r in valid if not r.get("agent_id") or str(r.get("agent_id")) == agent]
    sparks_n = len(valid)
    convergent_n = sum(1 for r in valid if _is_convergent(r))
    layer = _layer(day, sparks_n=sparks_n, convergent_n=convergent_n, source=source)
    log_event(
        logger,
        "INFO",
        _MODULE,
        "spark_day_summary",
        "summarised",
        day_id=day,
        agent_filter=bool(agent),
        source=source,
        rows_n=len(rows),
        sparks_n=sparks_n,
        convergent_n=convergent_n,
        convergent_rate=layer["convergent_rate"],
        duration_ms=int((time.monotonic() - started) * 1000),
    )
    return layer


__all__ = ["spark_day_summary"]
