#!/usr/bin/env python3
"""Common file helpers for cowork-flow scripts."""

from __future__ import annotations

import json
from pathlib import Path


def read_json_file(path: Path) -> dict | None:
    """Read and parse a JSON file. Returns None if missing or unreadable."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        # A read-only query never destroys an authoritative file.
        import sys
        print(f"Warning: Corrupt JSON preserved: {path}", file=sys.stderr)
        return None


def read_text_utf8(path: Path) -> str:
    """Read a text file as UTF-8; return "" if missing or unreadable."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
