#!/usr/bin/env python3
"""Direct lifecycle fact checks.

These checks intentionally avoid a dynamic gate registry or natural-language
spec validators. The workflow kernel only blocks on facts it can decide from
task metadata and the current git snapshot.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from kernel.git_snapshot import collect_changed_paths


PROTECTED_WORKFLOW_PATTERNS = (
    r"(^|/)\.cowork-flow/spec/",
    r"(^|/)\.cowork-flow/workflow\.md$",
    r"(^|/)AGENTS\.md$",
    r"(^|/)CLAUDE\.md$",
)


@dataclass(frozen=True)
class LifecycleCheckResult:
    """Result of direct lifecycle fact checks."""

    stage: str
    blockers: tuple[str, ...] = ()

    @property
    def blocked(self) -> bool:
        return bool(self.blockers)

    @property
    def exit_code(self) -> int:
        return 1 if self.blocked else 0


class LifecycleCheckRunner:
    """Run direct lifecycle fact checks for one repository."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)

    def review(
        self,
        task_dir: Path,
        *,
        allow_spec_file_modifications: bool = False,
    ) -> LifecycleCheckResult:
        return LifecycleCheckResult(
            stage="review",
            blockers=tuple(
                _review_completion_blockers(
                    self.repo_root,
                    task_dir,
                    allow_spec_file_modifications=allow_spec_file_modifications,
                )
            ),
        )

    def complete(
        self,
        task_dir: Path,
        *,
        allow_spec_file_modifications: bool = False,
    ) -> LifecycleCheckResult:
        return LifecycleCheckResult(
            stage="complete",
            blockers=tuple(
                _review_completion_blockers(
                    self.repo_root,
                    task_dir,
                    allow_spec_file_modifications=allow_spec_file_modifications,
                )
            ),
        )


def _review_completion_blockers(
    repo_root: Path,
    task_dir: Path,
    *,
    allow_spec_file_modifications: bool,
) -> list[str]:
    changed_files = collect_changed_paths(repo_root)
    blockers: list[str] = []
    if not allow_spec_file_modifications:
        blockers.extend(_protected_workflow_file_blockers(changed_files))
    blockers.extend(_allowed_file_scope_blockers(task_dir, changed_files))
    return blockers


def _protected_workflow_file_blockers(changed_files: list[str]) -> list[str]:
    blockers: list[str] = []
    for file_path in changed_files:
        normalized = _normalize_git_path(file_path)
        if any(re.search(pattern, normalized) for pattern in PROTECTED_WORKFLOW_PATTERNS):
            blockers.append(
                "Protected workflow/spec file changed outside main session: "
                f"{normalized}"
            )
    return blockers


def _allowed_file_scope_blockers(task_dir: Path, changed_files: list[str]) -> list[str]:
    implement_jsonl = task_dir / "implement.jsonl"
    if not implement_jsonl.exists():
        return []

    allowed_files, scope_blockers = _load_allowed_context_files(implement_jsonl)
    if scope_blockers:
        return scope_blockers

    blockers: list[str] = []
    for file_path in changed_files:
        normalized = _normalize_git_path(file_path)
        if _is_runtime_metadata_path(normalized):
            continue
        if normalized not in allowed_files:
            blockers.append(f"Modified file not listed in implement.jsonl: {normalized}")
    return blockers


def _is_runtime_metadata_path(file_path: str) -> bool:
    return file_path.startswith(
        (
            ".cowork-flow/.runtime/",
            ".cowork-flow/logs/",
            ".cowork-flow/tasks/",
        )
    )


def _load_allowed_context_files(implement_jsonl: Path) -> tuple[set[str], list[str]]:
    allowed_files: set[str] = set()
    blockers: list[str] = []
    try:
        lines = implement_jsonl.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        return allowed_files, [f"Cannot read implement.jsonl: {error}"]

    for line_number, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            blockers.append(f"Invalid implement.jsonl JSON at line {line_number}")
            continue
        if not isinstance(entry, dict):
            blockers.append(f"Invalid implement.jsonl entry at line {line_number}: expected object")
            continue
        normalized, error = _normalize_allowed_context_file(entry)
        if error is not None:
            blockers.append(f"Invalid implement.jsonl file scope at line {line_number}: {error}")
            continue
        if normalized is not None:
            allowed_files.add(normalized)
    if not allowed_files:
        blockers.append("implement.jsonl contains no valid file-scope entries")
    return allowed_files, blockers


def _normalize_allowed_context_file(entry: dict) -> tuple[str | None, str | None]:
    entry_type = entry.get("type", "file")
    file_path = entry.get("file")
    if entry_type == "directory":
        return None, None
    if entry_type not in ("file", "planned-file", "deleted-file"):
        return None, f"unsupported type {entry_type!r}"
    if not isinstance(file_path, str) or not file_path:
        return None, "missing file path"
    normalized = _normalize_git_path(file_path)
    segments = normalized.split("/")
    invalid = (
        normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized)
        or any(segment in ("", ".", "..") for segment in segments)
        or any(character in normalized for character in "*?[]")
    )
    return (None, f"non-canonical path {file_path!r}") if invalid else (normalized, None)


def _normalize_git_path(file_path: str) -> str:
    normalized = file_path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized
