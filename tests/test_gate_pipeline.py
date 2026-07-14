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
    @staticmethod
    def _write_context_scope_fixture(task_dir: Path) -> None:
        entries = [
            {
                "file": "src/planned.py",
                "reason": "Planned source",
                "type": "planned-file",
            },
            {
                "file": "src/unknown.py",
                "reason": "Unknown type",
                "type": "mystery",
            },
            {
                "file": "src/",
                "reason": "Directory context",
                "type": "directory",
            },
        ]
        (task_dir / "implement.jsonl").write_text(
            "\n".join(json.dumps(entry) for entry in entries) + "\n",
            encoding="utf-8",
        )

    def _write_allowed_file_task(self, root: Path, task_dir: Path, status: str) -> None:
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "task.json").write_text(
            json.dumps({"status": status, "completedAt": None}),
            encoding="utf-8",
        )
        (task_dir / "decision-anchor.md").write_text(
            "# Demo\n\n## 验收标准\n\n- AC-001: only planned files change.\n",
            encoding="utf-8",
        )
        (task_dir / "implement.jsonl").write_text(
            json.dumps({"file": "src/allowed.py", "reason": "planned"})
            + "\n",
            encoding="utf-8",
        )
        (task_dir / "tdd.jsonl").write_text(
            json.dumps(
                {
                    "type": "exemption",
                    "acceptanceId": "AC-001",
                    "exemptionType": "test-only",
                    "reason": "Fixture covers implementation gate file scope only.",
                    "verificationCommand": "python -m pytest tests/test_gate_pipeline.py -q",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        for name in ("check.jsonl", "debug.jsonl"):
            (task_dir / name).write_text(
                json.dumps({"file": "src/allowed.py", "reason": "fixture"}) + "\n",
                encoding="utf-8",
            )
        self._write_quality_review_evidence(task_dir, files=("src/allowed.py",))
        self._write_rules_file(
            root,
            [
                {
                    **self._workflow_rule("R-AG-005", "all"),
                    "type": "forbidden_action",
                    "enforcement": "validate_implementation",
                    "message": "Modified file is outside implement.jsonl scope",
                    "fix_hint": "List the file in implement.jsonl or remove the change.",
                }
            ],
        )

    def _write_mixed_git_status_fixture(self, root: Path) -> None:
        src = root / "src"
        src.mkdir(parents=True, exist_ok=True)
        (src / "allowed.py").write_text("VALUE = 1\n", encoding="utf-8")
        (src / "unstaged.py").write_text("VALUE = 1\n", encoding="utf-8")
        (src / "staged.py").write_text("VALUE = 1\n", encoding="utf-8")
        self._commit_all(root, "baseline")
        (src / "unstaged.py").write_text("VALUE = 2\n", encoding="utf-8")
        (src / "staged.py").write_text("VALUE = 2\n", encoding="utf-8")
        self._run_git(root, "add", "src/staged.py")
        (src / "untracked.py").write_text("VALUE = 2\n", encoding="utf-8")

    def test_r_ag_005_only_authorizes_known_exact_context_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            task_dir.mkdir(parents=True)
            self._write_context_scope_fixture(task_dir)
            implementation = importlib.import_module(
                "common.gates.validate_implementation"
            )
            rule_index = {
                "R-AG-005": self._workflow_rule("R-AG-005", "all"),
            }

            with patch.object(
                implementation,
                "_get_modified_files",
                return_value=[
                    "src/planned.py",
                    "src/planned_extra.py",
                    "src/unknown.py",
                    "src/nested.py",
                ],
            ):
                violations = implementation._check_unrequested_features(
                    root,
                    "",
                    task_dir,
                    rule_index,
                )

            violation_paths = {violation.get("file") for violation in violations}
            self.assertNotIn("src/planned.py", violation_paths)
            self.assertEqual(
                {"src/planned_extra.py", "src/unknown.py", "src/nested.py"},
                violation_paths,
            )

    def test_r_ag_005_checks_unstaged_staged_and_untracked_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            task_dir = root / ".cowork-flow" / "tasks" / "07-12-demo"
            self._write_allowed_file_task(root, task_dir, "in_progress")
            self._write_mixed_git_status_fixture(root)
            implementation = importlib.import_module(
                "common.gates.validate_implementation"
            )

            violations = implementation.validate_implementation(root, task_dir)

            self.assertEqual(
                {"src/staged.py", "src/unstaged.py", "src/untracked.py"},
                {
                    violation.get("file")
                    for violation in violations
                    if violation.get("rule_id") == "R-AG-005"
                },
            )

    def test_cmd_complete_blocks_unrequested_files_without_status_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_allowed_file_task(root, task_dir, "review")
            self._write_mixed_git_status_fixture(root)
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
            self.assertEqual(1, result, stderr.getvalue())
            self.assertEqual("review", data["status"])
            self.assertIsNone(data["completedAt"])
            self.assertIn(
                "Implementation gate blocked lifecycle transition",
                stderr.getvalue(),
            )
            self.assertNotIn("blocked task review", stderr.getvalue())
            self.assertIn("R-AG-005", stderr.getvalue())

    def test_cmd_review_and_complete_update_active_task_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                '{"status": "in_progress", "completedAt": null}\n',
                encoding="utf-8",
            )
            self._write_quality_review_evidence(task_dir)
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

    def test_cmd_complete_blocks_missing_quality_review_without_status_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                '{"status": "review", "completedAt": null}\n',
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
            self.assertEqual(1, result, stderr.getvalue())
            self.assertEqual("review", data["status"])
            self.assertIsNone(data["completedAt"])
            self.assertIn("Quality review gate blocked lifecycle transition", stderr.getvalue())
            self.assertIn("QUALITY-REVIEW-MISSING-001", stderr.getvalue())

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
            self._write_quality_review_evidence(task_dir)
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
                        review_result = self.task.cmd_review(argparse.Namespace(dir=None))
                        complete_result = self.task.cmd_complete(argparse.Namespace(dir=None))
            finally:
                os.chdir(previous_cwd)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(0, review_result, stderr.getvalue())
            self.assertEqual(0, complete_result, stderr.getvalue())
            self.assertEqual("completed", data["status"])

    def _write_bound_subagent_review_fixture(
        self,
        root: Path,
        *,
        status: str = "in_progress",
    ) -> Path:
        self._init_git_repo(root)
        workflow_dir = root / ".cowork-flow"
        task_dir = workflow_dir / "tasks" / "05-19-demo"
        task_dir.mkdir(parents=True)
        (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
        (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
        (task_dir / "task.json").write_text(
            json.dumps({"status": status, "completedAt": None}) + "\n",
            encoding="utf-8",
        )
        self._write_session_task(
            root,
            scope="subagent",
            runtime_context_id="runtime-demo",
        )
        self._write_rules_file(
            root,
            [{
                **self._workflow_rule("R-AG-002", "all"),
                "type": "forbidden_action",
                "enforcement": "validate_implementation",
                "message": "Subagent attempted to modify spec files",
                "fix_hint": "Spec files can only be modified by main session",
            }],
        )
        self._commit_all(root, "baseline")
        (root / "AGENTS.md").write_text(
            "# Rules changed by subagent\n",
            encoding="utf-8",
        )
        return task_dir

    def test_cmd_complete_blocks_spec_changes_for_bound_subagent_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._write_bound_subagent_review_fixture(
                root,
                status="review",
            )

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
            self.assertEqual("review", data["status"])
            self.assertIn("Subagent attempted to modify spec files", stderr.getvalue())

    def test_cmd_review_rejects_coordinator_flag_for_bound_subagent_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._write_bound_subagent_review_fixture(root)

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
            (task_dir / "implement.jsonl").write_text(
                "".join(
                    json.dumps({"file": file_path}) + "\n"
                    for file_path in (
                        "src/modified.py",
                        "src/staged.js",
                        "scripts/untracked.ps1",
                    )
                ),
                encoding="utf-8",
            )
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
                stdout = (
                    ""
                    if "rev-parse" in args
                    else " M src/example.py\n"
                )
                return subprocess.CompletedProcess(
                    args,
                    0,
                    stdout=stdout,
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
