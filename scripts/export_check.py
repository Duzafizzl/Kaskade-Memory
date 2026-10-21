#!/usr/bin/env python3
"""
export_check.py – Release gate: forbidden files, secret patterns and private-identifier leaks (tree or git history).

Usage:
  python scripts/export_check.py                      # scan working tree (CI default)
  python scripts/export_check.py --history            # scan every blob reachable from any ref
  python scripts/export_check.py --history --range origin/main..HEAD   # only blobs introduced in a range

Created: 2026-08-28
Last updated: 2026-10-21
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable, Iterator, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
SELF_REL = "scripts/export_check.py"

FORBIDDEN_NAME_GLOBS = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.keystore",
    "id_rsa*",
    "id_ed25519*",
    "*.db",
    "*.sqlite",
    "*.db-wal",
    "*.db-shm",
]
ALLOWED_NAMES = {"example.env", ".env.example"}

SECRET_PATTERNS = [
    r"sk-or-v1-[0-9a-f]{8,}",
    r"\bsk-[A-Za-z0-9_-]{24,}",
    r"\bxox[abprs]-[A-Za-z0-9-]{8,}",
    r"\bghp_[A-Za-z0-9]{20,}",
    r"\bgithub_pat_[A-Za-z0-9_]{20,}",
    r"\bAKIA[0-9A-Z]{16}\b",
    r"\bAIza[0-9A-Za-z_-]{30,}",
    r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
]

PRIVATE_PATTERNS = [
    r"\bclary\b",
    r"\bmiu\b",
    r"\bmior[eé]\b",
    r"red[ _-]?room",
    r"\bintimacy\b",
    r"\bnic_quant\b",
    r"\bquantbro\b",
    r"\bterzetto\b",
    r"\bpatong\b",
    r"\bultrahuman\b",
    r"\braspbot\b",
    r"\btresorro\b",
    r"\bmyzel\b",
    r"saint[ _-]michael",
    r"\bdiscord_channel",
    r"heyclicky",
    r"clicky_ui",
    r"mini-von-mac",
    r"macsubstrate",
    r"/users/[a-z0-9._-]+/",
    r"/volumes/",
    r"\b192\.168\.\d{1,3}\.\d{1,3}\b",
    r"\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b",
    r"(?<![\w.-])\d{17,20}(?![\w.-])",
]

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "drafts", "tmp", "logs"}
SKIP_DIR_SUFFIXES = (".egg-info",)
MAX_BYTES = 2_000_000

_SECRET_RE = [re.compile(p) for p in SECRET_PATTERNS]
_PRIVATE_RE = [re.compile(p, re.IGNORECASE) for p in PRIVATE_PATTERNS]


def _tty() -> bool:
    return sys.stderr.isatty()


def _progress(i: int, n: int, label: str) -> None:
    if not _tty() or n <= 0:
        return
    pct = (i / n) * 100
    filled = int(pct // 5)
    bar = "█" * filled + "░" * (20 - filled)
    sys.stderr.write(f"\r  {bar} [{i}/{n}] ({pct:5.1f}%) {label[:48]:<48}")
    sys.stderr.flush()


def _banner(title: str) -> None:
    if not _tty():
        return
    line = "═" * (len(title) + 2)
    sys.stderr.write(f"╔{line}╗\n║ {title} ║\n╚{line}╝\n")
    sys.stderr.flush()


def _log(level: str, message: str, **fields: object) -> None:
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "level": level,
        "module": "scripts.export_check",
        "message": message,
        **fields,
    }
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)


def is_forbidden_name(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    if name in ALLOWED_NAMES:
        return False
    return any(fnmatch.fnmatch(name, g) for g in FORBIDDEN_NAME_GLOBS)


def scan_text(rel: str, data: bytes) -> List[str]:
    """Return finding strings for one file body. Binary (NUL byte) bodies are skipped."""
    if rel == SELF_REL or b"\x00" in data[:8192]:
        return []
    text = data[:MAX_BYTES].decode("utf-8", errors="replace")
    findings: List[str] = []
    for rx in _SECRET_RE:
        if rx.search(text):
            findings.append(f"secret pattern {rx.pattern!r} in {rel}")
    for rx in _PRIVATE_RE:
        if rx.search(text):
            findings.append(f"private identifier {rx.pattern!r} in {rel}")
    return findings


def iter_tree_files() -> Iterator[Tuple[str, Path]]:
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(ROOT).parts
        if any(p in SKIP_DIRS or p.endswith(SKIP_DIR_SUFFIXES) for p in rel_parts[:-1]):
            continue
        yield path.relative_to(ROOT).as_posix(), path


def scan_tree() -> List[str]:
    files = list(iter_tree_files())
    errors: List[str] = []
    for i, (rel, path) in enumerate(files, 1):
        _progress(i, len(files), rel)
        if is_forbidden_name(rel):
            errors.append(f"forbidden file: {rel}")
            continue
        try:
            errors.extend(scan_text(rel, path.read_bytes()))
        except OSError as exc:
            errors.append(f"read failed {rel}: {exc}")
    if _tty():
        sys.stderr.write("\n")
    return errors


def _git(args: List[str], stdin: bytes | None = None) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, input=stdin, capture_output=True, check=True).stdout


def iter_history_blobs(rev_range: str) -> Iterable[Tuple[str, str]]:
    rev_args = rev_range.split() if rev_range else ["--all"]
    seen = set()
    for line in _git(["rev-list", "--objects", *rev_args]).decode("utf-8", "replace").splitlines():
        parts = line.split(" ", 1)
        if len(parts) != 2 or not parts[1]:
            continue
        sha, rel = parts
        if sha in seen:
            continue
        seen.add(sha)
        yield sha, rel


def scan_history(rev_range: str) -> List[str]:
    blobs = [(sha, rel) for sha, rel in iter_history_blobs(rev_range)]
    types = _git(["cat-file", "--batch-check=%(objecttype)"], stdin="\n".join(s for s, _ in blobs).encode()).decode().split()
    blobs = [b for b, t in zip(blobs, types) if t == "blob"]
    errors: List[str] = []
    for i, (sha, rel) in enumerate(blobs, 1):
        top = rel.split("/", 1)[0]
        if top in SKIP_DIRS:
            continue
        _progress(i, len(blobs), rel)
        if is_forbidden_name(rel):
            errors.append(f"forbidden file in history: {rel} (blob {sha[:10]})")
            continue
        data = _git(["cat-file", "blob", sha])
        errors.extend(f"{e} (blob {sha[:10]})" for e in scan_text(rel, data))
    if _tty():
        sys.stderr.write("\n")
    return errors


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1] if __doc__ else "")
    ap.add_argument("--history", action="store_true", help="scan git blobs instead of the working tree")
    ap.add_argument("--range", default="", help="rev range for --history, e.g. 'origin/main..HEAD' (default: --all)")
    args = ap.parse_args(argv)

    started = time.monotonic()
    mode = "history" if args.history else "tree"
    _banner(f"KASKADE EXPORT CHECK · {mode}")
    try:
        errors = scan_history(args.range) if args.history else scan_tree()
    except subprocess.CalledProcessError as exc:
        _log("ERROR", "git_failed", cmd=" ".join(exc.cmd), stderr=exc.stderr.decode("utf-8", "replace")[:300])
        return 2
    duration_ms = int((time.monotonic() - started) * 1000)
    if errors:
        print("EXPORT CHECK FAILED:", file=sys.stderr)
        for e in errors[:100]:
            print(f"  ❌ {e}", file=sys.stderr)
        _log("ERROR", "export_check_failed", mode=mode, findings_n=len(errors), duration_ms=duration_ms)
        return 1
    print("EXPORT CHECK OK")
    _log("INFO", "export_check_ok", mode=mode, duration_ms=duration_ms)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
