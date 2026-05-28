"""Detect active delegated work from persisted filesystem state.

Reads status.json (agent-team) and index.json (generic subagents) to determine
whether any worker assignments or subagents are currently in-flight.

This module does NOT rely on the caller declaring its role — it inspects
filesystem state written by the Python scripts themselves.
"""

from __future__ import annotations

import json
from pathlib import Path

from .paths import DIR_WORKFLOW, get_tasks_dir

ACTIVE_WORKER_STATUSES = {"ready", "in_progress"}
ACTIVE_SUBAGENT_STATUSES = {"active"}
FILE_LAST_WORKER = ".last-worker"


def last_worker_sentinel(repo_root: Path) -> Path:
    """Path to the recovery sentinel for the most recently spawned worker."""
    return repo_root / DIR_WORKFLOW / FILE_LAST_WORKER


def find_workers(repo_root: Path) -> list[dict]:
    """Scan all task agent-team status.json files for in-flight assignments."""
    workers: list[dict] = []
    tasks_dir = get_tasks_dir(repo_root)
    if not tasks_dir.is_dir():
        return workers

    for task_dir in sorted(tasks_dir.iterdir()):
        if not task_dir.is_dir() or task_dir.name == "archive":
            continue
        status_path = task_dir / "agent-team" / "status.json"
        if not status_path.is_file():
            continue
        try:
            status_data = json.loads(status_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        assignments = status_data.get("assignments", {})
        if not isinstance(assignments, dict):
            continue
        task_rel = f".cowork-flow/tasks/{task_dir.name}"
        for aid, assignment in assignments.items():
            if not isinstance(assignment, dict):
                continue
            if assignment.get("status") in ACTIVE_WORKER_STATUSES:
                workers.append({
                    "assignment_id": aid,
                    "task_dir": task_rel,
                    "context_file": f"{task_rel}/agent-team/assignments/{aid}.context.json",
                    "role": assignment.get("role", "unknown"),
                    "status": assignment.get("status", "unknown"),
                })
    return workers


def find_subagents(repo_root: Path) -> list[dict]:
    """Scan subagents index for active generic subagent contexts."""
    subagents: list[dict] = []
    index_path = repo_root / DIR_WORKFLOW / "subagents" / "index.json"
    if not index_path.is_file():
        return subagents
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return subagents
    for entry in index.get("subagents", []):
        if not isinstance(entry, dict):
            continue
        if entry.get("status") in ACTIVE_SUBAGENT_STATUSES:
            subagents.append(entry)
    return subagents


def has_active_work(repo_root: Path) -> bool:
    """True if any worker assignment or subagent is currently active."""
    return bool(find_workers(repo_root)) or bool(find_subagents(repo_root))
