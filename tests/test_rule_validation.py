from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


from tests.flow_test_support import FlowScriptTestCase, ROOT, SCRIPTS


class RuleValidationTest(FlowScriptTestCase):
    def test_validate_rules_accepts_current_task_link_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            child_dir = self._write_l2_task_tree(root)
            self._write_l2_change_fixture(
                root,
                task_link=".cowork-flow/tasks/05-19-child",
            )
            self._write_rules_file(
                root,
                [
                    self._workflow_rule("R-WF-001", "task_start"),
                    self._workflow_rule("R-WF-002", "task_start"),
                    self._workflow_rule("R-WF-003", "task_start"),
                    self._workflow_rule("R-WF-004", "task_start"),
                    self._workflow_rule("R-WF-005", "task_start"),
                ],
            )
            validator = importlib.import_module("common.gates.validate_rules")

            violations = validator.validate_rules(root, "task_start", child_dir)

            self.assertEqual([], violations)

    def test_validate_rules_uses_explicit_utf8_for_rule_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_ready_task_files(root, task_dir)
            task_data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            task_data["status"] = "in_progress"
            (task_dir / "task.json").write_text(
                json.dumps(task_data, ensure_ascii=False),
                encoding="utf-8",
            )
            rule = self._workflow_rule("R-WF-007", "task_complete")
            rule["message"] = "🚦 check gate blocked"
            self._write_rules_file(root, [rule])
            validator = importlib.import_module("common.gates.validate_rules")
            real_open = open

            def strict_text_open(file, mode="r", *args, **kwargs):
                if "b" not in mode and "encoding" not in kwargs:
                    raise AssertionError(f"missing explicit encoding for {file}")
                return real_open(file, mode, *args, **kwargs)

            with patch("builtins.open", side_effect=strict_text_open):
                violations = validator.validate_rules(root, "task_complete", task_dir)
                validator.log_violations(violations, "task_complete", task_dir, root)

            self.assertEqual(["R-WF-007"], [v["rule_id"] for v in violations])

    def test_validate_rules_blocks_missing_runtime_rules_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_ready_task_files(root, task_dir)
            validator = importlib.import_module("common.gates.validate_rules")

            violations = validator.validate_rules(root, "task_review", task_dir)

            self.assertEqual(["RULES-CONFIG-001"], [v["rule_id"] for v in violations])
            self.assertEqual("block", violations[0]["severity"])
            self.assertIn(
                ".cowork-flow/spec/runtime/rules.json",
                violations[0]["file"].replace("\\", "/"),
            )

    def test_validate_rules_blocks_incomplete_runtime_rule_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_ready_task_files(root, task_dir)
            incomplete_rule = self._workflow_rule("R-WF-007", "task_complete")
            incomplete_rule.pop("message")
            self._write_rules_file(root, [incomplete_rule])
            validator = importlib.import_module("common.gates.validate_rules")

            violations = validator.validate_rules(root, "task_complete", task_dir)

            self.assertEqual(["RULES-CONFIG-004"], [v["rule_id"] for v in violations])
            self.assertEqual("block", violations[0]["severity"])
            self.assertIn("message", violations[0]["message"])

    def test_validate_rules_dispatches_by_validator_key_not_rule_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_ready_task_files(root, task_dir)
            task_data = json.loads(
                (task_dir / "task.json").read_text(encoding="utf-8")
            )
            task_data["status"] = "in_progress"
            (task_dir / "task.json").write_text(
                json.dumps(task_data, ensure_ascii=False),
                encoding="utf-8",
            )
            custom_rule = self._workflow_rule("R-WF-999", "task_complete")
            custom_rule["validator"] = "runtime.task_status"
            custom_rule["parameters"] = {"allowed_statuses": ["review"]}
            self._write_rules_file(root, [custom_rule])
            validator = importlib.import_module("common.gates.validate_rules")

            violations = validator.validate_rules(root, "task_complete", task_dir)

            self.assertEqual(["R-WF-999"], [v["rule_id"] for v in violations])

    def test_validate_rules_blocks_unknown_validator_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_ready_task_files(root, task_dir)
            unknown_rule = self._workflow_rule("R-WF-999", "task_review")
            unknown_rule["validator"] = "runtime.missing"
            self._write_rules_file(root, [unknown_rule])
            validator = importlib.import_module("common.gates.validate_rules")

            violations = validator.validate_rules(root, "task_review", task_dir)

            self.assertEqual(["RULES-CONFIG-005"], [v["rule_id"] for v in violations])
            self.assertIn("runtime.missing", violations[0]["message"])

    def test_validate_rules_blocks_invalid_validator_parameters(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_ready_task_files(root, task_dir)
            invalid_rule = self._workflow_rule("R-WF-999", "task_complete")
            invalid_rule["validator"] = "runtime.task_status"
            invalid_rule["parameters"] = {}
            self._write_rules_file(root, [invalid_rule])
            validator = importlib.import_module("common.gates.validate_rules")

            violations = validator.validate_rules(root, "task_complete", task_dir)

            self.assertEqual(["RULES-CONFIG-006"], [v["rule_id"] for v in violations])
            self.assertIn("allowed_statuses", violations[0]["message"])

    def test_rule_scope_contract_includes_task_review(self) -> None:
        for schema_path in (
            ROOT / "template" / ".cowork-flow" / "spec" / "schemas" / "rules.schema.json",
        ):
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            rule_item = schema["properties"]["rules"]["items"]
            required = rule_item["required"]
            scope_enum = rule_item["properties"]["scope"]["enum"]
            source_requirements = rule_item["anyOf"]
            self.assertIn({"required": ["source_anchor"]}, source_requirements)
            self.assertIn({"required": ["source_excerpt"]}, source_requirements)
            self.assertIn("enforcement", required)
            self.assertIn("validator", required)
            self.assertIn("parameters", required)
            self.assertIn("task_review", scope_enum)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_ready_task_files(root, task_dir)
            self._write_rules_file(root, [])
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "common" / "gates" / "validate_rules.py"),
                    "task_review",
                    "--repo-root",
                    str(root),
                    "--task-dir",
                    str(task_dir),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(0, result.returncode, result.stderr)

    def test_gate_runner_wraps_existing_validator_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_ready_task_files(root, task_dir)
            task_data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            task_data["status"] = "in_progress"
            (task_dir / "task.json").write_text(
                json.dumps(task_data, ensure_ascii=False),
                encoding="utf-8",
            )
            self._write_rules_file(root, [self._workflow_rule("R-WF-007", "task_complete")])
            gates = importlib.import_module("common.gates.gates")

            result = gates.GateRunner(root).run("task_complete", task_dir)

            self.assertTrue(result.blocked)
            self.assertEqual(1, result.exit_code)
            runtime_execution = next(
                execution
                for execution in result.executions
                if execution.definition.id == "runtime_rules"
            )
            self.assertEqual(
                ["R-WF-007"],
                [v["rule_id"] for v in runtime_execution.result.violations],
            )

    def test_implementation_gate_uses_runtime_rule_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (task_dir / "decision-anchor.md").write_text("# Demo\n", encoding="utf-8")
            self._write_rules_file(
                root,
                [
                    {
                        **self._workflow_rule("R-AG-002", "all"),
                        "type": "forbidden_action",
                        "enforcement": "validate_implementation",
                        "message": "custom spec mutation block",
                        "fix_hint": "custom fix from runtime rules",
                    }
                ],
            )
            self._commit_all(root, "baseline")
            (root / "AGENTS.md").write_text("# Changed rules\n", encoding="utf-8")
            implementation = importlib.import_module("common.gates.validate_implementation")

            violations = implementation.validate_implementation(root, task_dir)

            self.assertEqual(["R-AG-002"], [v["rule_id"] for v in violations])
            self.assertEqual("custom spec mutation block", violations[0]["message"])
            self.assertEqual("custom fix from runtime rules", violations[0]["fix_hint"])
