"""Base contracts for Flow task patterns."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class StepKind(str, Enum):
    """Pattern next-action kinds."""

    START = "start"
    DISPATCH = "dispatch"
    WAIT_CHILDREN = "wait_children"
    HUMAN_DECISION = "human_decision"
    REVIEW = "review"
    COMPLETE = "complete"
    ARCHIVE = "archive"


@dataclass
class TaskView:
    id: str
    artifact_dir: str
    title: str
    status: str
    pattern: str
    priority: str
    creator: str
    assignee: str
    parent_id: str | None
    children: list[str]
    meta: dict
    block_reason: str | None


@dataclass
class BlockView:
    id: int
    task_id: str
    reason: str
    blocked_at: str
    decision: str | None
    decided_by: str | None
    resolved_at: str | None


@dataclass
class TaskContext:
    task: TaskView
    children: list[TaskView]
    active_block: BlockView | None


@dataclass
class Action:
    kind: StepKind
    description: str
    task_id: str
    children: list[str] = field(default_factory=list)


class Pattern(ABC):
    """Base class for pure task pattern decisions."""

    name: str = ""
    valid_transitions: dict[str, set[str]] = {}

    @abstractmethod
    def validate(self, ctx: TaskContext) -> list[str]:
        """Return validation errors for the current task context."""

    @abstractmethod
    def next_action(self, ctx: TaskContext) -> Action | None:
        """Return the next recommended action without mutating state."""

    def transition_allowed(self, from_status: str, to_status: str) -> bool:
        """Fast status-transition whitelist check."""
        return to_status in self.valid_transitions.get(from_status, set())

    def can_transition(self, ctx: TaskContext, to_status: str) -> bool:
        """Conditional transition gate. Subclasses may add constraints."""
        return self.transition_allowed(ctx.task.status, to_status)
