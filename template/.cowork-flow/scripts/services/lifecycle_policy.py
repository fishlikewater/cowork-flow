#!/usr/bin/env python3
"""Pure lifecycle policy facts shared by services and delivery adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from runtime.execution_context import ExecutionContext
from runtime.session_state import is_main_session
from services.task_context import TaskContextService


PLANNED_FILE_HINT = (
    "If this is a planned new file, add "
    '"type": "planned-file"; if this is an already-deleted file in scope, add '
    '"type": "deleted-file" before retrying.'
)


@dataclass(frozen=True)
class LifecyclePolicyFailure:
    """Structured lifecycle policy blocker without terminal rendering."""

    code: str
    title: str
    blockers: tuple[str, ...]
    hint: str = ""


@dataclass(frozen=True)
class LifecycleExecutionPolicy:
    """Execution scope facts used by lifecycle checks."""

    execution_scope: str
    allow_spec_file_modifications: bool


def start_readiness_failure(
    repo_root: Path,
    task_dir: Path,
) -> LifecyclePolicyFailure | None:
    """Return the first start readiness failure, or None when start is ready."""
    repo_root = Path(repo_root)
    task_dir = Path(task_dir)
    context_service = TaskContextService(repo_root)

    blockers = tuple(context_service.start_blockers(task_dir))
    if blockers:
        return LifecyclePolicyFailure(
            code="TASK-START-001",
            title="Task is not ready to start yet",
            blockers=blockers,
            hint=(
                "write decision-anchor.md and required context JSONL files, "
                "then retry `task next <dir> --run`"
            ),
        )

    validation_issues = tuple(context_service.validation_issue_summaries(task_dir))
    if validation_issues:
        context_service.ensure_task_artifact_placeholders(task_dir)
        validation_issues = tuple(context_service.validation_issue_summaries(task_dir))
    if validation_issues:
        return LifecyclePolicyFailure(
            code="TASK-CONTEXT-001",
            title="Task context validation failed",
            blockers=validation_issues,
            hint=(
                "run task next <dir> --validate and fix the "
                f"reported issues. {PLANNED_FILE_HINT}"
            ),
        )

    readiness_blockers = _task_readiness_blockers(repo_root, task_dir)
    if readiness_blockers:
        return LifecyclePolicyFailure(
            code="TASK-READINESS-001",
            title="Task readiness failed",
            blockers=readiness_blockers,
            hint=(
                "run task next <dir> and complete the "
                "reported readiness artifacts"
            ),
        )
    return None


def resolve_execution_policy(
    repo_root: Path,
    execution_context: ExecutionContext | None = None,
    *,
    allow_spec_file_modifications: bool | None = None,
) -> LifecycleExecutionPolicy:
    """Resolve lifecycle scope capability from execution facts."""
    if execution_context is None:
        if allow_spec_file_modifications is not None:
            return LifecycleExecutionPolicy(
                execution_scope="explicit",
                allow_spec_file_modifications=allow_spec_file_modifications,
            )
        execution_context = ExecutionContext()

    if allow_spec_file_modifications is not None:
        allowed = allow_spec_file_modifications
    elif execution_context.is_worker or execution_context.is_subagent:
        allowed = False
    else:
        allowed = is_main_session(Path(repo_root))
    return LifecycleExecutionPolicy(
        execution_scope=execution_context.mode,
        allow_spec_file_modifications=allowed,
    )


def _task_readiness_blockers(repo_root: Path, task_dir: Path) -> tuple[str, ...]:
    try:
        from services.readiness import task_readiness_blockers
    except Exception:
        return ()
    try:
        blockers = task_readiness_blockers(repo_root, task_dir)
    except Exception:
        return (
            "readiness check failed; run task next <dir> --validate and inspect "
            "task readiness artifacts",
        )
    return tuple(str(blocker) for blocker in blockers if str(blocker).strip())
