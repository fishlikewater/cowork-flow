#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure in-memory Batch state transitions and action construction."""

from __future__ import annotations

from typing import Any

BATCH_STEPS = (
    "start_task",
    "init_implement_context",
    "await_implement_result",
    "review_task",
    "init_check_context",
    "await_check_result",
    "complete_task",
    "archive_task",
    "commit_task",
)
STEP_PHASES = {
    "start_task": "start",
    "await_implement_result": "implement",
    "review_task": "review",
    "await_check_result": "check",
    "complete_task": "complete",
    "archive_task": "archive",
    "commit_task": "commit",
}
LIFECYCLE_STATUSES = {
    "start_task": "in_progress",
    "review_task": "review",
    "complete_task": "completed",
    "archive_task": "completed",
}
RUNTIME_ROLES = {
    "init_implement_context": "implement",
    "await_implement_result": "implement",
    "init_check_context": "check",
    "await_check_result": "check",
}


class BatchExecutionError(RuntimeError):
    """Raised when Batch graph, state, or host input is invalid."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def phase_for_step(step: str) -> str:
    """Return the public Batch phase for a step name."""

    if "implement" in step:
        return "implement"
    if "check" in step:
        return "check"
    return STEP_PHASES[step]


def runtime_for(state: dict[str, Any], task_name: str, role: str) -> dict[str, Any]:
    """Return a previously initialized runtime context reference."""

    runtime_contexts = dict(state.get("runtime_contexts") or {})
    task_contexts = dict(runtime_contexts.get(task_name) or {})
    runtime = task_contexts.get(role)
    if not isinstance(runtime, dict):
        raise BatchExecutionError(
            "BATCH-RUNTIME-MISSING-001",
            f"runtime context was not initialized for {task_name}:{role}",
        )
    return runtime


def build_action(state: dict[str, Any], task_name: str, step: str) -> dict[str, Any]:
    """Build the next host-neutral Batch action without external side effects."""

    sequence = int(state.get("next_action_sequence") or 0) + 1
    state["next_action_sequence"] = sequence
    action: dict[str, Any] = {
        "action_id": f"{state['operation_id']}:{sequence}:{task_name}:{step}",
        "type": step,
        "phase": phase_for_step(step),
        "task": task_name,
        "task_dir": f".cowork-flow/tasks/{task_name}",
    }
    role = RUNTIME_ROLES.get(step)
    if step.startswith("init_") and role:
        action.update(
            {
                "role": role,
                "agent_type": f"cowork-{role}",
                "title": f"{role.capitalize()} Batch task {task_name}",
            }
        )
    if step.startswith("await_") and role:
        runtime = runtime_for(state, task_name, role)
        action.update(
            {
                "role": role,
                "runtime_context_id": runtime["runtime_context_id"],
                "host_context_key": runtime["host_context_key"],
            }
        )
    return action


def advance_state(state: dict[str, Any]) -> bool:
    """Advance Batch state in memory until it needs Host input or is complete."""

    if state.get("phase") in {"completed", "paused"}:
        return False
    if isinstance(state.get("next_action"), dict):
        return False

    changed = False
    completed_tasks = list(state.get("completed_tasks") or [])
    task_steps = dict(state.get("task_steps") or {})
    retry_count = dict(state.get("retry_count") or {})

    for task_name in state["ordered_tasks"]:
        if task_name in completed_tasks:
            continue
        if state.get("current_task") != task_name:
            state["current_task"] = task_name
            changed = True
        completed_steps = list(task_steps.get(task_name) or [])
        for step in BATCH_STEPS:
            if step in completed_steps:
                continue
            action = build_action(state, task_name, step)
            state["next_action"] = action
            state["phase"] = "awaiting_host"
            return True

        completed_tasks.append(task_name)
        state["completed_tasks"] = completed_tasks
        retry_count[task_name] = 0
        state["retry_count"] = retry_count
        state["current_task"] = None
        changed = True

    state["phase"] = "completed"
    state["current_task"] = None
    state["next_action"] = None
    state["pause_reason"] = None
    return True or changed


def mark_step_completed(
    state: dict[str, Any],
    action: dict[str, Any],
    result: dict[str, Any],
) -> None:
    """Record a verified Host action result in the in-memory Batch state."""

    task_name = str(action["task"])
    step = str(action["type"])
    task_steps = dict(state.get("task_steps") or {})
    completed_steps = list(task_steps.get(task_name) or [])
    if step not in completed_steps:
        completed_steps.append(step)
    task_steps[task_name] = completed_steps
    state["task_steps"] = task_steps

    phase = STEP_PHASES.get(step)
    if phase:
        task_phases = dict(state.get("task_phases") or {})
        completed_phases = list(task_phases.get(task_name) or [])
        if phase not in completed_phases:
            completed_phases.append(phase)
        task_phases[task_name] = completed_phases
        state["task_phases"] = task_phases

    if step == "commit_task":
        commits = dict(state.get("commits") or {})
        commits[task_name] = result["commit_id"].strip()
        state["commits"] = commits


def pause_state(
    state: dict[str, Any],
    action: dict[str, Any],
    result: dict[str, Any],
    detail: str,
) -> dict[str, Any]:
    """Move Batch state to paused after a fail-closed Host result."""

    task_name = str(action["task"])
    retry_count = dict(state.get("retry_count") or {})
    retry_count[task_name] = int(retry_count.get(task_name, 0)) + 1
    state["retry_count"] = retry_count
    action_results = dict(state.get("action_results") or {})
    action_results[result["action_id"]] = dict(result)
    state["action_results"] = action_results
    state["phase"] = "paused"
    state["current_task"] = task_name
    state["next_action"] = None
    state["pause_reason"] = f"{task_name}:{action['type']}: {detail}"
    return state
