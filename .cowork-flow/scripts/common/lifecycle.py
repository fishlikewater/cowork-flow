#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Task lifecycle state machine — pure transition logic.

Provides:
    transition_allowed(from_status, to_status) -> bool
    transition_blockers(from_status, to_status) -> list[str]
    get_available_transitions(status) -> list[str]
    is_terminal(status) -> bool
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Transition table
# ---------------------------------------------------------------------------

ALLOWED_TRANSITIONS: set[tuple[str, str]] = {
    ("planning", "in_progress"),
    ("in_progress", "review"),
    ("review", "in_progress"),       # allow round-trip for fixes
    ("review", "completed"),
    ("in_progress", "blocked"),
    ("review", "blocked"),
    ("blocked", "in_progress"),
    ("blocked", "review"),
    ("completed", "archived"),
    ("archived", "completed"),       # allow un-archive
}

# The wildcard "*" scope means any source status can transition to this target
WILDCARD_TRANSITIONS: set[str] = {"blocked"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transition_allowed(from_status: str, to_status: str) -> bool:
    """Check if a transition is allowed."""
    if from_status == to_status:
        return False
    if (from_status, to_status) in ALLOWED_TRANSITIONS:
        return True
    if to_status in WILDCARD_TRANSITIONS:
        return True
    return False


def transition_blockers(from_status: str, to_status: str) -> list[str]:
    """Return a list of blocker messages for an invalid transition.

    Empty list when the transition is allowed.
    """
    if from_status == to_status:
        return [f"Task is already in '{from_status}' state."]
    if not transition_allowed(from_status, to_status):
        available = get_available_transitions(from_status)
        if available:
            return [
                f"Cannot transition from '{from_status}' to '{to_status}'. "
                f"Available: {', '.join(available)}."
            ]
        return [f"Cannot transition from '{from_status}' to '{to_status}'."]
    return []


def get_available_transitions(from_status: str) -> list[str]:
    """Get all valid target statuses from the given status."""
    targets: set[str] = set()
    for src, dst in ALLOWED_TRANSITIONS:
        if src == from_status:
            targets.add(dst)
    # Add wildcard targets
    targets.update(WILDCARD_TRANSITIONS)
    targets.discard(from_status)
    return sorted(targets)


def is_terminal(status: str) -> bool:
    """Check if the status has no outgoing transitions."""
    return len(get_available_transitions(status)) == 0


# ---------------------------------------------------------------------------
# Status metadata
# ---------------------------------------------------------------------------

STATUS_METADATA = {
    "planning": {
        "label": "Planning",
        "description": "Task is being designed and scoped.",
        "icon": "📝",
    },
    "in_progress": {
        "label": "In Progress",
        "description": "Task is being implemented.",
        "icon": "🔨",
    },
    "review": {
        "label": "Review",
        "description": "Task is under review/check.",
        "icon": "🔍",
    },
    "completed": {
        "label": "Completed",
        "description": "Task is done and verified.",
        "icon": "✅",
    },
    "archived": {
        "label": "Archived",
        "description": "Task is archived.",
        "icon": "📦",
    },
    "blocked": {
        "label": "Blocked",
        "description": "Task is blocked awaiting decision.",
        "icon": "🚫",
    },
}


def get_status_label(status: str) -> str:
    meta = STATUS_METADATA.get(status)
    return meta["label"] if meta else status


@dataclass(frozen=True)
class LifecycleResult:
    """Result for DB-backed lifecycle operations."""

    ok: bool
    task_id: str
    from_status: str | None = None
    to_status: str | None = None
    pattern_name: str | None = None
    issues: list[str] | None = None


class TaskLifecycleService:
    """DB-backed task lifecycle service used by the task CLI.

    The service owns Flow task lookup, pattern transition validation, and the
    final status mutation. CLI commands remain responsible for readiness gates,
    output formatting, hooks, and other command-specific side effects.
    """

    def __init__(self, store) -> None:
        self.store = store

    def _context(self, task_id: str):
        from patterns.base import BlockView, TaskContext

        task = self.store.get_task(task_id)
        if task is None:
            return None
        active_block = self.store.get_active_block(task_id)
        block_view = BlockView(**active_block) if active_block else None
        return TaskContext(
            task=task,
            children=self.store.list_children(task_id),
            active_block=block_view,
        )

    def _pattern(self, ctx):
        from patterns.registry import create_registry

        return create_registry().resolve(ctx.task)

    def _transition_issues(self, pattern, ctx, to_status: str) -> list[str]:
        issues = pattern.validate(ctx)
        if not pattern.can_transition(ctx, to_status):
            issues.append(
                f"Pattern '{pattern.name}' does not allow {ctx.task.status} -> {to_status}"
            )
        return issues

    def validate_transition(self, task_id: str, to_status: str, *, validate_current: bool = False) -> LifecycleResult:
        ctx = self._context(task_id)
        if ctx is None:
            return LifecycleResult(False, task_id, issues=[f"Flow task not found: {task_id}"])
        pattern = self._pattern(ctx)
        issues = pattern.validate(ctx) if validate_current else self._transition_issues(pattern, ctx, to_status)
        return LifecycleResult(
            not issues,
            task_id,
            from_status=ctx.task.status,
            to_status=to_status,
            pattern_name=pattern.name,
            issues=issues,
        )

    def transition(self, task_id: str, to_status: str, *, operator: str = "system", reason: str = "", validate_current: bool = False) -> LifecycleResult:
        result = self.validate_transition(task_id, to_status, validate_current=validate_current)
        if not result.ok:
            return result
        if not self.store.update_status(task_id, to_status, operator, reason):
            return LifecycleResult(False, task_id, result.from_status, to_status, result.pattern_name, [f"Flow task not found: {task_id}"])
        return result

    def review(self, task_id: str) -> LifecycleResult:
        return self.transition(task_id, "review", operator="system", reason="task review")

    def complete(self, task_id: str) -> LifecycleResult:
        validation = self.validate_transition(task_id, "completed", validate_current=True)
        if not validation.ok:
            return validation
        return self.transition(task_id, "completed", operator="system", reason="task complete")

    def block(self, task_id: str, reason: str) -> LifecycleResult:
        result = self.validate_transition(task_id, "blocked")
        if not result.ok:
            return result
        if not self.store.block_task(task_id, reason):
            return LifecycleResult(False, task_id, result.from_status, "blocked", result.pattern_name, [f"failed to block task: {task_id}"])
        return result

    def force_unblock(self, task_id: str) -> LifecycleResult:
        task = self.store.get_task(task_id)
        if task is None:
            return LifecycleResult(False, task_id, issues=[f"Flow task not found: {task_id}"])
        if not self.store.update_status(task_id, "in_progress", "manual", "force unblock"):
            return LifecycleResult(False, task_id, task.status, "in_progress", None, [f"failed to unblock task: {task_id}"])
        return LifecycleResult(True, task_id, task.status, "in_progress", None, [])
