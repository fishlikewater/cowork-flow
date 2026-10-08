from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"


class TaskDependenciesTest(unittest.TestCase):
    def setUp(self) -> None:
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
            self.addCleanup(sys.path.remove, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        self.creation = importlib.import_module("services.task_creation")
        self.graph = importlib.import_module("services.task_graph")
        self.lifecycle = importlib.import_module("services.task_lifecycle")
        self.policy = importlib.import_module("services.lifecycle_policy")

    def _cleanup_imports(self) -> None:
        for name in (
            "services.task_creation",
            "services.task_graph",
            "services.task_tree",
            "services.task_repository",
            "services.plan_binding",
            "services.task_utils",
            "infra.paths",
            "infra.files",
            "common",
        ):
            sys.modules.pop(name, None)

    @staticmethod
    def _write_task(root: Path, name: str, status: str, **extra) -> Path:
        task_dir = root / ".cowork-flow" / "tasks" / name
        task_dir.mkdir(parents=True, exist_ok=True)
        data = {"id": name, "name": name, "title": name, "status": status}
        data.update(extra)
        (task_dir / "task.json").write_text(json.dumps(data), encoding="utf-8")
        return task_dir

    @staticmethod
    def _write_archived_task(root: Path, name: str, status: str) -> Path:
        task_dir = root / ".cowork-flow" / "tasks" / "archive" / "2026-09" / name
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "task.json").write_text(
            json.dumps({"id": name, "name": name, "title": name, "status": status}),
            encoding="utf-8",
        )
        return task_dir

    @staticmethod
    def _write_start_ready_context(task_dir: Path) -> None:
        (task_dir / "decision-anchor.md").write_text(
            "# Demo\n\n## 目标\n\nDependencies.\n\n## 验收标准\n\n- AC-001: Ready.\n",
            encoding="utf-8",
        )
        entry = {
            "file": f".cowork-flow/tasks/{task_dir.name}/task.json",
            "reason": "Dependency fixture",
        }
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        for context_name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
            (task_dir / context_name).write_text(line, encoding="utf-8")

    def _create(self, root: Path, slug: str, *, depends_on=(), title="Dependency demo"):
        service = self.creation.TaskCreationService(root)
        request = self.creation.TaskCreationRequest(
            title=title,
            slug=slug,
            assignee="tester",
            priority="P2",
            depends_on=tuple(depends_on),
        )
        return service.create(request)

    def test_create_records_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_task(root, "10-01-foundation", "completed")

            result = self._create(root, "feature", depends_on=("10-01-foundation",))

            data = json.loads(
                (result.task_dir / "task.json").read_text(encoding="utf-8")
            )
            self.assertEqual(["10-01-foundation"], data["dependsOn"])

    def test_create_rejects_missing_and_self_dependencies(self) -> None:
        cases = (
            (("nope-missing",), "TASK-CREATE-DEPENDENCY-001"),
            (("feature",), "TASK-CREATE-DEPENDENCY-002"),
        )
        for depends_on, expected_code in cases:
            with self.subTest(depends_on=depends_on):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    with self.assertRaises(self.creation.TaskCreationError) as raised:
                        self._create(root, "feature", depends_on=depends_on)

                    self.assertEqual(expected_code, raised.exception.code)
                    tasks_dir = root / ".cowork-flow" / "tasks"
                    created = (
                        [path for path in tasks_dir.glob("*feature*")]
                        if tasks_dir.is_dir()
                        else []
                    )
                    self.assertEqual([], created, "failed create must leave nothing")

    def test_create_rejects_dependency_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = importlib.import_module("infra.paths")
            new_name = paths.ensure_task_date_prefix("gamma")
            # Hand-edited fact: beta claims a dependency on the task that is
            # about to be created, so declaring gamma -> beta closes a loop.
            self._write_task(
                root, "20-02-beta", "planning", dependsOn=[new_name]
            )

            with self.assertRaises(self.creation.TaskCreationError) as raised:
                self._create(root, "gamma", depends_on=("20-02-beta",))

            self.assertEqual("TASK-CREATE-DEPENDENCY-003", raised.exception.code)
            self.assertIn("20-02-beta", raised.exception.detail)

    def test_dependencies_resolve_across_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_archived_task(root, "10-01-foundation", "completed")

            result = self._create(root, "feature", depends_on=("10-01-foundation",))

            self.assertEqual(
                [],
                self.graph.unresolved_dependencies(root, result.task_dir),
                "an archived completed dependency must not block",
            )

    def test_unresolved_dependencies_reports_unfinished_and_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_task(root, "10-01-active", "in_progress")
            self._write_archived_task(root, "10-02-done", "completed")
            task_dir = self._write_task(
                root,
                "10-03-feature",
                "planning",
                dependsOn=["10-01-active", "10-02-done", "10-04-vanished"],
            )

            unresolved = self.graph.unresolved_dependencies(root, task_dir)

            self.assertEqual(["10-01-active", "10-04-vanished"], unresolved)

    def test_start_preflight_blocks_unresolved_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_task(root, "10-01-active", "in_progress")
            task_dir = self._write_task(
                root,
                "10-03-feature",
                "planning",
                dependsOn=["10-01-active"],
                meta={"taskType": "Tiny"},
            )
            self._write_start_ready_context(task_dir)

            failure = self.policy.start_readiness_failure(root, task_dir)

            self.assertIsNotNone(failure)
            self.assertEqual("LIFECYCLE-DEPENDENCY-001", failure.code)
            self.assertIn("10-01-active", " ".join(failure.blockers))

    def test_service_start_blocks_unresolved_dependencies_then_clears(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dependency_dir = self._write_task(root, "10-01-active", "in_progress")
            task_dir = self._write_task(
                root,
                "10-03-feature",
                "planning",
                dependsOn=["10-01-active"],
                meta={"taskType": "Tiny"},
            )
            self._write_start_ready_context(task_dir)
            service = self.lifecycle.TaskLifecycleService(root)

            with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                blocked = service.start(task_dir)

            self.assertFalse(blocked.ok)
            self.assertEqual("LIFECYCLE-DEPENDENCY-001", blocked.code)
            persisted = json.loads(
                (task_dir / "task.json").read_text(encoding="utf-8")
            )
            self.assertEqual("planning", persisted["status"], "block must not start")

            dependency_data = json.loads(
                (dependency_dir / "task.json").read_text(encoding="utf-8")
            )
            dependency_data["status"] = "completed"
            (dependency_dir / "task.json").write_text(
                json.dumps(dependency_data), encoding="utf-8"
            )

            with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                started = service.start(task_dir)

            self.assertTrue(started.ok, started.blockers)
            self.assertEqual(
                "in_progress",
                json.loads(
                    (task_dir / "task.json").read_text(encoding="utf-8")
                )["status"],
            )

    def test_started_task_is_not_retroactively_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_task(root, "10-01-active", "in_progress")
            task_dir = self._write_task(
                root,
                "10-03-feature",
                "in_progress",
                dependsOn=["10-01-active"],
                executor="session-a",
            )
            service = self.lifecycle.TaskLifecycleService(root)

            with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "session-a"}):
                result = service.start(task_dir)

            self.assertTrue(result.ok, result.blockers)
            self.assertEqual("LIFECYCLE-IDEMPOTENT", result.code)


if __name__ == "__main__":
    unittest.main()
