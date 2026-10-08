#!/usr/bin/env python3
"""Board facts for the shared task list.

Ownership, evidence coverage, and dependency blockage for one task. The CLI
list and the MCP `task_list` tool render these same fields from this single
implementation, so a second session sees one board.
"""

from __future__ import annotations

import json
from pathlib import Path

from infra.paths import DIR_TASKS, DIR_WORKFLOW, FILE_TASK_JSON
from services import task_graph
from services.ac_evidence import coverage_summary


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _normalize_rel(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.rstrip("/")


def bound_task_paths(repo_root: Path) -> set[str]:
    """Repository-relative task paths currently bound by a session."""
    from runtime.session_state import sessions_dir

    bound: set[str] = set()
    try:
        files = sorted(sessions_dir(Path(repo_root)).glob("*.json"))
    except OSError:
        return bound
    for path in files:
        data = _read_json(path)
        if not isinstance(data, dict):
            continue
        active = data.get("active_task_path")
        if isinstance(active, str) and active.strip():
            bound.add(_normalize_rel(active))
    return bound


def board_facts(
    repo_root: Path,
    task_dir: Path,
    *,
    bound_paths: set[str] | None = None,
) -> dict[str, object]:
    """Board columns for one task.

    `ownerSessionActive` is a hint, not a verdict: a session that works by
    passing an explicit task directory never binds, so `false` means "no
    session binding points here", never "the task is orphaned".
    """
    task_dir = Path(task_dir)
    data = _read_json(task_dir / FILE_TASK_JSON)
    task_data = data if isinstance(data, dict) else {}
    executor = task_data.get("executor")
    executor = (
        executor.strip()
        if isinstance(executor, str) and executor.strip()
        else None
    )
    relative_path = f"{DIR_WORKFLOW}/{DIR_TASKS}/{task_dir.name}"
    if bound_paths is None:
        bound_paths = bound_task_paths(repo_root)
    unresolved = task_graph.unresolved_dependencies(repo_root, task_dir)
    return {
        "executor": executor,
        "ownerSessionActive": bool(executor) and relative_path in bound_paths,
        "evidenceCoverage": coverage_summary(task_dir),
        "blocked": bool(unresolved),
        "blockedBy": unresolved,
    }
