#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compatibility entry point and lifecycle adapters for task commands."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

if __package__:
    from . import _bootstrap as _bootstrap  # noqa: F401
else:
    import _bootstrap  # noqa: F401

from application.task_context import (
    TaskContextService,
    detect_installed_platforms as _detect_installed_platforms,
    discover_spec_files as _discover_spec_files,
    get_check_context,
    get_debug_context,
    get_implement_backend,
    get_implement_base,
    get_implement_frontend,
    get_implement_spec,
    is_skill_path as _is_skill_path,
    iter_jsonl_lines as _iter_jsonl_lines,
    skill_path as _skill_path,
    use_claude_skill_context as _use_claude_skill_context,
    write_jsonl as _write_jsonl,
)
from application.task_lifecycle import (
    LifecyclePreflightFailure,
    LifecycleResult,
    TaskLifecycleService,
)
from application.batch_execution import (
    BatchExecutionError,
    BatchExecutionService,
)
from commands.task_archive_commands import cmd_archive
from commands.task_context_commands import (
    cmd_add_context,
    cmd_init_context,
    cmd_list_context,
    cmd_validate,
)
from commands.task_create_command import cmd_create, ensure_tasks_dir
from commands.task_navigation import cmd_next
from commands.task_parser import build_parser, show_usage
from commands.task_support import (
    Colors,
    colored,
    resolve_task_dir as _resolve_task_dir,
    run_hooks as _run_hooks,
)
from commands.task_tree_commands import (
    cmd_add_subtask,
    cmd_list,
    cmd_list_archive,
    cmd_remove_subtask,
)
from common.core.execution_context import (
    execution_context_from_namespace,
    worker_command_block_message,
)
from common.core.paths import (
    DIR_WORKFLOW,
    FILE_TASK_JSON,
    get_repo_root,
)
from common.gates.gates import GateResult, GateRunner
from common.task.active_task import clear_active_task, get_active_task, is_main_session


def _allow_spec_file_modifications(repo_root: Path, execution_context) -> bool:
    if execution_context.is_worker or execution_context.is_subagent:
        return False
    return is_main_session(repo_root)

def _report_gate_block(
    title: str,
    result: GateResult,
    runner: GateRunner | None = None,
) -> int:
    print(colored(f"Error: {title}", Colors.RED), file=sys.stderr)
    for violation in result.violations:
        print(json.dumps(violation, ensure_ascii=False), file=sys.stderr)
    if runner is not None:
        runner.log(result)
    return result.exit_code


def _report_gate_warnings(title: str, result: GateResult) -> None:
    if not result.violations:
        return
    print(colored(f"Warning: {title}", Colors.YELLOW), file=sys.stderr)
    for violation in result.violations:
        print(json.dumps(violation, ensure_ascii=False), file=sys.stderr)


def _report_pipeline_outcomes(
    result: GateResult,
    runner: GateRunner,
) -> int | None:
    for execution in result.executions:
        definition = execution.definition
        if execution.blocked:
            return _report_gate_block(
                definition.block_message,
                execution.result,
                runner if definition.log_violations else None,
            )
        if definition.warning_message and execution.result.violations:
            _report_gate_warnings(
                definition.warning_message,
                execution.result,
            )
    return None


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


def _migrate_prd_to_anchor(task_dir: Path) -> bool:
    migrated = TaskContextService(
        get_repo_root(task_dir)
    ).migrate_legacy_prd(task_dir)
    if migrated:
        print(
            colored(
                "  [迁移] prd.md → decision-anchor.md",
                Colors.YELLOW,
            ),
            file=sys.stderr,
        )
    return migrated


def _task_start_blockers(task_dir: Path) -> list[str]:
    return list(
        TaskContextService(get_repo_root(task_dir)).start_blockers(task_dir)
    )


def _task_context_validation_issues(
    task_dir: Path,
    repo_root: Path,
    quiet: bool = False,
) -> list[str]:
    del quiet
    return list(
        TaskContextService(repo_root).validation_issue_summaries(task_dir)
    )


def _optional_readiness_blockers(
    repo_root: Path,
    task_dir: Path,
) -> list[str]:
    try:
        from common.task.readiness import task_readiness_blockers
    except Exception:
        return []
    try:
        blockers = task_readiness_blockers(repo_root, task_dir)
    except Exception:
        return [
            "readiness check failed; run task validate and inspect "
            "linked change"
        ]
    return [str(blocker) for blocker in blockers if str(blocker).strip()]


def _start_preflight(
    task_dir: Path,
    repo_root: Path,
) -> LifecyclePreflightFailure | None:
    blockers = _task_start_blockers(task_dir)
    if blockers:
        return LifecyclePreflightFailure(
            code="TASK-START-001",
            title="Task is not ready to start yet",
            blockers=tuple(blockers),
            hint=(
                "write decision-anchor.md, run ./.cowork-flow/run task "
                "init-context <dir> <dev_type>, then retry"
            ),
        )

    validation_issues = _task_context_validation_issues(
        task_dir,
        repo_root,
    )
    if validation_issues:
        return LifecyclePreflightFailure(
            code="TASK-CONTEXT-001",
            title="Task context validation failed",
            blockers=tuple(validation_issues),
            hint=(
                "run ./.cowork-flow/run task validate <dir> and fix the "
                "reported issues"
            ),
        )

    readiness_blockers = _optional_readiness_blockers(
        repo_root,
        task_dir,
    )
    if readiness_blockers:
        return LifecyclePreflightFailure(
            code="TASK-READINESS-001",
            title="Task readiness failed",
            blockers=tuple(readiness_blockers),
            hint=(
                "run ./.cowork-flow/run task next <dir> and complete the "
                "reported readiness artifacts"
            ),
        )
    return None


def _report_lifecycle_preflight(
    result: LifecyclePreflightFailure | LifecycleResult,
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

    full_path = _resolve_task_dir(task_input, repo_root)
    if not full_path.is_dir():
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
        return 1

    _migrate_prd_to_anchor(full_path)

    def preflight(
        task_dir: Path,
    ) -> LifecyclePreflightFailure | None:
        return _start_preflight(task_dir, repo_root)

    if getattr(args, "auto", False):
        failure = preflight(full_path)
        if failure is not None:
            return _report_lifecycle_preflight(failure)
        from common.task.batch_mode import run_batch_entry

        return run_batch_entry(repo_root, full_path, args)

    service = TaskLifecycleService(repo_root)
    result = service.start(full_path, preflight=preflight)
    if not result.ok:
        if result.title:
            return _report_lifecycle_preflight(result)
        if result.code == "LIFECYCLE-TRANSITION-001":
            _print_transition_blockers(list(result.blockers))
            return 1
        if result.code == "LIFECYCLE-GATE-001":
            return _report_gate_block(
                "Spec enforcement blocked task start",
                result.gate_result,
                service.gate_runner,
            )
        if result.code == "LIFECYCLE-CONTEXT-001":
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
        if result.repository_error is not None:
            return _report_lifecycle_repository_error(result)
        print(
            colored("Error: Task lifecycle failed", Colors.RED),
            file=sys.stderr,
        )
        return 1

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
    _run_hooks("after_start", full_path / FILE_TASK_JSON, repo_root)
    return 0


def _print_batch_state(state: dict) -> None:
    print(json.dumps(state, ensure_ascii=False, indent=2))


def _report_batch_error(error: BatchExecutionError) -> int:
    print(
        f"Error [{error.code}]: {error.detail}",
        file=sys.stderr,
    )
    return 2


def cmd_batch_resume(args: argparse.Namespace) -> int:
    """Resume a paused Batch operation and publish its next action."""
    try:
        state = BatchExecutionService(get_repo_root()).resume(
            args.operation_id
        )
    except BatchExecutionError as error:
        return _report_batch_error(error)
    _print_batch_state(state)
    return 0


def cmd_batch_record_result(args: argparse.Namespace) -> int:
    """Record one UTF-8 Host action result and advance Batch."""
    try:
        payload = json.loads(args.file.read_text(encoding="utf-8"))
    except OSError as error:
        print(
            f"Error: Failed to read Batch result file: {error}",
            file=sys.stderr,
        )
        return 2
    except json.JSONDecodeError as error:
        print(
            f"Error: Invalid Batch result JSON: {error}",
            file=sys.stderr,
        )
        return 2
    if not isinstance(payload, dict):
        print(
            "Error: Batch result JSON must be an object",
            file=sys.stderr,
        )
        return 2
    try:
        state = BatchExecutionService(get_repo_root()).record_result(
            args.operation_id,
            payload,
        )
    except BatchExecutionError as error:
        return _report_batch_error(error)
    _print_batch_state(state)
    return 2 if state.get("phase") == "paused" else 0


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
        allow_spec_file_modifications=_allow_spec_file_modifications(
            repo_root,
            execution_context,
        ),
    )
    if not result.ok:
        if result.code == "LIFECYCLE-TRANSITION-001":
            _print_transition_blockers(list(result.blockers))
            return 1
        if result.code == "LIFECYCLE-GATE-001":
            gate_exit = _report_pipeline_outcomes(
                result.gate_result,
                service.gate_runner,
            )
            return gate_exit if gate_exit is not None else 1
        if result.repository_error is not None:
            return _report_lifecycle_repository_error(result)
        return 1

    if result.gate_result is not None:
        _report_pipeline_outcomes(result.gate_result, service.gate_runner)
    if result.summary:
        print(colored("Coding Standards to Verify:", Colors.CYAN))
        print(result.summary)

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
    task_dir = _resolve_status_task_dir(args, repo_root)
    if task_dir is None:
        return 1

    service = TaskLifecycleService(repo_root)
    result = service.complete(
        task_dir,
        completed_at=datetime.now().strftime("%Y-%m-%d"),
    )
    if not result.ok:
        if result.code == "LIFECYCLE-TRANSITION-001":
            _print_transition_blockers(list(result.blockers))
            print(
                "Hint: run ./.cowork-flow/run task review <task-dir> "
                "to mark the task ready for check",
                file=sys.stderr,
            )
            return 1
        if result.code == "LIFECYCLE-GATE-001":
            gate_exit = _report_pipeline_outcomes(
                result.gate_result,
                service.gate_runner,
            )
            return gate_exit if gate_exit is not None else 1
        if result.repository_error is not None:
            return _report_lifecycle_repository_error(result)
        return 1

    _report_pipeline_outcomes(result.gate_result, service.gate_runner)
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
    if task_json_path.is_file():
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


def main() -> int:
    """CLI entry point."""
    args = build_parser().parse_args()
    execution_context = execution_context_from_namespace(args)
    if not args.command:
        show_usage()
        return 1

    worker_blocked_commands = {
        "create",
        "init-context",
        "add-context",
        "start",
        "batch-resume",
        "batch-record-result",
        "review",
        "complete",
        "finish",
        "archive",
        "add-subtask",
        "remove-subtask",
    }
    if execution_context.is_worker and args.command in worker_blocked_commands:
        print(
            worker_command_block_message(
                execution_context,
                f"task {args.command}",
                "Workers must not activate, archive, or mutate "
                "cowork-flow task state.",
            ),
            file=sys.stderr,
        )
        return 2

    commands = {
        "create": cmd_create,
        "init-context": cmd_init_context,
        "add-context": cmd_add_context,
        "validate": cmd_validate,
        "list-context": cmd_list_context,
        "start": cmd_start,
        "batch-resume": cmd_batch_resume,
        "batch-record-result": cmd_batch_record_result,
        "current": cmd_current,
        "review": cmd_review,
        "complete": cmd_complete,
        "next": cmd_next,
        "finish": cmd_finish,
        "archive": cmd_archive,
        "add-subtask": cmd_add_subtask,
        "remove-subtask": cmd_remove_subtask,
        "list": cmd_list,
        "list-archive": cmd_list_archive,
    }
    command = commands.get(args.command)
    if command is None:
        show_usage()
        return 1
    return command(args)


if __name__ == "__main__":
    raise SystemExit(main())
