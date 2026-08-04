from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.flow_test_support import FlowScriptTestCase


ROOT = Path(__file__).resolve().parents[1]
PYTHON_RUNNER = ROOT / "template" / ".cowork-flow" / "scripts" / "run.py"


class BatchModeFailClosedTest(FlowScriptTestCase):
    def test_batch_skill_documents_recovery_without_default_batch_mode(self) -> None:
        skill_text = (
            ROOT
            / "template"
            / "skills"
            / "batch-execution"
            / "SKILL.md"
        ).read_text(encoding="utf-8")

        required_markers = (
            "Batch is not the default path for ordinary task work.",
            "Use normal step-by-task progression unless the user explicitly approves automatic continuous execution.",
            "Inspect the paused operation first:",
            "batch-action inspect <operation_id>",
            "Repair or rerun the failed Host action outside the Batch state file.",
            "Resume only after the failed action can succeed:",
            "batch-action resume <operation_id>",
            "Do not use inspect as completion evidence.",
        )
        forbidden_markers = (
            "tdd.jsonl",
            'type: "tdd"',
            "TDD evidence",
            "./.cowork-flow/run task batch-",
        )

        self.assertEqual(
            [],
            [marker for marker in required_markers if marker not in skill_text],
        )
        self.assertEqual(
            [],
            [marker for marker in forbidden_markers if marker in skill_text],
        )

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

    @staticmethod
    def _run_public_batch_action(
        root: Path,
        *args: str,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(PYTHON_RUNNER), "batch-action", *args],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def test_batch_adapter_dispatches_manifest_owned_start_action(self) -> None:
        batch_mode = importlib.import_module("adapters.cli.batch_mode")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._task(root)
            action = root / "batch-action.py"
            action.write_text(
                "import json, sys\n"
                "print(json.dumps({'argv': sys.argv[1:]}))\n",
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with patch.object(
                batch_mode,
                "skill_command_scripts",
                return_value={"batch-action": action},
            ):
                with contextlib.redirect_stdout(stdout):
                    result = batch_mode.run_batch_entry(
                        root,
                        task_dir,
                        argparse.Namespace(auto=True, approved=True),
                    )

        self.assertEqual(0, result)
        self.assertEqual(["start", task_dir.name], json.loads(stdout.getvalue())["argv"])

    def test_batch_runtime_emits_first_host_action_without_completion(self) -> None:
        batch_mode = importlib.import_module("adapters.cli.batch_mode")
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
        batch_mode = importlib.import_module("adapters.cli.batch_mode")
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
        parser_module = importlib.import_module("adapters.cli.task_parser")
        parser = parser_module.build_parser()
        subparser_actions = [
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        ]
        self.assertEqual(1, len(subparser_actions))
        public_commands = set(subparser_actions[0].choices)
        internal_commands = {
            "batch-resume",
            "batch-record-result",
            "batch-inspect",
        }

        for command in internal_commands:
            with self.subTest(command=command):
                with self.assertRaises(SystemExit) as raised:
                    parser.parse_args([command])
                self.assertEqual(2, raised.exception.code)
        self.assertEqual(set(), internal_commands & public_commands)

        task_command_names = {
            name for name in dir(self.task) if name.startswith("cmd_batch_")
        }
        self.assertEqual(
            set(),
            {
                "cmd_batch_resume",
                "cmd_batch_record_result",
                "cmd_batch_inspect",
            }
            & task_command_names,
        )

    def test_batch_record_result_command_advances_verified_action(self) -> None:
        batch_mode = importlib.import_module("adapters.cli.batch_mode")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._task(root)
            started = self._run_public_batch_action(root, "start", task_dir.name)
            self.assertEqual(0, started.returncode, started.stderr)
            state = json.loads(started.stdout)
            payload_path = self._write_start_result(
                root,
                task_dir,
                state,
            )
            recorded = self._run_public_batch_action(
                root,
                "record-result",
                state["operation_id"],
                str(payload_path),
            )

        advanced = json.loads(recorded.stdout)
        self.assertEqual(0, recorded.returncode, recorded.stderr)
        self.assertEqual(
            "init_implement_context",
            advanced["next_action"]["type"],
        )

    def test_public_batch_inspect_reports_active_state_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._task(root)
            started = self._run_public_batch_action(root, "start", task_dir.name)
            self.assertEqual(0, started.returncode, started.stderr)
            state = json.loads(started.stdout)
            state_path = (
                root
                / ".cowork-flow"
                / "runtime"
                / "batches"
                / f"{state['operation_id']}.json"
            )
            before = state_path.read_text(encoding="utf-8")

            inspected = self._run_public_batch_action(
                root,
                "inspect",
                state["operation_id"],
            )
            after = state_path.read_text(encoding="utf-8")

        self.assertEqual(0, inspected.returncode, inspected.stderr)
        self.assertEqual(before, after)
        report = json.loads(inspected.stdout)
        self.assertEqual(state["operation_id"], report["operationId"])
        self.assertEqual("awaiting_host", report["state"])
        self.assertEqual(task_dir.name, report["rootTask"])
        self.assertEqual(task_dir.name, report["currentTask"])
        self.assertEqual("start", report["currentPhase"])
        self.assertEqual([], report["completedTasks"])
        self.assertIsNone(report["pausedReason"])
        self.assertEqual(state["next_action"], report["nextAction"])
        self.assertEqual({}, report["recovery"])

    def test_public_batch_inspect_reports_paused_recovery_facts_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._task(root)
            started = self._run_public_batch_action(root, "start", task_dir.name)
            self.assertEqual(0, started.returncode, started.stderr)
            state = json.loads(started.stdout)
            invalid_result = root / "invalid-result.json"
            invalid_result.write_text(
                json.dumps(
                    {
                        "action_id": state["next_action"]["action_id"],
                        "type": "start_task",
                        "outcome": "success",
                        "task_status": "in_progress",
                    }
                ),
                encoding="utf-8",
            )
            paused = self._run_public_batch_action(
                root,
                "record-result",
                state["operation_id"],
                str(invalid_result),
            )
            self.assertEqual(2, paused.returncode)
            state_path = (
                root
                / ".cowork-flow"
                / "runtime"
                / "batches"
                / f"{state['operation_id']}.json"
            )
            before = state_path.read_text(encoding="utf-8")

            inspected = self._run_public_batch_action(
                root,
                "inspect",
                state["operation_id"],
            )
            after = state_path.read_text(encoding="utf-8")

        self.assertEqual(0, inspected.returncode, inspected.stderr)
        self.assertEqual(before, after)
        report = json.loads(inspected.stdout)
        self.assertEqual("paused", report["state"])
        self.assertEqual(task_dir.name, report["currentTask"])
        self.assertIn("task status", report["pausedReason"])
        self.assertEqual("start_task", report["failedAction"]["type"])
        self.assertEqual(
            state["next_action"]["action_id"],
            report["failedAction"]["actionId"],
        )
        self.assertEqual("success", report["failedAction"]["outcome"])
        self.assertEqual(
            "batch-action resume batch-07-10-demo",
            report["recovery"]["resumeCommand"],
        )
        self.assertEqual(task_dir.name, report["recovery"]["retryTask"])
        self.assertIsNone(report["nextAction"])

    def test_public_batch_resume_recovers_paused_operation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._task(root)
            started = self._run_public_batch_action(root, "start", task_dir.name)
            self.assertEqual(0, started.returncode, started.stderr)
            state = json.loads(started.stdout)
            invalid_result = root / "invalid-result.json"
            invalid_result.write_text(
                json.dumps(
                    {
                        "action_id": state["next_action"]["action_id"],
                        "type": "start_task",
                        "outcome": "success",
                        "task_status": "in_progress",
                    }
                ),
                encoding="utf-8",
            )
            paused = self._run_public_batch_action(
                root,
                "record-result",
                state["operation_id"],
                str(invalid_result),
            )
            resumed = self._run_public_batch_action(
                root,
                "resume",
                state["operation_id"],
            )

        self.assertEqual(2, paused.returncode)
        self.assertEqual("paused", json.loads(paused.stdout)["phase"])
        self.assertEqual(0, resumed.returncode, resumed.stderr)
        self.assertEqual("start_task", json.loads(resumed.stdout)["next_action"]["type"])


if __name__ == "__main__":
    unittest.main()
