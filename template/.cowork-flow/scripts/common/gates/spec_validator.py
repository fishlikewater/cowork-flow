#!/usr/bin/env python3
"""Spec markdown section validator for cowork-flow."""

from __future__ import annotations

import re
from pathlib import Path

SECTION_CONFIG: dict[str, tuple[str, ...]] = {
    "contract": ("Goal", "When to Use", "Rules", "Examples"),
    "skill": ("Overview", "When to Use", "Steps", "Verification"),
    "guide": ("Goal", "When to Use", "Process", "Anti-Rationalization"),
    "default": ("Goal", "Rules"),
}

HEADER_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def validate_sections(file_path: Path | str, spec_type: str = "default") -> tuple[bool, list[str]]:
    """Validate a spec markdown file has all required sections.

    Returns (is_valid, error_messages).
    """
    path = Path(file_path)
    errors: list[str] = []

    if not path.is_file():
        return False, [f"File not found: {path}"]

    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return False, ["File is empty"]

    required = SECTION_CONFIG.get(spec_type)
    if required is None:
        return False, [f"Unknown spec type: {spec_type}"]

    matches = list(HEADER_RE.finditer(content))
    found: dict[str, str] = {}
    for i, m in enumerate(matches):
        name = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end].strip()
        found[name] = body

    for req in required:
        if req not in found:
            errors.append(f"Missing: {req}")
        elif not found[req]:
            errors.append(f"Empty: {req}")

    return (not errors, errors)
