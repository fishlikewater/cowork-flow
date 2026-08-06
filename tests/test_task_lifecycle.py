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
        repository_module = importlib.import_module("services.task_repository")
        self.TaskRepository = repository_module.TaskRepository
        self.TaskRepositoryError = repository_module.TaskRepositoryError

    def _cleanup_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in (
            "services.task_repository",
            "services.task_utils",
            "infra.files",
            "infra.paths",
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
        lifecycle_module = importlib.import_module("services.task_lifecycle")
        self.LifecyclePreflightFailure = lifecycle_module.LifecyclePreflightFailure
        self.LifecycleTransition = lifecycle_module.LifecycleTransition
        self.TaskLifecycleService = lifecycle_module.TaskLifecycleService

    def _cleanup_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in (
            "services.task_lifecycle",
            "application",
            "runtime.session_state",
            "kernel.task_state",
            "services.task_repository",
            "services.task_utils",
            "services.lifecycle_checks",
            "infra.files",
            "infra.paths",
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
                    "meta": {"taskType": "Tiny"},
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
    def _write_start_ready_context(task_dir: Path) -> None:
        anchor = (
            "# Demo\n\n"
            "## \u76ee\u6807\n\n"
            "Run lifecycle.\n\n"
            "## \u9a8c\u6536\u6807\u51c6\n\n"
            "- AC-001: Ready.\n"
        )
        (task_dir / "decision-anchor.md").write_text(anchor, encoding="utf-8")
        entry = {
            "file": f".cowork-flow/tasks/{task_dir.name}/task.json",
            "reason": "Lifecycle fixture",
        }
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        for context_name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
            (task_dir / context_name).write_text(line, encoding="utf-8")

    @staticmethod
    def _check_runner(*, blocked: bool = False):
        class FakeCheckRunner:
            def __init__(self) -> None:
                self.calls: list[tuple[str, Path, dict]] = []

            def review(self, task_dir: Path, **kwargs):
                return self._record("task_review", task_dir, kwargs)

            def complete(self, task_dir: Path, **kwargs):
                return self._record("task_complete", task_dir, kwargs)

            def _record(self, stage: str, task_dir: Path, kwargs: dict):
                self.calls.append((stage, task_dir, kwargs))
                blockers = ("TEST-CHECK-001 blocked",) if blocked else ()
                return SimpleNamespace(blocked=blocked, blockers=blockers)

        return FakeCheckRunner()

    def test_task_lifecycle_imports_on_supported_python_runtime(self) -> None:
        lifecycle_module = importlib.import_module("services.task_lifecycle")

        self.assertEqual(
            "TaskLifecycleService",
            lifecycle_module.TaskLifecycleService.__name__,
        )
        self.assertEqual(
            "LifecyclePreflightFailure",
            lifecycle_module.LifecyclePreflightFailure.__name__,
        )

    def test_successful_start_result_declares_transition_active_task_and_event(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            self._write_task(task_dir, "planning")
            self._write_start_ready_context(task_dir)
            service = self.TaskLifecycleService(root, check_runner=self._check_runner())

            with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}, clear=True):
                result = service.start(task_dir)

            self.assertTrue(result.ok)
            self.assertEqual("LIFECYCLE-OK", result.code)
            self.assertEqual(
                self.LifecycleTransition(
                    previous_status="planning",
                    next_status="in_progress",
                    changed=True,
                ),
                result.transition,
            )
            self.assertEqual(".cowork-flow/tasks/07-10-demo", result.active_task_path)
            self.assertEqual(("after_start",), result.emitted_events)

    def test_start_readiness_policy_reports_missing_anchor_without_terminal_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            self._write_task(task_dir, "planning")
            policy = importlib.import_module("services.lifecycle_policy")
            stdout = io.StringIO()
            stderr = io.StringIO()

            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                failure = policy.start_readiness_failure(root, task_dir)

            self.assertIsNotNone(failure)
            self.assertEqual("TASK-START-001", failure.code)
            self.assertIn("decision-anchor.md is missing or empty", failure.blockers)
            self.assertEqual("", stdout.getvalue())
            self.assertEqual("", stderr.getvalue())

    def test_review_execution_policy_centralizes_spec_modification_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            self._write_task(task_dir, "in_progress")
            execution = importlib.import_module("runtime.execution_context")
            context = execution.ExecutionContext(
                mode=execution.MODE_WORKER,
                assignment="impl",
                task_dir=str(task_dir),
                prompt_file="prompt.md",
            )
            check_runner = self._check_runner()
            service = self.TaskLifecycleService(root, check_runner=check_runner)

            result = service.review(
                task_dir,
                execution_context=context,
            )

            self.assertTrue(result.ok)
            self.assertIsNotNone(result.execution_policy)
            self.assertFalse(result.execution_policy.allow_spec_file_modifications)
            self.assertFalse(
                check_runner.calls[0][2]["allow_spec_file_modifications"]
            )

    def test_preflight_failure_stops_before_check_and_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            self._write_task(task_dir, "planning")
            check_runner = self._check_runner()
            service = self.TaskLifecycleService(root, check_runner=check_runner)
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
            self.assertEqual([], check_runner.calls)
            self.assertEqual("planning", self._status(task_dir))

    def test_check_failure_leaves_task_metadata_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            self._write_task(task_dir, "in_progress")
            check_runner = self._check_runner(blocked=True)
            service = self.TaskLifecycleService(root, check_runner=check_runner)

            result = service.review(task_dir)

            self.assertFalse(result.ok)
            self.assertEqual("LIFECYCLE-CHECK-001", result.code)
            self.assertEqual("in_progress", self._status(task_dir))
            self.assertEqual("task_review", check_runner.calls[0][0])

    def test_repeated_review_reruns_checks_without_persisting_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            self._write_task(task_dir, "review")
            before = (task_dir / "task.json").read_text(encoding="utf-8")
            check_runner = self._check_runner()
            service = self.TaskLifecycleService(root, check_runner=check_runner)

            result = service.review(task_dir)

            self.assertTrue(result.ok)
            self.assertEqual("LIFECYCLE-IDEMPOTENT-VALIDATED", result.code)
            self.assertIsNotNone(result.check_result)
            self.assertEqual("task_review", check_runner.calls[0][0])
            self.assertEqual(
                before,
                (task_dir / "task.json").read_text(encoding="utf-8"),
            )

    def test_repeated_complete_reruns_checks_without_persisting_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            self._write_task(task_dir, "completed")
            before = (task_dir / "task.json").read_text(encoding="utf-8")
            check_runner = self._check_runner()
            service = self.TaskLifecycleService(root, check_runner=check_runner)

            result = service.complete(task_dir, completed_at="2026-07-10")

            self.assertTrue(result.ok)
            self.assertEqual("LIFECYCLE-IDEMPOTENT-VALIDATED", result.code)
            self.assertIsNotNone(result.check_result)
            self.assertEqual("task_complete", check_runner.calls[0][0])
            self.assertEqual(
                before,
                (task_dir / "task.json").read_text(encoding="utf-8"),
            )

    def test_review_and_complete_share_transition_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            self._write_task(task_dir, "in_progress")
            check_runner = self._check_runner()
            service = self.TaskLifecycleService(root, check_runner=check_runner)

            review = service.review(
                task_dir,
                allow_spec_file_modifications=True,
            )
            complete = service.complete(
                task_dir,
                completed_at="2026-07-10",
            )

            self.assertTrue(review.ok)
            self.assertTrue(complete.ok)
            persisted = json.loads(
                (task_dir / "task.json").read_text(encoding="utf-8")
            )
            self.assertEqual("completed", persisted["status"])
            self.assertEqual("2026-07-10", persisted["completedAt"])
            self.assertEqual({"keep": True}, persisted["customMetadata"])
            self.assertEqual(
                ["task_review", "task_complete"],
                [call[0] for call in check_runner.calls],
            )
            self.assertTrue(
                check_runner.calls[0][2]["allow_spec_file_modifications"]
            )

    def test_start_without_session_context_does_not_change_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            self._write_task(task_dir, "planning")
            self._write_start_ready_context(task_dir)
            check_runner = self._check_runner()
            service = self.TaskLifecycleService(root, check_runner=check_runner)

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
            self._write_start_ready_context(task_dir)
            check_runner = self._check_runner()

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
                    check_runner=check_runner,
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
                    check_runner=self._check_runner(),
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
