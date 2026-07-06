#!/usr/bin/env python3
"""JSONL file format validator for cowork-flow context files."""

from __future__ import annotations

import json
from pathlib import Path


def validate_format(file_path: Path | str) -> tuple[bool, list[str]]:
    """Validate a JSONL file and return (is_valid, error_messages)."""
    path = Path(file_path)
    errors: list[str] = []

    try:
        content = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as exc:
        return False, [f"Cannot read file: {exc}"]

    if not content:
        return False, ["File is empty"]

    for line_no, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"Line {line_no}: Invalid JSON: {exc}")

    return (not errors, errors)
