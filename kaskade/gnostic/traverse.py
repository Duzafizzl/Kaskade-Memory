#!/usr/bin/env python3
"""
traverse.py – Gnostic Search: BFS graph traversal until convergence.

Created: 2026-08-28
Last updated: 2026-08-28
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections import deque
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

DEFAULT_EDGE_TYPES = ["CO_RECALLED_WITH", "TAGGED_WITH", "ABOUT", "REFERENCES"]


def gnostic_traverse(
    *,
    seeds: List[str],
    edges: List[Dict[str, Any]],
    hops: int = 3,
    edge_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Traverse in-memory edge list until multiple paths meet (gnostic moment)."""
    trace_id = str(uuid.uuid4())
    start = time.monotonic()
    allowed = set(edge_types or DEFAULT_EDGE_TYPES)
    adj: Dict[str, List[str]] = {}
    for e in edges:
        if e.get("edge_type") not in allowed:
            continue
        adj.setdefault(e["src_node_id"], []).append(e["dst_node_id"])
        adj.setdefault(e["dst_node_id"], []).append(e["src_node_id"])

    visited: Set[str] = set()
    convergence: Dict[str, int] = {}
    queue: deque[tuple[str, int]] = deque((s, 0) for s in seeds)

    while queue:
        node, depth = queue.popleft()
        if depth > hops:
            continue
        if node in visited:
            convergence[node] = convergence.get(node, 1) + 1
            continue
        visited.add(node)
        for nxt in adj.get(node, []):
            queue.append((nxt, depth + 1))

    hubs = sorted(convergence.items(), key=lambda x: -x[1])[:5]
    moment = hubs[0][0] if hubs else (seeds[0] if seeds else None)
    out = {
        "trace_id": trace_id,
        "gnostic_moment": moment,
        "convergence_hubs": [{"node": n, "hits": c} for n, c in hubs],
        "visited_n": len(visited),
        "duration_ms": int((time.monotonic() - start) * 1000),
    }
    logger.info(json.dumps({"level": "INFO", "module": "gnostic.traverse", "message": "traverse_done", **out}))
    return out
