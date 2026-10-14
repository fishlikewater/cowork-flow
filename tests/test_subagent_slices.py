from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
SUBAGENT = SCRIPTS / "adapters" / "cli" / "subagent.py"
TASK = ".cowork-flow/tasks/10-14-demo"
OTHER_TASK = ".cowork-flow/tasks/10-15-other"


def _context(
    runtime_context_id: str,
    *,
    task_dir: str = TASK,
    owned: list[str] | None = None,
    agent_type: str = "cowork-implement",
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
        "role": "implement",
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


class SubagentSliceTest(unittest.TestCase):
    def setUp(self) -> None:
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
            self.addCleanup(sys.path.remove, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        workflow_runtime = importlib.import_module("services.workflow_runtime")
        self.RuntimeContextService = workflow_runtime.RuntimeContextService
        self.RuntimeContextError = workflow_runtime.RuntimeContextError
        self.owned_paths_overlap = workflow_runtime.owned_paths_overlap
        os.environ["CODEX_SESSION_ID"] = "codex-slice-test"
        self.addCleanup(os.environ.pop, "CODEX_SESSION_ID", None)

    def _cleanup_imports(self) -> None:
        for module_name in (
            "services.workflow_runtime",
            "services.review_receipt",
            "runtime.session_state",
            "runtime.host_identity",
            "infra.paths",
            "infra.storage.state_store",
            "infra.storage.unit_of_work",
        ):
            sys.modules.pop(module_name, None)

    @staticmethod
    def _root(temp_dir: str) -> Path:
        root = Path(temp_dir)
        (root / ".cowork-flow" / ".runtime").mkdir(parents=True)
        return root

    def _run_cli(self, root: Path, *argv: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SUBAGENT), *argv],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_overlapping_owned_paths_fail_closed_and_write_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._root(temp_dir)
            service = self.RuntimeContextService(root)
            service.initialize("rtx_first", _context("rtx_first", owned=["src/api"]))
            context_path = (
                root / ".cowork-flow" / ".runtime" / "subagents" / "rtx_first.json"
            )
            before = context_path.read_bytes()

            for owned in (["src/api"], ["src/api/routes.py"], ["src"]):
                with self.subTest(owned=owned):
                    with self.assertRaises(self.RuntimeContextError) as raised:
                        service.initialize(
                            "rtx_second",
                            _context("rtx_second", owned=owned),
                        )
                    self.assertEqual("SUBAGENT-SLICE-001", raised.exception.code)
                    self.assertIn("rtx_first", raised.exception.detail)

            self.assertFalse(
                (
                    root / ".cowork-flow" / ".runtime" / "subagents" / "rtx_second.json"
                ).exists()
            )
            self.assertFalse(
                (
                    root
                    / ".cowork-flow"
                    / ".runtime"
                    / "sessions"
                    / "subagent_rtx_second.json"
                ).exists()
            )
            self.assertEqual(before, context_path.read_bytes())

    def test_disjoint_slices_initialize_side_by_side(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._root(temp_dir)
            service = self.RuntimeContextService(root)
            service.initialize("rtx_api", _context("rtx_api", owned=["src/api"]))
            service.initialize("rtx_web", _context("rtx_web", owned=["src/web"]))

            for runtime_context_id in ("rtx_api", "rtx_web"):
                context = service.load(runtime_context_id)
                self.assertEqual("pending", context["status"])

            with self.assertRaises(self.RuntimeContextError) as raised:
                service.initialize(
                    "rtx_second",
                    _context("rtx_second", owned=["src\\api\\"]),
                )
            self.assertEqual("SUBAGENT-SLICE-001", raised.exception.code)

    def test_closed_context_releases_its_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._root(temp_dir)
            service = self.RuntimeContextService(root)
            service.initialize("rtx_done", _context("rtx_done", owned=["src/api"]))
            service.close("rtx_done")

            service.initialize("rtx_again", _context("rtx_again", owned=["src/api"]))

            self.assertTrue(
                (
                    root / ".cowork-flow" / ".runtime" / "subagents" / "rtx_again.json"
                ).is_file()
            )

    def test_other_tasks_and_agent_types_do_not_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._root(temp_dir)
            service = self.RuntimeContextService(root)
            service.initialize(
                "rtx_other_task",
                _context("rtx_other_task", task_dir=OTHER_TASK, owned=["src/api"]),
            )
            service.initialize(
                "rtx_check",
                _context("rtx_check", owned=["src/api"], agent_type="cowork-check"),
            )

            service.initialize("rtx_new", _context("rtx_new", owned=["src/api"]))

            self.assertTrue(
                (
                    root / ".cowork-flow" / ".runtime" / "subagents" / "rtx_new.json"
                ).is_file()
            )

    def test_context_without_owned_paths_claims_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._root(temp_dir)
            service = self.RuntimeContextService(root)
            service.initialize("rtx_plain", _context("rtx_plain"))

            service.initialize("rtx_slice", _context("rtx_slice", owned=["src/api"]))

            service.initialize("rtx_plain_second", _context("rtx_plain_second"))

            for runtime_context_id in ("rtx_plain", "rtx_slice", "rtx_plain_second"):
                self.assertTrue(
                    (
                        root
                        / ".cowork-flow"
                        / ".runtime"
                        / "subagents"
                        / f"{runtime_context_id}.json"
                    ).is_file()
                )

    def test_owned_paths_overlap_uses_directory_boundaries(self) -> None:
        self.assertEqual(
            [("src\\api\\", "src/api")],
            self.owned_paths_overlap(["src\\api\\"], ["src/api"]),
        )
        self.assertEqual(
            [("src/api", "src/api/routes.py")],
            self.owned_paths_overlap(["src/api"], ["src/api/routes.py"]),
        )
        self.assertEqual([], self.owned_paths_overlap(["src/api"], ["src/apis"]))
        self.assertEqual([], self.owned_paths_overlap([], ["src/api"]))

    def test_init_records_slice_and_owned_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._root(temp_dir)
            result = self._run_cli(
                root,
                "--execution-task-dir",
                TASK,
                "init",
                "--title",
                "API slice",
                "--role",
                "implement",
                "--slice",
                "api",
                "--owns",
                "src/api",
                "--owns",
                "src\\api\\shared",
            )
            self.assertEqual(
                0,
                result.returncode,
                msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
            )
            payload = json.loads(result.stdout)
            context = json.loads(
                (root / payload["runtimeContextFile"]).read_text(encoding="utf-8")
            )

        assignment = context["assignment"]
        self.assertEqual("api", assignment["slice"])
        self.assertEqual(["src/api", "src/api/shared"], assignment["owned_paths"])

    def test_init_reports_slice_conflict_over_an_open_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._root(temp_dir)
            first = self._run_cli(
                root,
                "--execution-task-dir",
                TASK,
                "init",
                "--title",
                "API slice",
                "--role",
                "implement",
                "--owns",
                "src/api",
            )
            self.assertEqual(0, first.returncode, msg=first.stderr)

            second = self._run_cli(
                root,
                "--execution-task-dir",
                TASK,
                "init",
                "--title",
                "API internals",
                "--role",
                "implement",
                "--owns",
                "src/api/routes.py",
            )

            context_files = sorted(
                (
                    root / ".cowork-flow" / ".runtime" / "subagents"
                ).glob("*.json")
            )

        self.assertEqual(1, second.returncode)
        self.assertIn("SUBAGENT-SLICE-001", second.stderr)
        self.assertEqual(1, len(context_files))

    def test_prompt_renders_transport_lines_and_assignment_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._root(temp_dir)
            init = self._run_cli(
                root,
                "--execution-task-dir",
                TASK,
                "init",
                "--title",
                "API slice",
                "--role",
                "implement",
                "--goal",
                "Inspect API routes",
                "--slice",
                "api",
                "--owns",
                "src/api",
            )
            self.assertEqual(0, init.returncode, msg=init.stderr)
            payload = json.loads(init.stdout)

            prompt = self._run_cli(root, "prompt", payload["runtimeContextId"])

        self.assertEqual(0, prompt.returncode, msg=prompt.stderr)
        self.assertIn(payload["promptTransport"], prompt.stdout)
        self.assertIn(
            f"subagent status {payload['runtimeContextId']}",
            prompt.stdout,
        )
        self.assertIn("Goal: Inspect API routes", prompt.stdout)
        self.assertIn("Owned paths: src/api", prompt.stdout)

    def test_list_filters_task_and_open(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._root(temp_dir)
            open_here = self._run_cli(
                root,
                "--execution-task-dir",
                TASK,
                "init",
                "--title",
                "API slice",
                "--role",
                "implement",
                "--slice",
                "api",
                "--owns",
                "src/api",
            )
            closed_here = self._run_cli(
                root,
                "--execution-task-dir",
                TASK,
                "init",
                "--title",
                "Review pass",
                "--role",
                "check",
                "--agent-type",
                "cowork-check",
            )
            other_task = self._run_cli(
                root,
                "--execution-task-dir",
                OTHER_TASK,
                "init",
                "--title",
                "Other task",
                "--role",
                "implement",
            )
            for result in (open_here, closed_here, other_task):
                self.assertEqual(0, result.returncode, msg=result.stderr)
            closed_id = json.loads(closed_here.stdout)["runtimeContextId"]
            close = self._run_cli(root, "close", closed_id)
            self.assertEqual(0, close.returncode, msg=close.stderr)

            open_only = self._run_cli(root, "list", "--open")
            here_only = self._run_cli(root, "list", "--task", TASK)

        self.assertEqual(0, open_only.returncode, msg=open_only.stderr)
        self.assertIn(json.loads(open_here.stdout)["runtimeContextId"], open_only.stdout)
        self.assertIn(
            json.loads(other_task.stdout)["runtimeContextId"],
            open_only.stdout,
        )
        self.assertNotIn(closed_id, open_only.stdout)

        self.assertEqual(0, here_only.returncode, msg=here_only.stderr)
        self.assertIn(json.loads(open_here.stdout)["runtimeContextId"], here_only.stdout)
        self.assertIn(closed_id, here_only.stdout)
        self.assertNotIn(
            json.loads(other_task.stdout)["runtimeContextId"],
            here_only.stdout,
        )
        self.assertIn("pending", here_only.stdout)
        self.assertIn("owns=src/api", here_only.stdout)


if __name__ == "__main__":
    unittest.main()
