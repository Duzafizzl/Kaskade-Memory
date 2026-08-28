#!/usr/bin/env python3
"""
main.py – Thin FastAPI server for Kaskade Memory OSS.

Created: 2026-08-28
Last updated: 2026-08-28
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from kaskade.cascade.eod.reconcile import run_eod_reconcile
from kaskade.cascade.maintainer.queue import read_queue
from kaskade.erip.weighting import parse_mandatory_erip_from_content
from kaskade.gnostic.shadow import maybe_generate_spark
from kaskade.gnostic.traverse import gnostic_traverse
from kaskade.memory.postgres_store import connect, get_day_bundle, init_schema, insert_archival, list_cascade_days
from kaskade.memory.prompt_gates import filter_core_blocks_for_prompt
from kaskade.reflex.significance_gate import evaluate_cascade_significance

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

app = FastAPI(title="Kaskade Memory", version="0.1.0")


@app.on_event("startup")
def _startup() -> None:
    try:
        with connect() as conn:
            init_schema(conn)
    except Exception:
        pass


class ArchivalInsert(BaseModel):
    content: str
    person_id: str
    theme_id: Optional[str] = None
    episode_date: Optional[str] = None


class TraverseRequest(BaseModel):
    seeds: List[str]
    edges: List[Dict[str, Any]]
    hops: int = 3


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/cascade/days")
def cascade_days(limit: int = 60) -> Dict[str, Any]:
    with connect() as conn:
        return {"days": list_cascade_days(conn, limit=limit)}


@app.get("/api/cascade/day/{day_id}")
def cascade_day(day_id: str) -> Dict[str, Any]:
    with connect() as conn:
        return get_day_bundle(conn, day_id)


@app.get("/api/cascade/persons/aliases")
def persons_aliases() -> Dict[str, Any]:
    from kaskade.config import persons_alias_config

    return persons_alias_config()


@app.post("/api/cascade/archival")
def archival_insert(body: ArchivalInsert) -> Dict[str, Any]:
    gate = evaluate_cascade_significance(content=body.content, theme_id=body.theme_id)
    if gate.get("decision") == "reject":
        raise HTTPException(400, detail=gate)
    meta: Dict[str, Any] = {"episode_date": body.episode_date} if body.episode_date else {}
    if body.theme_id:
        meta["theme_id"] = body.theme_id
    with connect() as conn:
        mid = insert_archival(conn, content=body.content, person_id=body.person_id, metadata=meta)
    return {"memory_id": mid, "gate": gate}


@app.post("/api/cascade/gnostic_traverse")
def cascade_gnostic_traverse(body: TraverseRequest) -> Dict[str, Any]:
    return gnostic_traverse(seeds=body.seeds, edges=body.edges, hops=body.hops)


@app.post("/api/gnostic/spark/simulate")
def spark_simulate() -> Dict[str, Any]:
    candidates = [{"memory_id": "demo-1", "content": "Walked the trail at sunset.", "score": 0.8, "privacy": 2, "recall_inject_l1": "Alex · hike · evening"}]
    spark = maybe_generate_spark(agent_id="agent", candidates=candidates)
    return {"spark": spark}


@app.post("/api/cascade/eod/{day_id}")
def cascade_eod(day_id: str, dry_run: bool = False) -> Dict[str, Any]:
    return run_eod_reconcile(day_id=day_id, dry_run=dry_run)


@app.get("/api/cascade/queue")
def cascade_queue(status: Optional[str] = None) -> Dict[str, Any]:
    return {"items": read_queue(status=status)}


@app.get("/api/memory/core/filter")
def core_filter(channel_id: str = "", message_type: str = "user", message: str = "") -> Dict[str, Any]:
    blocks = [
        {"label": "Weekend Hobbies", "content": "hiking trails near the lake"},
        {"label": "Project Alpha Notes", "content": "sprint roadmap for alpha"},
        {"label": "ABOUT ME", "content": "always visible demo block"},
    ]
    return {"blocks": filter_core_blocks_for_prompt(blocks, channel_id=channel_id, message_type=message_type, user_message=message)}


if WEB.is_dir():
    app.mount("/time-circle", StaticFiles(directory=str(WEB / "time-circle"), html=True), name="time-circle")
    app.mount("/gnostic-shadow", StaticFiles(directory=str(WEB / "gnostic-shadow"), html=True), name="gnostic-shadow")
