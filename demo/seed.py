#!/usr/bin/env python3
"""
seed.py – Demo data: persons, archivals, graph edges, spark audits.

Created: 2026-08-28
Last updated: 2026-08-28
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kaskade.erip.weighting import archival_erip_suffix_block
from kaskade.memory.postgres_store import add_graph_edge, connect, init_schema, insert_archival, insert_core_block, insert_spark_audit


def ensure_day_node(conn, day: str) -> None:
    conn.execute(
        """
        INSERT INTO memory_graph_nodes (id, node_type, ref_id, label, metadata)
        VALUES (%s, 'day', %s, %s, '{}'::jsonb)
        ON CONFLICT (id) DO NOTHING
        """,
        (f"day_{day}", day, f"day:{day}"),
    )
    conn.commit()

SAMPLE = archival_erip_suffix_block(4, 3, 3, 2)


def main() -> None:
    total_steps = 14
    print("STEP 1: Connecting to database...", flush=True)
    with connect() as conn:
        init_schema(conn)
        print(f"✅ [1/{total_steps}] (7.1%) Schema ready", flush=True)
        today = date.today()
        for i in range(14):
            day = (today - timedelta(days=i)).isoformat()
            pct = ((i + 2) / total_steps) * 100
            content = f"Demo archival for {day}. Alex and Sam discussed project alpha.\n{SAMPLE}"
            mid = insert_archival(
                conn,
                content=content,
                person_id="alex",
                metadata={"episode_date": day, "theme_id": "demo_notes", "recall_inject_l1": f"Alex · demo · {day}"},
                tags=["demo"],
            )
            ensure_day_node(conn, day)
            add_graph_edge(conn, src=f"day_{day}", dst=f"mem-{mid}", edge_type="CONTAINS")
            print(f"✅ [{i+2}/{total_steps}] ({pct:.1f}%) Seeded day {day}", end="\r", flush=True)
        print(f"\n✅ [{13}/{total_steps}] (92.9%) Core blocks", flush=True)
        insert_core_block(conn, label="ABOUT ME", content="Demo agent profile.")
        insert_core_block(conn, label="Weekend Hobbies", content="hiking and photography")
        insert_spark_audit(conn, agent_id="agent", spark_text="Sunset on the trail — felt calm.", extra={"convergent": True})
        print(f"✅ [{total_steps}/{total_steps}] (100.0%) Done — demo seed complete", flush=True)


if __name__ == "__main__":
    main()
