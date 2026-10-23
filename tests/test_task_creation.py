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
ROOT = Path(__file__).resolve().parents[1]
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
            self.assertNotIn("planFile", task_data["meta"])
            self.assertEqual("strict", task_data["meta"]["gateProfile"])
            anchor = (result.task_dir / "decision-anchor.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("## 目标", anchor)
            self.assertIn("## 验收标准", anchor)
            self.assertIn("## 验证命令", anchor)
            self.assertIn("规范核对：", anchor)
            self.assertIn("<dev_type>", anchor)
            self.assertIn("<!--", anchor)
            self.assertTrue(result.generated_anchor)
            self.assertFalse(result.generated_anchor_from_plan)

    def test_create_with_english_config_and_plan_uses_english_headings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow = root / ".cowork-flow"
            plans_dir = workflow / "plans"
            plans_dir.mkdir(parents=True)
            (workflow / "config.yaml").write_text(
                'language: "en-US"\n', encoding="utf-8"
            )
            plan_path = plans_dir / "english-plan.md"
            plan_path.write_text("**Goal:** Ship the English path\n", encoding="utf-8")

            result = self.TaskCreationService(root).create(
                self.TaskCreationRequest(
                    title="English task",
                    slug="english-task",
                    assignee="codex",
                    priority="P2",
                    from_plan=plan_path,
                    created_at="2026-07-10",
                    date_prefix="07-10",
                )
            )

            anchor = (result.task_dir / "decision-anchor.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("## Goal", anchor)
            self.assertIn("## Acceptance Criteria", anchor)
            self.assertIn("## Verification Commands", anchor)
            self.assertIn("Spec check:", anchor)
            self.assertIn("Ship the English path", anchor)
            self.assertNotIn("## 目标", anchor)
            self.assertNotIn("## 验证命令", anchor)
            self.assertTrue(result.generated_anchor)
            self.assertTrue(result.generated_anchor_from_plan)

    def test_create_extracts_goal_from_legacy_table_row(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plans_dir = root / ".cowork-flow" / "plans"
            plans_dir.mkdir(parents=True)
            plan_path = plans_dir / "table-plan.md"
            plan_path.write_text(
                "| Field | Content |\n| --- | --- |\n"
                "| **Goal** | Table goal |\n",
                encoding="utf-8",
            )

            result = self.TaskCreationService(root).create(
                self.TaskCreationRequest(
                    title="Table task",
                    slug="table-task",
                    assignee="codex",
                    priority="P2",
                    from_plan=plan_path,
                    created_at="2026-07-10",
                    date_prefix="07-10",
                )
            )

            anchor = (result.task_dir / "decision-anchor.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("Table goal", anchor)
            self.assertTrue(result.generated_anchor_from_plan)

    def test_create_does_not_overwrite_an_existing_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plans_dir = root / ".cowork-flow" / "plans"
            plans_dir.mkdir(parents=True)
            plan_path = plans_dir / "plan.md"
            plan_path.write_text("**Goal:** New goal\n", encoding="utf-8")
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-existing-anchor"
            task_dir.mkdir(parents=True)
            existing = "## 目标\n\n手写内容\n\n## 验收标准\n\n- [ ] AC-001: keep\n"
            (task_dir / "decision-anchor.md").write_text(existing, encoding="utf-8")

            created, from_plan = self.TaskCreationService(root)._generate_anchor(
                task_dir, plan_path
            )

            self.assertFalse(created)
            self.assertFalse(from_plan)
            self.assertEqual(
                existing,
                (task_dir / "decision-anchor.md").read_text(encoding="utf-8"),
            )

    def test_anchor_scaffold_uses_dev_type_or_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plans_dir = root / ".cowork-flow" / "plans"
            plans_dir.mkdir(parents=True)
            plan_path = plans_dir / "plan.md"
            plan_path.write_text("**目标:** 演示\n", encoding="utf-8")

            typed = self.TaskCreationService(root).create(
                self.TaskCreationRequest(
                    title="后端任务",
                    slug="typed-task",
                    assignee="codex",
                    priority="P2",
                    from_plan=plan_path,
                    dev_type="backend",
                    created_at="2026-07-10",
                    date_prefix="07-10",
                )
            ).task_dir
            untyped = self.TaskCreationService(root).create(
                self.TaskCreationRequest(
                    title="未声明类型",
                    slug="untyped-task",
                    assignee="codex",
                    priority="P2",
                    created_at="2026-07-10",
                    date_prefix="07-10",
                )
            ).task_dir

            typed_anchor = (typed / "decision-anchor.md").read_text(encoding="utf-8")
            untyped_anchor = (untyped / "decision-anchor.md").read_text(
                encoding="utf-8"
            )

        self.assertIn(".cowork-flow/spec/backend/", typed_anchor)
        self.assertNotIn(".cowork-flow/spec/<dev_type>/", typed_anchor)
        self.assertIn(".cowork-flow/spec/<dev_type>/", untyped_anchor)


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


class DevTypeWiringTest(unittest.TestCase):
    """dev_type must be writable and readable end to end: persisted at
    creation, backfillable on an unstarted task, and never silently
    swapped under a task that already started."""

    @classmethod
    def setUpClass(cls) -> None:
        module = importlib.import_module("services.task_creation")
        cls.creation_module = module
        cls.TaskCreationRequest = module.TaskCreationRequest
        cls.TaskCreationService = module.TaskCreationService
        cls.TaskCreationError = module.TaskCreationError
        cls.VALID_DEV_TYPES = module.VALID_DEV_TYPES
        cls.TaskRepository = importlib.import_module(
            "services.task_repository"
        ).TaskRepository

    def set_dev_type(self, root: Path, task_dir: Path, dev_type: str) -> None:
        self.creation_module.set_task_dev_type(root, task_dir, dev_type)

    def _create(self, root: Path, **overrides) -> Path:
        kwargs = {
            "title": "dev type wiring",
            "slug": "dev-type-wiring",
            "assignee": "codex",
            "priority": "P2",
            "created_at": "2026-10-09",
            "date_prefix": "10-09",
        }
        kwargs.update(overrides)
        return self.TaskCreationService(root).create(
            self.TaskCreationRequest(**kwargs)
        ).task_dir

    def _task_json(self, task_dir: Path) -> dict:
        return json.loads(
            (task_dir / "task.json").read_text(encoding="utf-8")
        )

    def test_create_persists_declared_dev_type(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            task_dir = self._create(Path(temp_dir), dev_type="backend")

            self.assertEqual("backend", self._task_json(task_dir)["dev_type"])

    def test_create_defaults_dev_type_to_null(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            task_dir = self._create(Path(temp_dir))

            self.assertIsNone(self._task_json(task_dir)["dev_type"])

    def test_create_task_json_has_no_scope_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            task_dir = self._create(Path(temp_dir), dev_type="backend")

            self.assertNotIn("scope", self._task_json(task_dir))
            self.assertEqual(
                {
                    "_state",
                    "assignee",
                    "children",
                    "commit",
                    "completedAt",
                    "createdAt",
                    "creator",
                    "dependsOn",
                    "description",
                    "dev_type",
                    "id",
                    "meta",
                    "name",
                    "notes",
                    "parent",
                    "priority",
                    "relatedFiles",
                    "status",
                    "subtasks",
                    "title",
                },
                set(self._task_json(task_dir)),
            )

    def test_create_rejects_unknown_dev_type(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(self.TaskCreationError) as caught:
                self._create(Path(temp_dir), dev_type="nope")

            self.assertEqual(
                "TASK-CREATE-DEVTYPE-001", caught.exception.code
            )

    def test_backfill_sets_dev_type_on_planning_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._create(root)

            self.set_dev_type(root, task_dir, "frontend")

            self.assertEqual(
                "frontend", self._task_json(task_dir)["dev_type"]
            )

    def test_backfill_refuses_started_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._create(root)
            self.TaskRepository(root).save(
                task_dir, {"status": "in_progress"}
            )

            with self.assertRaises(self.TaskCreationError) as caught:
                self.set_dev_type(root, task_dir, "frontend")

            self.assertEqual(
                "TASK-CREATE-DEVTYPE-002", caught.exception.code
            )
            self.assertIsNone(self._task_json(task_dir)["dev_type"])

    def test_backfill_rejects_unknown_dev_type(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._create(root)

            with self.assertRaises(self.TaskCreationError) as caught:
                self.set_dev_type(root, task_dir, "nope")

            self.assertEqual(
                "TASK-CREATE-DEVTYPE-001", caught.exception.code
            )

    def test_valid_dev_types_all_have_a_dispatch_effect(self) -> None:
        """Every offered value must change the implement reading list —
        otherwise the flag advertises a promise it never keeps."""
        context_discovery = importlib.import_module(
            "services.context_discovery"
        )
        base = {
            entry["file"]
            for entry in context_discovery.implement_spec_entries(
                ROOT, None
            )
        }
        for dev_type in self.VALID_DEV_TYPES:
            with self.subTest(dev_type=dev_type):
                dispatched = {
                    entry["file"]
                    for entry in context_discovery.implement_spec_entries(
                        ROOT, dev_type
                    )
                }
                self.assertNotEqual(base, dispatched)

    def test_create_extracts_plan_acceptance_rows_into_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plans_dir = root / ".cowork-flow" / "plans"
            plans_dir.mkdir(parents=True)
            plan_path = plans_dir / "2026-10-09-ac-demo.md"
            plan_path.write_text(
                """**目标:** 演示目标

## 验收标准

- AC-001: 第一条行为。
- [ ] AC-002: 第二条行为。
""",
                encoding="utf-8",
            )

            task_dir = self._create(root, from_plan=plan_path, dev_type="backend")
            anchor = (task_dir / "decision-anchor.md").read_text(
                encoding="utf-8"
            )

        self.assertIn("- [ ] AC-001: 第一条行为。", anchor)
        self.assertIn("- [ ] AC-002: 第二条行为。", anchor)
        self.assertNotIn("至少一条", anchor)

    def test_create_marks_strict_tasks_for_plan_ready_finalize(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._create(root, dev_type="backend")
            meta = self._task_json(task_dir)["meta"]
            tiny_dir = self._create(
                root,
                title="tiny demo",
                slug="tiny-demo",
                task_type="tiny",
            )
            tiny_meta = self._task_json(tiny_dir)["meta"]

        self.assertTrue(meta["planReadyRequired"])
        self.assertNotIn("planReadyRequired", tiny_meta)



if __name__ == "__main__":
    unittest.main()
