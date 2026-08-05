from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


from tests.flow_test_support import FlowScriptTestCase, ROOT, SCRIPTS


class TaskArchiveCommandsTest(FlowScriptTestCase):
    def test_is_git_dirty_checks_porcelain_output(self) -> None:
        archive_commands = importlib.import_module(
            "adapters.cli.task_archive_commands"
        )

        for status, expected in (("", False), (" M src/example.py\n", True)):
            with self.subTest(status=status), patch.object(
                archive_commands,
                "_run_git_command",
                return_value=(0, status, ""),
            ):
                self.assertEqual(
                    expected,
                    archive_commands.is_git_dirty(Path("/repo")),
                )

    def test_task_archive_resumes_when_source_and_destination_match(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow_dir = root / ".cowork-flow"
            tasks_dir = workflow_dir / "tasks"
            task_dir = tasks_dir / "05-19-demo"
            task_dir.mkdir(parents=True)
            (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                '{"name": "demo", "status": "completed", "assignee": "codex"}',
                encoding="utf-8",
            )
            month = datetime.now().strftime("%Y-%m")
            archive_dest = tasks_dir / "archive" / month / "05-19-demo"
            archive_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(task_dir, archive_dest)

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()) as stdout,
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_archive(argparse.Namespace(name="05-19-demo"))
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(0, result, stderr.getvalue())
            self.assertFalse(task_dir.exists())
            self.assertTrue((archive_dest / "task.json").is_file())
            self.assertIn(".cowork-flow/tasks/archive/", stdout.getvalue())

    def test_task_archive_archives_linked_active_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow_dir = root / ".cowork-flow"
            tasks_dir = workflow_dir / "tasks"
            task_dir = tasks_dir / "05-19-demo"
            task_dir.mkdir(parents=True)
            (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                '{"name": "demo", "status": "completed", "assignee": "codex"}',
                encoding="utf-8",
            )
            change_dir = self._write_l2_change_fixture(
                root,
                level="L1",
                task_link=".cowork-flow/tasks/05-19-demo",
            )
            month = datetime.now().strftime("%Y-%m")
            task_archive_dest = tasks_dir / "archive" / month / "05-19-demo"
            change_archive_dest = workflow_dir / "changes" / "archive" / month / change_dir.name

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()) as stdout,
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_archive(
                        argparse.Namespace(name="05-19-demo", commit=False)
                    )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(0, result, stderr.getvalue())
            self.assertFalse(task_dir.exists())
            self.assertTrue((task_archive_dest / "task.json").is_file())
            self.assertFalse(change_dir.exists())
            self.assertTrue((change_archive_dest / "change.yaml").is_file())
            metadata = (change_archive_dest / "change.yaml").read_text(encoding="utf-8")
            self.assertIn("status: archived", metadata)
            self.assertIn("task: archive/", metadata)
            self.assertIn("05-19-demo", metadata)
            self.assertIn("Archived linked change: 05-19-demo-change", stderr.getvalue())
            self.assertIn(".cowork-flow/tasks/archive/", stdout.getvalue())

    def test_task_archive_rolls_back_task_when_linked_change_archive_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow_dir = root / ".cowork-flow"
            tasks_dir = workflow_dir / "tasks"
            task_dir = tasks_dir / "05-19-demo"
            task_dir.mkdir(parents=True)
            (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                '{"name": "demo", "status": "completed", "assignee": "codex"}',
                encoding="utf-8",
            )
            change_dir = self._write_l2_change_fixture(
                root,
                level="L1",
                task_link=".cowork-flow/tasks/05-19-demo",
            )
            month = datetime.now().strftime("%Y-%m")
            task_archive_dest = tasks_dir / "archive" / month / "05-19-demo"

            change_module = importlib.import_module("adapters.cli.change")
            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.object(change_module, "archive_change_by_slug", return_value=None):
                    with (
                        contextlib.redirect_stdout(io.StringIO()),
                        contextlib.redirect_stderr(io.StringIO()) as stderr,
                    ):
                        result = self.task.cmd_archive(
                            argparse.Namespace(name="05-19-demo", commit=False)
                        )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(1, result)
            self.assertTrue(task_dir.is_dir())
            self.assertFalse(task_archive_dest.exists())
            self.assertTrue(change_dir.is_dir())
            self.assertIn("Failed to archive linked change", stderr.getvalue())

    def _write_multi_change_archive_fixture(self, root: Path):
        workflow_dir = root / ".cowork-flow"
        tasks_dir = workflow_dir / "tasks"
        task_dir = tasks_dir / "05-19-demo"
        task_dir.mkdir(parents=True)
        (workflow_dir / ".developer").write_text(
            "name=codex\n",
            encoding="utf-8",
        )
        (task_dir / "task.json").write_text(
            '{"name": "demo", "status": "completed", "assignee": "codex"}',
            encoding="utf-8",
        )
        first_change = self._write_l2_change_fixture(
            root,
            level="L1",
            task_link=".cowork-flow/tasks/05-19-demo",
        )
        second_change = first_change.parent / "05-19-z-change"
        shutil.copytree(first_change, second_change)
        second_metadata = (second_change / "change.yaml").read_text(
            encoding="utf-8"
        )
        (second_change / "change.yaml").write_text(
            second_metadata.replace(
                "slug: 05-19-demo-change",
                "slug: 05-19-z-change",
            ),
            encoding="utf-8",
        )
        changes = (first_change, second_change)
        metadata = {
            change.name: (change / "change.yaml").read_bytes()
            for change in changes
        }
        return workflow_dir, tasks_dir, task_dir, changes, metadata

    def _archive_with_second_change_failure(
        self,
        root: Path,
        second_change: Path,
    ):
        change_module = importlib.import_module("adapters.cli.change")
        archive_change = change_module.archive_change_by_slug

        def fail_second_change(repo_root, slug):
            if slug == second_change.name:
                return None
            return archive_change(repo_root, slug)

        previous_cwd = Path.cwd()
        try:
            os.chdir(root)
            with patch.object(
                change_module,
                "archive_change_by_slug",
                side_effect=fail_second_change,
            ):
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_archive(
                        argparse.Namespace(name="05-19-demo", commit=False)
                    )
        finally:
            os.chdir(previous_cwd)
        return result, stderr.getvalue()

    def test_task_archive_rolls_back_previously_archived_linked_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = self._write_multi_change_archive_fixture(root)
            workflow_dir, tasks_dir, task_dir, changes, metadata = fixture
            result, stderr = self._archive_with_second_change_failure(
                root,
                changes[1],
            )

            month = datetime.now().strftime("%Y-%m")
            self.assertEqual(1, result)
            self.assertTrue(task_dir.is_dir())
            self.assertFalse((tasks_dir / "archive" / month / task_dir.name).exists())
            for change in changes:
                self.assertTrue(change.is_dir())
                self.assertEqual(
                    metadata[change.name],
                    (change / "change.yaml").read_bytes(),
                )
                self.assertFalse(
                    (
                        workflow_dir
                        / "changes"
                        / "archive"
                        / month
                        / change.name
                    ).exists()
                )
            self.assertIn("Failed to archive linked change", stderr)
            self.assertNotIn("Archived linked change", stderr)

    def test_task_archive_does_not_commit_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            workflow_dir = root / ".cowork-flow"
            tasks_dir = workflow_dir / "tasks"
            task_dir = tasks_dir / "05-19-demo"
            task_dir.mkdir(parents=True)
            (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                '{"name": "demo", "status": "completed", "assignee": "codex"}',
                encoding="utf-8",
            )
            baseline = self._commit_all(root, "initial")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_archive(
                        argparse.Namespace(name="05-19-demo", commit=False)
                    )
            finally:
                os.chdir(previous_cwd)

            head = self._run_git(root, "rev-parse", "HEAD")
            self.assertEqual(0, result, stderr.getvalue())
            self.assertEqual(baseline, head)
            self.assertNotIn("Auto-committed", stderr.getvalue())

    def test_task_archive_rejects_removed_no_commit_flag(self) -> None:
        with patch.object(sys, "argv", ["task.py", "archive", "05-19-demo", "--no-commit"]):
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                with self.assertRaises(SystemExit) as raised:
                    self.task.main()

        self.assertEqual(2, raised.exception.code)
        self.assertIn("invalid choice: 'archive'", stderr.getvalue())

    def test_task_archive_commit_flag_auto_commits(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            workflow_dir = root / ".cowork-flow"
            tasks_dir = workflow_dir / "tasks"
            task_dir = tasks_dir / "05-19-demo"
            task_dir.mkdir(parents=True)
            (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                '{"name": "demo", "status": "completed", "assignee": "codex"}',
                encoding="utf-8",
            )
            baseline = self._commit_all(root, "initial")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_archive(
                        argparse.Namespace(name="05-19-demo", commit=True)
                    )
            finally:
                os.chdir(previous_cwd)

            head = self._run_git(root, "rev-parse", "HEAD")
            message = self._run_git(root, "log", "-1", "--pretty=%s")
            self.assertEqual(0, result, stderr.getvalue())
            self.assertNotEqual(baseline, head)
            self.assertEqual("chore(task): archive 05-19-demo", message)
            self.assertIn("Auto-committed", stderr.getvalue())

    def test_placeholder_developer_identity_is_not_initialized(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow_dir = root / ".cowork-flow"
            workflow_dir.mkdir()
            (workflow_dir / ".developer").write_text(
                "name=<your-developer-name>\ninitialized_at=<YYYY-MM-DD>\n",
                encoding="utf-8",
            )

            self.assertIsNone(self.paths.get_developer(root))
            self.assertFalse(self.paths.check_developer(root))

    def test_init_developer_replaces_placeholder_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow_dir = root / ".cowork-flow"
            workflow_dir.mkdir()
            (workflow_dir / ".developer").write_text(
                "name=<your-developer-name>\ninitialized_at=<YYYY-MM-DD>\n",
                encoding="utf-8",
            )
            init_developer = importlib.import_module("adapters.cli.init_developer")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.object(
                    sys,
                    "argv",
                    ["init_developer.py", "codex"],
                ):
                    with self.assertRaises(SystemExit) as raised:
                        init_developer.main()
            finally:
                os.chdir(previous_cwd)
                sys.modules.pop("adapters.cli.init_developer", None)

            self.assertEqual(0, raised.exception.code)
            self.assertEqual("codex", self.paths.get_developer(root))
            self.assertFalse((workflow_dir / "workspace").exists())

    def test_context_text_includes_minimal_resume_checklist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow_dir = root / ".cowork-flow"
            task_dir = workflow_dir / "tasks" / "05-19-demo"
            plan_file = workflow_dir / "plans" / "2026-05-19-demo.md"
            task_dir.mkdir(parents=True)
            plan_file.parent.mkdir(parents=True)
            (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
            self._write_session_task(root)
            (task_dir / "task.json").write_text(
                '{"name": "demo", "status": "in_progress", "assignee": "codex"}',
                encoding="utf-8",
            )
            (task_dir / "decision-anchor.md").write_text("# Demo\n", encoding="utf-8")
            (task_dir / "implement.jsonl").write_text(
                '{"file": ".cowork-flow/plans/2026-05-19-demo.md"}\n',
                encoding="utf-8",
            )
            for name in ("check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")
            plan_file.write_text(
                "## Current Execution Status\nResume from task 2.\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                output = self.git_context.get_context_text(root)

            self.assertIn("## RESUME CHECKLIST", output)
            self.assertIn(
                "Recovery entrypoint (rerun only if context is stale): ./.cowork-flow/run resume",
                output,
            )
            self.assertIn("Read active task decision-anchor: .cowork-flow/tasks/05-19-demo/decision-anchor.md", output)
            self.assertIn("Read task context JSONL files under .cowork-flow/tasks/05-19-demo directly", output)
            self.assertIn("Read current plan status: .cowork-flow/plans/2026-05-19-demo.md", output)
            self.assertIn("Do not bulk-read .cowork-flow/spec/", output)
            self.assertNotIn("workspace journals", output)

    def test_context_json_includes_resume_checklist_without_file_contents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow_dir = root / ".cowork-flow"
            task_dir = workflow_dir / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
            self._write_session_task(root)
            (task_dir / "task.json").write_text(
                '{"name": "demo", "status": "in_progress", "assignee": "codex"}',
                encoding="utf-8",
            )
            (task_dir / "decision-anchor.md").write_text("# Secret decision-anchor body should not appear\n", encoding="utf-8")
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")

            with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                context = self.git_context.get_context_json(root)

            self.assertNotIn("journal", context)
            self.assertIn("resumeChecklist", context)
            self.assertEqual(
                "./.cowork-flow/run resume",
                context["resumeChecklist"]["commands"][0],
            )
            self.assertIn(
                ".cowork-flow/tasks/05-19-demo/decision-anchor.md",
                context["resumeChecklist"]["readFiles"],
            )

    def test_resume_script_outputs_resume_checklist_without_file_contents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow_dir = root / ".cowork-flow"
            task_dir = workflow_dir / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
            self._write_session_task(root)
            (task_dir / "task.json").write_text(
                '{"name": "demo", "status": "in_progress", "assignee": "codex"}',
                encoding="utf-8",
            )
            (task_dir / "decision-anchor.md").write_text("# Secret decision-anchor body should not appear\n", encoding="utf-8")
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")

            env = os.environ.copy()
            env["COWORK_FLOW_CONTEXT_ID"] = "main"
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "adapters" / "cli" / "resume.py")],
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )

            self.assertEqual(0, result.returncode)
            self.assertIn("COWORK-FLOW RESUME", result.stdout)
            self.assertIn("## RESUME CHECKLIST", result.stdout)
            self.assertNotIn("Secret decision-anchor body", result.stdout)


if __name__ == "__main__":
    unittest.main()
