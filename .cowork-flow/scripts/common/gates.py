#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GateRunner — unified facade for lifecycle quality gates.

Provides:
    GateRunner.run(scope, task_dir) -> GateResult
    GateRunner.check_start(task_dir) -> GateResult
    GateRunner.check_review(task_dir) -> GateResult
    GateRunner.check_complete(task_dir) -> GateResult
"""

from __future__ import annotations

from pathlib import Path

from .quality_gate import GateResult
from .validate_rules import check_scope, format_violations, load_rules


class GateRunner:
    """Unified gate runner — loads rules.json and dispatches by scope.

    Usage:
        runner = GateRunner(repo_root)
        result = runner.run("task_start", task_dir)
        if result.blocked:
            print(format_violations(result.blockers))
    """

    def __init__(self, repo_root: Path):
        self.repo_root = Path(repo_root)
        self._rules: list[dict] | None = None

    @property
    def rules(self) -> list[dict]:
        if self._rules is None:
            self._rules = load_rules(self.repo_root)
        return self._rules

    def run(self, scope: str, task_dir: Path) -> GateResult:
        """Run all rules matching the given scope.

        Args:
            scope: One of "task_start", "task_review", "task_complete", "implement".
            task_dir: Path to the task directory.
        Returns:
            GateResult with structured violations.
        """
        result = GateResult(ok=True, scope=scope)
        violations = check_scope(self.rules, scope, Path(task_dir), self.repo_root)
        for v in violations:
            result.add_violation(
                rule_id=v["rule_id"],
                severity=v.get("severity", "warn"),
                message=v["message"],
                fix_hint=v.get("fix_hint", ""),
                file=v.get("file", ""),
            )
        return result

    def check_start(self, task_dir: Path) -> GateResult:
        """Convenience: run task_start scope gates."""
        return self.run("task_start", task_dir)

    def check_review(self, task_dir: Path) -> GateResult:
        """Convenience: run task_review scope gates."""
        return self.run("task_review", task_dir)

    def check_complete(self, task_dir: Path) -> GateResult:
        """Convenience: run task_complete scope gates."""
        return self.run("task_complete", task_dir)

    def format(self, result: GateResult) -> str:
        """Format a GateResult for human-readable output."""
        return format_violations(result.violations)
