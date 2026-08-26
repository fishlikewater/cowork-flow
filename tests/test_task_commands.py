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


ANCHOR_TEXT = "# Demo\n\n## 目标\n\nDemo\n\n## 验收标准\n\n- AC-001: Demo.\n"


class TaskCommandsTest(FlowScriptTestCase):
    @staticmethod
    def _start_readiness_blockers(root: Path, task_dir: Path) -> list[str]:
        policy = importlib.import_module("services.lifecycle_policy")
        failure = policy.start_readiness_failure(root, task_dir)
        return list(failure.blockers) if failure is not None else []

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

    def _seed_fallback_binding(self, root: Path) -> Path:
        task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
        task_dir.mkdir(parents=True)
        (task_dir / "task.json").write_text(
            '{"status":"in_progress"}\n',
            encoding="utf-8",
        )
        sessions = root / ".cowork-flow" / ".runtime" / "sessions"
        sessions.mkdir(parents=True)
        (sessions / "zcode_local-1.json").write_text(
            json.dumps(
                {
                    "active_task_path": ".cowork-flow/tasks/07-10-demo",
                    "scope": "main",
                    "platform": "zcode",
                    "identity_provenance": "process_fallback",
                }
            ),
            encoding="utf-8",
        )
        return sessions / "zcode_local-1.json"

    def test_cmd_finish_refuses_process_fallback_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            session_file = self._seed_fallback_binding(root)
            lifecycle_commands = importlib.import_module(
                "adapters.cli.task_lifecycle_commands"
            )

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(
                    os.environ, {"ZCODE_PROCESS_LABEL": "local-1"}, clear=True
                ):
                    with (
                        patch.object(lifecycle_commands, "_run_hooks"),
                        contextlib.redirect_stdout(io.StringIO()),
                        contextlib.redirect_stderr(io.StringIO()) as stderr,
                    ):
                        result = self.task.cmd_finish(argparse.Namespace())
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(1, result)
            self.assertTrue(session_file.exists())
            self.assertIn("process-fallback", stderr.getvalue())

    def test_cmd_finish_clears_trusted_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                '{"status":"in_progress"}\n',
                encoding="utf-8",
            )
            sessions = root / ".cowork-flow" / ".runtime" / "sessions"
            sessions.mkdir(parents=True)
            session_file = sessions / "main.json"
            session_file.write_text(
                json.dumps(
                    {
                        "active_task_path": ".cowork-flow/tasks/07-10-demo",
                        "scope": "main",
                        "platform": "manual",
                    }
                ),
                encoding="utf-8",
            )
            lifecycle_commands = importlib.import_module(
                "adapters.cli.task_lifecycle_commands"
            )

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(
                    os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}, clear=True
                ):
                    with (
                        patch.object(lifecycle_commands, "_run_hooks"),
                        contextlib.redirect_stdout(io.StringIO()),
                        contextlib.redirect_stderr(io.StringIO()),
                    ):
                        result = self.task.cmd_finish(argparse.Namespace())
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(0, result)
            self.assertFalse(session_file.exists())

    def test_run_delivery_refuses_process_fallback_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._seed_fallback_binding(root)
            runner = importlib.import_module("adapters.cli.task_next_runner")

            def _forbidden(*args, **kwargs):
                raise AssertionError("lifecycle handler must not run")

            handlers = SimpleNamespace(
                create=_forbidden,
                start=_forbidden,
                review=_forbidden,
                complete=_forbidden,
                archive=_forbidden,
            )
            args = argparse.Namespace(
                dir=None,
                json=False,
                intent=None,
                auto=False,
                approved=False,
                title=None,
                slug=None,
                assignee=None,
                priority=None,
                description=None,
                parent=None,
                from_plan=None,
                commit=False,
            )

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(
                    os.environ, {"ZCODE_PROCESS_LABEL": "local-1"}, clear=True
                ):
                    with (
                        contextlib.redirect_stdout(io.StringIO()),
                        contextlib.redirect_stderr(io.StringIO()) as stderr,
                    ):
                        result = runner.run_next_action(args, handlers)
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(1, result)
            self.assertIn("blocked", stderr.getvalue())

    def test_run_delivery_target_legs_split_on_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._seed_fallback_binding(root)
            runner = importlib.import_module("adapters.cli.task_next_runner")

            with patch.dict(
                os.environ, {"ZCODE_PROCESS_LABEL": "local-1"}, clear=True
            ):
                fallback_target = runner._next_target_for_run(
                    argparse.Namespace(dir=None), root
                )
                blockers = runner._fallback_binding_blockers(
                    argparse.Namespace(dir=None), root
                )

            self.assertEqual((None, None, False), fallback_target)
            self.assertEqual([runner.FALLBACK_BINDING_BLOCKER], blockers)

            sessions = root / ".cowork-flow" / ".runtime" / "sessions"
            (sessions / "main.json").write_text(
                json.dumps(
                    {
                        "active_task_path": ".cowork-flow/tasks/07-10-demo",
                        "scope": "main",
                        "platform": "manual",
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}, clear=True
            ):
                trusted_target = runner._next_target_for_run(
                    argparse.Namespace(dir=None), root
                )

            self.assertEqual(".cowork-flow/tasks/07-10-demo", trusted_target[1])
            self.assertTrue(trusted_target[2])

    def test_cmd_start_runs_hooks_only_from_lifecycle_result_events(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                '{"status":"planning"}\n',
                encoding="utf-8",
            )
            lifecycle_result = SimpleNamespace(
                ok=True,
                code="LIFECYCLE-OK",
                active_task_path=".cowork-flow/tasks/07-10-demo",
                emitted_events=(),
            )
            service = SimpleNamespace(start=lambda *args, **kwargs: lifecycle_result)
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
                    patch.object(lifecycle_commands, "_run_hooks") as run_hooks,
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    result = self.task.cmd_start(
                        argparse.Namespace(dir=".cowork-flow/tasks/07-10-demo")
                    )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(0, result)
            run_hooks.assert_not_called()

    def test_lifecycle_commands_do_not_define_domain_policy_helpers(self) -> None:
        lifecycle_commands = importlib.import_module(
            "adapters.cli.task_lifecycle_commands"
        )

        for helper in (
            "_allow_spec_file_modifications",
            "_task_start_blockers",
            "_task_context_validation_issues",
            "_refresh_task_artifact_placeholders",
            "_optional_readiness_blockers",
            "_start_preflight",
        ):
            with self.subTest(helper=helper):
                self.assertFalse(hasattr(lifecycle_commands, helper))

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

            blockers = self._start_readiness_blockers(root, task_dir)

        self.assertEqual(
            [
                "decision-anchor.md is missing or empty",
                "implement.jsonl is missing or empty",
                "planFile is required before implementation starts",
            ],
            blockers,
        )
        self.assertNotIn("check.jsonl is missing or empty", blockers)
        self.assertNotIn("debug.jsonl is missing or empty", blockers)

    def test_task_start_blockers_clear_when_decision_anchor_and_context_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                '{"meta": {"taskType": "Tiny"}}',
                encoding="utf-8",
            )
            (task_dir / "decision-anchor.md").write_text(
                ANCHOR_TEXT,
                encoding="utf-8",
            )
            (task_dir / "implement.jsonl").write_text(
                '{"file": "AGENTS.md"}\n', encoding="utf-8"
            )

            self.assertEqual([], self._start_readiness_blockers(root, task_dir))

    def test_task_start_blocks_non_tiny_task_without_bound_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                '{"status": "planning"}',
                encoding="utf-8",
            )
            (task_dir / "decision-anchor.md").write_text(
                ANCHOR_TEXT,
                encoding="utf-8",
            )
            (task_dir / "implement.jsonl").write_text(
                '{"file": "AGENTS.md"}\n', encoding="utf-8"
            )

            blockers = self._start_readiness_blockers(root, task_dir)

        self.assertEqual(
            ["planFile is required before implementation starts"],
            blockers,
        )

    def test_task_start_blocks_anchor_without_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            plan_file = root / ".cowork-flow" / "plans" / "2026-05-19-demo.md"
            task_dir.mkdir(parents=True)
            plan_file.parent.mkdir(parents=True)
            plan_file.write_text("# Plan\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                json.dumps(
                    {
                        "status": "planning",
                        "meta": {
                            "planFile": ".cowork-flow/plans/2026-05-19-demo.md",
                        },
                    }
                ),
                encoding="utf-8",
            )
            (task_dir / "decision-anchor.md").write_text("# Demo\n", encoding="utf-8")
            (task_dir / "implement.jsonl").write_text(
                '{"file": "AGENTS.md"}\n', encoding="utf-8"
            )

            blockers = self._start_readiness_blockers(root, task_dir)

        self.assertEqual(
            [
                "decision-anchor.md missing required section: ## 目标",
                "decision-anchor.md missing required section: ## 验收标准",
            ],
            blockers,
        )

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
            (task_dir / "task.json").write_text(
                '{"meta": {"taskType": "Tiny"}}',
                encoding="utf-8",
            )
            (task_dir / "decision-anchor.md").write_text(ANCHOR_TEXT, encoding="utf-8")
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
            (task_dir / "task.json").write_text(
                '{"status": "planning", "meta": {"taskType": "Tiny"}}\n',
                encoding="utf-8",
            )
            (task_dir / "decision-anchor.md").write_text(ANCHOR_TEXT, encoding="utf-8")
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
            (task_dir / "task.json").write_text(
                '{"status": "planning", "meta": {"taskType": "Tiny"}}\n',
                encoding="utf-8",
            )
            (task_dir / "decision-anchor.md").write_text(ANCHOR_TEXT, encoding="utf-8")
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
            (task_dir / "task.json").write_text(
                '{"meta": {"taskType": "Tiny"}}',
                encoding="utf-8",
            )
            (task_dir / "decision-anchor.md").write_text(ANCHOR_TEXT, encoding="utf-8")
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

    def test_cmd_next_run_from_plan_binds_planning_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                '{"status": "planning"}\n',
                encoding="utf-8",
            )
            (task_dir / "decision-anchor.md").write_text(ANCHOR_TEXT, encoding="utf-8")
            (task_dir / "implement.jsonl").write_text(
                '{"file": "AGENTS.md"}\n',
                encoding="utf-8",
            )
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            plan_file = root / ".cowork-flow" / "plans" / "2026-07-10-demo.md"
            plan_file.parent.mkdir(parents=True)
            plan_file.write_text("# Plan\n\nDemo.\n", encoding="utf-8")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()) as stdout,
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_next(
                        argparse.Namespace(
                            dir=str(task_dir),
                            run=True,
                            from_plan=".cowork-flow/plans/2026-07-10-demo.md",
                        )
                    )
            finally:
                os.chdir(previous_cwd)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(0, result, stderr.getvalue())
            self.assertEqual(
                ".cowork-flow/plans/2026-07-10-demo.md",
                data["meta"]["planFile"],
            )
            self.assertEqual("planning", data["status"])
            self.assertIn("Plan bound", stdout.getvalue())
            self.assertIn("task next", stdout.getvalue())

    def test_cmd_next_run_from_plan_rejects_missing_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                '{"status": "planning"}\n',
                encoding="utf-8",
            )
            (task_dir / "decision-anchor.md").write_text(ANCHOR_TEXT, encoding="utf-8")
            (task_dir / "implement.jsonl").write_text(
                '{"file": "AGENTS.md"}\n',
                encoding="utf-8",
            )
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_next(
                        argparse.Namespace(
                            dir=str(task_dir),
                            run=True,
                            from_plan=".cowork-flow/plans/missing.md",
                        )
                    )
            finally:
                os.chdir(previous_cwd)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(1, result)
            self.assertNotIn("meta", data)
            self.assertIn("missing.md", stderr.getvalue())

    def test_cmd_next_run_from_plan_rejected_outside_planning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                '{"status": "in_progress"}\n',
                encoding="utf-8",
            )
            plan_file = root / ".cowork-flow" / "plans" / "2026-07-10-demo.md"
            plan_file.parent.mkdir(parents=True)
            plan_file.write_text("# Plan\n\nDemo.\n", encoding="utf-8")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_next(
                        argparse.Namespace(
                            dir=str(task_dir),
                            run=True,
                            from_plan=".cowork-flow/plans/2026-07-10-demo.md",
                        )
                    )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(1, result)
            self.assertIn(
                "--from-plan binds a plan to a planning task",
                stderr.getvalue(),
            )
