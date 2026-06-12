"""Fan-out pattern: one parent waits for generic child tasks."""

from __future__ import annotations

from .base import Action, Pattern, StepKind, TaskContext


class FanOut(Pattern):
    name = "fan_out"
    valid_transitions = {
        "planning": {"in_progress"},
        "in_progress": {"review"},
        "review": {"completed"},
        "completed": {"archived"},
    }

    def validate(self, ctx: TaskContext) -> list[str]:
        issues: list[str] = []
        if not ctx.children:
            issues.append("Fan-out task must have child tasks")
            return issues

        for child in ctx.children:
            if child.pattern != "generic":
                issues.append(f"Child '{child.id}' pattern must be 'generic'")
        return issues

    def next_action(self, ctx: TaskContext) -> Action | None:
        if ctx.task.status != "in_progress":
            return None
        pending = [child.id for child in ctx.children if child.status not in {"completed", "archived"}]
        if pending:
            return Action(
                kind=StepKind.WAIT_CHILDREN,
                description=f"Waiting for {len(pending)} child task(s)",
                task_id=ctx.task.id,
                children=pending,
            )
        return Action(
            kind=StepKind.COMPLETE,
            description="All child tasks finished",
            task_id=ctx.task.id,
        )

    def can_transition(self, ctx: TaskContext, to_status: str) -> bool:
        if not super().can_transition(ctx, to_status):
            return False
        if to_status == "review":
            return all(child.status in {"completed", "archived"} for child in ctx.children)
        return True
