#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for rules engine (gates.py + validate_rules.py)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".cowork-flow" / "scripts"
sys.path.insert(0, str(SCRIPTS))


class TestLoadRules(unittest.TestCase):
    """Tests for validate_rules.load_rules."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rules_test_"))
        self.addCleanup(self._cleanup)
        (self.tmp / ".cowork-flow").mkdir()
        (self.tmp / ".cowork-flow" / "spec").mkdir()
        (self.tmp / ".cowork-flow" / "spec" / "runtime").mkdir(parents=True)

    def _cleanup(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_rules(self, rules: list):
        data = {"schemaVersion": 1, "rules": rules}
        path = self.tmp / ".cowork-flow" / "spec" / "runtime" / "rules.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_load_valid_rules(self):
        from common import validate_rules
        rule = {
            "id": "R-WF-001", "type": "phase_gate", "severity": "block",
            "scope": "task_start", "condition": "test", "message": "blocked",
            "fix_hint": "fix it", "source_file": "test.md",
            "source_excerpt": "excerpt", "enforcement": "validate_rules",
        }
        self._write_rules([rule])
        result = validate_rules.load_rules(self.tmp)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "R-WF-001")

    def test_load_skips_invalid_rule(self):
        from common import validate_rules
        rules = [
            {
                "id": "BAD", "type": "phase_gate", "severity": "block",
                "scope": "task_start", "condition": "test", "message": "msg",
                "fix_hint": "fix", "source_file": "f.md",
                "source_excerpt": "x", "enforcement": "validate_rules",
            },
            {
                "id": "R-WF-002", "type": "forbidden_action", "severity": "warn",
                "scope": "all", "condition": "test", "message": "warned",
                "fix_hint": "fix", "source_file": "f.md",
                "source_excerpt": "x", "enforcement": "host_contract",
            },
        ]
        self._write_rules(rules)
        result = validate_rules.load_rules(self.tmp)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "R-WF-002")

    def test_load_missing_file_returns_empty(self):
        from common import validate_rules
        result = validate_rules.load_rules(self.tmp)
        self.assertEqual(result, [])

    def test_load_broken_json_returns_empty(self):
        from common import validate_rules
        path = self.tmp / ".cowork-flow" / "spec" / "runtime" / "rules.json"
        path.write_text("{broken", encoding="utf-8")
        result = validate_rules.load_rules(self.tmp)
        self.assertEqual(result, [])


class TestGateResult(unittest.TestCase):
    """Tests for quality_gate.GateResult enhancement."""

    def test_default_ok(self):
        from common.quality_gate import GateResult
        r = GateResult(ok=True)
        self.assertTrue(r.ok)
        self.assertFalse(r.blocked)
        self.assertEqual(r.exit_code, 0)
        self.assertEqual(r.blockers, [])

    def test_add_blocker_violation(self):
        from common.quality_gate import GateResult
        r = GateResult(ok=True)
        r.add_violation("R-WF-001", "block", "missing proposal", "create it")
        self.assertFalse(r.ok)
        self.assertTrue(r.blocked)
        self.assertEqual(r.exit_code, 1)
        self.assertEqual(len(r.blockers), 1)
        self.assertEqual(r.blockers[0]["rule_id"], "R-WF-001")

    def test_add_warn_violation(self):
        from common.quality_gate import GateResult
        r = GateResult(ok=True)
        r.add_violation("R-AG-005", "warn", "abstraction", "keep simple")
        self.assertTrue(r.ok)  # warn doesn't set ok=False
        self.assertFalse(r.blocked)
        self.assertEqual(r.exit_code, 0)


class TestCheckScope(unittest.TestCase):
    """Tests for validate_rules.check_scope."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="scope_test_"))
        self.addCleanup(self._cleanup)
        (self.tmp / ".cowork-flow").mkdir()
        (self.tmp / ".cowork-flow" / "changes").mkdir(parents=True)
        (self.tmp / ".cowork-flow" / "spec").mkdir()
        (self.tmp / ".cowork-flow" / "spec" / "runtime").mkdir(parents=True)

    def _cleanup(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_check_scope_skips_non_matching(self):
        from common import validate_rules
        rule = {
            "id": "R-WF-001", "type": "phase_gate", "severity": "block",
            "scope": "task_start", "condition": "test", "message": "msg",
            "fix_hint": "fix", "source_file": "f.md",
            "source_excerpt": "x", "enforcement": "validate_rules",
        }
        result = validate_rules.check_scope([rule], "task_complete", self.tmp / "task", self.tmp)
        self.assertEqual(result, [])

    def test_r_wf_008_missing_prd(self):
        from common import validate_rules
        rule = {
            "id": "R-WF-008", "type": "phase_gate", "severity": "block",
            "scope": "task_start", "condition": "prd required", "message": "prd missing",
            "fix_hint": "add prd.md", "source_file": "task.py",
            "source_excerpt": "prd check", "enforcement": "validate_rules",
        }
        task_dir = self.tmp / "06-20-test-task"
        task_dir.mkdir()
        result = validate_rules.check_scope([rule], "task_start", task_dir, self.tmp)
        self.assertTrue(len(result) > 0)
        self.assertEqual(result[0]["rule_id"], "R-WF-008")

    def test_r_wf_008_with_prd_and_jsonl(self):
        from common import validate_rules
        rule = {
            "id": "R-WF-008", "type": "phase_gate", "severity": "block",
            "scope": "task_start", "condition": "prd required", "message": "prd missing",
            "fix_hint": "add prd.md", "source_file": "task.py",
            "source_excerpt": "prd check", "enforcement": "validate_rules",
        }
        task_dir = self.tmp / "06-20-test-task"
        task_dir.mkdir()
        (task_dir / "prd.md").write_text("Plan required task", encoding="utf-8")
        (task_dir / "implement.jsonl").write_text("{}\n", encoding="utf-8")
        result = validate_rules.check_scope([rule], "task_start", task_dir, self.tmp)
        self.assertEqual(result, [])

    def test_r_wf_007_no_review_evidence(self):
        from common import validate_rules
        rule = {
            "id": "R-WF-007", "type": "phase_gate", "severity": "block",
            "scope": "task_complete", "condition": "review evidence",
            "message": "no review", "fix_hint": "review first",
            "source_file": "f.md", "source_excerpt": "x",
            "enforcement": "validate_rules",
        }
        task_dir = self.tmp / "06-20-test-task"
        task_dir.mkdir()
        (task_dir / "prd.md").write_text("Task", encoding="utf-8")
        result = validate_rules.check_scope([rule], "task_complete", task_dir, self.tmp)
        self.assertTrue(len(result) > 0)
        self.assertEqual(result[0]["rule_id"], "R-WF-007")


if __name__ == "__main__":
    raise SystemExit(unittest.main())
