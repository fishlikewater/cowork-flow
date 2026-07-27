from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path

from tests.flow_test_support import FlowScriptTestCase, ROOT, SCRIPTS


class LifecycleRuleRemovalTest(FlowScriptTestCase):
    def test_runtime_rules_registry_assets_are_removed_from_template(self) -> None:
        removed_paths = (
            ROOT / "template" / ".cowork-flow" / "spec" / "runtime" / "rules.json",
            ROOT / "template" / ".cowork-flow" / "spec" / "schemas" / "rules.schema.json",
            SCRIPTS / "common" / "gates" / "validate_rules.py",
            SCRIPTS / "common" / "gates" / "validate_implementation.py",
            SCRIPTS / "common" / "gates" / "validate_coding_standards.py",
            SCRIPTS / "common" / "gates" / "gates.py",
            SCRIPTS / "common" / "gates" / "models.py",
            SCRIPTS / "common" / "gates" / "registry.py",
        )

        self.assertEqual([], [str(path) for path in removed_paths if path.exists()])

    def test_lifecycle_check_result_has_no_gate_pipeline_shape(self) -> None:
        checks = importlib.import_module("common.task.lifecycle_checks")

        result = checks.LifecycleCheckResult(stage="review")

        self.assertFalse(result.blocked)
        self.assertEqual(0, result.exit_code)
        self.assertFalse(hasattr(result, "violations"))
        self.assertFalse(hasattr(result, "executions"))

    def test_lifecycle_check_runner_does_not_read_runtime_rules_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "implement.jsonl").write_text(
                json.dumps({"file": "src/allowed.py", "reason": "planned"}) + "\n",
                encoding="utf-8",
            )
            (root / "src").mkdir()
            (root / "src" / "allowed.py").write_text("VALUE = 1\n", encoding="utf-8")
            self._commit_all(root, "baseline")
            (root / "src" / "allowed.py").write_text("VALUE = 2\n", encoding="utf-8")
            checks = importlib.import_module("common.task.lifecycle_checks")

            result = checks.LifecycleCheckRunner(root).review(
                task_dir,
                allow_spec_file_modifications=True,
            )

        self.assertFalse((root / ".cowork-flow" / "spec" / "runtime" / "rules.json").exists())
        self.assertFalse(result.blocked)
        self.assertEqual((), result.blockers)

    def test_task_review_skill_owns_user_spec_review_contract(self) -> None:
        skill = (ROOT / "template" / "skills" / "task-review" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertIn(".cowork-flow/spec/backend/", skill)
        self.assertIn(".cowork-flow/spec/frontend/", skill)
        self.assertIn(".cowork-flow/spec/guides/", skill)
        self.assertIn("user_spec_review", skill)
        self.assertNotIn("machine_gate_review", skill)
        self.assertNotIn("complexity signals", skill)


if __name__ == "__main__":
    unittest.main()
