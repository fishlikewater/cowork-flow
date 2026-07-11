#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration tests for rules engine with real task directories.

Tests the full flow: create task → run gates → verify blocking/warnings.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Insert BOTH the root-level and template-level scripts dirs so `common.*` resolves.
# When cowork-flow installs into a project, scripts live at `.cowork-flow/scripts/`.
for p in [
    str(ROOT / ".cowork-flow" / "scripts"),
    str(ROOT / "template" / ".cowork-flow" / "scripts"),
]:
    if p not in sys.path:
        sys.path.insert(0, p)

from common.gates import GateRunner
from common.quality_gate import GateResult


class TestGateRunnerIntegration(unittest.TestCase):
    """Integration tests for GateRunner with real file system."""

    def setUp(self):
        from tests.integration.conftest import TempRepo
        self.repo = TempRepo()
        self.addCleanup(self.repo.cleanup)
        self.runner = GateRunner(self.repo.repo_root)

    def test_rules_loaded(self):
        """rules.json should be loaded from spec/runtime/."""
        self.assertTrue(len(self.runner.rules) > 0)
        rule_ids = [r["id"] for r in self.runner.rules]
        self.assertIn("R-WF-001", rule_ids)
        self.assertIn("R-WF-008", rule_ids)

    def test_clean_task_passes_start(self):
        """A task with prd.md + jsonl should pass task_start gates."""
        task_dir = self.repo.create_task_dir(
            "06-26-clean-task",
            prd_content="Implement feature X with acceptance criteria:\n- AC-001: works correctly",
        )
        (task_dir / "implement.jsonl").write_text(
            '{"type":"step","description":"initial setup"}\n', encoding="utf-8"
        )
        result = self.runner.check_start(task_dir)
        self.assertFalse(result.blocked, f"Unexpected blockers: {result.blockers}")

    def test_missing_prd_blocks_start(self):
        """A task without prd.md should fail task_start gates."""
        import tempfile
        task_dir = self.repo.repo_root / ".cowork-flow" / "tasks" / "06-26-bad-task"
        task_dir.mkdir(parents=True)
        (task_dir / "implement.jsonl").write_text("{}\n", encoding="utf-8")
        result = self.runner.check_start(task_dir)
        self.assertTrue(result.blocked)
        rule_ids = [b["rule_id"] for b in result.blockers]
        self.assertIn("R-WF-008", rule_ids)

    def test_missing_jsonl_blocks_start(self):
        """A task with prd.md but no jsonl files should fail."""
        task_dir = self.repo.create_task_dir(
            "06-26-no-jsonl", prd_content="Task with no jsonl"
        )
        result = self.runner.check_start(task_dir)
        self.assertTrue(result.blocked)
        rule_ids = [b["rule_id"] for b in result.blockers]
        self.assertIn("R-WF-008", rule_ids)

    def test_review_evidence_required(self):
        """task_complete should block when no review evidence exists."""
        task_dir = self.repo.create_task_dir(
            "06-26-review-test", prd_content="Task for review test"
        )
        result = self.runner.check_complete(task_dir)
        self.assertTrue(result.blocked)
        rule_ids = [b["rule_id"] for b in result.blockers]
        self.assertIn("R-WF-007", rule_ids)

    def test_review_evidence_present_passes(self):
        """task_complete with check.jsonl should pass R-WF-007."""
        task_dir = self.repo.create_task_dir(
            "06-26-review-ok", prd_content="Task with review"
        )
        (task_dir / "check.jsonl").write_text(
            '{"type":"check","result":"pass"}\n', encoding="utf-8"
        )
        result = self.runner.check_complete(task_dir)
        rule_ids = [b["rule_id"] for b in result.blockers]
        self.assertNotIn("R-WF-007", rule_ids)


class TestGateResultProperties(unittest.TestCase):
    """Test GateResult.blocked and exit_code properties."""

    def test_ok_result_not_blocked(self):
        r = GateResult(ok=True)
        self.assertFalse(r.blocked)
        self.assertEqual(r.exit_code, 0)

    def test_add_blocker_blocked(self):
        r = GateResult(ok=True)
        r.add_violation("R-TEST", "block", "blocked", "fix it")
        self.assertTrue(r.blocked)
        self.assertEqual(r.exit_code, 1)

    def test_warn_does_not_block(self):
        r = GateResult(ok=True)
        r.add_violation("R-TEST", "warn", "warning", "consider")
        self.assertFalse(r.blocked)
        self.assertEqual(r.exit_code, 0)


class TestViolationsFormatting(unittest.TestCase):
    """Test validate_rules.format_violations."""

    def test_empty_violations(self):
        from common.validate_rules import format_violations
        self.assertEqual(format_violations([]), "")

    def test_blocker_formatted(self):
        from common.validate_rules import format_violations
        violations = [{"rule_id": "R-WF-001", "severity": "block", "message": "missing", "fix_hint": "create it", "file": ""}]
        output = format_violations(violations)
        self.assertIn("[BLOCK]", output)
        self.assertIn("R-WF-001", output)
        self.assertIn("create it", output)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
