"""
kaskade.config – YAML-backed demo persons, channels, and path helpers.

Created: 2026-08-28
Last updated: 2026-08-28
"""

from __future__ import annotations

import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import yaml

_REPO = Path(__file__).resolve().parents[1]
_CONFIG = _REPO / "config"
_PERSON_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,48}$")


def repo_root() -> Path:
    raw = os.getenv("KASKADE_REPO_ROOT", "").strip()
    return Path(raw) if raw else _REPO


@lru_cache(maxsize=1)
def _load_yaml(name: str) -> Dict[str, Any]:
    path = _CONFIG / name
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def person_alias_map() -> Dict[str, str]:
    data = _load_yaml("demo_persons.yaml")
    aliases = data.get("aliases") or {}
    return {str(k).lower(): str(v).lower() for k, v in aliases.items()}


def known_person_ids() -> frozenset[str]:
    data = _load_yaml("demo_persons.yaml")
    ids = data.get("known_person_ids") or ["alex", "sam", "agent"]
    return frozenset(str(x).lower() for x in ids)


def normalize_person_id(raw: Any) -> str:
    if raw is None:
        return ""
    s = unicodedata.normalize("NFKC", str(raw)).strip().lower()
    if not s:
        return ""
    aliases = person_alias_map()
    return aliases.get(s, s)


def person_display_labels() -> Dict[str, str]:
    data = _load_yaml("demo_persons.yaml")
    labels = data.get("display_labels") or {}
    return {str(k).lower(): str(v) for k, v in labels.items()}


def persons_alias_config() -> Dict[str, Any]:
    return {
        "known": sorted(known_person_ids()),
        "aliases": person_alias_map(),
        "display_labels": person_display_labels(),
    }


def core_memory_gates_config() -> List[Dict[str, Any]]:
    data = _load_yaml("core_memory_gates.yaml")
    return list(data.get("gates") or [])
