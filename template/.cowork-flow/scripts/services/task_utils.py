#!/usr/bin/env python3
"""
Task utility functions.

Provides:
    find_task_by_name  - Find task directory by name
"""

from __future__ import annotations

from pathlib import Path


# =============================================================================
# Task Lookup
# =============================================================================

def find_task_by_name(task_name: str, tasks_dir: Path) -> Path | None:
    """Find task directory by name (exact or suffix match).

    Args:
        task_name: Task name to find.
        tasks_dir: Tasks directory path.

    Returns:
        Absolute path to task directory, or None if not found.
    """
    if not task_name or not tasks_dir or not tasks_dir.is_dir():
        return None

    # Try exact match first
    exact_match = tasks_dir / task_name
    if exact_match.is_dir():
        return exact_match

    # Try suffix match (e.g., "my-task" matches "01-21-my-task")
    for candidate in tasks_dir.iterdir():
        if candidate.is_dir() and candidate.name.endswith(f"-{task_name}"):
            return candidate

    return None
