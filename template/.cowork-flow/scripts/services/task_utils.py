#!/usr/bin/env python3
"""Task-directory lookup by name."""

from __future__ import annotations

from pathlib import Path


def find_task_by_name(task_name: str, tasks_dir: Path) -> Path | None:
    """Exact directory name first, then a '-<name>' suffix match."""
    if not task_name or not tasks_dir or not tasks_dir.is_dir():
        return None

    # Try exact match first
    exact_match = tasks_dir / task_name
    if exact_match.is_dir():
        return exact_match

    # Suffix match: "my-task" also matches "01-21-my-task".
    for candidate in tasks_dir.iterdir():
        if candidate.is_dir() and candidate.name.endswith(f"-{task_name}"):
            return candidate

    return None
