#!/usr/bin/env python3
"""
agent_hook.py – Generic coding-agent hook for EOD maintainer passes.

Created: 2026-08-28
Last updated: 2026-08-28
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Protocol

logger = logging.getLogger(__name__)


@dataclass
class AgentRunResult:
    ok: bool
    provider: str
    stdout: str
    stderr: str
    duration_sec: float
    exit_code: int


class MaintainerAgentHook(Protocol):
    name: str

    def run_maintainer_pass(
        self,
        *,
        day_id: str,
        prompt: str,
        allowed_paths: List[str],
        timeout_sec: int,
    ) -> AgentRunResult: ...


class NoOpAdapter:
    name = "noop"

    def run_maintainer_pass(self, *, day_id: str, prompt: str, allowed_paths: List[str], timeout_sec: int) -> AgentRunResult:
        logger.info(json.dumps({"level": "INFO", "module": "agent_hook", "message": "noop_skip", "day_id": day_id}))
        return AgentRunResult(ok=True, provider=self.name, stdout="", stderr="", duration_sec=0.0, exit_code=0)


class SubprocessAdapter:
    name = "subprocess"

    def __init__(self, cmd_template: Optional[str] = None) -> None:
        self.cmd_template = cmd_template or os.getenv("KASKADE_EOD_AGENT_CMD", "echo noop")

    def run_maintainer_pass(self, *, day_id: str, prompt: str, allowed_paths: List[str], timeout_sec: int) -> AgentRunResult:
        start = time.monotonic()
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
            fh.write(prompt)
            prompt_path = fh.name
        cmd = self.cmd_template.format(prompt_path=prompt_path, day_id=day_id)
        args = shlex.split(cmd)
        try:
            proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout_sec)
            ok = proc.returncode == 0
            return AgentRunResult(
                ok=ok,
                provider=self.name,
                stdout=proc.stdout or "",
                stderr=proc.stderr or "",
                duration_sec=time.monotonic() - start,
                exit_code=proc.returncode,
            )
        except subprocess.TimeoutExpired as exc:
            return AgentRunResult(ok=False, provider=self.name, stdout="", stderr=str(exc), duration_sec=time.monotonic() - start, exit_code=-1)


class CursorCliAdapter(SubprocessAdapter):
    name = "cursor"

    def __init__(self) -> None:
        super().__init__(os.getenv("KASKADE_EOD_AGENT_CMD", "cursor agent --print {prompt_path}"))


def get_agent_hook() -> MaintainerAgentHook:
    provider = (os.getenv("KASKADE_EOD_AGENT_PROVIDER") or "noop").strip().lower()
    if provider == "cursor":
        return CursorCliAdapter()
    if provider == "subprocess":
        return SubprocessAdapter()
    return NoOpAdapter()


def cascade_eod_agent_enabled() -> bool:
    return (os.getenv("KASKADE_EOD_AGENT_PROVIDER") or "noop").strip().lower() != "noop"


def run_eod_agent_pass(*, day_id: str, prompt: str, allowed_paths: List[str]) -> AgentRunResult:
    timeout = int(os.getenv("KASKADE_EOD_AGENT_TIMEOUT_SEC") or "720")
    hook = get_agent_hook()
    return hook.run_maintainer_pass(day_id=day_id, prompt=prompt, allowed_paths=allowed_paths, timeout_sec=timeout)
