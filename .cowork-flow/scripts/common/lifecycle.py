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
