#!/usr/bin/env bash
# File: smoke_release.sh
# Description: Release smoke test for Kaskade Memory (pytest + HTTP checks).
# Created: 2026-08-28
# Last updated: 2026-08-28
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "STEP 1/4: export_check"
python3 scripts/export_check.py

echo "STEP 2/4: pytest unit + integration"
.venv/bin/pytest -q

echo "STEP 3/4: optional live HTTP smoke (BASE_URL)"
BASE_URL="${BASE_URL:-http://localhost:8080}"
if curl -fsS "${BASE_URL}/api/health" >/dev/null 2>&1; then
  curl -fsS "${BASE_URL}/api/health" | python3 -m json.tool
  curl -fsS "${BASE_URL}/api/cascade/days?limit=3" | python3 -m json.tool
  curl -fsS -o /dev/null -w "time-circle HTTP %{http_code}\n" "${BASE_URL}/time-circle/"
else
  echo "SKIP live HTTP — server not reachable at ${BASE_URL}"
fi

echo "STEP 4/4: done — release smoke OK"
