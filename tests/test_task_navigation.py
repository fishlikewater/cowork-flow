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


class TaskNavigationTest(FlowScriptTestCase):
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

    def test_cmd_next_reports_no_task_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        result = self.task.cmd_next(argparse.Namespace(dir=None))
            finally:
                os.chdir(previous_cwd)

            output = stdout.getvalue()
            self.assertEqual(0, result)
            self.assertIn("Status: no_task", output)
            self.assertIn("Next action: create or start a task before repository changes", output)
            self.assertIn("./.cowork-flow/run task create", output)
            self.assertNotIn("delegated prompt", output)
            self.assertFalse((root / ".cowork-flow" / "tasks").exists())

    def test_cmd_next_reports_planning_blockers_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text('{"status": "planning"}\n', encoding="utf-8")
            self._write_session_task(root)

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        result = self.task.cmd_next(argparse.Namespace(dir=None))
            finally:
                os.chdir(previous_cwd)

            output = stdout.getvalue()
            self.assertEqual(0, result)
            self.assertIn("Task: .cowork-flow/tasks/05-19-demo", output)
            self.assertIn("Status: planning", output)
            self.assertIn("Blockers:", output)
            self.assertIn("decision-anchor.md is missing or empty", output)
            self.assertIn("./.cowork-flow/run task init-context", output)
            self.assertFalse((root / ".cowork-flow" / (".current" + "-task")).exists())

    def test_cmd_next_reports_in_progress_fixed_agent_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text('{"status": "in_progress"}\n', encoding="utf-8")
            self._write_session_task(root)

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        result = self.task.cmd_next(argparse.Namespace(dir=None))
            finally:
                os.chdir(previous_cwd)

            output = stdout.getvalue()
            self.assertEqual(0, result)
            self.assertIn("Status: in_progress", output)
            self.assertIn("Next action: execute implementation plan", output)
            self.assertIn("cowork-implement", output)
            self.assertIn("./.cowork-flow/run subagent init", output)
            self.assertIn("cowork_runtime_context_id", output)

    def test_cmd_next_prints_tdd_reminder_without_blocking_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (task_dir / "task.json").write_text('{"status": "in_progress"}\n', encoding="utf-8")
            (task_dir / "decision-anchor.md").write_text(
                "# Demo\n\n## 验收标准\n\n- AC-001: workflow behavior changes require TDD first.\n",
                encoding="utf-8",
            )
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")
            self._write_session_task(root)

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        result = self.task.cmd_next(argparse.Namespace(dir=None))
            finally:
                os.chdir(previous_cwd)

            output = stdout.getvalue()
            self.assertEqual(0, result)
            self.assertIn("Status: in_progress", output)
            self.assertIn("Next action: execute implementation plan", output)
            self.assertIn("TDD reminder:", output)
            self.assertIn("/tdd.jsonl before modifying code", output)
            self.assertIn("cowork-implement", output)
            self.assertIn("./.cowork-flow/run subagent init", output)
            self.assertNotIn("TDD red evidence is missing", output)

    def test_cmd_next_allows_implementation_after_tdd_red_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (task_dir / "task.json").write_text('{"status": "in_progress"}\n', encoding="utf-8")
            (task_dir / "decision-anchor.md").write_text(
                "# Demo\n\n## 验收标准\n\n- AC-001: workflow behavior changes require TDD first.\n",
                encoding="utf-8",
            )
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")
            (task_dir / "tdd.jsonl").write_text(
                json.dumps(
                    {
                        "acceptanceId": "AC-001",
                        "testFile": "tests/test_flow_script_paths.py",
                        "testName": "FlowScriptPathsTest.test_cmd_next_prints_tdd_reminder_without_blocking_dispatch",
                        "redCommand": "python -m unittest tests.test_flow_script_paths.FlowScriptPathsTest.test_cmd_next_prints_tdd_reminder_without_blocking_dispatch -v",
                        "redExitCode": 1,
                        "redOutputExcerpt": "TDD reminder",
                        "failureReason": "target behavior was not implemented",
                        "whyThisTestMatters": "It keeps implementation guidance visible without blocking fixed-agent dispatch.",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            self._write_session_task(root)

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        result = self.task.cmd_next(argparse.Namespace(dir=None))
            finally:
                os.chdir(previous_cwd)

            output = stdout.getvalue()
            self.assertEqual(0, result)
            self.assertIn("Next action: execute implementation plan", output)
            self.assertIn("TDD reminder:", output)
            self.assertIn("cowork-implement", output)
            self.assertNotIn("TDD red evidence is missing", output)

    def test_cmd_next_reports_review_check_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text('{"status": "review"}\n', encoding="utf-8")
            self._write_session_task(root)

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        result = self.task.cmd_next(argparse.Namespace(dir=None))
            finally:
                os.chdir(previous_cwd)

            output = stdout.getvalue()
            self.assertEqual(0, result)
            self.assertIn("Status: review", output)
            self.assertIn("Next action: verify implementation", output)
            self.assertIn("cowork-check", output)
            self.assertIn("./.cowork-flow/run task complete .cowork-flow/tasks/05-19-demo", output)

    def test_cmd_next_completed_mentions_linked_change_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text('{"status": "completed"}\n', encoding="utf-8")
            self._write_l2_change_fixture(
                root,
                level="L1",
                task_link=".cowork-flow/tasks/05-19-demo",
            )
            self._write_session_task(root)

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        result = self.task.cmd_next(argparse.Namespace(dir=None))
            finally:
                os.chdir(previous_cwd)

            output = stdout.getvalue()
            self.assertEqual(0, result)
            self.assertIn("task archive 05-19-demo", output)
            self.assertIn("change archive 05-19-demo-change", output)

    def test_cmd_next_routes_active_ready_planning_task_to_implementation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (task_dir / "task.json").write_text('{"status": "planning"}\n', encoding="utf-8")
            (task_dir / "decision-anchor.md").write_text("# Demo\n", encoding="utf-8")
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")
            self._write_session_task(root)

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        result = self.task.cmd_next(argparse.Namespace(dir=None))
            finally:
                os.chdir(previous_cwd)

            output = stdout.getvalue()
            self.assertEqual(0, result)
            self.assertIn("Next action: execute implementation plan", output)
            self.assertIn("cowork-implement", output)
            self.assertIn("Blockers: none", output)
            self.assertNotIn("implement.jsonl: [OK]", output)

    def test_cmd_next_routes_inactive_ready_planning_task_to_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (task_dir / "task.json").write_text('{"status": "planning"}\n', encoding="utf-8")
            (task_dir / "decision-anchor.md").write_text("# Demo\n", encoding="utf-8")
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")
            self._write_rules_file(root, [])

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        result = self.task.cmd_next(
                            argparse.Namespace(dir=".cowork-flow/tasks/05-19-demo")
                        )
            finally:
                os.chdir(previous_cwd)

            output = stdout.getvalue()
            self.assertEqual(0, result)
            self.assertIn("Source: argument", output)
            self.assertIn("Next action: start task", output)
            self.assertIn("./.cowork-flow/run task start .cowork-flow/tasks/05-19-demo", output)
