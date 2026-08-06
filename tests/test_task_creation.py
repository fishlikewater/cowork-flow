from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = (
    Path(__file__).resolve().parents[1]
    / "template"
    / ".cowork-flow"
    / "scripts"
)
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


class TaskCreationServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        module = importlib.import_module("services.task_creation")
        cls.TaskCreationRequest = module.TaskCreationRequest
        cls.TaskCreationService = module.TaskCreationService
        cls.TaskCreationError = module.TaskCreationError

    def test_create_persists_metadata_and_links_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tasks_dir = root / ".cowork-flow" / "tasks"
            plans_dir = root / ".cowork-flow" / "plans"
            parent_dir = tasks_dir / "07-10-parent"
            parent_dir.mkdir(parents=True)
            plans_dir.mkdir(parents=True)
            (parent_dir / "task.json").write_text(
                json.dumps(
                    {
                        "name": parent_dir.name,
                        "status": "planning",
                        "children": [],
                        "parent": None,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            plan_path = plans_dir / "2026-07-10-demo-task.md"
            plan_path.write_text(
                "**目标:** 保持创建流程可维护\n",
                encoding="utf-8",
            )

            result = self.TaskCreationService(root).create(
                self.TaskCreationRequest(
                    title="创建任务",
                    slug="demo-task",
                    assignee="codex",
                    priority="P2",
                    parent=parent_dir.name,
                    from_plan=plan_path,
                    created_at="2026-07-10",
                    date_prefix="07-10",
                )
            )

            task_data = json.loads(
                (result.task_dir / "task.json").read_text(
                    encoding="utf-8"
                )
            )
            parent_data = json.loads(
                (parent_dir / "task.json").read_text(
                    encoding="utf-8"
                )
            )
            anchor = (result.task_dir / "decision-anchor.md").read_text(
                encoding="utf-8"
            )

            self.assertEqual("planning", task_data["status"])
            self.assertEqual(parent_dir.name, task_data["parent"])
            self.assertEqual(
                ".cowork-flow/plans/2026-07-10-demo-task.md",
                task_data["meta"]["planFile"],
            )
            self.assertIn(result.task_dir.name, parent_data["children"])
            self.assertIn("保持创建流程可维护", anchor)
            self.assertTrue((tasks_dir / "archive").is_dir())

    def test_create_without_from_plan_leaves_plan_unbound(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            result = self.TaskCreationService(root).create(
                self.TaskCreationRequest(
                    title="无计划任务",
                    slug="no-plan-task",
                    assignee="codex",
                    priority="P2",
                    created_at="2026-07-10",
                    date_prefix="07-10",
                )
            )

            task_data = json.loads(
                (result.task_dir / "task.json").read_text(encoding="utf-8")
            )
            self.assertEqual({}, task_data["meta"])
            self.assertNotIn("planFile", task_data["meta"])


    def test_create_from_noncanonical_plan_path_uses_shared_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plan_path = root / ".cowork-flow" / "plans" / "demo.md"
            plan_path.parent.mkdir(parents=True)
            plan_path.write_text("**Goal:** Demo\n", encoding="utf-8")

            with self.assertRaises(self.TaskCreationError) as raised:
                self.TaskCreationService(root).create(
                    self.TaskCreationRequest(
                        title="Noncanonical plan",
                        slug="bad-plan",
                        assignee="codex",
                        priority="P2",
                        from_plan=".cowork-flow/plans/../plans/demo.md",
                        created_at="2026-07-10",
                        date_prefix="07-10",
                    )
                )

            self.assertEqual("TASK-CREATE-PLAN-005", raised.exception.code)
            self.assertFalse(
                (root / ".cowork-flow" / "tasks" / "07-10-bad-plan").exists()
            )

    def test_create_from_missing_plan_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            missing_plan = root / ".cowork-flow" / "plans" / "missing.md"

            with self.assertRaisesRegex(
                self.TaskCreationError,
                "plan file does not exist",
            ):
                self.TaskCreationService(root).create(
                    self.TaskCreationRequest(
                        title="缺失计划",
                        slug="missing-plan",
                        assignee="codex",
                        priority="P2",
                        from_plan=missing_plan,
                        created_at="2026-07-10",
                        date_prefix="07-10",
                    )
                )

            self.assertFalse(
                (root / ".cowork-flow" / "tasks" / "07-10-missing-plan").exists()
            )


if __name__ == "__main__":
    unittest.main()
