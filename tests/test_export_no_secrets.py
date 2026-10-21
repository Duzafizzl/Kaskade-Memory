#!/usr/bin/env python3
"""
test_export_no_secrets.py – Working-tree export gate must stay green.

Created: 2026-08-28
Last updated: 2026-10-20
"""

import subprocess
import sys
from pathlib import Path


def test_export_check_passes():
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run([sys.executable, str(root / "scripts" / "export_check.py")], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr + proc.stdout


def test_gitignore_keeps_drafts_local():
    root = Path(__file__).resolve().parents[1]
    ignored = (root / ".gitignore").read_text(encoding="utf-8")
    assert "drafts/" in ignored


def test_export_check_help_lists_history():
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, str(root / "scripts" / "export_check.py"), "--help"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "--history" in proc.stdout
