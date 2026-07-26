#!/usr/bin/env python3
"""Task workflow navigation and deterministic action contract."""

from __future__ import annotations

import json
from pathlib import Path

from application.task_context import TaskContextService
from commands.task_archive_commands import linked_active_changes_for_task
from commands.task_support import resolve_task_dir
from common.core.execution_context import execution_context_from_namespace
from common.core.paths import get_repo_root
from common.task.active_task import get_active_task
from common.task.readiness import task_readiness_blockers
from common.task.task_repository import TaskRepository, TaskRepositoryError


CHECK_STATUSES = ("review",)
DONE_STATUSES = ("completed", "done")
USER_INTENTS = (
    "question",
    "clarify",
    "plan",
    "implement",
    "archive",
    "review",
    "doubt_review",
    "debug",
    "discuss",
    "batch",
)
INTENT_OPERATIONS = {
    "question": {"answer_questions"},
    "clarify": {"edit_planning_artifacts"},
    "plan": {"edit_planning_artifacts"},
    "implement": {
        "implement_change",
        "execute_delegated_work",
        "start_task",
    },
    "archive": {"archive_task"},
    "review": {"request_review", "verify_change", "complete_task"},
    "doubt_review": {"request_review", "verify_change", "discuss_options"},
    "debug": {"debug_failure"},
    "discuss": {"discuss_options"},
    "batch": {"batch_execute"},
}


ACTION_SPECS = {
    "answer_questions": {
        "label": "answer the workflow question",
        "activatedSkill": None,
        "runtimeGate": None,
        "mutatesState": False,
    },
    "debug_failure": {
        "label": "diagnose the failure",
        "activatedSkill": "failure-analysis",
        "runtimeGate": None,
        "mutatesState": False,
    },
    "discuss_options": {
        "label": "discuss workflow options",
        "activatedSkill": "party-mode",
        "runtimeGate": None,
        "mutatesState": False,
    },
    "batch_execute": {
        "label": "execute approved batch plan",
        "activatedSkill": "batch-execution",
        "runtimeGate": "task_start",
        "mutatesState": True,
    },
    "create_task": {
        "label": "create a planned task",
        "activatedSkill": "brainstorming",
        "runtimeGate": None,
        "mutatesState": True,
    },
    "edit_planning_artifacts": {
        "label": "finish planning prerequisites",
        "activatedSkill": "task-planning",
        "runtimeGate": "task_start",
        "mutatesState": False,
    },
    "start_task": {
        "label": "start task",
        "activatedSkill": "cowork-flow",
        "runtimeGate": "task_start",
        "mutatesState": True,
    },
    "implement_change": {
        "label": "execute implementation plan",
        "activatedSkill": "cowork-flow",
        "runtimeGate": None,
        "mutatesState": False,
    },
    "request_review": {
        "label": "mark task ready for review",
        "activatedSkill": "task-review",
        "runtimeGate": "task_review",
        "mutatesState": True,
    },
    "complete_task": {
        "label": "complete reviewed task",
        "activatedSkill": "task-review",
        "runtimeGate": "task_complete",
        "mutatesState": True,
    },
    "archive_task": {
        "label": "archive completed task",
        "activatedSkill": "cowork-flow",
        "runtimeGate": "task_archive",
        "mutatesState": True,
    },
    "doubt_review": {
        "label": "run standalone doubt review",
        "activatedSkill": "adversarial-review",
        "runtimeGate": None,
        "mutatesState": False,
    },
    "execute_delegated_work": {
        "label": "execute delegated work",
        "activatedSkill": "cowork-flow",
        "runtimeGate": None,
        "mutatesState": False,
    },
    "repair_workflow_state": {
        "label": "inspect and repair workflow state",
        "activatedSkill": "cowork-flow",
        "runtimeGate": None,
        "mutatesState": False,
    },
}
RUNNABLE_ACTIONS = {
    action_id
    for action_id, spec in ACTION_SPECS.items()
    if spec["mutatesState"]
}


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


def _run_command(
    task_path: str | None,
    *,
    intent: str | None = None,
    create: bool = False,
    commit: bool = False,
) -> str:
    parts = ["./.cowork-flow/run", "task", "next"]
    if task_path:
        parts.append(task_path)
    parts.append("--run")
    if intent:
        parts.extend(["--intent", intent])
    if create:
        parts.extend([
            "--title",
            '"<title>"',
            "--slug",
            "<task-name>",
            "--assignee",
            "<name>",
        ])
    if commit:
        parts.append("--commit")
    return " ".join(parts)


def _action_command(action_id: str, task_path: str | None) -> str | None:
    if action_id == "create_task":
        return _run_command(None, create=True)
    if action_id == "start_task":
        return _run_command(task_path)
    if action_id == "request_review":
        return _run_command(task_path, intent="review")
    if action_id == "complete_task":
        return _run_command(task_path, intent="review")
    if action_id == "archive_task":
        return _run_command(task_path, intent="archive")
    if action_id == "batch_execute":
        return f"{_run_command(task_path, intent='batch')} --auto --approved"
    return None


def _action_contract(
    *,
    status: str,
    task_path: str | None,
    blockers: tuple[str, ...] | list[str],
    active_target: bool,
    intent: str,
) -> dict[str, object]:
    del active_target
    action_blockers = [str(blocker) for blocker in blockers]
    if intent == "question":
        action_id = "answer_questions"
    elif intent == "debug":
        action_id = "debug_failure"
    elif intent == "discuss":
        action_id = "discuss_options"
    elif intent == "batch":
        action_id = "batch_execute"
    elif status == "no_task":
        action_id = "create_task"
    elif status == "planning":
        action_id = "edit_planning_artifacts" if action_blockers else "start_task"
    elif status == "in_progress":
        action_id = "request_review" if intent == "review" else "implement_change"
    elif status in CHECK_STATUSES:
        action_id = "doubt_review" if intent == "doubt_review" else "complete_task"
    elif status in DONE_STATUSES:
        action_id = "archive_task"
    elif status == "delegated_subtask":
        action_id = "execute_delegated_work"
    else:
        action_id = "repair_workflow_state"

    command = _action_command(action_id, task_path)
    runnable = action_id in RUNNABLE_ACTIONS and not action_blockers
    spec = ACTION_SPECS[action_id]
    return {
        "id": action_id,
        "label": spec["label"],
        "activatedSkill": spec["activatedSkill"],
        "command": command,
        "mutatesState": spec["mutatesState"],
        "runtimeGate": spec["runtimeGate"],
        "runnable": runnable,
        "blockers": action_blockers,
    }


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

def _main_operations(
    status: str,
    blockers: tuple[str, ...],
    active_target: bool,
) -> list[str]:
    operations = ["answer_questions", "debug_failure", "discuss_options"]
    if status == "no_task":
        operations.extend(["create_task", "edit_planning_artifacts"])
    elif status == "planning":
        operations.append("edit_planning_artifacts")
        if not blockers:
            operations.append("start_task")
            operations.append("batch_execute")
    elif status == "in_progress":
        operations.extend(
            ["implement_change", "request_review", "batch_execute"]
        )
    elif status in CHECK_STATUSES:
        operations.extend(
            ["verify_change", "apply_review_fix", "complete_task"]
        )
    elif status in DONE_STATUSES:
        operations.extend(["archive_task", "create_task"])
    elif status == "delegated_subtask":
        operations.extend(["execute_delegated_work", "report_result"])
    else:
        operations.append("repair_workflow_state")
    return operations


def _allowed_operations(
    status: str,
    context: str,
    blockers: tuple[str, ...],
    active_target: bool,
) -> list[str]:
    if context == "delegated" and status != "delegated_subtask":
        return [
            "answer_questions",
            "debug_failure",
            "discuss_options",
            "report_needs_context",
        ]
    return _main_operations(status, blockers, active_target)


def _required_artifacts(status: str) -> list[str]:
    if status in {"no_task", "planning"}:
        return ["decision-anchor.md", "implement.jsonl"]
    if status == "in_progress":
        return ["decision-anchor.md", "implement.jsonl"]
    if status in CHECK_STATUSES:
        return ["decision-anchor.md", "check.jsonl"]
    if status in DONE_STATUSES:
        return ["check.jsonl"]
    if status == "delegated_subtask":
        return ["runtime-context"]
    return []


def _intent_is_allowed(intent: str, operations: list[str]) -> bool:
    return bool(INTENT_OPERATIONS[intent].intersection(operations))


def route_request(
    status: str,
    intent: str,
    context: str,
    blockers: tuple[str, ...] | list[str],
    active_target: bool,
    task_path: str | None = None,
) -> dict[str, object]:
    """Return the stable state, intent, action, and execution-context route."""
    if intent not in USER_INTENTS:
        raise ValueError(f"unsupported workflow intent: {intent}")
    if context not in {"main", "delegated"}:
        raise ValueError(f"unsupported workflow context: {context}")

    route_blockers, operations, intent_allowed = _resolve_route(
        status=status,
        intent=intent,
        context=context,
        blockers=blockers,
        active_target=active_target,
    )
    action = _action_contract(
        status=status,
        task_path=task_path,
        blockers=route_blockers,
        active_target=active_target,
        intent=intent,
    )
    recommended = action["activatedSkill"] if intent_allowed else None
    return {
        "status": status,
        "allowedOperations": operations,
        "requiredArtifacts": _required_artifacts(status),
        "recommendedSkill": recommended,
        "blockers": route_blockers,
        "nextAction": action["id"],
        "activatedSkill": action["activatedSkill"],
        "actionCommand": action["command"],
        "mutatesState": action["mutatesState"],
        "runtimeGate": action["runtimeGate"],
        "action": action,
    }


def _resolve_route(
    status: str,
    intent: str,
    context: str,
    blockers: tuple[str, ...] | list[str],
    active_target: bool,
) -> tuple[list[str], list[str], bool]:
    route_blockers = [str(blocker) for blocker in blockers]
    operations = _allowed_operations(
        status,
        context,
        tuple(route_blockers),
        active_target,
    )
    intent_allowed = _intent_is_allowed(intent, operations)

    if context == "delegated" and status != "delegated_subtask":
        route_blockers.append(
            "delegated context cannot operate main-session workflow state"
        )
    if not intent_allowed:
        route_blockers.append(
            f"intent {intent} is not allowed while status is {status}"
        )
    return route_blockers, operations, intent_allowed


def _default_intent(
    status: str,
    blockers: list[str],
    active_target: bool,
) -> str:
    if status == "no_task":
        return "clarify"
    if status == "planning":
        return "plan" if blockers else "implement"
    if status == "in_progress":
        return "implement"
    if status in CHECK_STATUSES:
        return "review"
    if status in DONE_STATUSES:
        return "archive"
    if status == "delegated_subtask":
        return "implement"
    if active_target:
        return "implement"
    return "question"


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
