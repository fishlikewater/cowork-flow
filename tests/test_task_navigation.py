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


ANCHOR_TEXT = "# Demo\n\n## 目标\n\nDemo\n\n## 验收标准\n\n- AC-001: Demo.\n"


class TaskNavigationTest(FlowScriptTestCase):
    def _seed_fallback_binding(self, root: Path, task_status: str) -> Path:
        task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
        task_dir.mkdir(parents=True)
        (task_dir / "task.json").write_text(
            json.dumps({"title": "Demo", "status": task_status}),
            encoding="utf-8",
        )
        sessions = root / ".cowork-flow" / ".runtime" / "sessions"
        sessions.mkdir(parents=True)
        (sessions / "zcode_local-1.json").write_text(
            json.dumps(
                {
                    "active_task_path": ".cowork-flow/tasks/05-19-demo",
                    "scope": "main",
                    "platform": "zcode",
                    "identity_provenance": "process_fallback",
                }
            ),
            encoding="utf-8",
        )
        return task_dir

    def _run_cmd_next_json(
        self,
        root: Path,
        *,
        env: dict[str, str],
        target: str | None,
    ) -> tuple[int, dict]:
        previous_cwd = Path.cwd()
        try:
            os.chdir(root)
            with patch.dict(os.environ, env, clear=True):
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    result = self.task.cmd_next(
                        argparse.Namespace(
                            dir=target,
                            json=True,
                            intent="question",
                        )
                    )
        finally:
            os.chdir(previous_cwd)
        return result, json.loads(stdout.getvalue())

    def test_cmd_next_json_does_not_follow_process_fallback_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._seed_fallback_binding(root, "in_progress")

            result, payload = self._run_cmd_next_json(
                root,
                env={"ZCODE_PROCESS_LABEL": "local-1"},
                target=None,
            )

            self.assertEqual(0, result)
            self.assertEqual("no_task", payload["status"])
            self.assertTrue(payload["blockers"])
            self.assertIn(
                "process-fallback",
                " ".join(str(blocker) for blocker in payload["blockers"]),
            )

    def test_cmd_next_json_explicit_dir_overrides_fallback_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._seed_fallback_binding(root, "in_progress")

            result, payload = self._run_cmd_next_json(
                root,
                env={"ZCODE_PROCESS_LABEL": "local-1"},
                target=".cowork-flow/tasks/05-19-demo",
            )

            self.assertEqual(0, result)
            self.assertEqual("in_progress", payload["status"])
            self.assertEqual([], payload["blockers"])

    def test_cmd_next_json_trusted_binding_still_auto_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                json.dumps({"title": "Demo", "status": "in_progress"}),
                encoding="utf-8",
            )
            sessions = root / ".cowork-flow" / ".runtime" / "sessions"
            sessions.mkdir(parents=True)
            (sessions / "main.json").write_text(
                json.dumps(
                    {
                        "active_task_path": ".cowork-flow/tasks/05-19-demo",
                        "scope": "main",
                        "platform": "manual",
                    }
                ),
                encoding="utf-8",
            )

            result, payload = self._run_cmd_next_json(
                root,
                env={"COWORK_FLOW_CONTEXT_ID": "main"},
                target=None,
            )

            self.assertEqual(0, result)
            self.assertEqual("in_progress", payload["status"])

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


    def test_task_parser_rejects_removed_public_commands(self) -> None:
        parser = self.task.build_parser()
        for command in (
            "create",
            "start",
            "review",
            "complete",
            "archive",
            "init-context",
            "add-context",
            "list",
        ):
            with self.subTest(command=command):
                with self.assertRaises(SystemExit) as raised:
                    parser.parse_args([command])
                self.assertEqual(2, raised.exception.code)

    def test_task_next_parser_accepts_run_action_inputs(self) -> None:
        args = self.task.build_parser().parse_args(
            [
                "next",
                "--run",
                "--title",
                "Demo task",
                "--slug",
                "demo-task",
            ]
        )

        self.assertEqual("next", args.command)
        self.assertTrue(args.run)
        self.assertEqual("Demo task", args.title)
        self.assertEqual("demo-task", args.slug)

    def test_task_next_parser_accepts_read_only_list_and_validate(self) -> None:
        list_args = self.task.build_parser().parse_args(["next", "--list"])
        validate_args = self.task.build_parser().parse_args(
            ["next", ".cowork-flow/tasks/05-19-demo", "--validate"]
        )

        self.assertTrue(list_args.list_tasks)
        self.assertTrue(validate_args.validate)

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
                    "blockers",
                    "nextAction",
                    "activatedSkill",
                    "actionCommand",
                    "diagnosticsCommand",
                    "mutatesState",
                    "lifecycleCheck",
                    "runtimeGate",
                    "action",
                },
                set(payload),
            )
            self.assertIn("answer_questions", payload["allowedOperations"])
            self.assertNotIn("internalProtocols", payload)
            self.assertIsNone(payload["recommendedSkill"])
            self.assertEqual("answer_questions", payload["nextAction"])
            self.assertFalse(payload["mutatesState"])
            self.assertIsNone(payload["actionCommand"])
            self.assertIsNone(payload["diagnosticsCommand"])
            self.assertIsNone(payload["lifecycleCheck"])
            self.assertIsNone(payload["runtimeGate"])

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


    def test_cmd_next_json_implement_action_exposes_read_first_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            plan_file = root / ".cowork-flow" / "plans" / "demo.md"
            task_dir.mkdir(parents=True)
            plan_file.parent.mkdir(parents=True)
            plan_file.write_text("# Plan\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                json.dumps(
                    {
                        "status": "in_progress",
                        "meta": {"planFile": ".cowork-flow/plans/demo.md"},
                    }
                ),
                encoding="utf-8",
            )
            (task_dir / "decision-anchor.md").write_text(ANCHOR_TEXT, encoding="utf-8")
            (task_dir / "implement.jsonl").write_text(
                '{"file": ".agents/skills/test-first/SKILL.md", "reason": "red-green guide"}\n'
                '{"file": "src/app.py", "reason": "implementation target"}\n',
                encoding="utf-8",
            )
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
                                intent=None,
                            )
                        )
            finally:
                os.chdir(previous_cwd)

            payload = json.loads(stdout.getvalue())
            read_first = payload["readFirst"]
            read_first_files = [entry["file"] for entry in read_first]
            self.assertEqual(0, result)
            self.assertEqual("implement_change", payload["nextAction"])
            self.assertEqual("in_progress", payload["status"])
            self.assertIn(
                ".cowork-flow/tasks/05-19-demo/decision-anchor.md",
                read_first_files,
            )
            self.assertIn(".cowork-flow/plans/demo.md", read_first_files)
            self.assertIn(
                ".cowork-flow/tasks/05-19-demo/implement.jsonl",
                read_first_files,
            )
            self.assertIn(".agents/skills/test-first/SKILL.md", read_first_files)
            self.assertIn("src/app.py", read_first_files)


    def test_task_next_run_starts_ready_planning_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                '{"status": "planning", "meta": {"taskType": "Tiny"}}\n',
                encoding="utf-8",
            )
            (task_dir / "decision-anchor.md").write_text(ANCHOR_TEXT, encoding="utf-8")
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text(
                    '{"file": "AGENTS.md"}\n',
                    encoding="utf-8",
                )

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        result = self.task.cmd_next(
                            argparse.Namespace(
                                dir=".cowork-flow/tasks/05-19-demo",
                                json=False,
                                run=True,
                                intent=None,
                                auto=False,
                                approved=False,
                            )
                        )
            finally:
                os.chdir(previous_cwd)

            task_data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(0, result)
            self.assertEqual("in_progress", task_data["status"])
            self.assertIn("Active session task set", stdout.getvalue())

    def test_task_next_run_blocks_non_runnable_implementation_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                '{"status": "in_progress"}\n',
                encoding="utf-8",
            )
            self._write_session_task(root)

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with contextlib.redirect_stderr(io.StringIO()) as stderr:
                        result = self.task.cmd_next(
                            argparse.Namespace(
                                dir=None,
                                json=False,
                                run=True,
                                intent=None,
                            )
                        )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(1, result)
            self.assertIn("not executable: implement_change", stderr.getvalue())

    def test_task_next_run_with_create_inputs_does_not_archive_completed_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                '{"status": "completed"}\n',
                encoding="utf-8",
            )
            self._write_session_task(root)

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with contextlib.redirect_stderr(io.StringIO()) as stderr:
                        result = self.task.cmd_next(
                            argparse.Namespace(
                                dir=None,
                                json=False,
                                run=True,
                                intent=None,
                                title="New task",
                                slug="new-task",
                                assignee="codex",
                                priority="P2",
                                description=None,
                                parent=None,
                                from_plan=None,
                                auto=False,
                                approved=False,
                                commit=False,
                            )
                        )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(1, result)
            self.assertTrue(task_dir.exists())
            self.assertFalse(
                (root / ".cowork-flow" / "tasks" / "archive" / "2026-07" / "05-19-demo").exists()
            )
            self.assertIn("create_task inputs cannot run archive_task", stderr.getvalue())

    def test_task_next_validate_reports_context_issues(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text('{"status": "planning"}\n', encoding="utf-8")
            (task_dir / "implement.jsonl").write_text(
                '{"file": "src/missing.py", "reason": "Missing"}\n',
                encoding="utf-8",
            )

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    result = self.task.cmd_next(
                        argparse.Namespace(
                            dir=".cowork-flow/tasks/05-19-demo",
                            json=False,
                            run=False,
                            intent=None,
                            validate=True,
                            list_tasks=False,
                        )
                    )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(1, result)
            self.assertIn("File not found: src/missing.py", stdout.getvalue())

    def test_task_next_list_prints_active_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                json.dumps(
                    {
                        "status": "planning",
                        "assignee": "codex",
                        "title": "Demo",
                        "children": [],
                        "parent": None,
                    }
                ),
                encoding="utf-8",
            )

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    result = self.task.cmd_next(
                        argparse.Namespace(
                            dir=None,
                            json=False,
                            run=False,
                            intent=None,
                            validate=False,
                            list_tasks=True,
                            mine=False,
                            status=None,
                        )
                    )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(0, result)
            self.assertIn("05-19-demo/", stdout.getvalue())

    def test_task_next_list_json_outputs_machine_readable_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                json.dumps(
                    {
                        "status": "planning",
                        "assignee": "codex",
                        "title": "Demo",
                        "children": [],
                        "parent": None,
                    }
                ),
                encoding="utf-8",
            )

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    result = self.task.cmd_next(
                        argparse.Namespace(
                            dir=None,
                            json=True,
                            run=False,
                            intent=None,
                            validate=False,
                            list_tasks=True,
                            mine=False,
                            status=None,
                        )
                    )
            finally:
                os.chdir(previous_cwd)

            payload = json.loads(stdout.getvalue())
            self.assertEqual(0, result)
            self.assertEqual(1, payload["count"])
            self.assertEqual(".cowork-flow/tasks/05-19-demo", payload["tasks"][0]["path"])
            self.assertEqual("planning", payload["tasks"][0]["status"])

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
            self.assertIn("Next action: create a planned task", output)
            self.assertIn("./.cowork-flow/run task next --run --title", output)
            self.assertNotIn("./.cowork-flow/run task create", output)
            self.assertNotIn("delegated prompt", output)
            self.assertFalse((root / ".cowork-flow" / "tasks").exists())

    def test_cmd_next_json_reports_repository_recovery_when_session_has_no_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            completed_dir = root / ".cowork-flow" / "tasks" / "05-20-completed"
            for path, status in ((task_dir, "in_progress"), (completed_dir, "completed")):
                path.mkdir(parents=True)
                (path / "task.json").write_text(
                    json.dumps({"status": status, "assignee": "codex"}),
                    encoding="utf-8",
                )

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        result = self.task.cmd_next(
                            argparse.Namespace(dir=None, json=True, intent="implement")
                        )
            finally:
                os.chdir(previous_cwd)

            payload = json.loads(stdout.getvalue())
            self.assertEqual(0, result)
            self.assertEqual("no_task", payload["status"])
            recovery = payload["recovery"]
            self.assertEqual(
                "./.cowork-flow/run task next --list --json",
                recovery["listCommand"],
            )
            self.assertEqual(
                {
                    ("active_unbound", ".cowork-flow/tasks/05-19-demo"),
                    ("completed_unarchived", ".cowork-flow/tasks/05-20-completed"),
                },
                {(signal["kind"], signal["task"]) for signal in recovery["signals"]},
            )

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
            self.assertIn("Command: none", output)
            self.assertNotIn("edit the required planning artifacts", output.split("Command:", 1)[1])
            self.assertNotIn("./.cowork-flow/run task init-context", output)
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
            self.assertIn("Skill: cowork-flow", output)
            self.assertIn("task next .cowork-flow/tasks/05-19-demo --run", output)
            self.assertNotIn("Then:", output)
            self.assertNotIn("--intent review", output)
            self.assertNotIn("./.cowork-flow/run subagent init", output)

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
            self.assertIn("Skill: cowork-flow", output)
            self.assertIn("task next .cowork-flow/tasks/05-19-demo --run", output)
            self.assertNotIn("Then:", output)
            self.assertNotIn("./.cowork-flow/run subagent init", output)
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
            self.assertIn("Next action: complete reviewed task", output)
            self.assertIn("Skill: task-review", output)
            self.assertIn("Diagnostics: ./.cowork-flow/run review-check .cowork-flow/tasks/05-19-demo --json", output)
            self.assertIn("./.cowork-flow/run task next .cowork-flow/tasks/05-19-demo --run --intent review", output)
            self.assertNotIn("cowork-check", output)
            self.assertNotIn("./.cowork-flow/run task complete", output)

    def test_review_route_required_artifacts_do_not_pressure_check_jsonl(self) -> None:
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
                            argparse.Namespace(dir=None, json=True, intent=None)
                        )
            finally:
                os.chdir(previous_cwd)

            payload = json.loads(stdout.getvalue())
            self.assertEqual(0, result)
            self.assertEqual("review", payload["status"])
            self.assertEqual(["decision-anchor.md"], payload["requiredArtifacts"])
            self.assertEqual(
                "./.cowork-flow/run review-check .cowork-flow/tasks/05-19-demo --json",
                payload["diagnosticsCommand"],
            )
            self.assertNotIn("check.jsonl", payload["requiredArtifacts"])

    def test_cmd_next_completed_renders_only_archive_action_contract(self) -> None:
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
                        result = self.task.cmd_next(argparse.Namespace(dir=None))
            finally:
                os.chdir(previous_cwd)

            output = stdout.getvalue()
            self.assertEqual(0, result)
            self.assertIn("task next .cowork-flow/tasks/05-19-demo --run --intent archive", output)
            self.assertNotIn("git status --short", output)
            self.assertNotIn("Then:", output)
            self.assertNotIn("task archive 05-19-demo", output)

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

    def test_cmd_next_json_routes_standalone_doubt_review_without_check_dispatch(self) -> None:
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
            self.assertEqual("adversarial-review", payload["recommendedSkill"])
            self.assertNotIn("internalProtocols", payload)
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
            self.assertIn("adversarial-review", output)
            self.assertIn("Command: none", output)
            self.assertNotIn("Target:", output)
            self.assertNotIn("Do not dispatch", output)
            self.assertNotIn("cowork-check", output)
            self.assertNotIn("subagent init --role check", output)
            self.assertNotIn("subagent bind", output)

    def test_text_navigation_adapter_has_no_phase_specific_control_plane(self) -> None:
        source = (
            ROOT
            / "template"
            / ".cowork-flow"
            / "scripts"
            / "adapters"
            / "cli"
            / "task_navigation.py"
        ).read_text(encoding="utf-8")

        for forbidden in (
            "_run_command",
            "_print_doubt_review_route",
            "_print_check_route",
            "_print_archive_route",
            "git status --short",
            "Then:",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        self.assertEqual(
            0,
            sum(
                marker in source
                for marker in (
                    "_run_command",
                    "_print_doubt_review_route",
                    "_print_check_route",
                    "_print_archive_route",
                    "git status --short",
                    "Then:",
                )
            ),
        )

    def test_task_next_run_dispatch_lives_in_runner_module(self) -> None:
        task_source = (
            ROOT / "template" / ".cowork-flow" / "scripts" / "adapters" / "cli" / "task.py"
        ).read_text(encoding="utf-8")
        runner_source = (
            ROOT
            / "template"
            / ".cowork-flow"
            / "scripts"
            / "adapters"
            / "cli"
            / "task_next_runner.py"
        ).read_text(encoding="utf-8")

        self.assertIn("run_next_action", task_source)
        self.assertIn("NextActionHandlers", task_source)
        self.assertIn("def run_next_action", runner_source)
        self.assertNotIn("def _dispatch_next_lifecycle_action", task_source)
        self.assertNotIn("def _validated_next_action", task_source)
        self.assertEqual(
            (True, True, True, False, False),
            (
                "run_next_action" in task_source,
                "NextActionHandlers" in task_source,
                "def run_next_action" in runner_source,
                "def _dispatch_next_lifecycle_action" in task_source,
                "def _validated_next_action" in task_source,
            ),
        )

    def test_cmd_next_routes_active_ready_planning_task_to_implementation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                '{"status": "planning", "meta": {"taskType": "Tiny"}}\n',
                encoding="utf-8",
            )
            (task_dir / "decision-anchor.md").write_text(ANCHOR_TEXT, encoding="utf-8")
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
            self.assertIn("Next action: start task", output)
            self.assertIn("Skill: cowork-flow", output)
            self.assertIn("task next .cowork-flow/tasks/05-19-demo --run", output)
            self.assertIn("Blockers: none", output)
            self.assertNotIn("implement.jsonl: [OK]", output)

    def test_cmd_next_routes_inactive_ready_planning_task_to_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                '{"status": "planning", "meta": {"taskType": "Tiny"}}\n',
                encoding="utf-8",
            )
            (task_dir / "decision-anchor.md").write_text(ANCHOR_TEXT, encoding="utf-8")
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")

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
            self.assertIn("./.cowork-flow/run task next .cowork-flow/tasks/05-19-demo --run", output)
            self.assertNotIn("./.cowork-flow/run task start", output)

    def test_cmd_next_create_command_carries_from_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        result = self.task.cmd_next(
                            argparse.Namespace(dir=None, json=True, intent="clarify")
                        )
            finally:
                os.chdir(previous_cwd)

            payload = json.loads(stdout.getvalue())
            self.assertEqual(0, result)
            self.assertEqual("create_task", payload["nextAction"])
            self.assertIn("--from-plan .cowork-flow/plans/YYYY-MM-DD-<task-name>.md", payload["actionCommand"])

    def test_cmd_next_planning_planfile_blocker_renders_bind_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                '{"status": "planning"}\n',
                encoding="utf-8",
            )
            (task_dir / "decision-anchor.md").write_text(ANCHOR_TEXT, encoding="utf-8")
            (task_dir / "implement.jsonl").write_text(
                '{"file": "AGENTS.md"}\n',
                encoding="utf-8",
            )

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        result = self.task.cmd_next(
                            argparse.Namespace(
                                dir=".cowork-flow/tasks/05-19-demo",
                                json=True,
                            )
                        )
            finally:
                os.chdir(previous_cwd)

            payload = json.loads(stdout.getvalue())
            self.assertEqual(0, result)
            self.assertEqual("edit_planning_artifacts", payload["nextAction"])
            self.assertIn("planFile is required before implementation starts", payload["blockers"])
            self.assertEqual(
                "./.cowork-flow/run task next .cowork-flow/tasks/05-19-demo --run --from-plan <plan-file>",
                payload["actionCommand"],
            )
