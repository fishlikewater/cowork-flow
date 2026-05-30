from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"


class FlowScriptPathsTest(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        self.paths = importlib.import_module("common.paths")
        self.task = importlib.import_module("task")
        self.git_context = importlib.import_module("common.git_context")

    def _cleanup_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in (
            "task",
            "common.active_task",
            "common.git_context",
            "common.paths",
            "common",
        ):
            sys.modules.pop(module_name, None)

    def _write_session_task(
        self,
        root: Path,
        task_path: str = ".cowork-flow/tasks/05-19-demo",
        context_key: str = "main",
    ) -> None:
        sessions_dir = root / ".cowork-flow" / ".runtime" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        (sessions_dir / f"{context_key}.json").write_text(
            f'{{"active_task_path": "{task_path}"}}\n',
            encoding="utf-8",
        )

    def test_workflow_and_agent_directory_constants_are_current(self) -> None:
        self.assertEqual(".cowork-flow", self.paths.DIR_WORKFLOW)
        self.assertEqual(".agent", self.paths.DIR_AGENT)
        self.assertEqual("changes", self.paths.DIR_CHANGES)

    def test_repo_root_detection_uses_cowork_flow_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            nested = root / "src" / "feature"
            nested.mkdir(parents=True)
            (root / ".cowork-flow").mkdir()

            self.assertEqual(root, self.paths.get_repo_root(nested))

    def test_task_relative_paths_accept_cowork_flow_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-18-demo"
            task_dir.mkdir(parents=True)

            resolved = self.task._resolve_task_dir(
                ".cowork-flow/tasks/05-18-demo",
                root,
            )

            self.assertEqual(task_dir, resolved)

    def test_cmd_create_adds_date_prefix_to_plain_slug(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()
            date_prefix = datetime.now().strftime("%m-%d")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()) as stdout,
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    result = self.task.cmd_create(
                        argparse.Namespace(
                            title="Demo task",
                            slug="demo-task",
                            assignee="codex",
                            priority="P2",
                            description=None,
                            parent=None,
                        )
                    )
            finally:
                os.chdir(previous_cwd)

            dir_name = f"{date_prefix}-demo-task"
            self.assertEqual(0, result)
            self.assertTrue((root / ".cowork-flow" / "tasks" / dir_name / "task.json").is_file())
            self.assertIn(dir_name, stdout.getvalue())

    def test_cmd_create_keeps_existing_date_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()
            date_prefix = datetime.now().strftime("%m-%d")
            slug = f"{date_prefix}-demo-task"

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()) as stdout,
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    result = self.task.cmd_create(
                        argparse.Namespace(
                            title="Demo task",
                            slug=slug,
                            assignee="codex",
                            priority="P2",
                            description=None,
                            parent=None,
                        )
                    )
            finally:
                os.chdir(previous_cwd)

            task_dir = root / ".cowork-flow" / "tasks" / slug
            doubled = root / ".cowork-flow" / "tasks" / f"{date_prefix}-{slug}"
            self.assertEqual(0, result)
            self.assertTrue((task_dir / "task.json").is_file())
            self.assertFalse(doubled.exists())
            self.assertIn(slug, stdout.getvalue())

    def test_default_context_references_new_skill_directory(self) -> None:
        self.assertEqual(
            ".agent/skills/finish-work/SKILL.md",
            self.task._skill_path("finish-work"),
        )

    def test_default_implement_context_includes_workflow_gates(self) -> None:
        files = [entry["file"] for entry in self.task.get_implement_base()]

        self.assertIn("AGENTS.md", files)
        self.assertIn(".cowork-flow/workflow.md", files)
        self.assertIn(".cowork-flow/spec/guides/index.md", files)
        self.assertIn(".cowork-flow/spec/guides/pre-implementation-checklist.md", files)

    def test_task_start_blockers_require_prd_and_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text("{}", encoding="utf-8")

            blockers = self.task._task_start_blockers(task_dir)

            self.assertIn("prd.md is missing or empty", blockers)
            self.assertIn("implement.jsonl is missing or empty", blockers)
            self.assertIn("check.jsonl is missing or empty", blockers)
            self.assertIn("debug.jsonl is missing or empty", blockers)

    def test_task_start_blockers_clear_when_prd_and_context_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text("{}", encoding="utf-8")
            (task_dir / "prd.md").write_text("# Demo\n", encoding="utf-8")
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")

            self.assertEqual([], self.task._task_start_blockers(task_dir))

    def test_cmd_start_blocks_unprepared_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text("{}", encoding="utf-8")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    result = self.task.cmd_start(
                        argparse.Namespace(dir=".cowork-flow/tasks/05-19-demo")
                    )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(1, result)
            self.assertFalse((root / ".cowork-flow" / (".current" + "-task")).exists())

    def test_cmd_start_blocks_invalid_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (task_dir / "task.json").write_text("{}", encoding="utf-8")
            (task_dir / "prd.md").write_text("# Demo\n", encoding="utf-8")
            (task_dir / "implement.jsonl").write_text("not-json\n", encoding="utf-8")
            for name in ("check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    result = self.task.cmd_start(
                        argparse.Namespace(dir=".cowork-flow/tasks/05-19-demo")
                    )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(1, result)
            self.assertFalse((root / ".cowork-flow" / (".current" + "-task")).exists())

    def test_cmd_start_requires_session_context_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (task_dir / "task.json").write_text("{}", encoding="utf-8")
            (task_dir / "prd.md").write_text("# Demo\n", encoding="utf-8")
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(
                    io.StringIO()
                ), contextlib.redirect_stderr(io.StringIO()):
                    result = self.task.cmd_start(
                        argparse.Namespace(dir=".cowork-flow/tasks/05-19-demo")
                    )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(1, result)
            self.assertFalse((root / ".cowork-flow" / (".current" + "-task")).exists())

    def test_cmd_current_prints_session_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()
            self._write_session_task(root)

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        result = self.task.cmd_current(argparse.Namespace())
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(0, result)
            self.assertIn("Active task: .cowork-flow/tasks/05-19-demo", stdout.getvalue())

    def test_cmd_current_requires_session_context_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {}, clear=True):
                    with contextlib.redirect_stderr(io.StringIO()) as stderr:
                        result = self.task.cmd_current(argparse.Namespace())
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(1, result)
            self.assertIn("Missing session context", stderr.getvalue())

    def test_task_archive_resumes_when_source_and_destination_match(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow_dir = root / ".cowork-flow"
            tasks_dir = workflow_dir / "tasks"
            task_dir = tasks_dir / "05-19-demo"
            task_dir.mkdir(parents=True)
            (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                '{"name": "demo", "status": "in_progress", "assignee": "codex"}',
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
                    result = self.task.cmd_archive(
                        argparse.Namespace(name="05-19-demo", no_commit=True)
                    )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(0, result, stderr.getvalue())
            self.assertFalse(task_dir.exists())
            self.assertTrue((archive_dest / "task.json").is_file())
            self.assertIn(".cowork-flow/tasks/archive/", stdout.getvalue())

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
            (task_dir / "prd.md").write_text("# Demo\n", encoding="utf-8")
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
            self.assertIn("Read active task PRD: .cowork-flow/tasks/05-19-demo/prd.md", output)
            self.assertIn("List task context before reading details: ./.cowork-flow/run task list-context .cowork-flow/tasks/05-19-demo", output)
            self.assertIn("Read current plan status: .cowork-flow/plans/2026-05-19-demo.md", output)
            self.assertIn("Do not bulk-read .cowork-flow/spec/ or workspace journals", output)

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
            (task_dir / "prd.md").write_text("# Secret PRD body should not appear\n", encoding="utf-8")
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")

            with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                context = self.git_context.get_context_json(root)
                record_context = self.git_context.get_context_record_json(root)

            self.assertIn("activeTask", record_context)
            self.assertNotIn("currentTask", record_context)
            self.assertEqual(
                ".cowork-flow/tasks/05-19-demo",
                record_context["activeTask"]["path"],
            )
            self.assertIn("resumeChecklist", context)
            self.assertEqual(
                "./.cowork-flow/run resume",
                context["resumeChecklist"]["commands"][0],
            )
            self.assertIn(
                ".cowork-flow/tasks/05-19-demo/prd.md",
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
            (task_dir / "prd.md").write_text("# Secret PRD body should not appear\n", encoding="utf-8")
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")

            env = os.environ.copy()
            env["COWORK_FLOW_CONTEXT_ID"] = "main"
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "resume.py")],
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )

            self.assertEqual(0, result.returncode)
            self.assertIn("COWORK-FLOW RESUME", result.stdout)
            self.assertIn("## RESUME CHECKLIST", result.stdout)
            self.assertNotIn("Secret PRD body", result.stdout)


if __name__ == "__main__":
    unittest.main()
