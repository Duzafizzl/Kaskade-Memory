#!/usr/bin/env python3
"""
cascade_maintainer_queue.py – JSONL queue for live archival → cascade linking.

Created: 2026-06-15
Last updated: 2026-07-18
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_REPO = Path(__file__).resolve().parents[2]
_DEFAULT_QUEUE_PATH = _REPO / "data" / "cascade_maintainer_queue.jsonl"
_lock = threading.Lock()

VALID_STATUSES = frozenset({
    "pending",
    "linking",
    "linked",
    "deferred_eod",
    "failed",
    "needs_human",
    "deleted",
})


def max_attempts() -> int:
    try:
        return max(1, int(os.getenv("CASCADE_MAINTAINER_MAX_ATTEMPTS") or "3"))
    except ValueError:
        return 3


def queue_path() -> Path:
    raw = (os.getenv("CASCADE_MAINTAINER_QUEUE_PATH") or "").strip()
    return Path(raw) if raw else _DEFAULT_QUEUE_PATH


def _log(level: str, message: str, **ctx: Any) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "module": "kaskade.cascade.maintainer.queue",
        "message": message,
        **ctx,
    }
    if level == "ERROR":
        logger.error(message, extra=ctx)
    else:
        logger.info(message, extra=ctx)
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def enqueue_cascade_link(
    *,
    memory_id: str,
    episode_date: str,
    person_id: str,
    theme_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    initial_status: Optional[str] = None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Append a cascade link job (idempotent per memory_id while pending/deferred).

    ``initial_status`` overrides the default (pending if theme_id else deferred_eod).
    Used by the M2 significance gate to enqueue deferrals without a worker tick.
    """
    mid = str(memory_id or "").strip()
    if not mid:
        return {"status": "skipped", "reason": "missing_memory_id"}
    day = str(episode_date or "").strip()[:10]
    pid = str(person_id or "").strip()
    tid = (theme_id or "").strip() or None
    status = (initial_status or "").strip() or ("deferred_eod" if not tid else "pending")
    if status not in VALID_STATUSES:
        return {"status": "skipped", "reason": f"invalid_initial_status:{status}"}
    item: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "memory_id": mid,
        "episode_date": day,
        "person_id": pid,
        "theme_id": tid,
        "trace_id": (trace_id or str(uuid.uuid4())).strip(),
        "agent_id": (agent_id or "").strip() or None,
        "status": status,
        "attempts": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if reason:
        item["reason"] = str(reason)[:200]
    path = queue_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        existing = _read_all_unlocked(path)
        for row in existing:
            if row.get("memory_id") == mid and row.get("status") in ("pending", "deferred_eod"):
                _log("INFO", "enqueue_dedup_skip", memory_id=mid[:36], existing_id=row.get("id"))
                return {"status": "dedup", "id": row.get("id"), "memory_id": mid}
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    _log(
        "INFO",
        "cascade_link_enqueued",
        memory_id=mid[:36],
        episode_date=day,
        person_id=pid,
        theme_id=item.get("theme_id"),
        status=item["status"],
        trace_id=item["trace_id"],
    )
    return {"status": "enqueued", **item}


def _read_all_unlocked(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def read_queue(*, status: Optional[str] = None, limit: int = 500) -> List[Dict[str, Any]]:
    path = queue_path()
    with _lock:
        rows = _read_all_unlocked(path)
    if status:
        rows = [r for r in rows if r.get("status") == status]
    return rows[:limit]


def update_queue_item(item_id: str, **fields: Any) -> bool:
    path = queue_path()
    with _lock:
        rows = _read_all_unlocked(path)
        found = False
        for row in rows:
            if row.get("id") == item_id:
                row.update(fields)
                row["updated_at"] = datetime.now(timezone.utc).isoformat()
                found = True
                break
        if not found:
            return False
        path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else ""),
            encoding="utf-8",
        )
    return True


def list_pending(*, include_deferred: bool = False, limit: int = 100) -> List[Dict[str, Any]]:
    statuses = {"pending", "linking"}
    if include_deferred:
        statuses.add("deferred_eod")
    path = queue_path()
    with _lock:
        rows = _read_all_unlocked(path)
    out = [r for r in rows if r.get("status") in statuses]
    return out[:limit]


def record_link_failure(item_id: str, item: Dict[str, Any], *, error: str, reason: str = "") -> str:
    """Increment attempts; return new status (pending or needs_human)."""
    attempts = int(item.get("attempts") or 0) + 1
    cap = max_attempts()
    if attempts >= cap:
        new_status = "needs_human"
    else:
        new_status = "pending"
    update_queue_item(
        item_id,
        status=new_status,
        attempts=attempts,
        error=(error or "")[:500],
        reason=(reason or "")[:200],
        last_failed_at=datetime.now(timezone.utc).isoformat(),
    )
    _log(
        "WARN" if new_status == "needs_human" else "INFO",
        "cascade_link_failure",
        item_id=item_id,
        memory_id=str(item.get("memory_id") or "")[:36],
        attempts=attempts,
        max_attempts=cap,
        new_status=new_status,
        error=(error or "")[:200],
    )
    return new_status


__all__ = [
    "enqueue_cascade_link",
    "list_pending",
    "max_attempts",
    "queue_path",
    "read_queue",
    "record_link_failure",
    "update_queue_item",
]
