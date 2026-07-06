#!/usr/bin/env python3
"""Shared gate result helpers for cowork-flow lifecycle commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GateResult:
    """Normalized result returned by workflow gates."""

    scope: str
    task_dir: Path | None = None
    violations: list[dict] = field(default_factory=list)

    @classmethod
    def from_violations(
        cls,
        scope: str,
        violations: list[dict],
        task_dir: Path | None = None,
    ) -> "GateResult":
        return cls(scope=scope, task_dir=task_dir, violations=list(violations))

    @property
    def blockers(self) -> list[dict]:
        return [
            violation
            for violation in self.violations
            if violation.get("severity") == "block"
        ]

    @property
    def blocked(self) -> bool:
        return bool(self.blockers)

    @property
    def exit_code(self) -> int:
        return 1 if self.blocked else 0


class GateRunner:
    """Run existing validators through a common gate interface."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)

    def run(self, scope: str, task_dir: Path | None = None) -> GateResult:
        from .validate_rules import validate_rules

        normalized_task_dir = Path(task_dir) if task_dir is not None else None
        violations = validate_rules(self.repo_root, scope, normalized_task_dir)
        if scope in {"task_review", "task_complete"}:
            from .validate_coding_standards import validate_coding_standards

            violations.extend(
                validate_coding_standards(self.repo_root, normalized_task_dir)
            )
            from .validate_coding_standards import validate_complexity_signals

            violations.extend(
                validate_complexity_signals(self.repo_root, normalized_task_dir)
            )
        return GateResult.from_violations(scope, violations, normalized_task_dir)

    def log(self, result: GateResult) -> None:
        from .validate_rules import log_violations

        log_violations(result.violations, result.scope, result.task_dir, self.repo_root)
