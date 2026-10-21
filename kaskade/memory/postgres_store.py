#!/usr/bin/env python3
"""
postgres_store.py – Minimal Postgres memory + graph store for Kaskade Memory OSS.

Created: 2026-08-28
Last updated: 2026-10-20
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

from kaskade.cascade.envelope import stamp_archival_metadata
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
    meta = stamp_archival_metadata(metadata, person_id=person_id)
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


def _coerce_json_obj(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _archival_row_to_ui(row: Dict[str, Any]) -> Dict[str, Any]:
    meta = _coerce_json_obj(row.get("metadata"))
    content = str(row.get("content") or "")
    return {
        "memory_id": str(row["id"]),
        "content": content,
        "content_preview": content[:200],
        "l1": meta.get("recall_inject_l1") or content[:120],
        "metadata": meta,
        "tags": row.get("tags") or [],
    }


def list_cascade_days(conn: psycopg.Connection, *, limit: int = 60) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            metadata->>'episode_date' AS day_id,
            COUNT(*)::int AS archival_count,
            COUNT(DISTINCT NULLIF(metadata->>'theme_id', ''))::int AS theme_count,
            ('day_' || (metadata->>'episode_date')) AS node_id
        FROM memories
        WHERE memory_type = 'archival' AND metadata ? 'episode_date'
        GROUP BY 1
        ORDER BY 1 DESC
        LIMIT %s
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
    archivals_ui = [_archival_row_to_ui(dict(r)) for r in archivals]
    theme_map: Dict[str, List[Dict[str, Any]]] = {}
    for archival in archivals_ui:
        theme_id = str((archival.get("metadata") or {}).get("theme_id") or "untagged")
        theme_map.setdefault(theme_id, []).append(archival)
    themes = [
        {"theme_id": theme_id, "id": theme_id, "archivals": items}
        for theme_id, items in sorted(theme_map.items())
    ]
    return {
        "day_id": day_id,
        "archivals": archivals_ui,
        "themes": themes,
    }


def get_archival_memory(conn: psycopg.Connection, memory_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        """
        SELECT id, content, metadata, tags, created_at
        FROM memories
        WHERE id = %s AND memory_type = 'archival'
        """,
        (memory_id,),
    ).fetchone()
    if not row:
        return None
    payload = _archival_row_to_ui(dict(row))
    payload["created_at"] = row.get("created_at")
    return payload


def suggest_themes(conn: psycopg.Connection, *, q: str = "", limit: int = 12) -> List[Dict[str, Any]]:
    pattern = f"%{q.strip().lower()}%" if q.strip() else "%"
    rows = conn.execute(
        """
        SELECT DISTINCT metadata->>'theme_id' AS theme_id
        FROM memories
        WHERE memory_type = 'archival'
          AND metadata ? 'theme_id'
          AND LOWER(metadata->>'theme_id') LIKE %s
        ORDER BY 1
        LIMIT %s
        """,
        (pattern, limit),
    ).fetchall()
    return [{"theme_id": r["theme_id"]} for r in rows if r.get("theme_id")]


def suggest_persons(conn: psycopg.Connection, *, q: str = "", limit: int = 12) -> List[Dict[str, Any]]:
    pattern = f"%{q.strip().lower()}%" if q.strip() else "%"
    rows = conn.execute(
        """
        SELECT DISTINCT metadata->>'person_id' AS person_id
        FROM memories
        WHERE memory_type = 'archival'
          AND metadata ? 'person_id'
          AND LOWER(metadata->>'person_id') LIKE %s
        ORDER BY 1
        LIMIT %s
        """,
        (pattern, limit),
    ).fetchall()
    return [{"person_id": r["person_id"]} for r in rows if r.get("person_id")]


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


def list_spark_audits_for_day(conn: psycopg.Connection, day_id: str) -> List[Dict[str, Any]]:
    """Read-only: Spark audit rows created on `day_id` (UTC date). Omits spark_text by design."""
    rows = conn.execute(
        """
        SELECT id::text AS id, agent_id, extra, created_at
        FROM recall_gnostic_shadow_audit
        WHERE (created_at AT TIME ZONE 'UTC')::date = %s::date
        ORDER BY created_at ASC, id ASC
        """,
        (day_id,),
    ).fetchall()
    out = [{**dict(r), "extra": _coerce_json_obj(r.get("extra"))} for r in rows]
    logger.debug(json.dumps({"level": "DEBUG", "message": "spark_audits_listed", "day_id": day_id, "rows_n": len(out)}))
    return out
