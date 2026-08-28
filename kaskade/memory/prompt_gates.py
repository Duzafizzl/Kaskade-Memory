#!/usr/bin/env python3
"""
prompt_gates.py – Configurable core-memory inclusion by channel, keywords, message types.

Created: 2026-08-28
Last updated: 2026-08-28
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from typing import Any, Dict, List, Mapping, Optional, Sequence

from kaskade.config import core_memory_gates_config

logger = logging.getLogger(__name__)


def _norm_label(label: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(label or "")).strip().lower().split())


def _match_keywords(text: str, keywords: Sequence[str]) -> bool:
    low = (text or "").lower()
    return any(k.lower() in low for k in keywords if k)


def should_include_core_block(
    label: str,
    *,
    channel_id: str = "",
    message_type: str = "user",
    user_message: str = "",
    context_messages: Optional[Sequence[str]] = None,
    block_metadata: Optional[Mapping[str, Any]] = None,
) -> bool:
    """Return True if core block should appear in prompt assembly."""
    meta = dict(block_metadata or {})
    gate_override = meta.get("prompt_gate")
    if isinstance(gate_override, dict):
        default = str(gate_override.get("default") or "include").lower()
        when = gate_override.get("include_when") or {}
    else:
        gate = None
        nl = _norm_label(label)
        for row in core_memory_gates_config():
            if _norm_label(str(row.get("label") or "")) == nl:
                gate = row
                break
        if not gate:
            return True
        default = str(gate.get("default") or "include").lower()
        when = gate.get("include_when") or {}

    if default == "include":
        base = True
    else:
        base = False

    combined = " ".join([user_message or "", *(context_messages or [])])
    channels = [str(c).lower() for c in (when.get("channels") or [])]
    keywords = list(when.get("keywords") or [])
    msg_types = [str(m).lower() for m in (when.get("message_types") or [])]
    content_tokens = list(when.get("content_tokens") or [])

    triggered = False
    channel_hit = bool(channels and channel_id.lower() in channels)
    keyword_hit = bool(keywords and _match_keywords(combined, keywords))
    token_hit = bool(content_tokens and _match_keywords(str(meta.get("content") or ""), content_tokens))
    type_ok = (not msg_types) or (message_type.lower() in msg_types)

    if type_ok and (channel_hit or keyword_hit or token_hit):
        triggered = True

    if default == "omit":
        return triggered
    if default == "include" and triggered:
        return False
    return base


def filter_core_blocks_for_prompt(
    blocks: List[Dict[str, Any]],
    *,
    channel_id: str = "",
    message_type: str = "user",
    user_message: str = "",
    context_messages: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for block in blocks:
        label = str(block.get("label") or block.get("name") or "")
        if should_include_core_block(
            label,
            channel_id=channel_id,
            message_type=message_type,
            user_message=user_message,
            context_messages=context_messages,
            block_metadata=block,
        ):
            out.append(block)
        else:
            logger.info(
                json.dumps(
                    {
                        "level": "INFO",
                        "module": "prompt_gates",
                        "message": "core_block_omitted",
                        "label": label,
                        "channel_id": channel_id,
                    }
                )
            )
    return out
