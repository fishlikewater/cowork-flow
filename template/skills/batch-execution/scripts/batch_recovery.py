#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only Batch inspect and recovery projections."""

from __future__ import annotations

from typing import Any

from batch_state_machine import BATCH_STEPS, phase_for_step


def failed_action(state: dict[str, Any]) -> dict[str, Any] | None:
    """Return public facts for the action that paused Batch, if any."""

    if state.get("phase") != "paused":
        return None
    action_results = dict(state.get("action_results") or {})
    if not action_results:
        return None
    action_id, result = next(reversed(action_results.items()))
    if not isinstance(result, dict):
        return {"actionId": str(action_id)}
    failed: dict[str, Any] = {"actionId": str(action_id)}
    result_type = result.get("type")
    if isinstance(result_type, str):
        failed["type"] = result_type
    outcome = result.get("outcome")
    if isinstance(outcome, str):
        failed["outcome"] = outcome
    detail = result.get("detail")
    if isinstance(detail, str) and detail.strip():
        failed["detail"] = detail.strip()
    return failed


def current_phase(
    state: dict[str, Any],
    failed_action_facts: dict[str, Any] | None,
) -> str | None:
    """Project the current user-visible Batch phase without mutating state."""

    next_action = state.get("next_action")
    if isinstance(next_action, dict):
        phase = next_action.get("phase")
        return str(phase) if isinstance(phase, str) else None
    if failed_action_facts is not None:
        action_type = failed_action_facts.get("type")
        if isinstance(action_type, str) and action_type in BATCH_STEPS:
            return phase_for_step(action_type)
    task_name = state.get("current_task")
    if isinstance(task_name, str):
        task_phases = dict(state.get("task_phases") or {})
        phases = task_phases.get(task_name)
        if isinstance(phases, list) and phases:
            phase = phases[-1]
            return str(phase) if isinstance(phase, str) else None
    phase = state.get("phase")
    return str(phase) if isinstance(phase, str) else None


def recovery_facts(state: dict[str, Any]) -> dict[str, object]:
    """Return read-only recovery hints for a paused Batch operation."""

    if state.get("phase") != "paused":
        return {}
    operation_id = state.get("operation_id")
    recovery: dict[str, object] = {}
    if isinstance(operation_id, str) and operation_id.strip():
        recovery["resumeCommand"] = f"batch-action resume {operation_id.strip()}"
    task_name = state.get("current_task")
    if isinstance(task_name, str) and task_name.strip():
        recovery["retryTask"] = task_name.strip()
    pause_reason = state.get("pause_reason")
    if isinstance(pause_reason, str) and pause_reason.strip():
        recovery["pausedReason"] = pause_reason.strip()
    return recovery


def inspect_projection(operation_id: str, state: dict[str, Any]) -> dict[str, Any]:
    """Build the public inspect payload without state mutation or IO."""

    failed = failed_action(state)
    return {
        "operationId": operation_id,
        "state": state.get("phase"),
        "rootTask": state.get("root_task"),
        "currentPhase": current_phase(state, failed),
        "currentTask": state.get("current_task"),
        "completedTasks": list(state.get("completed_tasks") or []),
        "pausedReason": state.get("pause_reason"),
        "failedAction": failed,
        "nextAction": state.get("next_action"),
        "recovery": recovery_facts(state),
    }
