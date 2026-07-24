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
    def test_task_next_parser_accepts_structured_output_options(self) -> None:
        args = self.task.build_parser().parse_args(
            ["next", "--json", "--intent", "question"]
        )

        self.assertTrue(args.json)
        self.assertEqual("question", args.intent)

    def test_task_next_parser_accepts_archive_intent(self) -> None:
        args = self.task.build_parser().parse_args(
            ["next", "--json", "--intent", "archive"]
        )

        self.assertEqual("archive", args.intent)

    def test_task_next_parser_accepts_doubt_review_intent(self) -> None:
        args = self.task.build_parser().parse_args(
            ["next", "--json", "--intent", "doubt_review"]
        )

        self.assertEqual("doubt_review", args.intent)

    def test_cmd_next_json_outputs_stable_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        result = self.task.cmd_next(
                            argparse.Namespace(
                                dir=None,
                                json=True,
                                intent="question",
                            )
                        )
            finally:
                os.chdir(previous_cwd)

            payload = json.loads(stdout.getvalue())
            self.assertEqual(0, result)
            self.assertEqual("no_task", payload["status"])
            self.assertEqual(
                {
                    "status",
                    "allowedOperations",
                    "requiredArtifacts",
                    "recommendedSkill",
                    "internalProtocols",
                    "blockers",
                },
                set(payload),
            )
            self.assertIn("answer_questions", payload["allowedOperations"])
            self.assertEqual([], payload["internalProtocols"])
            self.assertIsNone(payload["recommendedSkill"])

    def test_cmd_next_json_blocks_implementation_without_active_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        result = self.task.cmd_next(
                            argparse.Namespace(
                                dir=None,
                                json=True,
                                intent="implement",
                            )
                        )
            finally:
                os.chdir(previous_cwd)

            payload = json.loads(stdout.getvalue())
            self.assertEqual(0, result)
            self.assertEqual("no_task", payload["status"])
            self.assertIsNone(payload["recommendedSkill"])
            self.assertIn(
                "intent implement is not allowed while status is no_task",
                payload["blockers"],
            )

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

    def test_cmd_next_does_not_prompt_for_tdd_evidence(self) -> None:
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
            self.assertNotIn("TDD reminder:", output)
            self.assertNotIn("/check.jsonl", output)
            self.assertIn("cowork-implement", output)
            self.assertIn("./.cowork-flow/run subagent init", output)
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

    def test_cmd_next_json_defaults_completed_task_to_archive_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text('{"status": "completed"}\n', encoding="utf-8")
            self._write_session_task(root)

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        result = self.task.cmd_next(
                            argparse.Namespace(dir=None, json=True, intent=None)
                        )
            finally:
                os.chdir(previous_cwd)

            payload = json.loads(stdout.getvalue())
            self.assertEqual(0, result)
            self.assertEqual("completed", payload["status"])
            self.assertIn("archive_task", payload["allowedOperations"])
            self.assertEqual([], payload["blockers"])

    def test_cmd_next_json_blocks_implementation_for_completed_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text('{"status": "completed"}\n', encoding="utf-8")
            self._write_session_task(root)

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        result = self.task.cmd_next(
                            argparse.Namespace(
                                dir=None,
                                json=True,
                                intent="implement",
                            )
                        )
            finally:
                os.chdir(previous_cwd)

            payload = json.loads(stdout.getvalue())
            self.assertEqual(0, result)
            self.assertEqual("completed", payload["status"])
            self.assertIsNone(payload["recommendedSkill"])
            self.assertIn(
                "intent implement is not allowed while status is completed",
                payload["blockers"],
            )

    def test_cmd_next_json_routes_standalone_doubt_review_without_check_protocol(self) -> None:
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
                        result = self.task.cmd_next(
                            argparse.Namespace(
                                dir=None,
                                json=True,
                                intent="doubt_review",
                            )
                        )
            finally:
                os.chdir(previous_cwd)

            payload = json.loads(stdout.getvalue())
            self.assertEqual(0, result)
            self.assertEqual("review", payload["status"])
            self.assertEqual("doubt-review", payload["recommendedSkill"])
            self.assertEqual([], payload["internalProtocols"])
            self.assertEqual([], payload["blockers"])

    def test_cmd_next_text_routes_standalone_doubt_review_without_check_dispatch(self) -> None:
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
                        result = self.task.cmd_next(
                            argparse.Namespace(
                                dir=None,
                                json=False,
                                intent="doubt_review",
                            )
                        )
            finally:
                os.chdir(previous_cwd)

            output = stdout.getvalue()
            self.assertEqual(0, result)
            self.assertIn("standalone doubt review", output)
            self.assertIn("doubt-review", output)
            self.assertNotIn("cowork-check", output)
            self.assertNotIn("subagent init --role check", output)
            self.assertNotIn("subagent bind", output)

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
