#!/usr/bin/env python3
"""
export_check.py – CI gate: forbidden paths, blocklist strings, Miu-specific leaks.

Created: 2026-08-28
Last updated: 2026-08-28
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_GLOBS = [
    ".env",
    "data/*.db",
    "**/.env",
    "**/*.pem",
]

BLOCKLIST_PATTERNS = [
    r"\bclary\b",
    r"\bmiu\b",
    r"\bred_room\b",
    r"\bintimacy\b",
    r"sk-or-v1-",
    r"xoxb-",
    r"ghp_",
    r"192\.168\.\d+\.\d+",
    r"mini-von-mac",
    r"macsubstrate",
]

SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"}


def iter_text_files() -> list[Path]:
    out: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix in {".py", ".md", ".yaml", ".yml", ".html", ".js", ".css", ".env", ".json", ".sh"}:
            out.append(path)
    return out


def main() -> int:
    errors: list[str] = []
    for path in iter_text_files():
        rel = path.relative_to(ROOT)
        if rel.as_posix() == "scripts/export_check.py":
            continue
        if rel.name == ".env" or rel.name.startswith(".env."):
            errors.append(f"forbidden file: {rel}")
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace").lower()
        except OSError as exc:
            errors.append(f"read failed {rel}: {exc}")
            continue
        for pat in BLOCKLIST_PATTERNS:
            if re.search(pat, text, re.I):
                errors.append(f"blocklist match {pat!r} in {rel}")
    if errors:
        print("EXPORT CHECK FAILED:", file=sys.stderr)
        for e in errors[:50]:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("EXPORT CHECK OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
