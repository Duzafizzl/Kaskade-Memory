#!/usr/bin/env python3
"""
cascade_significance_gate.py – Sync filter before cascade maintainer enqueue (M2).

Decisions: pass | reject | defer_eod. Process-local rings (restart clears).
Fail-open is the caller's responsibility when this module raises.

Created: 2026-07-18
Last updated: 2026-07-18
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from collections import deque
from difflib import SequenceMatcher
from datetime import datetime, timezone
from typing import Any, Deque, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_content_hashes: Deque[str] = deque(maxlen=200)
_l1_ring: Deque[str] = deque(maxlen=50)
# theme_id -> monotonic deadline (time.monotonic())
_theme_cache: Dict[str, float] = {}

GATE_ENV = "CASCADE_SIGNIFICANCE_GATE_ENABLED"
NEAR_DUP_RATIO = 0.8
LOW_ERIP_COMPOSITE = 2.0
THEME_CACHE_TTL_SEC = 600.0


def gate_enabled(default: str = "true") -> bool:
    """Kill-switch: CASCADE_SIGNIFICANCE_GATE_ENABLED (default on)."""
    return (os.environ.get(GATE_ENV) or default).strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def reset_gate_state_for_tests() -> None:
    """Clear process-local rings/cache (tests only)."""
    with _lock:
        _content_hashes.clear()
        _l1_ring.clear()
        _theme_cache.clear()


def _log(level: str, message: str, **ctx: Any) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "module": "kaskade.reflex.significance_gate",
        "message": message,
        **{k: v for k, v in ctx.items() if v is not None},
    }
    if level == "ERROR":
        logger.error(message, extra=ctx)
    elif level == "WARN":
        logger.warning(message, extra=ctx)
    else:
        logger.info(message, extra=ctx)
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _content_hash(content: str) -> str:
    chunk = (content or "")[:500]
    return hashlib.sha256(chunk.encode("utf-8", errors="replace")).hexdigest()


def _normalize_l1(l1: str) -> str:
    return " ".join((l1 or "").strip().lower().split())


def _purge_theme_cache_unlocked(now: float) -> None:
    dead = [k for k, exp in _theme_cache.items() if exp <= now]
    for k in dead:
        del _theme_cache[k]


def _remember_pass_unlocked(*, content_hash: str, l1_norm: str, theme_id: Optional[str]) -> None:
    if content_hash:
        _content_hashes.append(content_hash)
    if l1_norm:
        _l1_ring.append(l1_norm)
    tid = (theme_id or "").strip()
    if tid:
        _theme_cache[tid] = time.monotonic() + THEME_CACHE_TTL_SEC


def _near_dup_l1(l1_norm: str) -> bool:
    if not l1_norm or len(l1_norm) < 8:
        return False
    for prev in _l1_ring:
        if SequenceMatcher(None, l1_norm, prev).ratio() >= NEAR_DUP_RATIO:
            return True
    return False


def evaluate_cascade_significance(
    *,
    content: str,
    recall_inject_l1: Optional[str] = None,
    theme_id: Optional[str] = None,
    erip_composite: Optional[float] = None,
    memory_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluate whether a live archival should enter the cascade queue.

    Returns dict with decision in {pass, reject, defer_eod}, reason, and trace.
    """
    if not gate_enabled():
        out = {
            "decision": "pass",
            "reason": "gate_disabled",
            "trace": {"gate_enabled": False},
        }
        _log("INFO", "cascade_significance_evaluated", memory_id=(memory_id or "")[:36], **out)
        return out

    from kaskade.erip.weighting import parse_mandatory_erip_from_content

    tid = (theme_id or "").strip() or None
    l1_raw = (recall_inject_l1 or "").strip()
    l1_norm = _normalize_l1(l1_raw)
    chash = _content_hash(content or "")
    mid = (memory_id or "").strip()[:36] or None

    parsed = parse_mandatory_erip_from_content(content or "")
    if parsed is None:
        out = {
            "decision": "reject",
            "reason": "erip_unparseable",
            "trace": {"has_content": bool(content)},
        }
        _log("WARN", "cascade_significance_evaluated", memory_id=mid, **out)
        return out

    composite = float(erip_composite) if erip_composite is not None else float(parsed.composite())

    import os
    try:
        high_p = int(os.getenv("HIGH_PRIVACY_THRESHOLD") or "4")
    except ValueError:
        high_p = 4
    if parsed.P >= high_p and not tid:
        out = {
            "decision": "defer_eod",
            "reason": "high_privacy_no_theme",
            "trace": {"P": parsed.P, "threshold": high_p},
        }
        _log("INFO", "cascade_significance_evaluated", memory_id=mid, **out)
        return out

    with _lock:
        now = time.monotonic()
        _purge_theme_cache_unlocked(now)

        if chash in _content_hashes:
            out = {
                "decision": "reject",
                "reason": "exact_dup",
                "trace": {"content_hash_prefix": chash[:12], "composite": composite},
            }
            _log("WARN", "cascade_significance_evaluated", memory_id=mid, **out)
            return out

        if _near_dup_l1(l1_norm):
            out = {
                "decision": "defer_eod",
                "reason": "near_dup_l1",
                "trace": {"l1_len": len(l1_norm), "composite": composite, "theme_id": tid},
            }
            _log("INFO", "cascade_significance_evaluated", memory_id=mid, **out)
            return out

        if composite < LOW_ERIP_COMPOSITE and not tid:
            out = {
                "decision": "defer_eod",
                "reason": "low_erip_no_theme",
                "trace": {"composite": composite, "threshold": LOW_ERIP_COMPOSITE},
            }
            _log("INFO", "cascade_significance_evaluated", memory_id=mid, **out)
            return out

        if tid and tid in _theme_cache and _theme_cache[tid] > now:
            _remember_pass_unlocked(content_hash=chash, l1_norm=l1_norm, theme_id=tid)
            out = {
                "decision": "pass",
                "reason": "theme_fast_path",
                "trace": {"theme_id": tid, "composite": composite},
            }
            _log("INFO", "cascade_significance_evaluated", memory_id=mid, **out)
            return out

        if not tid:
            out = {
                "decision": "defer_eod",
                "reason": "missing_theme_id",
                "trace": {"composite": composite},
            }
            _log("INFO", "cascade_significance_evaluated", memory_id=mid, **out)
            return out

        _remember_pass_unlocked(content_hash=chash, l1_norm=l1_norm, theme_id=tid)
        out = {
            "decision": "pass",
            "reason": "theme_erip_ok",
            "trace": {"theme_id": tid, "composite": composite},
        }
        _log("INFO", "cascade_significance_evaluated", memory_id=mid, **out)
        return out


def enqueue_status_for_decision(decision: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Map gate decision to enqueue action.

    Returns (initial_status_or_None_if_skip, reason).
    None status means do not enqueue (reject).
    """
    d = (decision or "").strip().lower()
    if d == "reject":
        return None, "gate_reject"
    if d == "defer_eod":
        return "deferred_eod", None
    return "pending", None


__all__ = [
    "GATE_ENV",
    "evaluate_cascade_significance",
    "enqueue_status_for_decision",
    "gate_enabled",
    "reset_gate_state_for_tests",
]
