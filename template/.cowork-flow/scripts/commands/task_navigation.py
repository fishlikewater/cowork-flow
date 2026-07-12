#!/usr/bin/env python3
"""Read-only task workflow navigation command."""

from __future__ import annotations

import json
from pathlib import Path

from application.task_context import TaskContextService
from commands.task_archive_commands import linked_active_changes_for_task
from commands.task_support import resolve_task_dir
from common.core.execution_context import execution_context_from_namespace
from common.core.paths import get_repo_root
from common.core.skill_registry import SkillRegistry, load_skill_registry
from common.gates.gates import GateRunner
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
    "debug",
    "discuss",
    "batch",
)
INTENT_REGISTRY_KEYS = {
    "question": None,
    "clarify": "clarify_requirement",
    "plan": "write_plan",
    "implement": "route_workflow",
    "archive": "route_workflow",
    "review": "route_workflow",
    "debug": "analyze_repeated_failure",
    "discuss": "discuss_options",
    "batch": "batch_execute_plan",
}
INTENT_OPERATIONS = {
    "question": {"answer_questions"},
    "clarify": {"edit_planning_artifacts"},
    "plan": {"edit_planning_artifacts"},
    "implement": {
        "implement_change",
        "execute_delegated_work",
    },
    "archive": {"archive_task"},
    "review": {"request_review", "verify_change", "complete_task"},
    "debug": {"debug_failure"},
    "discuss": {"discuss_options"},
    "batch": {"batch_execute"},
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
    result = GateRunner(repo_root).run("task_start", task_dir)
    blockers.extend(
        f"{item.get('rule_id') or item.get('id')}: {item.get('message') or 'Gate blocked'}"
        for item in result.blockers
    )
    return blockers


def _print_blockers(blockers: list[str]) -> None:
    if not blockers:
        print("Blockers: none")
        return
    print("Blockers:")
    for blocker in blockers:
        print(f"  - {blocker}")


def _implementation(task_path: str) -> None:
    print("Next action: execute implementation plan")
    print(f"TDD reminder: for behavior changes, write a failing test and record red evidence in {task_path}/tdd.jsonl before modifying code.")
    print(
        f"Command: ./.cowork-flow/run subagent init --role implement "
        f"--agent-type cowork-implement --execution-task-dir {task_path} "
        f"--title \"Implement {Path(task_path).name}\""
    )
    print("Then: pass cowork_runtime_context_id and cowork_host_context_key through the active Host Adapter")
    print("Then: child first step runs ./.cowork-flow/run subagent bind <runtime_context_id> <host_context_key>")
    print("Then: verify status=bound and bound_context_key before accepting output")
    print(f"Then: wait, verify output, close runtime context, then ./.cowork-flow/run task review {task_path}")


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
            if active_target:
                operations.extend(["implement_change", "request_review"])
            else:
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


def _matching_public_skills(
    registry: SkillRegistry,
    status: str,
    intent: str,
) -> list[str]:
    registry_intent = INTENT_REGISTRY_KEYS[intent]
    if registry_intent is None:
        return []
    return [
        entry.id
        for entry in registry.public_entries
        if status in entry.statuses and registry_intent in entry.intents
    ]


def route_request(
    registry: SkillRegistry,
    *,
    status: str,
    intent: str,
    context: str,
    blockers: tuple[str, ...] | list[str],
    active_target: bool,
) -> dict[str, object]:
    """Return the stable state, intent, and execution-context route."""
    if intent not in USER_INTENTS:
        raise ValueError(f"unsupported workflow intent: {intent}")
    if context not in {"main", "delegated"}:
        raise ValueError(f"unsupported workflow context: {context}")

    route_blockers, operations, intent_allowed, matches = _resolve_route(
        registry,
        status=status,
        intent=intent,
        context=context,
        blockers=blockers,
        active_target=active_target,
    )
    protocols = _route_protocols(status, intent, intent_allowed)
    return {
        "status": status,
        "allowedOperations": operations,
        "requiredArtifacts": _required_artifacts(status),
        "recommendedSkill": matches[0] if len(matches) == 1 else None,
        "internalProtocols": protocols,
        "blockers": route_blockers,
    }


def _resolve_route(
    registry: SkillRegistry,
    *,
    status: str,
    intent: str,
    context: str,
    blockers: tuple[str, ...] | list[str],
    active_target: bool,
) -> tuple[list[str], list[str], bool, list[str]]:
    route_blockers = [str(blocker) for blocker in blockers]
    operations = _allowed_operations(
        status,
        context,
        tuple(route_blockers),
        active_target,
    )
    intent_allowed = _intent_is_allowed(intent, operations)
    matches = (
        _matching_public_skills(registry, status, intent)
        if intent_allowed
        else []
    )

    if context == "delegated" and status != "delegated_subtask":
        route_blockers.append(
            "delegated context cannot operate main-session workflow state"
        )
    if not intent_allowed:
        route_blockers.append(
            f"intent {intent} is not allowed while status is {status}"
        )
    if len(matches) > 1:
        route_blockers.append(
            "multiple active public Skills match the same routing cell"
        )
    if intent == "batch" and not matches:
        route_blockers.append("batch-mode is disabled")
    return route_blockers, operations, intent_allowed, matches


def _route_protocols(
    status: str,
    intent: str,
    intent_allowed: bool,
) -> list[str]:
    if intent_allowed and intent == "implement" and status in {
        "in_progress",
        "delegated_subtask",
    }:
        return ["tdd"]
    if intent_allowed and intent == "review" and status in CHECK_STATUSES:
        return ["check"]
    return []


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


def _load_navigation_registry() -> SkillRegistry:
    runtime_root = Path(__file__).resolve().parents[3]
    return load_skill_registry(runtime_root, validate_sources=False)


def _print_json_route(
    *,
    args,
    status: str,
    blockers: list[str],
    active_target: bool,
) -> None:
    intent = getattr(args, "intent", None) or _default_intent(
        status,
        blockers,
        active_target,
    )
    payload = route_request(
        _load_navigation_registry(),
        status=status,
        intent=intent,
        context=_routing_context(args),
        blockers=blockers,
        active_target=active_target,
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
        )
    else:
        print("Status: no_task")
        print(f"Source: {source}")
        print("Next action: create or start a task before repository changes")
        print('Command: ./.cowork-flow/run task create "<title>" --slug <task-name>')
        print("Then: ./.cowork-flow/run task start <task-dir>")
        print("Runtime-context subagent state is injected by hook/plugin; do not infer it from prompt text.")
    return None


def _print_stale_route(args, task_path: str, source: str, active_target: bool) -> None:
    if bool(getattr(args, "json", False)):
        _print_json_route(
            args=args,
            status="stale",
            blockers=[f"task directory not found: {task_path}"],
            active_target=active_target,
        )
        return
    print("Status: stale")
    print(f"Source: {source}")
    print("Next action: clear or replace the missing active task")
    print("Command: ./.cowork-flow/run task list")
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
) -> None:
    print(f"Status: {status}")
    print(f"Source: {source}")
    if status == "planning":
        if blockers:
            print("Next action: finish planning prerequisites before starting task")
            print(f"Command: ./.cowork-flow/run task init-context {task_path} <dev_type>")
            print(f"Then: ./.cowork-flow/run task start {task_path}")
        elif active_target:
            _implementation(task_path)
        else:
            print("Next action: start task")
            print(f"Command: ./.cowork-flow/run task start {task_path}")
    elif status == "in_progress":
        _implementation(task_path)
    elif status in CHECK_STATUSES:
        _print_check_route(task_path)
    elif status in DONE_STATUSES:
        _print_archive_route(repo_root, task_path, task_dir)
    else:
        print("Next action: inspect task status and repair workflow state")
        print(f"Command: ./.cowork-flow/run task validate {task_path}")
    _print_blockers(blockers)


def _print_check_route(task_path: str) -> None:
    print("Next action: verify implementation")
    print(f"Command: ./.cowork-flow/run subagent init --role check --agent-type cowork-check --execution-task-dir {task_path} --title \"Check {Path(task_path).name}\"")
    print("Then: pass cowork_runtime_context_id and cowork_host_context_key through the active Host Adapter or run equivalent inline check")
    print("Then: child first step runs ./.cowork-flow/run subagent bind <runtime_context_id> <host_context_key>")
    print("Then: verify status=bound and bound_context_key before accepting output")
    print(f"Then: ./.cowork-flow/run task complete {task_path}")


def _print_archive_route(repo_root: Path, task_path: str, task_dir: Path) -> None:
    print("Next action: finalize, archive, commit, and record session")
    print("Command: git status --short")
    changes = linked_active_changes_for_task(repo_root, task_dir)
    print(f"Then: ./.cowork-flow/run task archive {Path(task_path).name}")
    for slug in changes:
        print(f"Then: ./.cowork-flow/run change archive {slug} (handled by task archive)")


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
    )
    return 0
