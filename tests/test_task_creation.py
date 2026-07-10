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
        module = importlib.import_module("application.task_creation")
        cls.TaskCreationRequest = module.TaskCreationRequest
        cls.TaskCreationService = module.TaskCreationService

    def test_create_persists_metadata_and_links_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tasks_dir = root / ".cowork-flow" / "tasks"
            parent_dir = tasks_dir / "07-10-parent"
            parent_dir.mkdir(parents=True)
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
            plan_path = root / "plan.md"
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
            self.assertIn(result.task_dir.name, parent_data["children"])
            self.assertIn("保持创建流程可维护", anchor)
            self.assertTrue((tasks_dir / "archive").is_dir())


if __name__ == "__main__":
    unittest.main()
