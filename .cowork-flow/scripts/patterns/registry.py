"""Registry for resolving task patterns."""

from __future__ import annotations

from .base import Pattern, TaskView
from .generic import Generic


class PatternRegistry:
    def __init__(self) -> None:
        self._patterns: dict[str, Pattern] = {}

    def register(self, pattern: Pattern) -> None:
        self._patterns[pattern.name] = pattern

    def get(self, name: str) -> Pattern | None:
        return self._patterns.get(name)

    def resolve(self, task: TaskView) -> Pattern:
        return self._patterns.get(task.pattern, self._patterns["generic"])


def create_registry() -> PatternRegistry:
    registry = PatternRegistry()
    registry.register(Generic())
    return registry
