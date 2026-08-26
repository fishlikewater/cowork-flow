#!/usr/bin/env python3
"""Readiness checks shared by task lifecycle commands."""

from __future__ import annotations

from pathlib import Path


def task_readiness_blockers(repo_root: Path, task_dir: Path) -> list[str]:
    """Return additional readiness blockers not covered by task context gates."""
    del repo_root, task_dir
    return []
