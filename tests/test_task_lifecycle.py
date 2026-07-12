from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"


class TaskRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        repository_module = importlib.import_module("common.task.task_repository")
        self.TaskRepository = repository_module.TaskRepository
        self.TaskRepositoryError = repository_module.TaskRepositoryError

    def _cleanup_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in (
            "common.task.task_repository",
            "common.task.task_utils",
            "common.core.files",
            "common.core.paths",
            "common",
        ):
            sys.modules.pop(module_name, None)

    @staticmethod
    def _write_task(task_dir: Path, data: dict) -> None:
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "task.json").write_text(
            json.dumps(data, ensure_ascii=False),
            encoding="utf-8",
        )

    def test_resolve_supports_existing_task_path_formats(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            task_dir.mkdir(parents=True)
            repository = self.TaskRepository(root)

            self.assertEqual(task_dir, repository.resolve(task_dir))
            self.assertEqual(
                task_dir,
                repository.resolve(".cowork-flow/tasks/07-10-demo"),
            )
            self.assertEqual(task_dir, repository.resolve("07-10-demo"))
            self.assertEqual(task_dir, repository.resolve("demo"))

    def test_load_and_save_preserve_unknown_fields_and_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            self._write_task(
                task_dir,
                {
                    "status": "in_progress",
                    "title": "生命周期拆分",
                    "customMetadata": {"owner": "架构组"},
                },
            )
            repository = self.TaskRepository(root)

            loaded = repository.load(task_dir)
            self.assertEqual("生命周期拆分", loaded["title"])

            repository.save(task_dir, {"status": "review"})

            persisted = json.loads(
                (task_dir / "task.json").read_text(encoding="utf-8")
            )
            self.assertEqual("review", persisted["status"])
            self.assertEqual("生命周期拆分", persisted["title"])
            self.assertEqual({"owner": "架构组"}, persisted["customMetadata"])

    def test_missing_task_json_raises_stable_error_without_printing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-missing"
            task_dir.mkdir(parents=True)
            repository = self.TaskRepository(root)
            stdout = io.StringIO()
            stderr = io.StringIO()

            with (
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
                self.assertRaises(self.TaskRepositoryError) as raised,
            ):
                repository.load(task_dir)

            self.assertEqual("TASK-LOAD-001", raised.exception.code)
            self.assertEqual("", stdout.getvalue())
            self.assertEqual("", stderr.getvalue())

    def test_invalid_task_json_raises_stable_error_without_printing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-invalid"
            task_dir.mkdir(parents=True)
            task_json = task_dir / "task.json"
            task_json.write_text("{invalid", encoding="utf-8")
            repository = self.TaskRepository(root)
            stdout = io.StringIO()
            stderr = io.StringIO()

            with (
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
                self.assertRaises(self.TaskRepositoryError) as raised,
            ):
                repository.load(task_dir)

            self.assertEqual("TASK-LOAD-002", raised.exception.code)
            self.assertEqual("{invalid", task_json.read_text(encoding="utf-8"))
            self.assertEqual("", stdout.getvalue())
            self.assertEqual("", stderr.getvalue())


class TaskLifecycleServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        lifecycle_module = importlib.import_module("application.task_lifecycle")
        self.LifecyclePreflightFailure = lifecycle_module.LifecyclePreflightFailure
        self.TaskLifecycleService = lifecycle_module.TaskLifecycleService

    def _cleanup_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in (
            "application.task_lifecycle",
            "application",
            "common.task.active_task",
            "common.task.state_machine",
            "common.task.task_repository",
            "common.task.task_utils",
            "common.gates.gates",
            "common.gates.models",
            "common.core.files",
            "common.core.paths",
            "common",
        ):
            sys.modules.pop(module_name, None)

    @staticmethod
    def _write_task(task_dir: Path, status: str) -> None:
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "task.json").write_text(
            json.dumps(
                {
                    "status": status,
                    "title": "Lifecycle demo",
                    "customMetadata": {"keep": True},
                }
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _status(task_dir: Path) -> str:
        return json.loads(
            (task_dir / "task.json").read_text(encoding="utf-8")
        )["status"]

    @staticmethod
    def _gate_runner(*, blocked: bool = False):
        class FakeGateRunner:
            def __init__(self) -> None:
                self.calls: list[tuple[str, Path, dict]] = []

            def run(self, scope: str, task_dir: Path, **kwargs):
                self.calls.append((scope, task_dir, kwargs))
                violations = (
                    [{"rule_id": "TEST-GATE-001", "severity": "block"}]
                    if blocked
                    else []
                )
                return SimpleNamespace(blocked=blocked, violations=violations)

            def coding_standards_summary(self, task_dir: Path) -> str:
                return f"summary:{task_dir.name}"

        return FakeGateRunner()

    def test_task_lifecycle_imports_on_supported_python_runtime(self) -> None:
        lifecycle_module = importlib.import_module("application.task_lifecycle")

        self.assertEqual(
            "TaskLifecycleService",
            lifecycle_module.TaskLifecycleService.__name__,
        )
        self.assertEqual(
            "LifecyclePreflightFailure",
            lifecycle_module.LifecyclePreflightFailure.__name__,
        )

    def test_preflight_failure_stops_before_gate_and_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            self._write_task(task_dir, "planning")
            gate_runner = self._gate_runner()
            service = self.TaskLifecycleService(root, gate_runner=gate_runner)
            failure = self.LifecyclePreflightFailure(
                code="TASK-CONTEXT-001",
                title="Task context validation failed",
                blockers=("missing implement context",),
                hint="initialize context",
            )

            result = service.start(task_dir, preflight=lambda _: failure)

            self.assertFalse(result.ok)
            self.assertEqual("TASK-CONTEXT-001", result.code)
            self.assertEqual(("missing implement context",), result.blockers)
            self.assertEqual([], gate_runner.calls)
            self.assertEqual("planning", self._status(task_dir))

    def test_gate_failure_leaves_task_metadata_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            self._write_task(task_dir, "in_progress")
            gate_runner = self._gate_runner(blocked=True)
            service = self.TaskLifecycleService(root, gate_runner=gate_runner)

            result = service.review(task_dir)

            self.assertFalse(result.ok)
            self.assertEqual("LIFECYCLE-GATE-001", result.code)
            self.assertEqual("in_progress", self._status(task_dir))
            self.assertEqual("task_review", gate_runner.calls[0][0])

    def test_repeated_review_reruns_gates_without_persisting_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            self._write_task(task_dir, "review")
            before = (task_dir / "task.json").read_text(encoding="utf-8")
            gate_runner = self._gate_runner()
            service = self.TaskLifecycleService(root, gate_runner=gate_runner)

            result = service.review(task_dir)

            self.assertTrue(result.ok)
            self.assertEqual("LIFECYCLE-IDEMPOTENT-VALIDATED", result.code)
            self.assertIsNotNone(result.gate_result)
            self.assertEqual("summary:07-10-demo", result.summary)
            self.assertEqual("task_review", gate_runner.calls[0][0])
            self.assertEqual(
                before,
                (task_dir / "task.json").read_text(encoding="utf-8"),
            )

    def test_repeated_complete_reruns_gates_without_persisting_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            self._write_task(task_dir, "completed")
            before = (task_dir / "task.json").read_text(encoding="utf-8")
            gate_runner = self._gate_runner()
            service = self.TaskLifecycleService(root, gate_runner=gate_runner)

            result = service.complete(task_dir, completed_at="2026-07-10")

            self.assertTrue(result.ok)
            self.assertEqual("LIFECYCLE-IDEMPOTENT-VALIDATED", result.code)
            self.assertIsNotNone(result.gate_result)
            self.assertEqual("task_complete", gate_runner.calls[0][0])
            self.assertEqual(
                before,
                (task_dir / "task.json").read_text(encoding="utf-8"),
            )

    def test_review_and_complete_share_transition_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            self._write_task(task_dir, "in_progress")
            gate_runner = self._gate_runner()
            service = self.TaskLifecycleService(root, gate_runner=gate_runner)

            review = service.review(
                task_dir,
                allow_spec_file_modifications=True,
            )
            complete = service.complete(
                task_dir,
                completed_at="2026-07-10",
            )

            self.assertTrue(review.ok)
            self.assertEqual("summary:07-10-demo", review.summary)
            self.assertTrue(complete.ok)
            persisted = json.loads(
                (task_dir / "task.json").read_text(encoding="utf-8")
            )
            self.assertEqual("completed", persisted["status"])
            self.assertEqual("2026-07-10", persisted["completedAt"])
            self.assertEqual({"keep": True}, persisted["customMetadata"])
            self.assertEqual(
                ["task_review", "task_complete"],
                [call[0] for call in gate_runner.calls],
            )
            self.assertTrue(
                gate_runner.calls[0][2]["allow_spec_file_modifications"]
            )

    def test_start_without_session_context_does_not_change_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            self._write_task(task_dir, "planning")
            gate_runner = self._gate_runner()
            service = self.TaskLifecycleService(root, gate_runner=gate_runner)

            with patch.dict(os.environ, {}, clear=True):
                result = service.start(task_dir)

            self.assertFalse(result.ok)
            self.assertEqual("LIFECYCLE-CONTEXT-001", result.code)
            self.assertEqual("planning", self._status(task_dir))


class TaskLifecycleTransactionTest(TaskLifecycleServiceTest):
    def test_crash_between_session_and_task_write_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            self._write_task(task_dir, "planning")
            gate_runner = self._gate_runner()

            def interrupt_after_session(
                index: int,
                _mutation: object,
            ) -> None:
                if index == 0:
                    raise RuntimeError("simulated lifecycle crash")

            with patch.dict(
                os.environ,
                {"COWORK_FLOW_CONTEXT_ID": "main"},
                clear=True,
            ):
                service = self.TaskLifecycleService(
                    root,
                    gate_runner=gate_runner,
                    fault_injector=interrupt_after_session,
                )
                with self.assertRaises(RuntimeError):
                    service.start(task_dir)

                session_path = (
                    root
                    / ".cowork-flow"
                    / ".runtime"
                    / "sessions"
                    / "main.json"
                )
                self.assertTrue(session_path.is_file())
                self.assertEqual("planning", self._status(task_dir))

                recovered = self.TaskLifecycleService(
                    root,
                    gate_runner=self._gate_runner(),
                ).start(task_dir)

            session = json.loads(
                session_path.read_text(encoding="utf-8")
            )
            self.assertTrue(recovered.ok)
            self.assertEqual("in_progress", self._status(task_dir))
            self.assertEqual(
                ".cowork-flow/tasks/07-10-demo",
                session["active_task_path"],
            )


if __name__ == "__main__":
    unittest.main()
