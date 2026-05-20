#!/usr/bin/env python3
"""Common file helpers for cowork-flow scripts."""

from __future__ import annotations

import json
from pathlib import Path


def read_json_file(path: Path) -> dict | None:
    """Read and parse a JSON file."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def write_json_file(path: Path, data: dict) -> bool:
    """Write dict to JSON file."""
    try:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except OSError:
        return False
