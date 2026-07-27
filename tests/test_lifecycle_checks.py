from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from tests.flow_test_support import FlowScriptTestCase


class LifecycleChecksTest(FlowScriptTestCase):
    @staticmethod
    def _write_context_scope_fixture(task_dir: Path) -> None:
        entries = [
            {"file": "src/planned.py", "reason": "Planned source", "type": "planned-file"},
            {"file": "src/obsolete.py", "reason": "Deleted source", "type": "deleted-file"},
            {"file": "src/", "reason": "Directory context", "type": "directory"},
        ]
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "implement.jsonl").write_text(
            "\n".join(json.dumps(entry) for entry in entries) + "\n",
            encoding="utf-8",
        )

    def _write_allowed_file_task(
        self,
        root: Path,
        task_dir: Path,
        status: str,
        *,
        allowed_files: tuple[str, ...] = ("src/allowed.py",),
    ) -> None:
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "task.json").write_text(
            json.dumps({"status": status, "completedAt": None}),
            encoding="utf-8",
        )
        (task_dir / "decision-anchor.md").write_text(
            "# Demo\n\n## 目标\n\nKeep scope explicit.\n\n## 验收标准\n\n- AC-001: only planned files change.\n",
            encoding="utf-8",
        )
        (task_dir / "implement.jsonl").write_text(
            "".join(json.dumps({"file": file_path, "reason": "planned"}) + "\n" for file_path in allowed_files),
            encoding="utf-8",
        )
        for name in ("check.jsonl", "debug.jsonl"):
            (task_dir / name).write_text(
                json.dumps({"file": allowed_files[0], "reason": "fixture"}) + "\n",
                encoding="utf-8",
            )

    def _write_mixed_git_status_fixture(self, root: Path) -> None:
        src = root / "src"
        src.mkdir(parents=True, exist_ok=True)
        for name in ("allowed.py", "unstaged.py", "staged.py"):
            (src / name).write_text("VALUE = 1\n", encoding="utf-8")
        self._commit_all(root, "baseline")
        (src / "unstaged.py").write_text("VALUE = 2\n", encoding="utf-8")
        (src / "staged.py").write_text("VALUE = 2\n", encoding="utf-8")
        self._run_git(root, "add", "src/staged.py")
        (src / "untracked.py").write_text("VALUE = 2\n", encoding="utf-8")

    def _run_review(self, root: Path) -> tuple[int, str, str]:
        previous_cwd = Path.cwd()
        try:
            os.chdir(root)
            with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                with (
                    contextlib.redirect_stdout(io.StringIO()) as stdout,
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_review(argparse.Namespace(dir=None))
        finally:
            os.chdir(previous_cwd)
        return result, stdout.getvalue(), stderr.getvalue()

    def _run_complete(self, root: Path) -> tuple[int, str, str]:
        previous_cwd = Path.cwd()
        try:
            os.chdir(root)
            with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                with (
                    contextlib.redirect_stdout(io.StringIO()) as stdout,
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_complete(argparse.Namespace(dir=None))
        finally:
            os.chdir(previous_cwd)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_allowed_file_scope_authorizes_known_exact_context_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            self._write_context_scope_fixture(task_dir)
            checks = importlib.import_module("services.lifecycle_checks")

            blockers = checks._allowed_file_scope_blockers(
                task_dir,
                [
                    "src/planned.py",
                    "src/obsolete.py",
                    "src/planned_extra.py",
                    "src/ignored.py",
                ],
            )

        self.assertEqual(
            [
                "Modified file not listed in implement.jsonl: src/planned_extra.py",
                "Modified file not listed in implement.jsonl: src/ignored.py",
            ],
            blockers,
        )

    def test_allowed_file_scope_blocks_malformed_existing_implement_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            task_dir = Path(temp_dir) / ".cowork-flow" / "tasks" / "07-10-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "implement.jsonl").write_text(
                "{\"file\": \"src/allowed.py\"}\nnot-json\n",
                encoding="utf-8",
            )
            checks = importlib.import_module("services.lifecycle_checks")

            blockers = checks._allowed_file_scope_blockers(task_dir, ["src/allowed.py"])

        self.assertEqual(["Invalid implement.jsonl JSON at line 2"], blockers)

    def test_allowed_file_scope_blocks_existing_implement_jsonl_without_file_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            task_dir = Path(temp_dir) / ".cowork-flow" / "tasks" / "07-10-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "implement.jsonl").write_text(
                json.dumps({"file": "src/", "reason": "directory context", "type": "directory"}) + "\n",
                encoding="utf-8",
            )
            checks = importlib.import_module("services.lifecycle_checks")

            blockers = checks._allowed_file_scope_blockers(task_dir, ["src/allowed.py"])

        self.assertEqual(["implement.jsonl contains no valid file-scope entries"], blockers)

    def test_lifecycle_checks_unstaged_staged_and_untracked_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            task_dir = root / ".cowork-flow" / "tasks" / "07-12-demo"
            self._write_allowed_file_task(root, task_dir, "in_progress")
            self._write_mixed_git_status_fixture(root)
            checks = importlib.import_module("services.lifecycle_checks")

            result = checks.LifecycleCheckRunner(root).review(
                task_dir,
                allow_spec_file_modifications=True,
            )

        self.assertTrue(result.blocked)
        self.assertEqual(
            {
                "Modified file not listed in implement.jsonl: src/staged.py",
                "Modified file not listed in implement.jsonl: src/unstaged.py",
                "Modified file not listed in implement.jsonl: src/untracked.py",
            },
            set(result.blockers),
        )

    def test_cmd_complete_blocks_unrequested_files_without_status_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_allowed_file_task(root, task_dir, "review")
            self._write_mixed_git_status_fixture(root)
            self._write_session_task(root)

            result, _stdout, stderr = self._run_complete(root)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(1, result, stderr)
            self.assertEqual("review", data["status"])
            self.assertIsNone(data["completedAt"])
            self.assertIn("Lifecycle checks blocked completion", stderr)
            self.assertIn("Modified file not listed in implement.jsonl: src/staged.py", stderr)

    def test_cmd_review_and_complete_update_active_task_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_allowed_file_task(root, task_dir, "in_progress")
            self._write_session_task(root)

            review_result, _review_stdout, review_stderr = self._run_review(root)
            complete_result, _complete_stdout, complete_stderr = self._run_complete(root)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(0, review_result, review_stderr)
            self.assertEqual(0, complete_result, complete_stderr)
            self.assertEqual("completed", data["status"])
            self.assertEqual(datetime.now().strftime("%Y-%m-%d"), data["completedAt"])

    def test_cmd_complete_allows_missing_task_local_review_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_allowed_file_task(root, task_dir, "review")
            self._write_session_task(root)

            result, _stdout, stderr = self._run_complete(root)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(0, result, stderr)
            self.assertEqual("completed", data["status"])

    def _write_bound_subagent_review_fixture(
        self,
        root: Path,
        *,
        status: str = "in_progress",
        allowed_files: tuple[str, ...] = ("AGENTS.md",),
    ) -> Path:
        self._init_git_repo(root)
        workflow_dir = root / ".cowork-flow"
        task_dir = workflow_dir / "tasks" / "05-19-demo"
        (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
        (workflow_dir / ".developer").parent.mkdir(parents=True, exist_ok=True)
        (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
        self._write_allowed_file_task(root, task_dir, status, allowed_files=allowed_files)
        self._write_session_task(
            root,
            scope="subagent",
            runtime_context_id="runtime-demo",
        )
        self._commit_all(root, "baseline")
        (root / "AGENTS.md").write_text("# Rules changed by subagent\n", encoding="utf-8")
        return task_dir

    def test_cmd_review_blocks_protected_workflow_changes_for_bound_subagent_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._write_bound_subagent_review_fixture(root)

            result, _stdout, stderr = self._run_review(root)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(1, result, stderr)
            self.assertEqual("in_progress", data["status"])
            self.assertIn(
                "Protected workflow/spec file changed outside main session: AGENTS.md",
                stderr,
            )

    def test_cmd_review_allows_protected_workflow_changes_for_default_main_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            workflow_dir = root / ".cowork-flow"
            task_dir = workflow_dir / "tasks" / "05-19-demo"
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (workflow_dir / ".developer").parent.mkdir(parents=True, exist_ok=True)
            (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
            self._write_allowed_file_task(root, task_dir, "in_progress", allowed_files=("AGENTS.md",))
            self._write_session_task(root)
            self._commit_all(root, "baseline")
            (root / "AGENTS.md").write_text("# Rules changed by coordinator\n", encoding="utf-8")

            review_result, _review_stdout, review_stderr = self._run_review(root)
            complete_result, _complete_stdout, complete_stderr = self._run_complete(root)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(0, review_result, review_stderr)
            self.assertEqual(0, complete_result, complete_stderr)
            self.assertEqual("completed", data["status"])

    def test_cmd_review_rejects_coordinator_flag_for_bound_subagent_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._write_bound_subagent_review_fixture(root)

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with (
                        contextlib.redirect_stdout(io.StringIO()),
                        contextlib.redirect_stderr(io.StringIO()) as stderr,
                    ):
                        result = self.task.cmd_review(
                            argparse.Namespace(
                                dir=None,
                                execution_mode="coordinator",
                                execution_assignment=None,
                                execution_task_dir=None,
                                execution_prompt_file=None,
                                execution_context_file=None,
                            )
                        )
            finally:
                os.chdir(previous_cwd)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(1, result, stderr.getvalue())
            self.assertEqual("in_progress", data["status"])
            self.assertIn("Protected workflow/spec file changed outside main session", stderr.getvalue())

    def test_checks_scope_git_changes_to_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            outer = Path(temp_dir)
            self._init_git_repo(outer)
            outer_src = outer / "src"
            outer_src.mkdir()
            (outer_src / "outer.py").write_text("VALUE = 'safe'\n", encoding="utf-8")
            self._commit_all(outer, "baseline")
            (outer_src / "outer.py").write_text("VALUE = 'changed'\n", encoding="utf-8")

            nested = outer / "nested-project"
            task_dir = nested / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_allowed_file_task(nested, task_dir, "in_progress")
            checks = importlib.import_module("services.lifecycle_checks")

            result = checks.LifecycleCheckRunner(nested).review(task_dir)

        self.assertFalse(result.blocked)
        self.assertEqual((), result.blockers)

    def test_cmd_review_allows_behavior_change_without_legacy_tdd_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_allowed_file_task(root, task_dir, "in_progress")
            (task_dir / "tdd.jsonl").write_text(
                "this is ignored, not parsed as workflow evidence\n",
                encoding="utf-8",
            )
            self._write_session_task(root)

            result, _stdout, stderr = self._run_review(root)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(0, result, stderr)
            self.assertEqual("review", data["status"])
            self.assertNotIn("TDD", stderr)

    def test_cmd_complete_blocks_without_review_without_status_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_allowed_file_task(root, task_dir, "in_progress")
            self._write_session_task(root)

            result, _stdout, stderr = self._run_complete(root)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(1, result, stderr)
            self.assertEqual("in_progress", data["status"])
            self.assertIsNone(data["completedAt"])
            self.assertIn("Task state transition blocked", stderr)


if __name__ == "__main__":
    unittest.main()
