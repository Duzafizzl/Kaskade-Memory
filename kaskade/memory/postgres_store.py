#!/usr/bin/env python3
"""
postgres_store.py – Minimal Postgres memory + graph store for Kaskade Memory OSS.

Created: 2026-08-28
Last updated: 2026-08-28
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional

import psycopg
from psycopg.rows import dict_row

from kaskade.erip.weighting import ERIPScores, merge_erip_tags, parse_mandatory_erip_from_content

logger = logging.getLogger(__name__)


def database_url() -> str:
    return (os.getenv("DATABASE_URL") or "postgresql://kaskade:kaskade@localhost:5432/kaskade").strip()


@contextmanager
def connect() -> Generator[psycopg.Connection, None, None]:
    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        yield conn


def init_schema(conn: psycopg.Connection) -> None:
    sql = (os.path.join(os.path.dirname(__file__), "..", "..", "migrations", "001_init.sql"))
    path = os.path.abspath(sql)
    with open(path, encoding="utf-8") as fh:
        conn.execute(fh.read())
    conn.commit()


def insert_archival(
    conn: psycopg.Connection,
    *,
    content: str,
    person_id: str,
    metadata: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
) -> str:
    mid = str(uuid.uuid4())
    meta = dict(metadata or {})
    meta["person_id"] = person_id
    erip = parse_mandatory_erip_from_content(content)
    if erip:
        meta["erip"] = erip.to_dict()
    final_tags = merge_erip_tags(list(tags or []), erip) if erip else list(tags or [])
    conn.execute(
        """
        INSERT INTO memories (id, memory_type, label, content, metadata, tags, created_at, updated_at)
        VALUES (%s, 'archival', 'archival', %s, %s::jsonb, %s::jsonb, NOW(), NOW())
        """,
        (mid, content, json.dumps(meta), json.dumps(final_tags)),
    )
    conn.execute(
        "INSERT INTO memory_graph_nodes (id, node_type, ref_id, label, metadata) VALUES (%s, 'archival', %s, %s, %s::jsonb)",
        (f"mem-{mid}", mid, f"archival:{mid[:8]}", json.dumps({"person_id": person_id})),
    )
    conn.commit()
    return mid


def insert_core_block(
    conn: psycopg.Connection,
    *,
    label: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    mid = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO memories (id, memory_type, label, content, metadata, tags, created_at, updated_at)
        VALUES (%s, 'core', %s, %s, %s::jsonb, '[]'::jsonb, NOW(), NOW())
        ON CONFLICT (label) WHERE memory_type = 'core' DO UPDATE SET content = EXCLUDED.content, metadata = EXCLUDED.metadata, updated_at = NOW()
        RETURNING id
        """,
        (mid, label, content, json.dumps(metadata or {})),
    )
    conn.commit()
    return mid


def list_cascade_days(conn: psycopg.Connection, *, limit: int = 60) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT DISTINCT metadata->>'episode_date' AS day_id, COUNT(*) AS archival_count
        FROM memories
        WHERE memory_type = 'archival' AND metadata ? 'episode_date'
        GROUP BY 1 ORDER BY 1 DESC LIMIT %s
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_day_bundle(conn: psycopg.Connection, day_id: str) -> Dict[str, Any]:
    archivals = conn.execute(
        """
        SELECT id, content, metadata, tags FROM memories
        WHERE memory_type = 'archival' AND metadata->>'episode_date' = %s
        ORDER BY created_at
        """,
        (day_id,),
    ).fetchall()
    themes = conn.execute(
        """
        SELECT DISTINCT metadata->>'theme_id' AS theme_id FROM memories
        WHERE memory_type = 'archival' AND metadata->>'episode_date' = %s AND metadata ? 'theme_id'
        """,
        (day_id,),
    ).fetchall()
    return {
        "day_id": day_id,
        "archivals": [dict(r) for r in archivals],
        "themes": [r["theme_id"] for r in themes if r.get("theme_id")],
    }


def add_graph_edge(conn: psycopg.Connection, *, src: str, dst: str, edge_type: str) -> None:
    conn.execute(
        """
        INSERT INTO memory_graph_edges (id, src_node_id, dst_node_id, edge_type, metadata)
        VALUES (%s, %s, %s, %s, '{}'::jsonb)
        ON CONFLICT DO NOTHING
        """,
        (str(uuid.uuid4()), src, dst, edge_type),
    )
    conn.commit()


def insert_spark_audit(
    conn: psycopg.Connection,
    *,
    agent_id: str,
    spark_text: str,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    aid = str(uuid.uuid4())
    payload = {"spontaneous_spark": True, **(extra or {})}
    conn.execute(
        """
        INSERT INTO recall_gnostic_shadow_audit (id, agent_id, spark_text, extra, created_at)
        VALUES (%s, %s, %s, %s::jsonb, NOW())
        """,
        (aid, agent_id, spark_text, json.dumps(payload)),
    )
    conn.commit()
    return aid
