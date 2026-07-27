"""Workflow route coordination layer.

The pure workflow route contract lives in kernel.workflow_route; this module
keeps CLI-facing coordination (route_request with action commands) and
re-exports the stable contract for compatibility.
"""

from __future__ import annotations

from kernel.workflow_route import (
    ACTION_SPECS,
    INTENT_OPERATIONS,
    RUNNABLE_ACTIONS,
    USER_INTENTS,
    _action_contract,
    _default_intent,
    _intent_is_allowed,
    _required_artifacts,
    _resolve_route,
)
from kernel.task_state import CHECK_STATUSES, DONE_STATUSES


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
    if action_id in {"start_task", "implement_change"}:
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
    action["command"] = _action_command(action["id"], task_path)
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
