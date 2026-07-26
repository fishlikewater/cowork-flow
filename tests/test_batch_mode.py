from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.flow_test_support import FlowScriptTestCase


class BatchModeFailClosedTest(FlowScriptTestCase):
    def _task(self, root: Path) -> Path:
        task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
        task_dir.mkdir(parents=True)
        (task_dir / "task.json").write_text(
            json.dumps(
                {
                    "name": "07-10-demo",
                    "status": "planning",
                    "children": [],
                    "parent": None,
                }
            ),
            encoding="utf-8",
        )
        return task_dir

    def _ready_task(self, root: Path) -> Path:
        task_dir = self._task(root)
        (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
        (task_dir / "decision-anchor.md").write_text(
            "# Demo\n\n## 验收标准\n- AC-001: fail closed\n",
            encoding="utf-8",
        )
        for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
            (task_dir / name).write_text(
                '{"file":"AGENTS.md","reason":"rules"}\n',
                encoding="utf-8",
            )
        self._write_rules_file(root, [])
        return task_dir

    @staticmethod
    def _run_in_repo(root: Path, command, args) -> tuple[int, str]:
        stdout = io.StringIO()
        previous_cwd = Path.cwd()
        try:
            os.chdir(root)
            with contextlib.redirect_stdout(stdout):
                result = command(args)
        finally:
            os.chdir(previous_cwd)
        return result, stdout.getvalue()

    @staticmethod
    def _write_start_result(
        root: Path,
        task_dir: Path,
        state: dict,
    ) -> Path:
        task_json = task_dir / "task.json"
        task_data = json.loads(task_json.read_text(encoding="utf-8"))
        task_data["status"] = "in_progress"
        task_json.write_text(
            json.dumps(task_data, ensure_ascii=False),
            encoding="utf-8",
        )
        payload_path = root / "result.json"
        payload_path.write_text(
            json.dumps(
                {
                    "action_id": state["next_action"]["action_id"],
                    "type": "start_task",
                    "outcome": "success",
                    "task_status": "in_progress",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return payload_path

    def test_batch_runtime_emits_first_host_action_without_completion(self) -> None:
        batch_mode = importlib.import_module("common.task.batch_mode")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._task(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                result = batch_mode.run_batch_entry(
                    root,
                    task_dir,
                    argparse.Namespace(auto=True, approved=True),
                )

            state = json.loads(stdout.getvalue())

            self.assertEqual(0, result)
            self.assertEqual("awaiting_host", state["phase"])
            self.assertEqual("start_task", state["next_action"]["type"])
            self.assertEqual([], state["completed_tasks"])

    def test_cmd_start_auto_creates_batch_without_mutating_task_or_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._ready_task(root)
            task_json = task_dir / "task.json"
            before = task_json.read_text(encoding="utf-8")
            with patch.dict(
                os.environ,
                {"COWORK_FLOW_CONTEXT_ID": "main"},
            ):
                result, output = self._run_in_repo(
                    root,
                    self.task.cmd_start,
                    argparse.Namespace(
                        dir=str(task_dir),
                        auto=True,
                        approved=True,
                    ),
                )

            state = json.loads(output)
            self.assertEqual(0, result)
            self.assertEqual("start_task", state["next_action"]["type"])
            self.assertEqual(before, task_json.read_text(encoding="utf-8"))
            self.assertFalse(
                (root / ".cowork-flow" / ".runtime" / "sessions" / "main.json").exists()
            )
            self.assertTrue(
                (
                    root
                    / ".cowork-flow"
                    / "runtime"
                    / "batches"
                    / "batch-07-10-demo.json"
                ).is_file()
            )

    def test_batch_requires_explicit_approval_without_mutation(self) -> None:
        batch_mode = importlib.import_module("common.task.batch_mode")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._task(root)
            stderr = io.StringIO()

            with contextlib.redirect_stderr(stderr):
                result = batch_mode.run_batch_entry(
                    root,
                    task_dir,
                    argparse.Namespace(auto=True, approved=False),
                )

            self.assertEqual(batch_mode.BATCH_REJECTED_EXIT_CODE, result)
            self.assertIn(
                batch_mode.BATCH_APPROVAL_REQUIRED_CODE,
                stderr.getvalue(),
            )
            self.assertFalse(
                (root / ".cowork-flow" / "runtime" / "batches").exists()
            )

    def test_batch_internal_commands_are_not_public_parser_commands(self) -> None:
        parser_module = importlib.import_module("commands.task_parser")
        parser = parser_module.build_parser()

        for command in ("batch-resume", "batch-record-result"):
            with self.subTest(command=command):
                with self.assertRaises(SystemExit) as raised:
                    parser.parse_args([command])
                self.assertEqual(2, raised.exception.code)

    def test_batch_record_result_command_advances_verified_action(self) -> None:
        batch_execution = importlib.import_module(
            "application.batch_execution"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._task(root)
            state = batch_execution.BatchExecutionService(
                root,
                commit_verifier=lambda _: True,
            ).start(task_dir.name)
            payload_path = self._write_start_result(
                root,
                task_dir,
                state,
            )
            result, output = self._run_in_repo(
                root,
                self.task.cmd_batch_record_result,
                argparse.Namespace(
                    operation_id=state["operation_id"],
                    file=payload_path,
                ),
            )

        advanced = json.loads(output)
        self.assertEqual(0, result)
        self.assertEqual(
            "init_implement_context",
            advanced["next_action"]["type"],
        )


if __name__ == "__main__":
    unittest.main()
