#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lifecycle task CLI command handlers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__:
    from . import _bootstrap as _bootstrap  # noqa: F401
else:
    import _bootstrap  # noqa: F401

from services.task_lifecycle import LifecycleResult, TaskLifecycleService
from adapters.cli.task_support import (
    Colors,
    colored,
    resolve_task_dir as _resolve_task_dir,
    run_hooks as _run_hooks,
)
from adapters.cli.execution_context_args import execution_context_from_namespace
from infra.paths import (
    DIR_WORKFLOW,
    FILE_TASK_JSON,
    get_repo_root,
)
from runtime.session_state import clear_active_task, get_active_task


def _report_check_block(title: str, blockers: tuple[str, ...]) -> int:
    print(colored(f"Error: {title}", Colors.RED), file=sys.stderr)
    for blocker in blockers:
        print(f"  - {blocker}", file=sys.stderr)
    return 1


def _print_transition_blockers(blockers: list[str]) -> None:
    print(
        colored("Error: Task state transition blocked", Colors.RED),
        file=sys.stderr,
    )
    for blocker in blockers:
        print(f"  - {blocker}", file=sys.stderr)


def _display_task_path(repo_root: Path, task_dir: Path) -> str:
    try:
        return task_dir.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(task_dir)


def _resolve_status_task_dir(
    args: argparse.Namespace,
    repo_root: Path,
) -> Path | None:
    target_input = getattr(args, "dir", None)
    if target_input:
        task_dir = _resolve_task_dir(target_input, repo_root)
    else:
        active = get_active_task(repo_root)
        if not active.context_key:
            print(
                colored(
                    "Error: Missing session context. Set "
                    "COWORK_FLOW_CONTEXT_ID or pass a task dir.",
                    Colors.RED,
                ),
                file=sys.stderr,
            )
            return None
        if not active.task_path:
            print(
                colored(
                    "Error: No active task set for this session",
                    Colors.RED,
                ),
                file=sys.stderr,
            )
            return None
        task_dir = repo_root / active.task_path

    if not task_dir.is_dir():
        print(
            colored(
                f"Error: Task not found: {target_input or task_dir}",
                Colors.RED,
            ),
            file=sys.stderr,
        )
        return None
    if not (task_dir / FILE_TASK_JSON).is_file():
        print(
            colored(
                f"Error: task.json not found: {task_dir}",
                Colors.RED,
            ),
            file=sys.stderr,
        )
        return None
    return task_dir


def _report_lifecycle_preflight(
    result: LifecycleResult,
) -> int:
    print(colored(f"Error: {result.title}", Colors.RED), file=sys.stderr)
    for blocker in result.blockers:
        print(f"  - {blocker}", file=sys.stderr)
    if result.hint:
        print(f"Hint: {result.hint}", file=sys.stderr)
    return 1


def _report_lifecycle_repository_error(
    result: LifecycleResult,
) -> int:
    error = result.repository_error
    action = (
        "read"
        if error is not None and error.code.startswith("TASK-LOAD-")
        else "write"
    )
    task_json = result.task_dir / FILE_TASK_JSON
    print(
        colored(
            f"Error: Failed to {action} task metadata: {task_json}",
            Colors.RED,
        ),
        file=sys.stderr,
    )
    return 1


def _resolve_start_task(
    task_input: str,
    repo_root: Path,
) -> Path | None:
    full_path = _resolve_task_dir(task_input, repo_root)
    if full_path.is_dir():
        return full_path
    print(
        colored(
            f"Error: Task not found: {task_input}",
            Colors.RED,
        )
    )
    print(
        "Hint: Use task name (e.g., 'my-task') or full path "
        f"(e.g., '{DIR_WORKFLOW}/tasks/01-31-my-task')"
    )
    return None


def _run_auto_start(
    args: argparse.Namespace,
    full_path: Path,
    service: TaskLifecycleService,
) -> int:
    readiness = service.start_readiness(full_path)
    if not readiness.ok:
        return _report_lifecycle_preflight(readiness)
    from adapters.cli.batch_mode import run_batch_entry

    return run_batch_entry(get_repo_root(), full_path, args)


def _report_start_failure(
    result: LifecycleResult,
) -> int:
    if result.title:
        return _report_lifecycle_preflight(result)
    if result.code == "LIFECYCLE-TRANSITION-001":
        _print_transition_blockers(list(result.blockers))
        return 1
    if result.code == "LIFECYCLE-CHECK-001":
        return _report_check_block(
            "Lifecycle checks blocked start_task action",
            result.blockers,
        )
    if result.code == "LIFECYCLE-CONTEXT-001":
        return _report_missing_session_context()
    if result.repository_error is not None:
        return _report_lifecycle_repository_error(result)
    print(
        colored("Error: Task lifecycle failed", Colors.RED),
        file=sys.stderr,
    )
    return 1


def _report_missing_session_context() -> int:
    print(
        colored(
            "Error: Missing session context. Set "
            "COWORK_FLOW_CONTEXT_ID or run inside a "
            "supported host session.",
            Colors.RED,
        ),
        file=sys.stderr,
    )
    return 1


def _report_start_success(
    result: LifecycleResult,
    repo_root: Path,
    full_path: Path,
) -> None:
    task_dir = result.active_task_path or _display_task_path(
        repo_root,
        full_path,
    )
    print(
        colored(
            f"[OK] Active session task set to: {task_dir}",
            Colors.GREEN,
        )
    )
    print()
    print(
        colored(
            "Fixed agents will load context from this task's jsonl files.",
            Colors.BLUE,
        )
    )


def cmd_start(args: argparse.Namespace) -> int:
    """Set the active task for this session."""
    repo_root = get_repo_root()
    task_input = args.dir
    if not task_input:
        print(
            colored(
                "Error: task directory or name required",
                Colors.RED,
            )
        )
        return 1

    full_path = _resolve_start_task(task_input, repo_root)
    if full_path is None:
        return 1

    service = TaskLifecycleService(repo_root)
    if getattr(args, "auto", False):
        return _run_auto_start(args, full_path, service)

    result = service.start(full_path)
    if not result.ok:
        return _report_start_failure(result)

    _report_start_success(result, repo_root, full_path)
    if "after_start" in getattr(result, "emitted_events", ()):
        _run_hooks("after_start", full_path / FILE_TASK_JSON, repo_root)
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    """Mark a task ready for check."""
    repo_root = get_repo_root()
    execution_context = execution_context_from_namespace(args)
    task_dir = _resolve_status_task_dir(args, repo_root)
    if task_dir is None:
        return 1

    service = TaskLifecycleService(repo_root)
    result = service.review(
        task_dir,
        execution_context=execution_context,
    )
    if not result.ok:
        if result.code == "LIFECYCLE-TRANSITION-001":
            _print_transition_blockers(list(result.blockers))
            return 1
        if result.code == "LIFECYCLE-CHECK-001":
            return _report_check_block(
                "Lifecycle checks blocked review",
                result.blockers,
            )
        if result.repository_error is not None:
            return _report_lifecycle_repository_error(result)
        return 1

    task_path = _display_task_path(repo_root, task_dir)
    print(
        colored(
            f"[OK] Task marked for check: {task_path}",
            Colors.GREEN,
        )
    )
    print(f"Next: ./.cowork-flow/run task next {task_path}")
    return 0


def cmd_complete(args: argparse.Namespace) -> int:
    """Mark a task completed after final check."""
    repo_root = get_repo_root()
    execution_context = execution_context_from_namespace(args)
    task_dir = _resolve_status_task_dir(args, repo_root)
    if task_dir is None:
        return 1

    service = TaskLifecycleService(repo_root)
    result = service.complete(
        task_dir,
        execution_context=execution_context,
    )
    if not result.ok:
        if result.code == "LIFECYCLE-TRANSITION-001":
            _print_transition_blockers(list(result.blockers))
            print(
                "Hint: run ./.cowork-flow/run task next <task-dir> "
                "--run --intent review to mark the task ready for check",
                file=sys.stderr,
            )
            return 1
        if result.code == "LIFECYCLE-CHECK-001":
            return _report_check_block(
                "Lifecycle checks blocked completion",
                result.blockers,
            )
        if result.repository_error is not None:
            return _report_lifecycle_repository_error(result)
        return 1

    task_path = _display_task_path(repo_root, task_dir)
    print(
        colored(
            f"[OK] Task marked completed: {task_path}",
            Colors.GREEN,
        )
    )
    print(f"Next: ./.cowork-flow/run task next {task_path}")
    return 0


def cmd_finish(args: argparse.Namespace) -> int:
    """Clear the active task for this session."""
    repo_root = get_repo_root()
    active = get_active_task(repo_root)
    if not active.task_path:
        print(
            colored(
                "No active task set for this session",
                Colors.YELLOW,
            )
        )
        return 0

    task_json_path = repo_root / active.task_path / FILE_TASK_JSON
    clear_active_task(repo_root)
    print(
        colored(
            f"[OK] Cleared active session task (was: {active.task_path})",
            Colors.GREEN,
        )
    )
    emitted_events = ("after_finish",) if task_json_path.is_file() else ()
    if "after_finish" in emitted_events:
        _run_hooks("after_finish", task_json_path, repo_root)
    return 0


def cmd_current(args: argparse.Namespace) -> int:
    """Show the active task for this session."""
    repo_root = get_repo_root()
    active = get_active_task(repo_root)
    if not active.context_key:
        print(
            colored(
                "Error: Missing session context. Set "
                "COWORK_FLOW_CONTEXT_ID or run inside a "
                "supported host session.",
                Colors.RED,
            ),
            file=sys.stderr,
        )
        return 1
    if not active.task_path:
        print("Active task: (none)")
        return 0
    print(f"Active task: {active.task_path}")
    print(f"Source: {active.source}:{active.context_key}")
    return 0
