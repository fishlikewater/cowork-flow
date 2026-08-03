"""Resolve kernel route facts through distributed Skill ownership metadata."""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class ActionContract:
    """Internal action facts before adapter compatibility aliases are added."""

    action_id: str
    label: str
    activated_skill: str | None
    command: str | None
    diagnostics_command: str | None
    mutates_state: bool
    lifecycle_check: str | None
    runnable: bool
    blockers: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "id": self.action_id,
            "label": self.label,
            "activatedSkill": self.activated_skill,
            "command": self.command,
            "diagnosticsCommand": self.diagnostics_command,
            "mutatesState": self.mutates_state,
            "lifecycleCheck": self.lifecycle_check,
            "runnable": self.runnable,
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True)
class RouteContract:
    """Internal route facts before CLI adapter rendering."""

    status: str
    allowed_operations: tuple[str, ...]
    required_artifacts: tuple[str, ...]
    recommended_skill: str | None
    blockers: tuple[str, ...]
    action: ActionContract

    def to_payload(self) -> dict[str, object]:
        action = self.action.to_payload()
        return {
            "status": self.status,
            "allowedOperations": list(self.allowed_operations),
            "requiredArtifacts": list(self.required_artifacts),
            "recommendedSkill": self.recommended_skill,
            "blockers": list(self.blockers),
            "nextAction": self.action.action_id,
            "activatedSkill": self.action.activated_skill,
            "actionCommand": self.action.command,
            "diagnosticsCommand": self.action.diagnostics_command,
            "mutatesState": self.action.mutates_state,
            "lifecycleCheck": self.action.lifecycle_check,
            "action": action,
        }


def _action_contract(
    *,
    status: str,
    task_path: str | None,
    blockers: tuple[str, ...] | list[str],
    active_target: bool,
    intent: str,
    repo_root: Path | None = None,
) -> ActionContract:
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
        if owner.lifecycle_check != action["lifecycleCheck"]:
            action_blockers.append(f"Skill owner lifecycle mismatch: {action_id}")

    lifecycle_check = owner.lifecycle_check if owner is not None else action["lifecycleCheck"]
    return ActionContract(
        action_id=action_id,
        label=owner.label if owner is not None else action_id,
        activated_skill=owner.skill if owner is not None else None,
        command=owner.command if owner is not None else None,
        diagnostics_command=owner.diagnostics_command if owner is not None else None,
        mutates_state=bool(action["mutatesState"]),
        lifecycle_check=lifecycle_check,
        runnable=bool(action["runnable"]) and not action_blockers,
        blockers=tuple(action_blockers),
    )


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
    route_blockers = action.blockers
    recommended = action.activated_skill if intent_allowed and not route_blockers else None
    return RouteContract(
        status=status,
        allowed_operations=tuple(operations),
        required_artifacts=tuple(_required_artifacts(status)),
        recommended_skill=recommended,
        blockers=route_blockers,
        action=action,
    ).to_payload()
