#!/usr/bin/env python3
"""Export check smoke test."""

import subprocess
import sys
from pathlib import Path


def test_export_check_passes():
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run([sys.executable, str(root / "scripts" / "export_check.py")], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
