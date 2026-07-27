#!/usr/bin/env python3
"""Task workflow navigation and deterministic action contract."""

from __future__ import annotations

import json
from pathlib import Path

from services.task_context import TaskContextService
from adapters.cli.task_archive_commands import linked_active_changes_for_task
from adapters.cli.task_support import resolve_task_dir
from adapters.cli.execution_context_args import execution_context_from_namespace
from kernel.paths import get_repo_root
from kernel.session_state import get_active_task
from services.readiness import task_readiness_blockers
from kernel.task_repository import TaskRepository, TaskRepositoryError


from services.task_routing import (
    CHECK_STATUSES,
    DONE_STATUSES,
    USER_INTENTS,
    _action_contract,
    _default_intent,
    _run_command,
    route_request,
)



def _display(repo_root: Path, task_dir: Path) -> str:
    try:
        return task_dir.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(task_dir)


def _status(repo_root: Path, task_dir: Path) -> str:
    try:
        data = TaskRepository(repo_root).load(task_dir)
    except TaskRepositoryError:
        return "stale"
    status = data.get("status")
    return status.strip() if isinstance(status, str) and status.strip() else "unknown"


def _blockers(repo_root: Path, task_dir: Path) -> list[str]:
    blockers = list(TaskContextService(repo_root).start_blockers(task_dir))
    blockers.extend(task_readiness_blockers(repo_root, task_dir))
    return blockers


def _print_blockers(blockers: list[str]) -> None:
    if not blockers:
        print("Blockers: none")
        return
    print("Blockers:")
    for blocker in blockers:
        print(f"  - {blocker}")


def _implementation(task_path: str) -> None:
    action = _action_contract(
        status="in_progress",
        task_path=task_path,
        blockers=[],
        active_target=True,
        intent="implement",
    )
    print(f"Next action: {action['label']}")
    print(f"Skill: {action['activatedSkill']}")
    print("Command: none — implement the plan guided by the activated Skill")
    print(f"Then: {_run_command(task_path, intent='review')}")

def _routing_context(args) -> str:
    execution_context = execution_context_from_namespace(args)
    if execution_context.is_worker or execution_context.is_subagent:
        return "delegated"
    return "main"


def build_navigation_payload(
    *,
    args,
    status: str,
    blockers: list[str],
    active_target: bool,
    task_path: str | None = None,
) -> dict[str, object]:
    intent = getattr(args, "intent", None) or _default_intent(
        status,
        blockers,
        active_target,
    )
    return route_request(
        status=status,
        intent=intent,
        context=_routing_context(args),
        blockers=blockers,
        active_target=active_target,
        task_path=task_path,
    )


def _print_json_route(
    *,
    args,
    status: str,
    blockers: list[str],
    active_target: bool,
    task_path: str | None = None,
) -> None:
    payload = build_navigation_payload(
        args=args,
        status=status,
        blockers=blockers,
        active_target=active_target,
        task_path=task_path,
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=False))


def _navigation_target(args, repo_root: Path, structured: bool):
    target = getattr(args, "dir", None)
    if target:
        task_dir = resolve_task_dir(target, repo_root)
        task_path = _display(repo_root, task_dir)
        return task_dir, task_path, "argument", False

    active = get_active_task(repo_root)
    source = f"{active.source}:{active.context_key or '-'}"
    if active.task_path:
        return repo_root / active.task_path, active.task_path, source, True
    if structured:
        _print_json_route(
            args=args,
            status="no_task",
            blockers=[],
            active_target=False,
            task_path=None,
        )
    else:
        print("Status: no_task")
        print(f"Source: {source}")
        action = _action_contract(
            status="no_task",
            task_path=None,
            blockers=[],
            active_target=False,
            intent="clarify",
        )
        print(f"Next action: {action['label']}")
        print(f"Skill: {action['activatedSkill']}")
        print(f"Command: {action['command']}")
        print("Runtime-context state is injected by hook/plugin; do not infer it from prompt text.")
    return None


def _print_stale_route(args, task_path: str, source: str, active_target: bool) -> None:
    if bool(getattr(args, "json", False)):
        _print_json_route(
            args=args,
            status="stale",
            blockers=[f"task directory not found: {task_path}"],
            active_target=active_target,
            task_path=task_path,
        )
        return
    print("Status: stale")
    print(f"Source: {source}")
    print("Next action: inspect and repair workflow state")
    print("Command: none — inspect task state before mutating")
    print("Blockers:")
    print(f"  - task directory not found: {task_path}")


def _print_text_route(
    repo_root: Path,
    task_path: str,
    task_dir: Path,
    status: str,
    source: str,
    blockers: list[str],
    active_target: bool,
    intent: str | None = None,
) -> None:
    print(f"Status: {status}")
    print(f"Source: {source}")
    if status == "planning":
        action = _action_contract(
            status=status,
            task_path=task_path,
            blockers=blockers,
            active_target=active_target,
            intent=intent or _default_intent(status, blockers, active_target),
        )
        print(f"Next action: {action['label']}")
        print(f"Skill: {action['activatedSkill']}")
        if action["command"]:
            print(f"Command: {action['command']}")
        else:
            print("Command: none — edit the required planning artifacts")
    elif status == "in_progress":
        _implementation(task_path)
    elif status in CHECK_STATUSES:
        if intent == "doubt_review":
            _print_doubt_review_route(task_path)
        else:
            _print_check_route(task_path)
    elif status in DONE_STATUSES:
        _print_archive_route(repo_root, task_path, task_dir)
    else:
        print("Next action: inspect task status and repair workflow state")
        print("Command: none — inspect task state before mutating")
    _print_blockers(blockers)


def _print_check_route(task_path: str) -> None:
    action = _action_contract(
        status="review",
        task_path=task_path,
        blockers=[],
        active_target=True,
        intent="review",
    )
    print(f"Next action: {action['label']}")
    print(f"Skill: {action['activatedSkill']}")
    print(f"Command: {action['command']}")
    print("Then: complete only after the activated review Skill has checked the current diff and user specs")

def _print_doubt_review_route(task_path: str) -> None:
    print("Next action: run standalone doubt review")
    print("Skill: adversarial-review")
    print(f"Target: {task_path}")
    print("Do not dispatch the lifecycle check agent unless this becomes review/complete work.")


def _print_archive_route(repo_root: Path, task_path: str, task_dir: Path) -> None:
    action = _action_contract(
        status="completed",
        task_path=task_path,
        blockers=[],
        active_target=True,
        intent="archive",
    )
    print(f"Next action: {action['label']}")
    print(f"Skill: {action['activatedSkill']}")
    print("Command: git status --short")
    print(f"Then: {action['command']}")
    changes = linked_active_changes_for_task(repo_root, task_dir)
    for slug in changes:
        print(f"Then: ./.cowork-flow/run change archive {slug} (handled by archive_task)")


def cmd_next(args) -> int:
    repo_root = get_repo_root()
    structured = bool(getattr(args, "json", False))
    if not structured:
        print("Workflow Next")
    target = _navigation_target(args, repo_root, structured)
    if target is None:
        return 0
    task_dir, task_path, source, active_target = target

    if not structured:
        print(f"Task: {task_path}")
    if not task_dir.is_dir():
        _print_stale_route(args, task_path, source, active_target)
        return 0

    status = _status(repo_root, task_dir)
    blockers = _blockers(repo_root, task_dir) if status == "planning" else []
    if structured:
        _print_json_route(
            args=args,
            status=status,
            blockers=blockers,
            active_target=active_target,
            task_path=task_path,
        )
        return 0

    _print_text_route(
        repo_root,
        task_path,
        task_dir,
        status,
        source,
        blockers,
        active_target,
        getattr(args, "intent", None),
    )
    return 0
