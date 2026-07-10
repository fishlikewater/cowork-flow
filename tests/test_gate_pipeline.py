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


class GatePipelineTest(FlowScriptTestCase):
    def test_cmd_review_and_complete_update_active_task_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                '{"status": "in_progress", "completedAt": null}\n',
                encoding="utf-8",
            )
            self._write_session_task(root)

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with (
                        contextlib.redirect_stdout(io.StringIO()),
                        contextlib.redirect_stderr(io.StringIO()),
                    ):
                        review_result = self.task.cmd_review(argparse.Namespace(dir=None))
                        complete_result = self.task.cmd_complete(argparse.Namespace(dir=None))
            finally:
                os.chdir(previous_cwd)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(0, review_result)
            self.assertEqual(0, complete_result)
            self.assertEqual("completed", data["status"])
            self.assertEqual(datetime.now().strftime("%Y-%m-%d"), data["completedAt"])

    def test_cmd_review_blocks_spec_changes_for_bound_subagent_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            workflow_dir = root / ".cowork-flow"
            task_dir = workflow_dir / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                '{"status": "in_progress", "completedAt": null}\n',
                encoding="utf-8",
            )
            self._write_session_task(
                root,
                scope="subagent",
                runtime_context_id="runtime-demo",
            )
            self._write_rules_file(
                root,
                [
                    {
                        **self._workflow_rule("R-AG-002", "all"),
                        "type": "forbidden_action",
                        "enforcement": "validate_implementation",
                        "message": "Subagent attempted to modify spec files",
                        "fix_hint": "Spec files can only be modified by main session",
                    }
                ],
            )
            self._commit_all(root, "baseline")
            (root / "AGENTS.md").write_text("# Rules changed by implementation\n", encoding="utf-8")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with (
                        contextlib.redirect_stdout(io.StringIO()),
                        contextlib.redirect_stderr(io.StringIO()) as stderr,
                    ):
                        result = self.task.cmd_review(argparse.Namespace(dir=None))
            finally:
                os.chdir(previous_cwd)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(1, result)
            self.assertEqual("in_progress", data["status"])
            self.assertIn("Subagent attempted to modify spec files", stderr.getvalue())

    def test_cmd_review_allows_spec_changes_for_default_main_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            workflow_dir = root / ".cowork-flow"
            task_dir = workflow_dir / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                '{"status": "in_progress", "completedAt": null}\n',
                encoding="utf-8",
            )
            self._write_session_task(root)
            self._write_rules_file(
                root,
                [
                    {
                        **self._workflow_rule("R-AG-002", "all"),
                        "type": "forbidden_action",
                        "enforcement": "validate_implementation",
                        "message": "Subagent attempted to modify spec files",
                        "fix_hint": "Spec files can only be modified by main session",
                    }
                ],
            )
            self._commit_all(root, "baseline")
            (root / "AGENTS.md").write_text("# Rules changed by coordinator\n", encoding="utf-8")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with (
                        contextlib.redirect_stdout(io.StringIO()),
                        contextlib.redirect_stderr(io.StringIO()) as stderr,
                    ):
                        result = self.task.cmd_review(argparse.Namespace(dir=None))
            finally:
                os.chdir(previous_cwd)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(0, result, stderr.getvalue())
            self.assertEqual("review", data["status"])

    def test_cmd_review_rejects_coordinator_flag_for_bound_subagent_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            workflow_dir = root / ".cowork-flow"
            task_dir = workflow_dir / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                '{"status": "in_progress", "completedAt": null}\n',
                encoding="utf-8",
            )
            self._write_session_task(
                root,
                scope="subagent",
                runtime_context_id="runtime-demo",
            )
            self._write_rules_file(
                root,
                [
                    {
                        **self._workflow_rule("R-AG-002", "all"),
                        "type": "forbidden_action",
                        "enforcement": "validate_implementation",
                        "message": "Subagent attempted to modify spec files",
                        "fix_hint": "Spec files can only be modified by main session",
                    }
                ],
            )
            self._commit_all(root, "baseline")
            (root / "AGENTS.md").write_text("# Rules changed by subagent\n", encoding="utf-8")

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
            self.assertEqual(1, result)
            self.assertEqual("in_progress", data["status"])
            self.assertIn("Subagent attempted to modify spec files", stderr.getvalue())

    def test_validators_scope_git_changes_to_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            outer = Path(temp_dir)
            self._init_git_repo(outer)
            outer_spec = outer / ".cowork-flow" / "spec" / "schemas" / "rules.schema.json"
            outer_src = outer / "src"
            outer_spec.parent.mkdir(parents=True)
            outer_src.mkdir()
            outer_spec.write_text('{"schemaVersion": 1}\n', encoding="utf-8")
            (outer_src / "outer.py").write_text("VALUE = 'safe'\n", encoding="utf-8")
            self._commit_all(outer, "baseline")

            outer_spec.write_text('{"schemaVersion": 2}\n', encoding="utf-8")
            (outer_src / "outer.py").write_text(
                "VALUE = open('data.txt').read()\n",
                encoding="utf-8",
            )

            nested = outer / "nested-project"
            task_dir = nested / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "decision-anchor.md").write_text("# Nested task\n", encoding="utf-8")

            implementation = importlib.import_module("common.gates.validate_implementation")
            coding = importlib.import_module("common.gates.validate_coding_standards")

            self.assertEqual([], implementation.validate_implementation(nested, task_dir))
            self.assertEqual([], coding.validate_coding_standards(nested, task_dir))

    def test_cmd_review_allows_regular_diff_that_mentions_spec_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            workflow_dir = root / ".cowork-flow"
            task_dir = workflow_dir / "tasks" / "05-19-demo"
            app_dir = root / "src"
            task_dir.mkdir(parents=True)
            app_dir.mkdir()
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                '{"status": "in_progress", "completedAt": null}\n',
                encoding="utf-8",
            )
            (app_dir / "check.py").write_text("MARKER = 'baseline'\n", encoding="utf-8")
            self._write_session_task(root)
            self._commit_all(root, "baseline")
            (app_dir / "check.py").write_text(
                "MARKER = 'AGENTS.md is context, not a changed file'\n",
                encoding="utf-8",
            )

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with (
                        contextlib.redirect_stdout(io.StringIO()),
                        contextlib.redirect_stderr(io.StringIO()) as stderr,
                    ):
                        result = self.task.cmd_review(argparse.Namespace(dir=None))
            finally:
                os.chdir(previous_cwd)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(0, result, stderr.getvalue())
            self.assertEqual("review", data["status"])

    def test_cmd_review_blocks_behavior_change_without_tdd_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                '{"status": "in_progress", "completedAt": null}\n',
                encoding="utf-8",
            )
            self._write_behavior_prd(task_dir)
            self._write_session_task(root)

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with (
                        contextlib.redirect_stdout(io.StringIO()),
                        contextlib.redirect_stderr(io.StringIO()) as stderr,
                    ):
                        result = self.task.cmd_review(argparse.Namespace(dir=None))
            finally:
                os.chdir(previous_cwd)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(1, result)
            self.assertEqual("in_progress", data["status"])
            self.assertIn("TDD evidence", stderr.getvalue())

    def test_cmd_review_accepts_valid_tdd_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                '{"status": "in_progress", "completedAt": null}\n',
                encoding="utf-8",
            )
            self._write_behavior_prd(task_dir)
            self._write_valid_tdd_evidence(task_dir)
            self._write_session_task(root)

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with (
                        contextlib.redirect_stdout(io.StringIO()),
                        contextlib.redirect_stderr(io.StringIO()) as stderr,
                    ):
                        result = self.task.cmd_review(argparse.Namespace(dir=None))
            finally:
                os.chdir(previous_cwd)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(0, result, stderr.getvalue())
            self.assertEqual("review", data["status"])

    def test_cmd_review_blocks_coding_standards_violations_across_git_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_non_behavior_review_task(root, task_dir)
            self._write_encoding_violation_changes(root)

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with (
                        contextlib.redirect_stdout(io.StringIO()),
                        contextlib.redirect_stderr(io.StringIO()) as stderr,
                    ):
                        result = self.task.cmd_review(argparse.Namespace(dir=None))
            finally:
                os.chdir(previous_cwd)

            stderr_text = stderr.getvalue()
            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(1, result, stderr_text)
            self.assertEqual("in_progress", data["status"])
            # R-AG-005 现在检查 modified files 是否在 implement.jsonl 中
            self.assertIn("R-AG-005", stderr_text)
            # 至少有一个不在 implement.jsonl 中的文件被报告
            self.assertTrue(
                "src/modified.py" in stderr_text
                or "src/staged.js" in stderr_text
                or "scripts/untracked.ps1" in stderr_text,
                f"Expected at least one file violation in stderr: {stderr_text}",
            )

    def test_cmd_complete_blocks_coding_standards_violations_without_status_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_non_behavior_review_task(root, task_dir, status="review")
            self._write_encoding_violation_changes(root)

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with (
                        contextlib.redirect_stdout(io.StringIO()),
                        contextlib.redirect_stderr(io.StringIO()) as stderr,
                    ):
                        result = self.task.cmd_complete(argparse.Namespace(dir=None))
            finally:
                os.chdir(previous_cwd)

            stderr_text = stderr.getvalue()
            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(1, result, stderr_text)
            self.assertEqual("review", data["status"])
            self.assertIsNone(data["completedAt"])
            self.assertIn("Coding standards", stderr_text)

    def test_coding_standards_summary_uses_explicit_utf8_for_git_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            spec_dir = root / ".cowork-flow" / "spec" / "backend"
            spec_dir.mkdir(parents=True)
            (spec_dir / "encoding-guidelines.md").write_text(
                "# Encoding\n\n- 禁止 依赖系统默认编码。\n",
                encoding="utf-8",
            )
            validator = importlib.import_module("common.gates.validate_coding_standards")
            calls: list[dict] = []

            def fake_run(args, **kwargs):
                calls.append(kwargs)
                return subprocess.CompletedProcess(
                    args,
                    0,
                    stdout=" M src/example.py\n",
                    stderr="",
                )

            with patch("subprocess.run", side_effect=fake_run):
                summary = validator.get_coding_standards_summary(root, task_dir)

            self.assertIn("Backend spec rules", summary)
            self.assertTrue(calls)
            self.assertEqual("utf-8", calls[0].get("encoding"))
            self.assertEqual("replace", calls[0].get("errors"))

    def test_tdd_evidence_accepts_documentation_exemption(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-docs"
            task_dir.mkdir(parents=True)
            (task_dir / "decision-anchor.md").write_text(
                "# Docs task\n\n## 验收标准\n\n- AC-001: 文档措辞更新。\n",
                encoding="utf-8",
            )
            (task_dir / "tdd.jsonl").write_text(
                json.dumps(
                    {
                        "type": "exemption",
                        "acceptanceId": "AC-001",
                        "exemptionType": "docs-only",
                        "reason": "Only documentation wording changes; no runtime behavior changes.",
                        "verificationCommand": "git diff --check",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            tdd_evidence = importlib.import_module("common.gates.tdd_evidence")

            self.assertEqual([], tdd_evidence.validate_tdd_evidence(task_dir))
            self.assertEqual([], tdd_evidence.validate_tdd_red_evidence(task_dir))

    def test_cmd_complete_blocks_without_review_without_status_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                '{"status": "in_progress", "completedAt": null}\n',
                encoding="utf-8",
            )
            self._write_session_task(root)

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with (
                        contextlib.redirect_stdout(io.StringIO()),
                        contextlib.redirect_stderr(io.StringIO()) as stderr,
                    ):
                        result = self.task.cmd_complete(argparse.Namespace(dir=None))
            finally:
                os.chdir(previous_cwd)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(1, result)
            self.assertEqual("in_progress", data["status"])
            self.assertIsNone(data["completedAt"])
            self.assertIn("task review", stderr.getvalue())
