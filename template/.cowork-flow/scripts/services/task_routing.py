"""Resolve kernel route facts through distributed Skill ownership metadata."""

from __future__ import annotations

from pathlib import Path

from infra.skill_manifest import SkillManifestError, action_metadata
from infra.paths import get_repo_root
from kernel.task_state import CHECK_STATUSES, DONE_STATUSES
from kernel.workflow_route import (
    INTENT_OPERATIONS,
    RUNNABLE_ACTIONS,
    USER_INTENTS,
    _action_contract as _kernel_action_contract,
    _default_intent,
    _intent_is_allowed,
    _required_artifacts,
    _resolve_route,
)


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
        parts.extend(["--title", '"<title>"', "--slug", "<task-name>", "--assignee", "<name>"])
    if commit:
        parts.append("--commit")
    return " ".join(parts)


def _action_command(action_id: str, task_path: str | None, template: str | None) -> str | None:
    if template:
        return template.replace("<task-dir>", task_path or "<task-dir>")
    if action_id in {"start_task", "implement_change"}:
        return _run_command(task_path)
    return None


def _diagnostics_command(task_path: str | None, template: str | None) -> str | None:
    if template:
        return template.replace("<task-dir>", task_path or "<task-dir>")
    return None


def _action_contract(
    *,
    status: str,
    task_path: str | None,
    blockers: tuple[str, ...] | list[str],
    active_target: bool,
    intent: str,
    repo_root: Path | None = None,
) -> dict[str, object]:
    action = _kernel_action_contract(
        status=status,
        blockers=blockers,
        active_target=active_target,
        intent=intent,
    )
    action_id = str(action["id"])
    owner = None
    owner_error: str | None = None
    if repo_root is None:
        repo_root = get_repo_root()
    if repo_root is not None:
        try:
            owner = action_metadata(Path(repo_root), action_id)
        except SkillManifestError as error:
            owner_error = str(error)

    action_blockers = [str(item) for item in action["blockers"]]
    if owner_error:
        action_blockers.append(f"Skill manifest invalid: {owner_error}")
    if action_id not in {"answer_questions", "discuss_options"} and owner is None:
        action_blockers.append(f"Skill owner missing for workflow action: {action_id}")
    if owner is not None:
        if owner.mutates_state != bool(action["mutatesState"]):
            action_blockers.append(f"Skill owner transition mismatch: {action_id}")
        if owner.lifecycle_check != action["runtimeGate"]:
            action_blockers.append(f"Skill owner lifecycle mismatch: {action_id}")

    lifecycle_check = owner.lifecycle_check if owner is not None else action["runtimeGate"]
    return {
        "id": action_id,
        "label": owner.label if owner is not None else action_id,
        "activatedSkill": owner.skill if owner is not None else None,
        "command": _action_command(action_id, task_path, owner.command if owner else None),
        "diagnosticsCommand": _diagnostics_command(
            task_path,
            owner.diagnostics_command if owner else None,
        ),
        "mutatesState": action["mutatesState"],
        "lifecycleCheck": lifecycle_check,
        "runtimeGate": lifecycle_check,
        "runnable": bool(action["runnable"]) and not action_blockers,
        "blockers": action_blockers,
    }


def route_request(
    status: str,
    intent: str,
    context: str,
    blockers: tuple[str, ...] | list[str],
    active_target: bool,
    task_path: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, object]:
    """Return state facts plus adapter-facing Skill/action metadata."""
    if repo_root is None:
        repo_root = get_repo_root()
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
        repo_root=repo_root,
    )
    route_blockers = list(action["blockers"])
    recommended = action["activatedSkill"] if intent_allowed and not route_blockers else None
    return {
        "status": status,
        "allowedOperations": operations,
        "requiredArtifacts": _required_artifacts(status),
        "recommendedSkill": recommended,
        "blockers": route_blockers,
        "nextAction": action["id"],
        "activatedSkill": action["activatedSkill"],
        "actionCommand": action["command"],
        "diagnosticsCommand": action["diagnosticsCommand"],
        "mutatesState": action["mutatesState"],
        "lifecycleCheck": action["lifecycleCheck"],
        "runtimeGate": action["runtimeGate"],
        "action": action,
    }
