#!/usr/bin/env python3
"""Common file helpers for cowork-flow scripts."""

from __future__ import annotations

import json
import os
from pathlib import Path


def read_json_file(path: Path) -> dict | None:
    """Read and parse a JSON file. Returns None if missing or unreadable."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError):
        # Corrupt/unreadable — remove to avoid orphan state, then report missing
        import sys
        print(f"Warning: Corrupt JSON cleaned up: {path}", file=sys.stderr)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        return None


def read_text_utf8(path: Path) -> str:
    """Read a text file as UTF-8; return "" if missing or unreadable."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def write_json_file(path: Path, data: dict) -> bool:
    """Write dict to JSON file atomically (temp + os.replace)."""
    try:
        json_text = json.dumps(data, indent=2, ensure_ascii=False)
        tmp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        tmp_path.write_text(json_text, encoding="utf-8")
        os.replace(tmp_path, path)
        return True
    except OSError:
        return False
