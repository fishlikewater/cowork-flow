#!/usr/bin/env python3
"""Git changed-file snapshot helpers for workflow gates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .git_context import _run_git_command


@dataclass(frozen=True)
class ChangedFile:
    """A file currently changed in git status."""

    path: str
    statuses: tuple[str, ...]


def collect_changed_files(repo_root: Path) -> list[ChangedFile]:
    """Return modified, staged, and untracked files from git status."""
    rc, stdout, _ = _run_git_command(
        ["status", "--porcelain=v1", "-uall", "--", "."],
        cwd=repo_root,
    )
    if rc != 0:
        return []

    changed: dict[str, set[str]] = {}
    for raw_line in stdout.splitlines():
        parsed = _parse_status_line(raw_line)
        if parsed is None:
            continue
        path, statuses = parsed
        changed.setdefault(path, set()).update(statuses)

    return [
        ChangedFile(path=path, statuses=tuple(sorted(statuses)))
        for path, statuses in sorted(changed.items())
    ]


def collect_changed_paths(repo_root: Path) -> list[str]:
    """Return only the relative paths from collect_changed_files."""
    return [changed.path for changed in collect_changed_files(repo_root)]


def _parse_status_line(raw_line: str) -> tuple[str, tuple[str, ...]] | None:
    if len(raw_line) < 4:
        return None

    code = raw_line[:2]
    raw_path = raw_line[3:]
    if " -> " in raw_path:
        raw_path = raw_path.split(" -> ", 1)[1]

    path = _normalize_git_path(raw_path)
    if not path:
        return None

    statuses: list[str] = []
    index_status = code[0]
    worktree_status = code[1]

    if code == "??":
        statuses.append("untracked")
    else:
        if index_status not in (" ", "?"):
            statuses.append("staged")
        if worktree_status not in (" ", "?"):
            statuses.append("modified")

    if not statuses:
        return None

    return path, tuple(statuses)


def _normalize_git_path(raw_path: str) -> str:
    path = raw_path.strip()
    if len(path) >= 2 and path[0] == path[-1] == '"':
        path = path[1:-1]
    return path.replace("\\", "/")
