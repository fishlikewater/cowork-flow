#!/usr/bin/env python3
"""Project readiness gates for task start.

cowork-flow ships no built-in gates: a project that needs its own start
conditions extends this module. A non-empty return value blocks
`task next <dir> --run` with TASK-READINESS-001, and a missing or raising
module blocks start as well.
"""

from __future__ import annotations

from pathlib import Path


def task_readiness_blockers(repo_root: Path, task_dir: Path) -> list[str]:
    """Gates evaluated before a start; an empty list means ready."""
    return []
