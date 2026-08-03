"""Pure workflow state and transition facts.

The kernel deliberately knows nothing about Skills, CLI commands, prompt
wording, or runtime script locations.  Those concerns are resolved by the
service and adapter layers from distributed Skill manifests.
"""

from __future__ import annotations

from kernel.task_state import CHECK_STATUSES, DONE_STATUSES


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
    "implement": {"implement_change", "execute_delegated_work", "start_task"},
    "archive": {"archive_task"},
    "review": {"request_review", "verify_change", "complete_task"},
    "doubt_review": {"doubt_review"},
    "debug": {"debug_failure"},
    "discuss": {"discuss_options"},
    "batch": {"batch_execute"},
}

# These are state-transition facts, not Skill metadata.
ACTION_TRANSITIONS = {
    "answer_questions": {"lifecycleCheck": None, "mutatesState": False},
    "debug_failure": {"lifecycleCheck": None, "mutatesState": False},
    "discuss_options": {"lifecycleCheck": None, "mutatesState": False},
    "doubt_review": {"lifecycleCheck": None, "mutatesState": False},
    "batch_execute": {"lifecycleCheck": "task_start", "mutatesState": True},
    "create_task": {"lifecycleCheck": None, "mutatesState": True},
    "edit_planning_artifacts": {"lifecycleCheck": "task_start", "mutatesState": False},
    "start_task": {"lifecycleCheck": "task_start", "mutatesState": True},
    "implement_change": {"lifecycleCheck": None, "mutatesState": False},
    "request_review": {"lifecycleCheck": "task_review", "mutatesState": True},
    "complete_task": {"lifecycleCheck": "task_complete", "mutatesState": True},
    "archive_task": {"lifecycleCheck": "task_archive", "mutatesState": True},
    "execute_delegated_work": {"lifecycleCheck": None, "mutatesState": False},
    "repair_workflow_state": {"lifecycleCheck": None, "mutatesState": False},
}
RUNNABLE_ACTIONS = {
    action_id
    for action_id, spec in ACTION_TRANSITIONS.items()
    if spec["mutatesState"]
}


def _main_operations(
    status: str,
    blockers: tuple[str, ...],
    active_target: bool,
) -> list[str]:
    del active_target
    operations = ["answer_questions", "debug_failure", "discuss_options", "doubt_review"]
    if status == "no_task":
        operations.extend(["create_task", "edit_planning_artifacts"])
    elif status == "planning":
        operations.append("edit_planning_artifacts")
        if not blockers:
            operations.extend(["start_task", "batch_execute"])
    elif status == "in_progress":
        operations.extend(["implement_change", "request_review", "batch_execute"])
    elif status in CHECK_STATUSES:
        operations.extend(["verify_change", "apply_review_fix", "complete_task"])
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
    if status in {"no_task", "planning", "in_progress"}:
        return ["decision-anchor.md", "implement.jsonl"]
    if status in CHECK_STATUSES:
        return ["decision-anchor.md"]
    if status in DONE_STATUSES:
        return []
    if status == "delegated_subtask":
        return ["runtime-context"]
    return []


def _intent_is_allowed(intent: str, operations: list[str]) -> bool:
    return bool(INTENT_OPERATIONS[intent].intersection(operations))


def _action_id(status: str, intent: str, blockers: list[str]) -> str:
    if intent == "question":
        return "answer_questions"
    if intent == "debug":
        return "debug_failure"
    if intent == "discuss":
        return "discuss_options"
    if intent == "doubt_review":
        return "doubt_review"
    if intent == "batch":
        return "batch_execute"
    if status == "no_task":
        return "create_task"
    if status == "planning":
        return "edit_planning_artifacts" if blockers else "start_task"
    if status == "in_progress":
        return "request_review" if intent == "review" else "implement_change"
    if status in CHECK_STATUSES:
        return "complete_task"
    if status in DONE_STATUSES:
        return "archive_task"
    if status == "delegated_subtask":
        return "execute_delegated_work"
    return "repair_workflow_state"


def _action_contract(
    *,
    status: str,
    blockers: tuple[str, ...] | list[str],
    active_target: bool,
    intent: str,
) -> dict[str, object]:
    del active_target
    action_blockers = [str(blocker) for blocker in blockers]
    action_id = _action_id(status, intent, action_blockers)
    spec = ACTION_TRANSITIONS[action_id]
    return {
        "id": action_id,
        "mutatesState": spec["mutatesState"],
        "lifecycleCheck": spec["lifecycleCheck"],
        "runnable": action_id in RUNNABLE_ACTIONS and not action_blockers,
        "blockers": action_blockers,
    }


def _resolve_route(
    status: str,
    intent: str,
    context: str,
    blockers: tuple[str, ...] | list[str],
    active_target: bool,
) -> tuple[list[str], list[str], bool]:
    route_blockers = [str(blocker) for blocker in blockers]
    operations = _allowed_operations(status, context, tuple(route_blockers), active_target)
    intent_allowed = _intent_is_allowed(intent, operations)
    if context == "delegated" and status != "delegated_subtask":
        route_blockers.append("delegated context cannot operate main-session workflow state")
    if not intent_allowed:
        route_blockers.append(f"intent {intent} is not allowed while status is {status}")
    return route_blockers, operations, intent_allowed


def _default_intent(status: str, blockers: list[str], active_target: bool) -> str:
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
