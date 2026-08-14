#!/usr/bin/env python3
"""Delivery runner for deterministic `task next --run` actions."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from adapters.cli import task_navigation
from adapters.cli.task_support import Colors, colored, resolve_task_dir
from infra.paths import get_repo_root
from runtime.session_state import get_active_task
from services.plan_binding import PlanBindingError, bind_task_plan


LifecycleCommand = Callable[[argparse.Namespace], int]


@dataclass(frozen=True)
class NextActionHandlers:
    create: LifecycleCommand
    start: LifecycleCommand
    review: LifecycleCommand
    complete: LifecycleCommand
    archive: LifecycleCommand


def namespace_with(args: argparse.Namespace, **overrides) -> argparse.Namespace:
    values = vars(args).copy()
    values.update(overrides)
    return argparse.Namespace(**values)


def _display_task_path(repo_root: Path, task_dir: Path) -> str:
    try:
        return task_dir.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(task_dir)


def _next_target_for_run(args: argparse.Namespace, repo_root: Path):
    target_input = getattr(args, "dir", None)
    if target_input:
        task_dir = resolve_task_dir(target_input, repo_root)
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


def _run_create_action(
    args: argparse.Namespace,
    action: dict[str, object],
    handlers: NextActionHandlers,
) -> int:
    if not getattr(args, "title", None):
        print(
            colored("Error: create_task requires --title", Colors.RED),
            file=sys.stderr,
        )
        print(f"Command: {action.get('command')}", file=sys.stderr)
        return 1
    return handlers.create(
        namespace_with(
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
    from_plan = getattr(args, "from_plan", None)
    if create_inputs and action_id != "create_task":
        print(
            colored(
                f"Error: create_task inputs cannot run {action_id}",
                Colors.RED,
            ),
            file=sys.stderr,
        )
        print(
            "Hint: those flags only create a new task. To continue the "
            "current task, run:",
            file=sys.stderr,
        )
        print("  ./.cowork-flow/run task next <task-dir> --run", file=sys.stderr)
        return None, 1
    if from_plan and action_id not in {"create_task", "edit_planning_artifacts"}:
        print(
            colored(
                "Error: --from-plan binds a plan to a planning task or "
                "creates a new task, but the next action is "
                f"{action_id}",
                Colors.RED,
            ),
            file=sys.stderr,
        )
        return None, 1
    if action_id == "edit_planning_artifacts" and from_plan:
        return action, 0
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
    handlers: NextActionHandlers,
) -> int:
    if action_id == "create_task":
        return _run_create_action(args, action, handlers)
    if task_path is None:
        return 1
    if action_id == "start_task":
        return handlers.start(
            namespace_with(
                args,
                dir=task_path,
                auto=bool(getattr(args, "auto", False)),
                approved=bool(getattr(args, "approved", False)),
            )
        )
    if action_id == "request_review":
        return handlers.review(namespace_with(args, dir=task_path))
    if action_id == "complete_task":
        return handlers.complete(namespace_with(args, dir=task_path))
    if action_id == "archive_task":
        return handlers.archive(
            namespace_with(
                args,
                name=Path(str(task_path)).name,
                commit=bool(getattr(args, "commit", False)),
            )
        )
    if action_id == "batch_execute":
        return handlers.start(
            namespace_with(
                args,
                dir=task_path,
                auto=True,
                approved=bool(getattr(args, "approved", False)),
            )
        )
    if action_id == "edit_planning_artifacts":
        return _run_plan_bind_action(args, task_path)
    print(
        colored(f"Error: unsupported next action: {action_id}", Colors.RED),
        file=sys.stderr,
    )
    return 1


def _run_plan_bind_action(args: argparse.Namespace, task_path: str) -> int:
    repo_root = get_repo_root()
    try:
        bind_task_plan(repo_root, repo_root / task_path, args.from_plan)
    except PlanBindingError as error:
        print(
            colored(f"Error: {error.detail}: {error.path}", Colors.RED),
            file=sys.stderr,
        )
        return 1
    print(colored(f"[OK] Plan bound to: {task_path}", Colors.GREEN))
    print(f"Next: ./.cowork-flow/run task next {task_path} --run")
    return 0


def run_next_action(args: argparse.Namespace, handlers: NextActionHandlers) -> int:
    action, error_code = _validated_next_action(args)
    if action is None:
        return error_code
    action_id = action.get("id")
    task_path = _resolved_next_action_task(args, action_id)
    return _dispatch_next_lifecycle_action(args, action_id, task_path, action, handlers)
