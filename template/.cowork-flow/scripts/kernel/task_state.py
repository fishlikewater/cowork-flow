#!/usr/bin/env python3
"""Task lifecycle state transition rules."""

from __future__ import annotations

CHECK_STATUSES = ("review",)
DONE_STATUSES = ("completed", "done")

ALLOWED_TRANSITIONS = {
    ("planning", "in_progress"),
    ("in_progress", "review"),
    ("review", "completed"),
}


def _normalize_status(status: str | None) -> str:
    if isinstance(status, str) and status.strip():
        return status.strip()
    return "unknown"


def transition_blockers(current_status: str | None, target_status: str) -> list[str]:
    """Return blockers for a task status transition."""
    current = _normalize_status(current_status)
    target = _normalize_status(target_status)

    if current == target:
        return []

    if (current, target) in ALLOWED_TRANSITIONS:
        return []

    if target == "completed":
        return [
            f"Task cannot be completed from status '{current}'. "
            "Run `task next <task-dir> --run --intent review` first to enter check phase."
        ]

    if target == "review":
        return [
            f"Task cannot enter review from status '{current}'. "
            "Run `task next <task-dir> --run` and finish implementation first."
        ]

    if target == "in_progress" and current in (*CHECK_STATUSES, *DONE_STATUSES):
        return [
            f"Task cannot return to in_progress from status '{current}'. "
            "Create a follow-up task instead of reopening checked work."
        ]

    return [f"Task transition is not allowed: {current} -> {target}."]


def transition_allowed(current_status: str | None, target_status: str) -> bool:
    """Return whether a task status transition is allowed."""
    return not transition_blockers(current_status, target_status)
