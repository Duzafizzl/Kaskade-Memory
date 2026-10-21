#!/usr/bin/env python3
"""
delivery.py – SparkDelivery hook: where a generated spark goes (log | webhook | next_turn).

Created: 2026-10-20
Last updated: 2026-10-21
"""

from __future__ import annotations

import ipaddress
import json
import logging
import os
import socket
import urllib.error
import urllib.request
from collections import defaultdict
from typing import Dict, List
from urllib.parse import urlparse

from kaskade.gnostic._log import log_event
from kaskade.gnostic.types import SparkResult

logger = logging.getLogger(__name__)
_MODULE = "kaskade.gnostic.delivery"

DELIVERY_ENV = "KASKADE_SPARK_DELIVERY"
WEBHOOK_ENV = "KASKADE_SPARK_WEBHOOK_URL"
WEBHOOK_TIMEOUT_S = 3.0
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

_NEXT_TURN: Dict[str, List[SparkResult]] = defaultdict(list)


class LogDelivery:
    name = "log"

    def deliver(self, result: SparkResult, *, agent_id: str) -> bool:
        log_event(
            logger,
            "INFO",
            _MODULE,
            "deliver",
            "spark_logged",
            delivery=self.name,
            agent_id=agent_id,
            trace_id=result.trace_id,
            memory_id=result.memory_id,
            score=result.score,
        )
        return True


class NextTurnDelivery:
    name = "next_turn"

    def deliver(self, result: SparkResult, *, agent_id: str) -> bool:
        _NEXT_TURN[str(agent_id or "")].append(result)
        log_event(
            logger,
            "INFO",
            _MODULE,
            "deliver",
            "spark_queued",
            delivery=self.name,
            agent_id=agent_id,
            trace_id=result.trace_id,
            memory_id=result.memory_id,
            queued_n=len(_NEXT_TURN[str(agent_id or "")]),
        )
        return True


def _host_blocked(host: str) -> bool:
    """Fail closed on private, link-local, reserved, or unresolvable targets."""
    if host in _LOCAL_HOSTS:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return True
    for info in infos:
        raw = info[4][0]
        try:
            ip = ipaddress.ip_address(raw)
        except ValueError:
            return True
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return True
    return False


def _webhook_allowed(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if not host or _host_blocked(host):
        return False
    if parsed.scheme == "https":
        return True
    return parsed.scheme == "http" and host in _LOCAL_HOSTS


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        raise urllib.error.HTTPError(req.full_url, code, "redirect_refused", headers, fp)


_WEBHOOK_OPENER = urllib.request.build_opener(_NoRedirect)


class WebhookDelivery:
    name = "webhook"

    def deliver(self, result: SparkResult, *, agent_id: str) -> bool:
        url = (os.getenv(WEBHOOK_ENV) or "").strip()
        if not url or not _webhook_allowed(url):
            log_event(logger, "WARN", _MODULE, "deliver", "webhook_rejected", delivery=self.name, allowed=False)
            return False
        payload = json.dumps(
            {
                "trace_id": result.trace_id,
                "memory_id": result.memory_id,
                "spark_text": result.spark_text,
                "score": result.score,
                "agent_id": agent_id,
            }
        ).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST", headers={"Content-Type": "application/json"})
        try:
            with _WEBHOOK_OPENER.open(req, timeout=WEBHOOK_TIMEOUT_S) as resp:
                log_event(
                    logger,
                    "INFO",
                    _MODULE,
                    "deliver",
                    "webhook_ok",
                    delivery=self.name,
                    status=getattr(resp, "status", 0),
                    trace_id=result.trace_id,
                    memory_id=result.memory_id,
                )
            return True
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            log_event(
                logger,
                "WARN",
                _MODULE,
                "deliver",
                "webhook_failed",
                delivery=self.name,
                error=type(exc).__name__,
                error_message=str(exc)[:200],
            )
            return False


_MODES = {
    "log": LogDelivery,
    "next_turn": NextTurnDelivery,
    "webhook": WebhookDelivery,
}


def get_delivery(mode: str = "") -> LogDelivery | NextTurnDelivery | WebhookDelivery:
    raw = (mode or os.getenv(DELIVERY_ENV) or "log").strip().lower()
    cls = _MODES.get(raw, LogDelivery)
    if raw not in _MODES:
        log_event(logger, "WARN", _MODULE, "get_delivery", "unknown_mode", requested=raw, fallback="log")
    return cls()


def drain_next_turn(agent_id: str) -> List[SparkResult]:
    key = str(agent_id or "")
    queued = list(_NEXT_TURN.get(key) or [])
    _NEXT_TURN[key] = []
    log_event(logger, "DEBUG", _MODULE, "drain_next_turn", "drained", agent_id=key, n=len(queued))
    return queued


def reset_next_turn_for_tests() -> None:
    _NEXT_TURN.clear()
