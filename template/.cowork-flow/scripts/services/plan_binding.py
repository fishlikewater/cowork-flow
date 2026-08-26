#!/usr/bin/env python3
"""Shared planFile binding policy for task lifecycle readiness and creation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from infra.files import read_text_utf8
from infra.paths import DIR_WORKFLOW
from services.task_repository import TaskRepository


PLAN_DIRECTORY = f"{DIR_WORKFLOW}/plans/"


@dataclass(frozen=True)
class BoundPlanFile:
    normalized: str
    path: Path


class PlanBindingError(RuntimeError):
    """Raised when a planFile path violates the shared binding policy."""

    def __init__(
        self,
        code: str,
        path: Path,
        detail: str,
        normalized: str | None = None,
    ) -> None:
        self.code = code
        self.path = path
        self.detail = detail
        self.normalized = normalized
        super().__init__(f"{code}: {detail}: {path}")


def normalize_plan_file(plan_file: str | Path) -> str | None:
    """Return a canonical repo-relative .cowork-flow/plans path."""
    normalized = normalize_repo_relative_path(plan_file)
    if normalized is None or not normalized.startswith(PLAN_DIRECTORY):
        return None
    return normalized


def normalize_repo_relative_path(path: str | Path) -> str | None:
    normalized = str(path).replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    segments = normalized.split("/")
    if (
        not normalized
        or normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized) is not None
        or any(segment in ("", ".", "..") for segment in segments)
    ):
        return None
    return normalized


def bind_plan_file(
    repo_root: Path,
    plan_file: str | Path,
    *,
    allow_absolute: bool = False,
    require_exists: bool = True,
    require_non_empty: bool = False,
) -> BoundPlanFile:
    """Resolve one planFile through the shared canonical path policy."""
    repo_root = Path(repo_root)
    raw_path = Path(plan_file)
    if raw_path.is_absolute():
        if not allow_absolute:
            raise PlanBindingError(
                "invalid_path",
                raw_path,
                "plan file must be a repository-relative path",
            )
        try:
            normalized = raw_path.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError as error:
            raise PlanBindingError(
                "outside_repository",
                raw_path,
                "plan file must be inside the repository",
            ) from error
    else:
        normalized = normalize_repo_relative_path(plan_file)
        if normalized is None:
            raise PlanBindingError(
                "invalid_path",
                repo_root / raw_path,
                "plan file must be a canonical repository-relative path",
            )

    if not normalized.startswith(PLAN_DIRECTORY):
        raise PlanBindingError(
            "wrong_location",
            repo_root / normalized,
            f"plan file must live under {DIR_WORKFLOW}/plans",
            normalized,
        )

    plan_path = repo_root / normalized
    if require_exists and not plan_path.is_file():
        raise PlanBindingError(
            "missing",
            plan_path,
            "plan file does not exist",
            normalized,
        )
    if require_non_empty and not read_text_utf8(plan_path).strip():
        raise PlanBindingError(
            "empty",
            plan_path,
            "plan file is empty",
            normalized,
        )
    return BoundPlanFile(normalized=normalized, path=plan_path)


def bind_task_plan(
    repo_root: Path,
    task_dir: Path,
    plan_file: str | Path,
) -> dict:
    """Validate and bind one plan file to a task's meta, preserving other meta keys."""
    bound = bind_plan_file(
        repo_root,
        plan_file,
        require_exists=True,
        require_non_empty=True,
    )
    repository = TaskRepository(repo_root)
    task_data = repository.load(task_dir)
    meta = task_data.get("meta")
    meta = dict(meta) if isinstance(meta, dict) else {}
    meta["planFile"] = bound.normalized
    return repository.save(task_dir, {"meta": meta})


def plan_file_blockers(repo_root: Path, task_data: dict) -> list[str]:
    """Return lifecycle readiness blockers for task.json meta.planFile."""
    meta = task_data.get("meta")
    plan_file = meta.get("planFile") if isinstance(meta, dict) else None
    if not isinstance(plan_file, str) or not plan_file.strip():
        return ["planFile is required before implementation starts"]
    try:
        bind_plan_file(
            repo_root,
            plan_file,
            allow_absolute=False,
            require_exists=True,
            require_non_empty=True,
        )
    except PlanBindingError as error:
        if error.code in {"invalid_path", "outside_repository", "wrong_location"}:
            return ["planFile must be a repo-relative .cowork-flow/plans path"]
        if error.code == "missing":
            return [f"planFile does not exist: {error.normalized}"]
        if error.code == "empty":
            return [f"planFile is empty: {error.normalized}"]
        return [error.detail]
    return []
