from __future__ import annotations

import contextlib
import importlib
import io
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


    def test_create_with_full_date_slug_normalizes_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            result = self.TaskCreationService(root).create(
                self.TaskCreationRequest(
                    title="完整日期前缀",
                    slug="2026-08-13-demo",
                    assignee="codex",
                    priority="P2",
                    created_at="2026-08-13",
                )
            )

            task_data = json.loads(
                (result.task_dir / "task.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual("08-13-demo", result.task_dir.name)
            self.assertEqual("08-13-demo", task_data["id"])
            self.assertEqual("08-13-demo", task_data["name"])

    def test_create_refuses_to_overwrite_existing_task_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo-task"
            task_dir.mkdir(parents=True)
            task_json = task_dir / "task.json"
            original = {
                "id": task_dir.name,
                "name": task_dir.name,
                "title": "原始任务",
                "status": "in_progress",
                "parent": "07-10-parent",
                "children": ["07-10-child"],
                "meta": {"keep": "原值"},
                "createdAt": "2026-07-01",
            }
            task_json.write_text(
                json.dumps(original, ensure_ascii=False),
                encoding="utf-8",
            )

            with self.assertRaises(self.TaskCreationError) as raised:
                self.TaskCreationService(root).create(
                    self.TaskCreationRequest(
                        title="新请求",
                        slug="demo-task",
                        assignee="other",
                        priority="P0",
                        created_at="2026-07-10",
                        date_prefix="07-10",
                    )
                )

            self.assertEqual("TASK-CREATE-EXISTS-001", raised.exception.code)
            self.assertEqual(
                original,
                json.loads(task_json.read_text(encoding="utf-8")),
            )

    def test_create_refuses_an_existing_task_directory_without_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo-task"
            task_dir.mkdir(parents=True)
            local_file = task_dir / "notes.txt"
            local_file.write_text("local content\n", encoding="utf-8")

            with self.assertRaises(self.TaskCreationError) as raised:
                self.TaskCreationService(root).create(
                    self.TaskCreationRequest(
                        title="新请求",
                        slug="demo-task",
                        assignee="other",
                        priority="P0",
                        date_prefix="07-10",
                    )
                )

            self.assertEqual("TASK-CREATE-EXISTS-001", raised.exception.code)
            self.assertFalse((task_dir / "task.json").exists())
            self.assertEqual(
                "local content\n",
                local_file.read_text(encoding="utf-8"),
            )

    def test_create_rolls_back_when_parent_link_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tasks_dir = root / ".cowork-flow" / "tasks"
            parent_dir = tasks_dir / "07-10-parent"
            parent_dir.mkdir(parents=True)
            (parent_dir / "task.json").write_text("{broken", encoding="utf-8")

            with self.assertRaises(self.TaskCreationError) as raised:
                self.TaskCreationService(root).create(
                    self.TaskCreationRequest(
                        title="子任务",
                        slug="child",
                        assignee="codex",
                        priority="P1",
                        parent=parent_dir.name,
                        date_prefix="07-10",
                    )
                )

            self.assertEqual("TASK-CREATE-LINK-001", raised.exception.code)
            child_dir = tasks_dir / "07-10-child"
            self.assertFalse((child_dir / "task.json").exists())
            self.assertFalse(child_dir.exists())

            retried = self.TaskCreationService(root).create(
                self.TaskCreationRequest(
                    title="子任务",
                    slug="child",
                    assignee="codex",
                    priority="P1",
                    date_prefix="07-10",
                )
            )
            self.assertTrue((retried.task_dir / "task.json").is_file())

    def test_read_json_file_preserves_corrupt_file_and_reports_diagnostic(self) -> None:
        files = importlib.import_module("infra.files")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "task.json"
            path.write_text("{broken", encoding="utf-8")
            stderr = io.StringIO()

            with contextlib.redirect_stderr(stderr):
                result = files.read_json_file(path)

            self.assertIsNone(result)
            self.assertEqual("{broken", path.read_text(encoding="utf-8"))
            self.assertIn(f"Corrupt JSON preserved: {path}", stderr.getvalue())

    def test_read_json_file_preserves_invalid_utf8_and_reports_diagnostic(self) -> None:
        files = importlib.import_module("infra.files")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "task.json"
            path.write_bytes(b"{\xff\xfe")
            stderr = io.StringIO()

            with contextlib.redirect_stderr(stderr):
                result = files.read_json_file(path)

            self.assertIsNone(result)
            self.assertEqual(b"{\xff\xfe", path.read_bytes())
            self.assertIn(f"Corrupt JSON preserved: {path}", stderr.getvalue())

    def test_context_query_preserves_corrupt_task_json(self) -> None:
        git_context = importlib.import_module("adapters.git.git_context")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_json = root / ".cowork-flow" / "tasks" / "07-10-demo" / "task.json"
            task_json.parent.mkdir(parents=True)
            task_json.write_text("{broken", encoding="utf-8")

            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                context = git_context.get_context_json(root)

            self.assertTrue(task_json.is_file())
            self.assertIn("Corrupt JSON preserved", stderr.getvalue())
            self.assertEqual([], context["tasks"]["active"])

    def test_create_sets_id_and_name_to_directory_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            result = self.TaskCreationService(root).create(
                self.TaskCreationRequest(
                    title="裸名同源",
                    slug="demo-task",
                    assignee="codex",
                    priority="P2",
                    created_at="2026-07-10",
                    date_prefix="07-10",
                )
            )

            task_data = json.loads(
                (result.task_dir / "task.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual("07-10-demo-task", result.task_dir.name)
            self.assertEqual(result.task_dir.name, task_data["id"])
            self.assertEqual(result.task_dir.name, task_data["name"])


if __name__ == "__main__":
    unittest.main()
