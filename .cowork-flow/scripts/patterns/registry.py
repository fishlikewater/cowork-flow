"""Registry for resolving task patterns."""

from __future__ import annotations

from .base import Pattern, TaskView
from .fan_out import FanOut
from .generic import Generic
from .human_loop import HumanLoop
from .pipeline import Pipeline


class PatternRegistry:
    def __init__(self) -> None:
        self._patterns: dict[str, Pattern] = {}

    def register(self, pattern: Pattern) -> None:
        self._patterns[pattern.name] = pattern

    def get(self, name: str) -> Pattern | None:
        return self._patterns.get(name)

    def resolve(self, task: TaskView) -> Pattern:
        return self._patterns.get(task.pattern, self._patterns["generic"])

    def select(self, task: TaskView) -> Pattern:
        if task.children:
            return self._patterns["fan_out"]
        if task.meta.get("stages") is not None:
            return self._patterns["pipeline"]
        if task.meta.get("decision_points") is not None:
            return self._patterns["human_loop"]
        return self._patterns["generic"]


def create_registry() -> PatternRegistry:
    registry = PatternRegistry()
    registry.register(FanOut())
    registry.register(Pipeline())
    registry.register(HumanLoop())
    registry.register(Generic())
    return registry
