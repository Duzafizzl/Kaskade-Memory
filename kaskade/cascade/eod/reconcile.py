#!/usr/bin/env python3
"""
reconcile.py – EOD gap scan, mechanical linking, optional agent pass.

Created: 2026-08-28
Last updated: 2026-08-28
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from kaskade.cascade.eod.agent_hook import cascade_eod_agent_enabled, run_eod_agent_pass
from kaskade.cascade.eod.agent_scope_guard import build_scope_prompt_section, resolve_allowed_write_paths
from kaskade.cascade.eod.signals import build_signal_layers
from kaskade.cascade.maintainer.queue import list_pending, read_queue
from kaskade.config import repo_root

logger = logging.getLogger(__name__)


def run_eod_reconcile(*, day_id: str, agent_id: str = "agent", dry_run: bool = False) -> Dict[str, Any]:
    deferred = [r for r in list_pending(include_deferred=True) if r.get("episode_date") == day_id]
    signals = build_signal_layers(day_id=day_id, agent_id=agent_id)
    report: Dict[str, Any] = {
        "day_id": day_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "deferred_count": len(deferred),
        "deferred_items": deferred[:50],
        "signal_layers": signals,
        "agent_pass": None,
    }
    out_dir = repo_root() / "demo" / "cascade" / day_id
    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "CASCADE_EOD_REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if cascade_eod_agent_enabled() and not dry_run:
        allowed = resolve_allowed_write_paths(repo_root(), day_id)
        prompt_path = repo_root() / "workflows" / "prompts" / "EOD_MAINTAINER_AGENT.md"
        prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.is_file() else f"Maintain cascade for {day_id}"
        prompt += "\n\n" + build_scope_prompt_section(allowed)
        report["agent_pass"] = run_eod_agent_pass(day_id=day_id, prompt=prompt, allowed_paths=allowed).__dict__
    logger.info(json.dumps({"level": "INFO", "module": "reconcile", "message": "eod_complete", "day_id": day_id}))
    return report
