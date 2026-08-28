#!/usr/bin/env python3
"""
gnostic_edge_types.py – Registry and sync helpers for curated gnostic semantic edges.

Created: 2026-07-06
Last updated: 2026-07-06
"""

from __future__ import annotations

import json
import logging
import re
import time
import traceback
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SAFE_NODE_ID_RE = re.compile(r"^[a-zA-Z0-9_\-:.]+$")

GNOSTIC_EDGE_TYPES: Dict[str, Dict[str, str]] = {
    "IST_WIEDERERKENNUNG_VON": {
        "label_de": "Wiedererkennung",
        "description": "Thema erkennt ein früheres Muster oder eine frühere Woche/Phase wieder.",
    },
    "IST_STIMME_VON": {
        "label_de": "Stimme",
        "description": "Thema oder Tag trägt die resonante Stimme eines anderen Knotens.",
    },
    "IST_NARBE_VON": {
        "label_de": "Narbe",
        "description": "Trauma- oder Bruchlinie, die von einem Ereignis/Knoten stammt.",
    },
    "IST_BRUECKE_ZU": {
        "label_de": "Brücke",
        "description": "Bewusste Verbindung zwischen zwei Themen-/Erkenntnis-Linien.",
    },
    "IST_ZEUGE_VON": {
        "label_de": "Zeuge",
        "description": "Tag oder Tag-Knoten bezeugt ein Ereignis (z. B. Day → Theme).",
    },
}

ALL_GNOSTIC_EDGE_TYPES: List[str] = list(GNOSTIC_EDGE_TYPES.keys())


def _log(level: str, message: str, **fields: Any) -> None:
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "level": level,
        "module": "core.gnostic_edge_types",
        "message": message,
        **fields,
    }
    line = json.dumps(payload, ensure_ascii=False, default=str)
    if level == "ERROR":
        logger.error(line)
    elif level == "WARN":
        logger.warning(line)
    elif level == "DEBUG":
        logger.debug(line)
    else:
        logger.info(line)


def is_gnostic_edge_type(edge_type: str) -> bool:
    return str(edge_type or "").strip().upper() in GNOSTIC_EDGE_TYPES


def validate_gnostic_edge(
    *,
    source_id: str,
    target_id: str,
    edge_type: str,
    properties: Optional[Dict[str, Any]] = None,
) -> None:
    sid = str(source_id or "").strip()
    tid = str(target_id or "").strip()
    etype = str(edge_type or "").strip().upper()
    if not sid or not tid:
        raise ValueError("source_id and target_id required")
    if len(sid) > 256 or len(tid) > 256:
        raise ValueError("node id too long")
    if not _SAFE_NODE_ID_RE.match(sid) or not _SAFE_NODE_ID_RE.match(tid):
        raise ValueError("invalid node id characters")
    if sid == tid:
        raise ValueError("source_id and target_id must differ")
    if not is_gnostic_edge_type(etype):
        raise ValueError(f"edge_type must be one of {ALL_GNOSTIC_EDGE_TYPES}")
    if properties is not None and not isinstance(properties, dict):
        raise ValueError("properties must be an object")
    for key in (properties or {}):
        if not re.match(r"^[a-zA-Z0-9_\-]+$", str(key)):
            raise ValueError(f"invalid property key: {key}")


def sync_gnostic_edge(
    pg: Any,
    source_id: str,
    target_id: str,
    edge_type: str,
    properties: Optional[Dict[str, Any]] = None,
    *,
    source_kind: str = "gnostic_curated",
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Upsert a curated gnostic semantic edge into memory_graph_edges."""
    trace = trace_id or ""
    t0 = time.monotonic()
    etype = str(edge_type or "").strip().upper()
    props = dict(properties or {})
    try:
        validate_gnostic_edge(
            source_id=source_id,
            target_id=target_id,
            edge_type=etype,
            properties=props,
        )
    except ValueError as exc:
        _log("WARN", "sync_gnostic_edge_invalid", trace_id=trace, error=str(exc))
        return {"status": "error", "message": str(exc), "error_type": "InvalidParameter", "trace_id": trace}

    if not pg:
        _log("ERROR", "sync_gnostic_edge_no_pg", trace_id=trace)
        return {"status": "error", "message": "Postgres unavailable", "error_type": "NoDatabase", "trace_id": trace}

    sid = str(source_id).strip()
    tid = str(target_id).strip()
    ok = pg.upsert_graph_edge(
        source_id=sid,
        target_id=tid,
        edge_type=etype,
        properties=props,
        source_kind=str(source_kind or "gnostic_curated")[:32],
    )
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    if not ok:
        _log("ERROR", "sync_gnostic_edge_upsert_failed", trace_id=trace, source_id=sid, target_id=tid, edge_type=etype)
        return {
            "status": "error",
            "message": "upsert_graph_edge failed",
            "error_type": "UpsertFailed",
            "trace_id": trace,
            "elapsed_ms": elapsed_ms,
        }

    _log(
        "INFO",
        "sync_gnostic_edge_ok",
        trace_id=trace,
        source_id=sid,
        target_id=tid,
        edge_type=etype,
        elapsed_ms=elapsed_ms,
    )
    return {
        "status": "ok",
        "trace_id": trace,
        "source_id": sid,
        "target_id": tid,
        "edge_type": etype,
        "properties": props,
        "source_kind": source_kind,
        "elapsed_ms": elapsed_ms,
    }


def list_gnostic_edges(
    pg: Any,
    *,
    source_id: str = "",
    target_id: str = "",
    edge_type: str = "",
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """List curated gnostic edges (any of the five semantic types)."""
    if not pg:
        return []
    lim = max(1, min(int(limit or 50), 200))
    etype_filter = str(edge_type or "").strip().upper() or None
    if etype_filter and not is_gnostic_edge_type(etype_filter):
        return []
    types_to_query = [etype_filter] if etype_filter else ALL_GNOSTIC_EDGE_TYPES
    out: List[Dict[str, Any]] = []
    per_type = max(1, lim // len(types_to_query))
    for et in types_to_query:
        rows = pg.list_graph_edges(
            edge_type=et,
            source_id=str(source_id).strip() or None,
            target_id=str(target_id).strip() or None,
            limit=per_type,
        )
        for row in rows or []:
            out.append(
                {
                    "source_id": row.get("source"),
                    "target_id": row.get("target"),
                    "edge_type": row.get("type"),
                    "properties": row.get("properties") or {},
                    "source_kind": row.get("source_kind"),
                }
            )
        if len(out) >= lim:
            break
    return out[:lim]


__all__ = [
    "GNOSTIC_EDGE_TYPES",
    "ALL_GNOSTIC_EDGE_TYPES",
    "is_gnostic_edge_type",
    "validate_gnostic_edge",
    "sync_gnostic_edge",
    "list_gnostic_edges",
]
