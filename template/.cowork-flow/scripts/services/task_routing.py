"""Pure workflow route contract for task navigation."""

from __future__ import annotations

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
        "lifecycleCheck": None,
        "mutatesState": False,
    },
    "debug_failure": {
        "label": "diagnose the failure",
        "activatedSkill": "failure-analysis",
        "lifecycleCheck": None,
        "mutatesState": False,
    },
    "discuss_options": {
        "label": "discuss workflow options",
        "activatedSkill": "party-mode",
        "lifecycleCheck": None,
        "mutatesState": False,
    },
    "batch_execute": {
        "label": "execute approved batch plan",
        "activatedSkill": "batch-execution",
        "lifecycleCheck": "task_start",
        "mutatesState": True,
    },
    "create_task": {
        "label": "create a planned task",
        "activatedSkill": "brainstorming",
        "lifecycleCheck": None,
        "mutatesState": True,
    },
    "edit_planning_artifacts": {
        "label": "finish planning prerequisites",
        "activatedSkill": "task-planning",
        "lifecycleCheck": "task_start",
        "mutatesState": False,
    },
    "start_task": {
        "label": "start task",
        "activatedSkill": "cowork-flow",
        "lifecycleCheck": "task_start",
        "mutatesState": True,
    },
    "implement_change": {
        "label": "execute implementation plan",
        "activatedSkill": "cowork-flow",
        "lifecycleCheck": None,
        "mutatesState": False,
    },
    "request_review": {
        "label": "mark task ready for review",
        "activatedSkill": "task-review",
        "lifecycleCheck": "task_review",
        "mutatesState": True,
    },
    "complete_task": {
        "label": "complete reviewed task",
        "activatedSkill": "task-review",
        "lifecycleCheck": "task_complete",
        "mutatesState": True,
    },
    "archive_task": {
        "label": "archive completed task",
        "activatedSkill": "cowork-flow",
        "lifecycleCheck": "task_archive",
        "mutatesState": True,
    },
    "doubt_review": {
        "label": "run standalone doubt review",
        "activatedSkill": "adversarial-review",
        "lifecycleCheck": None,
        "mutatesState": False,
    },
    "execute_delegated_work": {
        "label": "execute delegated work",
        "activatedSkill": "cowork-flow",
        "lifecycleCheck": None,
        "mutatesState": False,
    },
    "repair_workflow_state": {
        "label": "inspect and repair workflow state",
        "activatedSkill": "cowork-flow",
        "lifecycleCheck": None,
        "mutatesState": False,
    },
}
RUNNABLE_ACTIONS = {
    action_id
    for action_id, spec in ACTION_SPECS.items()
    if spec["mutatesState"]
}


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
    lifecycle_check = spec["lifecycleCheck"]
    return {
        "id": action_id,
        "label": spec["label"],
        "activatedSkill": spec["activatedSkill"],
        "command": command,
        "mutatesState": spec["mutatesState"],
        "lifecycleCheck": lifecycle_check,
        "runtimeGate": lifecycle_check,
        "runnable": runnable,
        "blockers": action_blockers,
    }


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
        "lifecycleCheck": action["lifecycleCheck"],
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
