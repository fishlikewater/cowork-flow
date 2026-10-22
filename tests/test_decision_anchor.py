from __future__ import annotations

import importlib
import re
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"


class DecisionAnchorDriftPreventionTest(unittest.TestCase):
    """Regression tests for decision-anchor drift prevention mechanism."""

    def setUp(self) -> None:
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
            self.addCleanup(sys.path.remove, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        self.policy = importlib.import_module("services.lifecycle_policy")

    def _cleanup_imports(self) -> None:
        for module_name in (
            "services.lifecycle_policy",
            "services.task_context",
            "services.plan_binding",
            "services.readiness",
        ):
            if module_name in sys.modules:
                del sys.modules[module_name]

    def test_task_start_keeps_prd_as_blocked_non_anchor_input(self) -> None:
        """正式版不迁移 prd.md，缺少 decision-anchor.md 时保持 blocker。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text("{}", encoding="utf-8")
            (task_dir / "prd.md").write_text("# Legacy PRD\n## Goal\nTest\n", encoding="utf-8")

            failure = self.policy.start_readiness_failure(root, task_dir)
            blockers = list(failure.blockers)

            self.assertTrue((task_dir / "prd.md").is_file())
            self.assertFalse((task_dir / "decision-anchor.md").exists())
            self.assertIn("decision-anchor.md is missing or empty", blockers)
            self.assertEqual(["decision-anchor.md is missing or empty"], blockers[:1])
            self.assertEqual(
                "# Legacy PRD\n## Goal\nTest\n",
                (task_dir / "prd.md").read_text(encoding="utf-8"),
            )

    def test_task_start_blockers_missing_anchor_and_no_legacy(self) -> None:
        """没有 prd.md 也没有 decision-anchor.md 时报 missing。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text("{}", encoding="utf-8")

            failure = self.policy.start_readiness_failure(root, task_dir)
            blockers = list(failure.blockers)
            self.assertIn("decision-anchor.md is missing or empty", blockers)
            self.assertEqual(["decision-anchor.md is missing or empty"], blockers[:1])
            self.assertEqual("TASK-START-001", failure.code)




class DecisionAnchorSchemaTest(unittest.TestCase):
    """Validate decision-anchor.md schema structure."""

    def test_anchor_spec_no_related_files_section(self) -> None:
        """decision-anchor schema 不应包含废弃章节或自动迁移承诺。"""
        anchor_paths = (
            SCRIPTS / ".." / ".." / "spec" / "contracts" / "decision-anchor.md",
            ROOT / "template" / ".cowork-flow" / "spec" / "contracts" / "decision-anchor.md",
            ROOT
            / "presets"
            / "zcode"
            / ".cowork-flow"
            / "spec"
            / "contracts"
            / "decision-anchor.md",
        )
        for anchor_path in anchor_paths:
            if not anchor_path.exists():
                continue
            content = anchor_path.read_text(encoding="utf-8")
            self.assertIn("## 目标", content)
            self.assertIn("## 验收标准", content)
            self.assertNotIn("## 相关文件", content)
            self.assertNotIn("自动搬运", content)
            self.assertNotIn("删除 `prd.md`", content)
            self.assertIn("The formal release does not auto-migrate a legacy `prd.md`", content)
            self.assertIn("fail-closed", content)
            self.assertEqual(
                [["目标", "验收标准", "被拒方案", "关键假设", "范围边界", "验证命令"]],
                [
                    re.findall(r"^## (\S+)$", block, re.MULTILINE)
                    for block in re.findall(r"```markdown\n(.*?)```", content, re.DOTALL)
                ],
            )


    def test_english_anchor_contract_keeps_the_machine_rules(self) -> None:
        path = (
            ROOT
            / "template"
            / "locales"
            / "en-US"
            / ".cowork-flow"
            / "spec"
            / "contracts"
            / "decision-anchor.md"
        )
        content = path.read_text(encoding="utf-8")

        self.assertIn("## Acceptance Criteria", content)
        self.assertIn("## Verification Commands", content)
        self.assertIn("LIFECYCLE-REVIEW-003", content)
        self.assertIn("The formal release does not auto-migrate a legacy `prd.md`", content)
        self.assertEqual(
            [["Goal", "Acceptance Criteria", "Rejected Options", "Key Assumptions",
              "Scope Boundary", "Verification Commands"]],
            [
                re.findall(r"^## (.+)$", block, re.MULTILINE)
                for block in re.findall(r"```markdown\n(.*?)```", content, re.DOTALL)
            ],
        )


if __name__ == "__main__":
    unittest.main()
