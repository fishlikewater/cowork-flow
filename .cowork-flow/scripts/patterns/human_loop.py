"""Human-loop pattern: explicit human decision blocking."""

from __future__ import annotations

from .base import Action, Pattern, StepKind, TaskContext


class HumanLoop(Pattern):
    name = "human_loop"
    valid_transitions = {
        "planning": {"in_progress"},
        "in_progress": {"blocked", "review"},
        "blocked": {"in_progress"},
        "review": {"completed"},
        "completed": {"archived"},
    }

    def _decision_points(self, ctx: TaskContext) -> list[dict]:
        points = ctx.task.meta.get("decision_points")
        return points if isinstance(points, list) else []

    def _current_decision(self, ctx: TaskContext) -> int:
        value = ctx.task.meta.get("current_decision", 0)
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def validate(self, ctx: TaskContext) -> list[str]:
        if not self._decision_points(ctx):
            return ["Human-loop task must define decision_points"]
        return []

    def next_action(self, ctx: TaskContext) -> Action | None:
        points = self._decision_points(ctx)
        if not points:
            return None

        if ctx.task.status == "blocked":
            current = min(self._current_decision(ctx), len(points) - 1)
            point = points[current] if isinstance(points[current], dict) else {}
            question = str(point.get("question", "Human decision required"))
            return Action(
                kind=StepKind.HUMAN_DECISION,
                description=question,
                task_id=ctx.task.id,
            )
        return None

    def can_transition(self, ctx: TaskContext, to_status: str) -> bool:
        if not super().can_transition(ctx, to_status):
            return False
        if to_status == "in_progress" and ctx.task.status == "blocked":
            return bool(ctx.active_block and ctx.active_block.decision)
        return True
