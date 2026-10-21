#!/usr/bin/env python3
"""
_log.py – Shared structured JSON logger for gnostic/* modules (one line per event).

Created: 2026-10-20
Last updated: 2026-10-20
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def log_event(logger: logging.Logger, level: str, module: str, function: str, message: str, **fields: Any) -> None:
    """Emit one JSON log line. Never raises; never pass secrets or raw memory content here."""
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "level": level,
        "module": module,
        "function": function,
        "message": message,
        **fields,
    }
    try:
        line = json.dumps(payload, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        line = json.dumps({**payload, "fields_error": True}, default=str)
    logger.log(_LEVELS.get(level, logging.INFO), line)
