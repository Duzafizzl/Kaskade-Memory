#!/usr/bin/env python3
"""
test_integration_api.py – Release smoke tests against Postgres + FastAPI.

Created: 2026-08-28
Last updated: 2026-10-21
"""

from __future__ import annotations

import os
from datetime import date

from kaskade.erip.weighting import archival_erip_suffix_block

ERIP_SAMPLE = archival_erip_suffix_block(4, 3, 3, 2)

import pytest
from fastapi.testclient import TestClient

from kaskade.memory.postgres_store import connect, get_day_bundle, init_schema, insert_archival, list_cascade_days


def _db_ready() -> bool:
    try:
        with connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="Postgres not reachable via DATABASE_URL")


@pytest.fixture(scope="module")
def client():
    from api.main import app

    with TestClient(app) as test_client:
        yield test_client


def test_health_reports_database(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "connected"


def test_cascade_days_and_day_bundle(client: TestClient):
    today = date.today().isoformat()
    with connect() as conn:
        init_schema(conn)
        insert_archival(
            conn,
            content=f"Integration test archival for release gate.\n{ERIP_SAMPLE}",
            person_id="alex",
            metadata={"episode_date": today, "theme_id": "release_gate", "recall_inject_l1": "Alex · release"},
        )
        days = list_cascade_days(conn, limit=5)
        assert any(row["day_id"] == today for row in days)
        bundle = get_day_bundle(conn, today)
        assert bundle["themes"]
        assert bundle["themes"][0]["archivals"]

    response = client.get("/api/cascade/days?limit=5")
    assert response.status_code == 200
    days_payload = response.json()["days"]
    assert any(row["day_id"] == today for row in days_payload)
    assert all("theme_count" in row for row in days_payload)

    day_response = client.get(f"/api/cascade/day/{today}")
    assert day_response.status_code == 200
    day_json = day_response.json()
    assert day_json["themes"][0]["archivals"]


def test_archival_insert_stamps_episode_date(client: TestClient):
    response = client.post(
        "/api/cascade/archival",
        json={
            "content": f"Release smoke insert without explicit episode date.\n{ERIP_SAMPLE}",
            "person_id": "alex",
            "theme_id": "release_gate",
        },
    )
    assert response.status_code == 200
    memory_id = response.json()["memory_id"]

    memory_response = client.get(f"/api/cascade/memory/{memory_id}")
    assert memory_response.status_code == 200
    metadata = memory_response.json()["metadata"]
    assert metadata.get("episode_date")


def test_time_circle_html_served(client: TestClient):
    response = client.get("/time-circle/")
    assert response.status_code == 200
    body = response.text
    assert "js/time_circle_data.js" in body or "time_circle_data.js" in body
    assert "kaskade" in body.lower()


def test_root_redirects_to_time_circle(client: TestClient):
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (307, 308)
    assert response.headers["location"].endswith("/time-circle/")


def test_spark_and_spread_simulate(client: TestClient):
    spark = client.post("/api/gnostic/spark/simulate", json={"seeds": ["hiking-trail"]})
    assert spark.status_code == 200
    payload = spark.json()["spark"]
    if payload:
        assert payload["memory_id"] != "mem-hike-03"
        assert "spark_text" in payload

    rise = client.post(
        "/api/cascade/spread/simulate",
        json={"turn_text": "should we do the ridge loop this weekend if my boots arrive?"},
    )
    assert rise.status_code == 200
    body = rise.json()
    assert body["fired"] is True
    assert "hiking-trail" in body["converged_themes"]
    assert all("Knee" not in line for line in body["inject_lines"])
    assert set(body.keys()) <= {
        "trace_id",
        "fired",
        "reason",
        "signals",
        "converged_themes",
        "leaf_ids",
        "inject_lines",
        "duration_ms",
    }


def test_gnostic_shadow_page_is_honest(client: TestClient):
    response = client.get("/gnostic-shadow/")
    assert response.status_code == 200
    text = response.text.lower()
    assert "bridge rise" in text
    assert "gnostic spark" in text
    assert "architecture doc" in text
