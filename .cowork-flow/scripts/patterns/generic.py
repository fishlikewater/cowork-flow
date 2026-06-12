"""Generic pattern: equivalent to the Phase 1 lifecycle."""

from __future__ import annotations

from .base import Action, Pattern, TaskContext


class Generic(Pattern):
    name = "generic"
    valid_transitions = {
        "planning": {"in_progress"},
        "in_progress": {"blocked", "review"},
        "blocked": {"in_progress"},
        "review": {"completed"},
        "completed": {"archived"},
    }

    def validate(self, ctx: TaskContext) -> list[str]:
        return []

    def next_action(self, ctx: TaskContext) -> Action | None:
        return None
