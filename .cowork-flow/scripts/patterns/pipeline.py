"""Pipeline pattern: staged review and rework."""

from __future__ import annotations

from .base import Action, Pattern, StepKind, TaskContext


class Pipeline(Pattern):
    name = "pipeline"
    valid_transitions = {
        "planning": {"in_progress"},
        "in_progress": {"review"},
        "review": {"in_progress", "completed"},
        "completed": {"archived"},
    }

    def _stages(self, ctx: TaskContext) -> list[dict]:
        stages = ctx.task.meta.get("stages")
        return stages if isinstance(stages, list) else []

    def _current_stage(self, ctx: TaskContext) -> int:
        value = ctx.task.meta.get("current_stage", 0)
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def validate(self, ctx: TaskContext) -> list[str]:
        stages = self._stages(ctx)
        if not stages:
            return ["Pipeline task must define stages"]
        if self._current_stage(ctx) < 0:
            return ["Pipeline task current_stage must be non-negative"]
        return []

    def next_action(self, ctx: TaskContext) -> Action | None:
        stages = self._stages(ctx)
        if not stages:
            return None

        current = self._current_stage(ctx)
        if ctx.task.status == "in_progress" and current < len(stages):
            stage = stages[current] if isinstance(stages[current], dict) else {}
            name = str(stage.get("name", f"stage {current + 1}"))
            return Action(
                kind=StepKind.REVIEW,
                description=f"Review stage {current + 1}/{len(stages)}: {name}",
                task_id=ctx.task.id,
            )
        if ctx.task.status == "review" and current < len(stages):
            stage = stages[current] if isinstance(stages[current], dict) else {}
            name = str(stage.get("name", f"stage {current + 1}"))
            return Action(
                kind=StepKind.DISPATCH,
                description=f"Redo stage {current + 1}/{len(stages)}: {name}",
                task_id=ctx.task.id,
            )
        if ctx.task.status == "review" and current >= len(stages):
            return Action(
                kind=StepKind.COMPLETE,
                description="Pipeline stages complete",
                task_id=ctx.task.id,
            )
        return None

    def can_transition(self, ctx: TaskContext, to_status: str) -> bool:
        if not super().can_transition(ctx, to_status):
            return False
        if to_status == "completed":
            return self._current_stage(ctx) >= len(self._stages(ctx))
        return True
