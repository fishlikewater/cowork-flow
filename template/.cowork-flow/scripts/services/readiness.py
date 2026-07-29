#!/usr/bin/env python3
"""Readiness checks shared by task lifecycle commands."""

from __future__ import annotations

import json
from pathlib import Path

from infra.paths import DIR_ARCHIVE, DIR_CHANGES, DIR_TASKS, DIR_WORKFLOW, FILE_TASK_JSON, get_tasks_dir
from services.task_utils import find_task_by_name

from infra.files import read_text_utf8


def _read_text(path: Path) -> str:
    return read_text_utf8(path).strip()


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _parse_scalar(value: str) -> object:
    if value == "null":
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    return value


def _read_metadata(path: Path) -> dict[str, object]:
    data: dict[str, object] = {}
    text = _read_text(path)
    if not text:
        return data

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = _parse_scalar(value.strip())
    return data


def _display_path(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _resolve_link(repo_root: Path, base_dir: str, value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None

    raw_path = Path(value)
    if raw_path.is_absolute():
        return raw_path

    direct = repo_root / raw_path
    workflow_base = Path(DIR_WORKFLOW) / base_dir
    if direct.exists() or raw_path.parts[:2] == workflow_base.parts:
        return direct
    return repo_root / workflow_base / raw_path


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return left == right


def _task_ancestry(repo_root: Path, task_dir: Path) -> list[Path]:
    tasks_dir = get_tasks_dir(repo_root)
    ancestry = [task_dir]
    seen = {task_dir.name}
    current = task_dir

    while True:
        data = _read_json(current / FILE_TASK_JSON)
        parent = data.get("parent")
        if not isinstance(parent, str) or not parent.strip() or parent in seen:
            break
        parent_dir = find_task_by_name(parent, tasks_dir)
        if parent_dir is None:
            break
        ancestry.append(parent_dir)
        seen.add(parent)
        current = parent_dir

    return ancestry


def _change_applies_to_task(
    repo_root: Path,
    metadata: dict[str, object],
    task_dir: Path,
) -> tuple[bool, bool]:
    ancestry = _task_ancestry(repo_root, task_dir)
    linked_task = _resolve_link(repo_root, DIR_TASKS, metadata.get("task"))
    if linked_task is not None and any(_same_path(linked_task, item) for item in ancestry):
        return True, False

    if linked_task is None:
        plan_path = _resolve_link(repo_root, "plans", metadata.get("plan"))
        if plan_path is not None:
            return True, True

    return False, False


def _append_missing_file_blocker(
    blockers: list[str],
    slug: str,
    path: Path,
    label: str,
) -> None:
    if not _read_text(path):
        blockers.append(f"L2 readiness ({slug}): {label} is missing or empty")


def _iter_change_dirs(repo_root: Path) -> list[Path]:
    changes_dir = repo_root / DIR_WORKFLOW / DIR_CHANGES
    if not changes_dir.is_dir():
        return []
    return [
        path
        for path in sorted(changes_dir.iterdir())
        if path.is_dir() and path.name != DIR_ARCHIVE
    ]


def task_readiness_blockers(repo_root: Path, task_dir: Path) -> list[str]:
    """Return readiness blockers for work linked to L2 changes."""
    blockers: list[str] = []

    for change_dir in _iter_change_dirs(repo_root):
        metadata = _read_metadata(change_dir / "change.yaml")
        if metadata.get("level") != "L2" or metadata.get("status") == "archived":
            continue

        applies, missing_task_link = _change_applies_to_task(repo_root, metadata, task_dir)
        if not applies:
            continue

        slug = change_dir.name
        if missing_task_link:
            blockers.append(f"L2 readiness ({slug}): change.yaml task link is missing")

        _append_missing_file_blocker(blockers, slug, change_dir / "proposal.md", "proposal.md")
        _append_missing_file_blocker(blockers, slug, change_dir / "spec.md", "spec.md")
        _append_missing_file_blocker(blockers, slug, change_dir / "design.md", "design.md")

        plan_path = _resolve_link(repo_root, "plans", metadata.get("plan"))
        if plan_path is None:
            blockers.append(f"L2 readiness ({slug}): change.yaml plan link is missing")
        elif not plan_path.exists():
            blockers.append(
                f"L2 readiness ({slug}): plan points to missing path: {_display_path(repo_root, plan_path)}"
            )
        else:
            if not _read_text(plan_path):
                blockers.append(f"L2 readiness ({slug}): linked plan is empty")

        linked_task = _resolve_link(repo_root, DIR_TASKS, metadata.get("task"))
        if linked_task is not None and not linked_task.exists():
            blockers.append(
                f"L2 readiness ({slug}): task points to missing path: {_display_path(repo_root, linked_task)}"
            )

    return blockers
