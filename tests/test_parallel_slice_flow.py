from __future__ import annotations

import importlib
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
TASK = ".cowork-flow/tasks/07-10-demo"


def _context(
    runtime_context_id: str,
    *,
    task_dir: str = TASK,
    owned: list[str] | None = None,
    agent_type: str = "cowork-implement",
    role: str = "implement",
) -> dict:
    assignment: dict = {
        "title": runtime_context_id,
        "goal": "Land one slice",
        "allowed_context": [],
        "expected_output": "Files changed, validation commands, and blockers.",
        "source": "auto",
    }
    if owned:
        assignment["owned_paths"] = owned
    return {
        "schema_version": 2,
        "runtime_context_id": runtime_context_id,
        "scope": "subagent",
        "host": "codex",
        "adapter": "codex",
        "agent_type": agent_type,
        "role": role,
        "task_dir": task_dir,
        "parent_context_key": "codex_main",
        "transport": {"kind": "prompt", "key": "cowork_runtime_context_id"},
        "assignment": assignment,
        "authority": {
            "may_start_task": False,
            "may_resume_main": False,
            "may_archive": False,
            "may_commit": False,
            "may_spawn": False,
        },
        "status": "pending",
        "dispatch_kind": "formal",
        "created_at": "2026-10-14T00:00:00Z",
        "bound_context_key": None,
        "closed_at": None,
    }


class ParallelSliceFlowTest(unittest.TestCase):
    """One end-to-end pass of the parallel slice contract.

    Two disjoint implement slices may run side by side; an overlapping third
    slice and an undeclared slice are both rejected without writing anything;
    review stays frozen while slices are open and proceeds once they close.
    """

    def setUp(self) -> None:
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
            self.addCleanup(sys.path.remove, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        workflow_runtime = importlib.import_module("services.workflow_runtime")
        self.RuntimeContextService = workflow_runtime.RuntimeContextService
        self.RuntimeContextError = workflow_runtime.RuntimeContextError
        lifecycle_module = importlib.import_module("services.task_lifecycle")
        self.TaskLifecycleService = lifecycle_module.TaskLifecycleService

    def _cleanup_imports(self) -> None:
        for module_name in (
            "services.workflow_runtime",
            "services.review_receipt",
            "runtime.session_state",
            "runtime.host_identity",
            "infra.paths",
            "infra.storage.state_store",
            "infra.storage.unit_of_work",
            "services.task_lifecycle",
            "services.task_lease",
            "application",
            "kernel.task_state",
            "services.task_repository",
            "services.task_utils",
            "services.lifecycle_checks",
            "infra.files",
            "common",
        ):
            sys.modules.pop(module_name, None)

    @staticmethod
    def _root(temp_dir: str) -> Path:
        root = Path(temp_dir)
        (root / ".cowork-flow" / ".runtime").mkdir(parents=True)
        return root

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

    def test_parallel_slices_then_review_freezes_until_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._root(temp_dir)
            task_dir = root / TASK
            self._write_task(task_dir, "in_progress")
            service = self.RuntimeContextService(root)

            service.initialize("rtx_api", _context("rtx_api", owned=["src/api"]))
            service.initialize("rtx_web", _context("rtx_web", owned=["src/web"]))
            for runtime_context_id in ("rtx_api", "rtx_web"):
                self.assertEqual(
                    "pending", service.load(runtime_context_id)["status"]
                )

            with self.assertRaises(self.RuntimeContextError) as nested:
                service.initialize(
                    "rtx_nested",
                    _context("rtx_nested", owned=["src/api/routes.py"]),
                )
            self.assertEqual("SUBAGENT-SLICE-001", nested.exception.code)
            self.assertIn("rtx_api", nested.exception.detail)

            with self.assertRaises(self.RuntimeContextError) as undeclared:
                service.initialize("rtx_plain", _context("rtx_plain"))
            self.assertEqual("SUBAGENT-SLICE-001", undeclared.exception.code)
            self.assertIn("(all paths)", undeclared.exception.detail)

            runtime_dir = root / ".cowork-flow" / ".runtime"
            for rejected_id in ("rtx_nested", "rtx_plain"):
                self.assertFalse(
                    (runtime_dir / "subagents" / f"{rejected_id}.json").exists()
                )
                self.assertFalse(
                    (
                        runtime_dir
                        / "sessions"
                        / f"subagent_{rejected_id}.json"
                    ).exists()
                )

            lifecycle = self.TaskLifecycleService(
                root, check_runner=self._check_runner()
            )

            with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                frozen = lifecycle.review(task_dir)

            self.assertFalse(frozen.ok)
            self.assertEqual("LIFECYCLE-REVIEW-005", frozen.code)
            blockers = " ".join(frozen.blockers)
            self.assertIn("rtx_api", blockers)
            self.assertIn("rtx_web", blockers)
            self.assertEqual("in_progress", self._status(task_dir))

            service.close("rtx_api")
            service.close("rtx_web")

            with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                reviewed = lifecycle.review(task_dir)

            self.assertTrue(reviewed.ok, reviewed.blockers)
            self.assertEqual("review", self._status(task_dir))

    def test_other_task_open_implement_does_not_freeze_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._root(temp_dir)
            task_dir = root / TASK
            self._write_task(task_dir, "in_progress")
            other_task_dir = root / ".cowork-flow" / "tasks" / "07-11-other"
            self._write_task(other_task_dir, "in_progress")
            self.RuntimeContextService(root).initialize(
                "rtx_other",
                _context(
                    "rtx_other",
                    task_dir=".cowork-flow/tasks/07-11-other",
                    owned=["src/api"],
                ),
            )

            lifecycle = self.TaskLifecycleService(
                root, check_runner=self._check_runner()
            )
            with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                reviewed = lifecycle.review(task_dir)

            self.assertTrue(reviewed.ok, reviewed.blockers)
            self.assertEqual("review", self._status(task_dir))

    def test_open_check_context_does_not_freeze_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._root(temp_dir)
            task_dir = root / TASK
            self._write_task(task_dir, "in_progress")
            self.RuntimeContextService(root).initialize(
                "rtx_check",
                _context("rtx_check", agent_type="cowork-check", role="check"),
            )

            lifecycle = self.TaskLifecycleService(
                root, check_runner=self._check_runner()
            )
            with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                reviewed = lifecycle.review(task_dir)

            self.assertTrue(reviewed.ok, reviewed.blockers)
            self.assertEqual("review", self._status(task_dir))


if __name__ == "__main__":
    unittest.main()
