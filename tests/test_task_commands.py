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
from types import SimpleNamespace
from unittest.mock import patch


from tests.flow_test_support import FlowScriptTestCase, ROOT, SCRIPTS


class TaskCommandsTest(FlowScriptTestCase):
    def test_cmd_review_handles_idempotent_result_without_protocol_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                '{"status":"review"}\n',
                encoding="utf-8",
            )
            lifecycle_result = SimpleNamespace(
                ok=True,
                code="LIFECYCLE-IDEMPOTENT",
                check_result=None,
            )
            service = SimpleNamespace(
                review=lambda *args, **kwargs: lifecycle_result,
            )
            lifecycle_commands = importlib.import_module(
                "adapters.cli.task_lifecycle_commands"
            )

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    patch.object(
                        lifecycle_commands,
                        "TaskLifecycleService",
                        return_value=service,
                    ),
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    result = self.task.cmd_review(argparse.Namespace(dir=str(task_dir)))
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(0, result)

    def test_context_commands_are_not_public_parser_commands(self) -> None:
        parser = self.task.build_parser()
        for command in ("add-context", "add-planned-file"):
            with self.subTest(command=command):
                with self.assertRaises(SystemExit) as raised:
                    parser.parse_args([command])
                self.assertEqual(2, raised.exception.code)

    def test_cmd_add_context_writes_explicit_planned_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "implement.jsonl").write_text("", encoding="utf-8")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    result = self.task.cmd_add_context(
                        argparse.Namespace(
                            dir=str(task_dir),
                            file="implement",
                            path="src/new_module.py",
                            reason="Planned source",
                            entry_type="planned-file",
                        )
                    )
            finally:
                os.chdir(previous_cwd)

            entries = [
                json.loads(line)
                for line in (task_dir / "implement.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if line
            ]
            self.assertEqual(0, result)
            self.assertEqual("planned-file", entries[0]["type"])
            self.assertFalse((root / "src" / "new_module.py").exists())

    def test_cmd_add_planned_file_writes_planned_file_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "implement.jsonl").write_text("", encoding="utf-8")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()) as stdout,
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    result = self.task.cmd_add_planned_file(
                        argparse.Namespace(
                            dir=str(task_dir),
                            file="implement",
                            path="src/new_module.py",
                            reason="Planned source",
                        )
                    )
            finally:
                os.chdir(previous_cwd)

            entries = [
                json.loads(line)
                for line in (task_dir / "implement.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if line
            ]
            self.assertEqual(0, result)
            self.assertIn("Added planned-file", stdout.getvalue())
            self.assertEqual("planned-file", entries[0]["type"])
            self.assertFalse((root / "src" / "new_module.py").exists())

    def test_cmd_validate_prints_planned_file_hint_for_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "implement.jsonl").write_text(
                json.dumps({"file": "src/new_module.py", "reason": "Planned source"})
                + "\n",
                encoding="utf-8",
            )

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()) as stdout,
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    result = self.task.cmd_validate(
                        argparse.Namespace(dir=str(task_dir))
                    )
            finally:
                os.chdir(previous_cwd)

            output = stdout.getvalue()
            self.assertEqual(1, result)
            self.assertIn("File not found: src/new_module.py", output)
            self.assertIn("planned-file", output)
            self.assertIn('"type": "planned-file"', output)

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
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
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
            self.assertIn("planned-file", stderr.getvalue())

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

    def test_cmd_create_sets_active_task_for_current_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()
            date_prefix = datetime.now().strftime("%m-%d")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}),
                    contextlib.redirect_stdout(io.StringIO()),
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

            session = json.loads(
                (
                    root
                    / ".cowork-flow"
                    / ".runtime"
                    / "sessions"
                    / "main.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(0, result)
            self.assertEqual(
                f".cowork-flow/tasks/{date_prefix}-demo-task",
                session["active_task_path"],
            )

    def test_cmd_create_without_developer_prefers_assignee_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    patch.dict(os.environ, {}, clear=True),
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_create(
                        argparse.Namespace(
                            title="Demo task",
                            slug="demo-task",
                            assignee=None,
                            priority="P2",
                            description=None,
                            parent=None,
                        )
                    )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(1, result)
            self.assertIn("--assignee <name>", stderr.getvalue())
            self.assertNotIn("Run init_developer.py first", stderr.getvalue())

    def test_task_start_blockers_require_decision_anchor_and_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text("{}", encoding="utf-8")

            blockers = self.task._task_start_blockers(task_dir)

        self.assertIn("decision-anchor.md is missing or empty", blockers)
        self.assertIn("implement.jsonl is missing or empty", blockers)
        self.assertNotIn("check.jsonl is missing or empty", blockers)
        self.assertNotIn("debug.jsonl is missing or empty", blockers)

    def test_task_start_blockers_clear_when_decision_anchor_and_context_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text("{}", encoding="utf-8")
            (task_dir / "decision-anchor.md").write_text("# Demo\n", encoding="utf-8")
            (task_dir / "implement.jsonl").write_text(
                '{"file": "AGENTS.md"}\n', encoding="utf-8"
            )

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
            (task_dir / "decision-anchor.md").write_text("# Demo\n", encoding="utf-8")
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

    def test_cmd_start_auto_creates_task_local_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (task_dir / "task.json").write_text('{"status": "planning"}\n', encoding="utf-8")
            (task_dir / "decision-anchor.md").write_text("# Demo\n", encoding="utf-8")
            (task_dir / "implement.jsonl").write_text(
                json.dumps(
                    {
                        "file": ".cowork-flow/tasks/05-19-demo/report.md",
                        "reason": "Task-local report",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            for name in ("check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}),
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    result = self.task.cmd_start(
                        argparse.Namespace(dir=".cowork-flow/tasks/05-19-demo")
                    )
            finally:
                os.chdir(previous_cwd)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(0, result)
            self.assertEqual("in_progress", data["status"])
            self.assertTrue((task_dir / "report.md").is_file())

    def test_cmd_start_keeps_non_task_missing_file_blocking_with_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (task_dir / "task.json").write_text('{"status": "planning"}\n', encoding="utf-8")
            (task_dir / "decision-anchor.md").write_text("# Demo\n", encoding="utf-8")
            (task_dir / "implement.jsonl").write_text(
                json.dumps({"file": "src/new_module.py", "reason": "Planned source"})
                + "\n",
                encoding="utf-8",
            )
            for name in ("check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}),
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_start(
                        argparse.Namespace(dir=".cowork-flow/tasks/05-19-demo")
                    )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(1, result)
            self.assertFalse((root / "src" / "new_module.py").exists())
            self.assertIn("Task context validation failed", stderr.getvalue())
            self.assertIn("planned-file", stderr.getvalue())
            self.assertIn("task next <dir> --validate", stderr.getvalue())
            self.assertNotIn("task validate", stderr.getvalue())

    def test_cmd_start_requires_session_context_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (task_dir / "task.json").write_text("{}", encoding="utf-8")
            (task_dir / "decision-anchor.md").write_text("# Demo\n", encoding="utf-8")
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

    def test_cmd_start_updates_task_status_to_in_progress(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (task_dir / "task.json").write_text('{"status": "planning"}\n', encoding="utf-8")
            (task_dir / "decision-anchor.md").write_text("# Demo\n", encoding="utf-8")
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}),
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    result = self.task.cmd_start(
                        argparse.Namespace(dir=".cowork-flow/tasks/05-19-demo")
                    )
            finally:
                os.chdir(previous_cwd)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(0, result)
            self.assertEqual("in_progress", data["status"])
