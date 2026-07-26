#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Task workflow entry point and lifecycle adapters."""

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
    PLANNED_FILE_HINT,
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
    cmd_add_planned_file,
    cmd_add_context,
    cmd_init_context,
    cmd_list_context,
    cmd_validate,
)
from commands.task_create_command import cmd_create, ensure_tasks_dir
from commands import task_navigation
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
from common.task.active_task import clear_active_task, get_active_task, is_main_session


def _allow_spec_file_modifications(repo_root: Path, execution_context) -> bool:
    if execution_context.is_worker or execution_context.is_subagent:
        return False
    return is_main_session(repo_root)


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


def _refresh_task_artifact_placeholders(
    task_dir: Path,
    repo_root: Path,
) -> list[str]:
    service = TaskContextService(repo_root)
    service.ensure_task_artifact_placeholders(task_dir)
    return _task_context_validation_issues(task_dir, repo_root)


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
            "readiness check failed; run task next <dir> --validate and inspect "
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
                "write decision-anchor.md and required context JSONL files, "
                "then retry `task next <dir> --run`"
            ),
        )

    validation_issues = _task_context_validation_issues(
        task_dir,
        repo_root,
    )
    if validation_issues:
        validation_issues = _refresh_task_artifact_placeholders(task_dir, repo_root)
    if validation_issues:
        return LifecyclePreflightFailure(
            code="TASK-CONTEXT-001",
            title="Task context validation failed",
            blockers=tuple(validation_issues),
            hint=(
                "run ./.cowork-flow/run task next <dir> --validate and fix the "
                f"reported issues. {PLANNED_FILE_HINT}"
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
    preflight,
) -> int:
    failure = preflight(full_path)
    if failure is not None:
        return _report_lifecycle_preflight(failure)
    from common.task.batch_mode import run_batch_entry

    return run_batch_entry(get_repo_root(), full_path, args)


def _report_start_failure(
    result: LifecycleResult,
    service: TaskLifecycleService,
) -> int:
    del service
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

    def preflight(
        task_dir: Path,
    ) -> LifecyclePreflightFailure | None:
        return _start_preflight(task_dir, repo_root)

    if getattr(args, "auto", False):
        return _run_auto_start(args, full_path, preflight)

    service = TaskLifecycleService(repo_root)
    result = service.start(full_path, preflight=preflight)
    if not result.ok:
        return _report_start_failure(result, service)

    _report_start_success(result, repo_root, full_path)
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
    task_dir = _resolve_status_task_dir(args, repo_root)
    if task_dir is None:
        return 1

    service = TaskLifecycleService(repo_root)
    result = service.complete(
        task_dir,
        completed_at=datetime.now().strftime("%Y-%m-%d"),
        allow_spec_file_modifications=is_main_session(repo_root),
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


def _next_target_for_run(args: argparse.Namespace, repo_root: Path):
    target_input = getattr(args, "dir", None)
    if target_input:
        task_dir = _resolve_task_dir(target_input, repo_root)
        return task_dir, _display_task_path(repo_root, task_dir), False

    active = get_active_task(repo_root)
    if active.task_path:
        task_dir = repo_root / active.task_path
        return task_dir, active.task_path, True
    return None, None, False


def _next_payload_for_run(args: argparse.Namespace, repo_root: Path) -> dict[str, object]:
    task_dir, task_path, active_target = _next_target_for_run(args, repo_root)
    if task_dir is None or task_path is None:
        return task_navigation.build_navigation_payload(
            args=args,
            status="no_task",
            blockers=[],
            active_target=False,
            task_path=None,
        )
    if not task_dir.is_dir():
        return task_navigation.build_navigation_payload(
            args=args,
            status="stale",
            blockers=[f"task directory not found: {task_path}"],
            active_target=active_target,
            task_path=task_path,
        )
    status = task_navigation._status(repo_root, task_dir)
    blockers = task_navigation._blockers(repo_root, task_dir) if status == "planning" else []
    return task_navigation.build_navigation_payload(
        args=args,
        status=status,
        blockers=blockers,
        active_target=active_target,
        task_path=task_path,
    )


def _args_with(args: argparse.Namespace, **overrides) -> argparse.Namespace:
    values = vars(args).copy()
    values.update(overrides)
    return argparse.Namespace(**values)


def _run_create_action(args: argparse.Namespace, action: dict[str, object]) -> int:
    if not getattr(args, "title", None):
        print(
            colored("Error: create_task requires --title", Colors.RED),
            file=sys.stderr,
        )
        print(f"Command: {action.get('command')}", file=sys.stderr)
        return 1
    return cmd_create(
        _args_with(
            args,
            title=args.title,
            slug=getattr(args, "slug", None),
            assignee=getattr(args, "assignee", None),
            priority=getattr(args, "priority", "P2"),
            description=getattr(args, "description", None),
            parent=getattr(args, "parent", None),
            from_plan=getattr(args, "from_plan", None),
        )
    )


def _create_input_names(args: argparse.Namespace) -> list[str]:
    names = (
        "title",
        "slug",
        "assignee",
        "description",
        "parent",
        "from_plan",
    )
    return [name for name in names if getattr(args, name, None)]


def _validated_next_action(args: argparse.Namespace) -> tuple[dict[str, object] | None, int]:
    payload = _next_payload_for_run(args, get_repo_root())
    action = payload.get("action")
    if not isinstance(action, dict):
        print(
            colored("Error: task next did not return an action", Colors.RED),
            file=sys.stderr,
        )
        return None, 1
    create_inputs = _create_input_names(args)
    action_id = action.get("id")
    if create_inputs and action_id != "create_task":
        print(
            colored(
                f"Error: create_task inputs cannot run {action_id}",
                Colors.RED,
            ),
            file=sys.stderr,
        )
        print(
            "Hint: archive or finish the current task first, then rerun "
            "`task next --run --title ... --slug ... --assignee <name>`.",
            file=sys.stderr,
        )
        return None, 1
    if payload.get("blockers") or action.get("blockers"):
        print(colored("Error: next action is blocked", Colors.RED), file=sys.stderr)
        for blocker in payload.get("blockers", []) or action.get("blockers", []):
            print(f"  - {blocker}", file=sys.stderr)
        return None, 1
    if not action.get("runnable"):
        action_id = action.get("id")
        print(
            colored(f"Error: next action is not executable: {action_id}", Colors.RED),
            file=sys.stderr,
        )
        if action.get("command"):
            print(f"Command: {action['command']}", file=sys.stderr)
        return None, 1
    return action, 0


def _resolved_next_action_task(args: argparse.Namespace, action_id: object) -> str | None:
    if action_id == "create_task":
        return None
    _, task_path_value, _ = _next_target_for_run(args, get_repo_root())
    if task_path_value is None:
        print(colored("Error: no task target for action", Colors.RED), file=sys.stderr)
        return None
    return task_path_value


def _dispatch_next_lifecycle_action(
    args: argparse.Namespace,
    action_id: object,
    task_path: str | None,
    action: dict[str, object],
) -> int:
    if action_id == "create_task":
        return _run_create_action(args, action)
    if task_path is None:
        return 1
    if action_id == "start_task":
        return cmd_start(_args_with(
            args,
            dir=task_path,
            auto=bool(getattr(args, "auto", False)),
            approved=bool(getattr(args, "approved", False)),
        ))
    if action_id == "request_review":
        return cmd_review(_args_with(args, dir=task_path))
    if action_id == "complete_task":
        return cmd_complete(_args_with(args, dir=task_path))
    if action_id == "archive_task":
        return cmd_archive(_args_with(
            args,
            name=Path(str(task_path)).name,
            commit=bool(getattr(args, "commit", False)),
        ))
    if action_id == "batch_execute":
        return cmd_start(_args_with(
            args,
            dir=task_path,
            auto=True,
            approved=bool(getattr(args, "approved", False)),
        ))
    print(
        colored(f"Error: unsupported next action: {action_id}", Colors.RED),
        file=sys.stderr,
    )
    return 1


def _run_next_action(args: argparse.Namespace) -> int:
    action, error_code = _validated_next_action(args)
    if action is None:
        return error_code
    action_id = action.get("id")
    task_path = _resolved_next_action_task(args, action_id)
    return _dispatch_next_lifecycle_action(args, action_id, task_path, action)

def cmd_next(args: argparse.Namespace) -> int:
    """Show or run the next workflow action."""
    if getattr(args, "list_tasks", False):
        if getattr(args, "run", False):
            print(
                colored("Error: --list is read-only; remove --run", Colors.RED),
                file=sys.stderr,
            )
            return 1
        return cmd_list(
            _args_with(
                args,
                mine=bool(getattr(args, "mine", False)),
                status=getattr(args, "status", None),
            )
        )
    if getattr(args, "validate", False):
        if getattr(args, "run", False):
            print(
                colored("Error: --validate is read-only; remove --run", Colors.RED),
                file=sys.stderr,
            )
            return 1
        if not getattr(args, "dir", None):
            print(
                colored("Error: --validate requires a task dir", Colors.RED),
                file=sys.stderr,
            )
            return 1
        return cmd_validate(_args_with(args, dir=args.dir))
    if getattr(args, "run", False):
        return _run_next_action(args)
    return task_navigation.cmd_next(args)


WORKER_BLOCKED_COMMANDS = frozenset()

COMMANDS = {
    "next": cmd_next,
}


def _worker_command_blocked(execution_context, command: str) -> bool:
    if not execution_context.is_worker or command not in WORKER_BLOCKED_COMMANDS:
        return False
    print(
        worker_command_block_message(
            execution_context,
            f"task {command}",
            "Workers must not activate, archive, or mutate "
            "cowork-flow task state.",
        ),
        file=sys.stderr,
    )
    return True


def main() -> int:
    """CLI entry point."""
    args = build_parser().parse_args()
    execution_context = execution_context_from_namespace(args)
    if not args.command:
        show_usage()
        return 1

    if _worker_command_blocked(execution_context, args.command):
        return 2

    command = COMMANDS.get(args.command)
    if command is None:
        show_usage()
        return 1
    return command(args)


if __name__ == "__main__":
    raise SystemExit(main())
