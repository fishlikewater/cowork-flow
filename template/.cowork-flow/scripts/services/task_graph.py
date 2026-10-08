#!/usr/bin/env python3
"""Task dependency graph facts (`dependsOn` edges).

Dependencies are declared at creation time and only gate the start
transition: a task cannot enter `in_progress` while any dependency is
missing or not `completed`. Archived tasks keep their completed status, so
they stay valid dependencies.
"""

from __future__ import annotations

import json
from pathlib import Path

from infra.paths import FILE_TASK_JSON, get_tasks_dir


COMPLETED_STATUS = "completed"
ARCHIVE_DIR_NAME = "archive"
MAX_PATH_DEPTH = 64


def task_dependencies(task_data: dict) -> list[str]:
    """Normalized `dependsOn` names: non-empty, order-preserving, unique."""
    raw = task_data.get("dependsOn")
    if not isinstance(raw, list):
        return []
    names: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            name = item.strip()
            if name not in names:
                names.append(name)
    return names


def read_task_data(task_dir: Path) -> dict:
    try:
        data = json.loads(
            (Path(task_dir) / FILE_TASK_JSON).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def find_task_dir(repo_root: Path, name: str) -> Path | None:
    """Locate a task directory by name in the active tree or the archive.

    Exact directory-name match only: dependencies store canonical names, so
    resolution never has to guess between the active and archived split.
    """
    tasks_dir = get_tasks_dir(Path(repo_root))
    candidate = tasks_dir / name
    if name != ARCHIVE_DIR_NAME and candidate.is_dir():
        return candidate
    archive_dir = tasks_dir / ARCHIVE_DIR_NAME
    if not archive_dir.is_dir():
        return None
    for date_dir in sorted(archive_dir.iterdir()):
        if not date_dir.is_dir():
            continue
        candidate = date_dir / name
        if candidate.is_dir():
            return candidate
    return None


def load_dependencies(repo_root: Path, task_dir: Path) -> list[str]:
    return task_dependencies(read_task_data(task_dir))


def dependency_status(repo_root: Path, name: str) -> str | None:
    """Status of a dependency task, or None when it is missing."""
    task_dir = find_task_dir(repo_root, name)
    if task_dir is None:
        return None
    status = read_task_data(task_dir).get("status")
    return status if isinstance(status, str) else None


def unresolved_dependencies(repo_root: Path, task_dir: Path) -> list[str]:
    """Dependency names that are missing or not completed."""
    return [
        name
        for name in load_dependencies(repo_root, task_dir)
        if dependency_status(repo_root, name) != COMPLETED_STATUS
    ]


def dependency_blockers(repo_root: Path, task_dir: Path) -> list[str]:
    """Blocker text shared by navigation and the start preflight."""
    unresolved = unresolved_dependencies(repo_root, task_dir)
    if not unresolved:
        return []
    return [
        "task depends on unfinished work: "
        + ", ".join(unresolved)
        + " (a dependency missing from tasks/ and tasks/archive/ counts as unfinished)"
    ]


def dependency_cycle_for_new(
    repo_root: Path,
    new_name: str,
    deps: list[str],
) -> list[str] | None:
    """Cycle path closed by declaring `deps` on a task named `new_name`.

    Existing tasks' edges are followed; reaching `new_name` means some task
    already depends (transitively) on the task about to be created.
    """

    def walk(name: str, path: list[str]) -> list[str] | None:
        if name == new_name:
            return path
        if len(path) > MAX_PATH_DEPTH:
            return None
        task_dir = find_task_dir(repo_root, name)
        if task_dir is None:
            return None
        for dep in load_dependencies(repo_root, task_dir):
            if dep in path:
                return path[path.index(dep):] + [dep]
            found = walk(dep, path + [dep])
            if found is not None:
                return found
        return None

    for dep in deps:
        found = walk(dep, [new_name, dep])
        if found is not None:
            return found
    return None
