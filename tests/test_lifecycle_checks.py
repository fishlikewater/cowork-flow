from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.flow_test_support import FlowScriptTestCase


class LifecycleChecksTest(FlowScriptTestCase):
    @staticmethod
    def _write_context_scope_fixture(task_dir: Path) -> None:
        entries = [
            {"file": "src/planned.py", "reason": "Planned source", "type": "planned-file"},
            {"file": "src/obsolete.py", "reason": "Deleted source", "type": "deleted-file"},
            {"file": "src/", "reason": "Directory context", "type": "directory"},
        ]
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "implement.jsonl").write_text(
            "\n".join(json.dumps(entry) for entry in entries) + "\n",
            encoding="utf-8",
        )

    def _write_allowed_file_task(
        self,
        root: Path,
        task_dir: Path,
        status: str,
        *,
        allowed_files: tuple[str, ...] = ("src/allowed.py",),
    ) -> None:
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "task.json").write_text(
            json.dumps({"status": status, "completedAt": None}),
            encoding="utf-8",
        )
        (task_dir / "decision-anchor.md").write_text(
            "# Demo\n\n## 目标\n\nKeep scope explicit.\n\n## 验收标准\n\n- Only planned files change.\n",
            encoding="utf-8",
        )
        (task_dir / "implement.jsonl").write_text(
            "".join(json.dumps({"file": file_path, "reason": "planned"}) + "\n" for file_path in allowed_files),
            encoding="utf-8",
        )
        for name in ("check.jsonl", "debug.jsonl"):
            (task_dir / name).write_text(
                json.dumps({"file": allowed_files[0], "reason": "fixture"}) + "\n",
                encoding="utf-8",
            )

    def _write_mixed_git_status_fixture(self, root: Path) -> None:
        src = root / "src"
        src.mkdir(parents=True, exist_ok=True)
        for name in ("allowed.py", "unstaged.py", "staged.py"):
            (src / name).write_text("VALUE = 1\n", encoding="utf-8")
        self._commit_all(root, "baseline")
        (src / "unstaged.py").write_text("VALUE = 2\n", encoding="utf-8")
        (src / "staged.py").write_text("VALUE = 2\n", encoding="utf-8")
        self._run_git(root, "add", "src/staged.py")
        (src / "untracked.py").write_text("VALUE = 2\n", encoding="utf-8")

    def _run_review(self, root: Path) -> tuple[int, str, str]:
        previous_cwd = Path.cwd()
        try:
            os.chdir(root)
            with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                with (
                    contextlib.redirect_stdout(io.StringIO()) as stdout,
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_review(argparse.Namespace(dir=None))
        finally:
            os.chdir(previous_cwd)
        return result, stdout.getvalue(), stderr.getvalue()

    def _run_complete(
        self,
        root: Path,
        *,
        allow_missing_evidence: bool = False,
        context_id: str | None = "main",
    ) -> tuple[int, str, str]:
        previous_cwd = Path.cwd()
        environment = (
            {} if context_id is None else {"COWORK_FLOW_CONTEXT_ID": context_id}
        )
        try:
            os.chdir(root)
            with patch.dict(os.environ, environment):
                if context_id is None:
                    os.environ.pop("COWORK_FLOW_CONTEXT_ID", None)
                with (
                    contextlib.redirect_stdout(io.StringIO()) as stdout,
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_complete(
                        argparse.Namespace(
                            dir=None,
                            allow_missing_evidence=allow_missing_evidence,
                        )
                    )
        finally:
            os.chdir(previous_cwd)
        return result, stdout.getvalue(), stderr.getvalue()

    def _write_ac_gate_task(
        self,
        root: Path,
        task_dir: Path,
        *,
        checked: bool = True,
        with_evidence: bool = False,
    ) -> None:
        self._write_allowed_file_task(root, task_dir, "review")
        (task_dir / "decision-anchor.md").write_text(
            "# Demo\n\n## 目标\n\nEvidence gate.\n\n## 验收标准\n\n"
            + f"- [{'x' if checked else ' '}] AC-001: parser exposes check state.\n",
            encoding="utf-8",
        )
        if with_evidence:
            (task_dir / "evidence.jsonl").write_text(
                json.dumps(
                    {
                        "ac": "AC-001",
                        "kind": "test",
                        "ref": "tests/test_x.py::test_y",
                        "recordedAt": "2026-10-06",
                        "by": "probe",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

    def test_complete_blocks_on_unchecked_acceptance_criteria(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_ac_gate_task(root, task_dir, checked=False)
            checks = importlib.import_module("services.lifecycle_checks")

            result = checks.LifecycleCheckRunner(root).complete(task_dir)

            self.assertTrue(result.blocked)
            codes = {issue.code for issue in result.issues}
            self.assertIn("LIFECYCLE-AC-001", codes)
            self.assertNotIn("LIFECYCLE-AC-002", codes)
            self.assertEqual(
                [
                    (
                        "LIFECYCLE-AC-001",
                        None,
                        "decision-anchor has 1 unchecked acceptance criterion(ies): AC-001; "
                        "finish them and tick the checkbox, or record evidence in evidence.jsonl",
                    )
                ],
                [(issue.code, issue.path, issue.message) for issue in result.issues],
            )

    def test_complete_blocks_on_checked_ac_without_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_ac_gate_task(root, task_dir, checked=True)
            checks = importlib.import_module("services.lifecycle_checks")

            result = checks.LifecycleCheckRunner(root).complete(task_dir)

            self.assertTrue(result.blocked)
            codes = {issue.code for issue in result.issues}
            self.assertIn("LIFECYCLE-AC-002", codes)
            self.assertNotIn("LIFECYCLE-AC-001", codes)
            ac002 = next(i for i in result.issues if i.code == "LIFECYCLE-AC-002")
            self.assertIn("evidence.jsonl", ac002.message)
            self.assertIn("--allow-missing-evidence", ac002.message)
            self.assertEqual(
                [
                    (
                        "LIFECYCLE-AC-002",
                        None,
                        "1 acceptance criterion(ies) lack evidence records: AC-001; append "
                        "{ac, kind: test|command|manual, ref, note?, recordedAt, by} records to "
                        "evidence.jsonl, or pass --allow-missing-evidence to record the exemption",
                    )
                ],
                [(issue.code, issue.path, issue.message) for issue in result.issues],
            )

    def test_complete_ac_gate_skipped_without_acceptance_criteria(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_allowed_file_task(root, task_dir, "review")
            checks = importlib.import_module("services.lifecycle_checks")

            result = checks.LifecycleCheckRunner(root).complete(task_dir)

            self.assertFalse(result.blocked)
            codes = {issue.code for issue in result.issues}
            self.assertNotIn("LIFECYCLE-AC-001", codes)
            self.assertNotIn("LIFECYCLE-AC-002", codes)
            self.assertEqual([], list(result.issues))
            self.assertEqual(0, len(result.blockers))

    def test_fingerprint_covers_declared_scope_and_spec_content(self) -> None:
        """`.cowork-flow/**` never reaches the change set, so the fingerprint
        has to carry the declared scope and the referenced spec bodies itself.

        A name-only spec list would leave both a rewritten requirement and a
        widened scope invisible, and the receipt would keep passing.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            spec = root / ".cowork-flow" / "spec" / "backend" / "demo.md"
            spec.parent.mkdir(parents=True, exist_ok=True)
            spec.write_text("原文要求。\n", encoding="utf-8")
            task_dir.mkdir(parents=True, exist_ok=True)
            (task_dir / "task.json").write_text(
                json.dumps({"status": "review", "dev_type": "backend"}),
                encoding="utf-8",
            )
            (task_dir / "decision-anchor.md").write_text(
                "# Demo\n\n## 目标\n\n演示。\n\n## 验收标准\n\n- [ ] AC-001: 条款。\n",
                encoding="utf-8",
            )

            def declare(files: tuple[str, ...]) -> None:
                (task_dir / "implement.jsonl").write_text(
                    "".join(
                        json.dumps(
                            {"file": item, "reason": "planned", "type": "planned-file"},
                            ensure_ascii=False,
                        )
                        + "\n"
                        for item in files
                    ),
                    encoding="utf-8",
                )

            checks = importlib.import_module("services.lifecycle_checks")
            declare((".cowork-flow/spec/backend/demo.md", "src/planned.py"))
            baseline = checks.compute_change_fingerprint(root, task_dir)

            spec.write_text("换了要求。\n", encoding="utf-8")
            self.assertNotEqual(
                baseline,
                checks.compute_change_fingerprint(root, task_dir),
                msg="改写被引用 spec 的正文必须改变指纹",
            )

            spec.write_text("原文要求。\n", encoding="utf-8")
            declare(
                (
                    ".cowork-flow/spec/backend/demo.md",
                    "src/planned.py",
                    "src/extra.py",
                )
            )
            self.assertNotEqual(
                baseline,
                checks.compute_change_fingerprint(root, task_dir),
                msg="扩大声明范围必须改变指纹",
            )

            # A pointer whose file is missing must still count: the reading
            # list changed, so the review judged a different list. The pointer
            # list is injected with implement.jsonl frozen at the baseline —
            # rewriting the file would move the scope digest as well and the
            # assertion would hold even if this component noticed nothing.
            declare((".cowork-flow/spec/backend/demo.md", "src/planned.py"))

            def fingerprint_for(pointers: list[str]) -> str:
                with patch.object(
                    checks, "spec_pointer_files", return_value=pointers
                ):
                    return checks.compute_change_fingerprint(root, task_dir)

            missing_one = fingerprint_for(
                [".cowork-flow/spec/backend/missing-one.md"]
            )
            missing_two = fingerprint_for(
                [".cowork-flow/spec/backend/missing-two.md"]
            )
            no_pointer = fingerprint_for([])

            self.assertNotEqual(
                no_pointer,
                missing_one,
                msg="缺失指针仍须进入指纹（缺失记 absent，而不是被丢掉）",
            )
            self.assertNotEqual(
                missing_one,
                missing_two,
                msg="两个缺失指针必须可区分（名字保留，不是折叠成同一个 absent）",
            )

    def test_evidence_record_satisfies_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_ac_gate_task(root, task_dir, checked=True, with_evidence=True)
            checks = importlib.import_module("services.lifecycle_checks")

            result = checks.LifecycleCheckRunner(root).complete(task_dir)

            self.assertFalse(result.blocked)
            self.assertIsNone(result.evidence_exemption)

    def test_allow_missing_evidence_sets_exemption_on_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_ac_gate_task(root, task_dir, checked=True)
            checks = importlib.import_module("services.lifecycle_checks")

            result = checks.LifecycleCheckRunner(root).complete(
                task_dir, allow_missing_evidence=True
            )

            self.assertFalse(result.blocked)
            self.assertEqual(
                {"missing": ["AC-001"], "flag": "--allow-missing-evidence"},
                result.evidence_exemption,
            )

    def test_service_complete_records_evidence_exemption_in_meta(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_ac_gate_task(root, task_dir, checked=True)
            service_module = importlib.import_module("services.task_lifecycle")
            service = service_module.TaskLifecycleService(root)

            result = service.complete(task_dir, allow_missing_evidence=True)

            self.assertTrue(result.ok, result.blockers)
            task_data = json.loads(
                (task_dir / "task.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                ["AC-001"],
                task_data["meta"]["evidenceExempt"]["missing"],
            )

    def test_allow_missing_evidence_flag_reaches_complete_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_ac_gate_task(root, task_dir, checked=True)
            calls: list[dict] = []

            class FakeCheckRunner:
                def complete(self, _task_dir: Path, **kwargs):
                    calls.append(kwargs)
                    return SimpleNamespace(
                        blocked=False, blockers=(), evidence_exemption=None
                    )

            service_module = importlib.import_module("services.task_lifecycle")
            service = service_module.TaskLifecycleService(
                root,
                check_runner=FakeCheckRunner(),
            )

            result = service.complete(
                task_dir, allow_missing_evidence=True
            )

            self.assertTrue(result.ok, result.blockers)
            self.assertIs(True, calls[0]["allow_missing_evidence"])

    def test_parsed_missing_evidence_flag_reaches_complete_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_ac_gate_task(root, task_dir, checked=True)
            self._write_session_task(root)
            self._commit_all(root, "baseline")
            calls: list[dict] = []

            class FakeCheckRunner:
                def complete(self, _task_dir: Path, **kwargs):
                    calls.append(kwargs)
                    return SimpleNamespace(
                        blocked=False, blockers=(), evidence_exemption=None
                    )

            args = self.task.build_parser().parse_args(
                ["next", "--run", "--allow-missing-evidence"]
            )
            service_module = importlib.import_module("services.task_lifecycle")
            service = service_module.TaskLifecycleService(
                root,
                check_runner=FakeCheckRunner(),
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
                    patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}),
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    result = self.task.cmd_complete(args)
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(0, result)
            self.assertEqual(1, len(calls))
            self.assertIs(True, calls[0]["allow_missing_evidence"])
            # The spec-check exemption flag is gone: the parser must reject it
            # rather than accept a flag nothing consults.
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    self.task.build_parser().parse_args(
                        ["next", "--run", "--allow-unchecked"]
                    )
            self.assertEqual(2, raised.exception.code)

    def test_degraded_git_snapshot_blocks_strict_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_allowed_file_task(root, task_dir, "review")
            task_json = task_dir / "task.json"
            task_data = json.loads(task_json.read_text(encoding="utf-8"))
            task_data["meta"] = {"baselineCommit": "baseline-sha"}
            task_json.write_text(
                json.dumps(task_data),
                encoding="utf-8",
            )
            checks = importlib.import_module("services.lifecycle_checks")

            with patch(
                "infra.git_snapshot.collect_changed_paths_since",
                return_value=([], True),
            ):
                result = checks.LifecycleCheckRunner(root).complete(task_dir)

            self.assertTrue(result.blocked)
            self.assertIn(
                "git snapshot degraded",
                "\n".join(result.blockers).lower(),
            )
            self.assertIn(
                "GIT-SNAPSHOT-DEGRADED",
                {issue.code for issue in result.issues},
            )
            self.assertEqual(
                [
                    (
                        "GIT-SNAPSHOT-DEGRADED",
                        None,
                        "Git snapshot degraded; cannot verify the complete file scope "
                        "because the baseline diff is unavailable",
                    )
                ],
                [(issue.code, issue.path, issue.message) for issue in result.issues],
            )

    def test_allowed_file_scope_authorizes_known_exact_context_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            self._write_context_scope_fixture(task_dir)
            checks = importlib.import_module("services.lifecycle_checks")

            blockers = checks._allowed_file_scope_blockers(
                task_dir,
                [
                    "src/planned.py",
                    "src/obsolete.py",
                    "src/planned_extra.py",
                    "src/ignored.py",
                ],
            )

        self.assertEqual(
            [
                "Modified file not listed in implement.jsonl: src/planned_extra.py",
                "Modified file not listed in implement.jsonl: src/ignored.py",
            ],
            blockers,
        )

    def test_allowed_file_scope_blocks_malformed_existing_implement_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            task_dir = Path(temp_dir) / ".cowork-flow" / "tasks" / "07-10-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "implement.jsonl").write_text(
                "{\"file\": \"src/allowed.py\"}\nnot-json\n",
                encoding="utf-8",
            )
            checks = importlib.import_module("services.lifecycle_checks")

            blockers = checks._allowed_file_scope_blockers(task_dir, ["src/allowed.py"])

        self.assertEqual(["Invalid implement.jsonl JSON at line 2"], blockers)

    def test_allowed_file_scope_blocks_missing_implement_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            task_dir = Path(temp_dir) / ".cowork-flow" / "tasks" / "07-10-demo"
            task_dir.mkdir(parents=True)
            checks = importlib.import_module("services.lifecycle_checks")

            blockers = checks._allowed_file_scope_blockers(
                task_dir, ["src/anything.py"]
            )

        self.assertEqual(
            ["implement.jsonl is missing; file-scope review cannot run (remove it and every unlisted edit becomes a free pass at review)"],
            blockers,
        )

    def test_allowed_file_scope_blocks_existing_implement_jsonl_without_file_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            task_dir = Path(temp_dir) / ".cowork-flow" / "tasks" / "07-10-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "implement.jsonl").write_text(
                json.dumps({"file": "src/", "reason": "directory context", "type": "directory"}) + "\n",
                encoding="utf-8",
            )
            checks = importlib.import_module("services.lifecycle_checks")

            blockers = checks._allowed_file_scope_blockers(task_dir, ["src/allowed.py"])

        self.assertEqual(["implement.jsonl contains no valid file-scope entries"], blockers)

    def test_lifecycle_checks_unstaged_staged_and_untracked_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            task_dir = root / ".cowork-flow" / "tasks" / "07-12-demo"
            self._write_allowed_file_task(root, task_dir, "in_progress")
            self._write_mixed_git_status_fixture(root)
            checks = importlib.import_module("services.lifecycle_checks")

            result = checks.LifecycleCheckRunner(root).review(
                task_dir,
                allow_spec_file_modifications=True,
            )

        self.assertTrue(result.blocked)
        self.assertEqual(
            {
                "Modified file not listed in implement.jsonl: src/staged.py",
                "Modified file not listed in implement.jsonl: src/unstaged.py",
                "Modified file not listed in implement.jsonl: src/untracked.py",
            },
            set(result.blockers),
        )
        self.assertEqual(
            {
                ("unlisted_changed_file", "src/staged.py"),
                ("unlisted_changed_file", "src/unstaged.py"),
                ("unlisted_changed_file", "src/untracked.py"),
            },
            {(issue.code, issue.path) for issue in result.issues},
        )

    def test_lifecycle_checks_expose_structured_protected_workflow_issues(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            task_dir = root / ".cowork-flow" / "tasks" / "07-12-demo"
            self._write_allowed_file_task(
                root,
                task_dir,
                "in_progress",
                allowed_files=("src/allowed.py", "AGENTS.md"),
            )
            (root / "src").mkdir(parents=True, exist_ok=True)
            (root / "src" / "allowed.py").write_text("VALUE = 1\n", encoding="utf-8")
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            self._commit_all(root, "baseline")
            (root / "AGENTS.md").write_text("# Rules changed\n", encoding="utf-8")
            checks = importlib.import_module("services.lifecycle_checks")

            result = checks.LifecycleCheckRunner(root).review(
                task_dir,
                allow_spec_file_modifications=False,
            )

        self.assertEqual(
            ("Protected workflow/spec file changed outside main session: AGENTS.md",),
            result.blockers,
        )
        self.assertEqual(1, len(result.issues))
        self.assertEqual("protected_workflow_file", result.issues[0].code)
        self.assertEqual("AGENTS.md", result.issues[0].path)

    def test_cmd_complete_blocks_unrequested_files_without_status_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_allowed_file_task(root, task_dir, "review")
            self._write_mixed_git_status_fixture(root)
            self._write_session_task(root)

            result, _stdout, stderr = self._run_complete(root)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(1, result, stderr)
            self.assertEqual("review", data["status"])
            self.assertIsNone(data["completedAt"])
            self.assertIn("Lifecycle checks blocked completion", stderr)
            self.assertIn("Modified file not listed in implement.jsonl: src/staged.py", stderr)

    def test_cmd_review_and_complete_update_active_task_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_allowed_file_task(root, task_dir, "in_progress")
            self._write_session_task(root)

            review_result, _review_stdout, review_stderr = self._run_review(root)
            complete_result, _complete_stdout, complete_stderr = self._run_complete(root)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(0, review_result, review_stderr)
            self.assertEqual(0, complete_result, complete_stderr)
            self.assertEqual("completed", data["status"])
            self.assertEqual(datetime.now().strftime("%Y-%m-%d"), data["completedAt"])

    def test_cmd_complete_allows_missing_task_local_review_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_allowed_file_task(root, task_dir, "review")
            self._write_session_task(root)

            result, _stdout, stderr = self._run_complete(root)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(0, result, stderr)
            self.assertEqual("completed", data["status"])

    def _run_next_command(
        self,
        root: Path,
        argv: list[str],
        *,
        env_context: str = "main",
    ) -> tuple[int, str, str]:
        args = self.task.build_parser().parse_args(argv)
        previous_cwd = Path.cwd()
        try:
            os.chdir(root)
            with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": env_context}):
                with (
                    contextlib.redirect_stdout(io.StringIO()) as stdout,
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_next(args)
        finally:
            os.chdir(previous_cwd)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_adopted_stale_task_runs_review_complete_archive_chain(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_ac_gate_task(root, task_dir, checked=True, with_evidence=True)
            self._write_session_task(root)
            self._commit_all(root, "baseline")

            # The stale task: a dead session owns it and its baseline was
            # recorded before the repository moved on.
            task_json = task_dir / "task.json"
            data = json.loads(task_json.read_text(encoding="utf-8"))
            data["status"] = "in_progress"
            data["executor"] = "session-dead"
            data["meta"] = {"baselineCommit": "stale-baseline-sha"}
            task_json.write_text(json.dumps(data), encoding="utf-8")
            self._commit_all(root, "repo moved on")

            adopted, stdout, stderr = self._run_next_command(
                root, ["next", str(task_dir), "--run", "--adopt"]
            )
            self.assertEqual(0, adopted, stderr)
            self.assertIn("Handover:", stdout)
            self.assertIn("session-dead -> main", stdout)
            self.assertIn("stale-baseline-sha", stdout)
            self.assertIn("pending acceptance criteria: 0 of 1", stdout)
            self.assertIn("evidence coverage: 1/1", stdout)
            data = json.loads(task_json.read_text(encoding="utf-8"))
            self.assertEqual("in_progress", data["status"], "adopt keeps status")
            self.assertEqual("main", data["executor"])
            self.assertEqual("session-dead", data["meta"]["previousExecutor"])
            self.assertEqual(
                "stale-baseline-sha", data["meta"]["previousBaseline"]
            )
            self.assertNotEqual(
                "stale-baseline-sha",
                data["meta"]["baselineCommit"],
                "adopt resets the review baseline",
            )

            reviewed, _stdout, stderr = self._run_next_command(
                root, ["next", str(task_dir), "--run", "--intent", "review"]
            )
            self.assertEqual(0, reviewed, stderr)
            self.assertEqual(
                "review",
                json.loads(task_json.read_text(encoding="utf-8"))["status"],
            )

            completed, _stdout, stderr = self._run_next_command(
                root, ["next", str(task_dir), "--run"]
            )
            self.assertEqual(0, completed, stderr)
            self.assertEqual(
                "completed",
                json.loads(task_json.read_text(encoding="utf-8"))["status"],
            )

            archived, _stdout, stderr = self._run_next_command(
                root, ["next", str(task_dir), "--run"]
            )
            self.assertEqual(0, archived, stderr)
            self.assertFalse(task_dir.exists())
            archived_dirs = [
                path
                for path in (
                    root / ".cowork-flow" / "tasks" / "archive"
                ).rglob("05-19-demo")
                if path.is_dir()
            ]
            self.assertEqual(1, len(archived_dirs))

    def test_completion_records_the_missing_ac_ids_flag_and_actor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_ac_gate_task(root, task_dir, checked=True)
            self._write_session_task(root)

            result, stdout, stderr = self._run_complete(
                root, allow_missing_evidence=True
            )

            self.assertEqual(0, result, stderr)
            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            record = data["meta"]["evidenceExempt"]
            self.assertEqual(["AC-001"], record["missing"])
            self.assertEqual("--allow-missing-evidence", record["flag"])
            self.assertEqual("main", record["by"])
            for line in importlib.import_module("services.lifecycle_checks").exemption_report_lines(data["meta"]):
                self.assertIn(line, stdout)

    def test_an_unresolved_actor_is_recorded_and_printed_as_null(self) -> None:
        """No session identity means an unknown actor, not the assignee."""
        host_identity = importlib.import_module("runtime.host_identity")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_ac_gate_task(root, task_dir, checked=True)
            task_json = json.loads(
                (task_dir / "task.json").read_text(encoding="utf-8")
            )
            task_json["assignee"] = "someone-else"
            (task_dir / "task.json").write_text(
                json.dumps(task_json), encoding="utf-8"
            )
            # Every identity source has to go: a process-level label is still
            # an identity, and leaving one set would make this test depend on
            # whoever launched pytest.
            cleared = (
                ["COWORK_FLOW_CONTEXT_ID"]
                + [name for _prefix, name in host_identity.session_env_providers()]
                + [
                    name
                    for _prefix, name in host_identity.process_label_providers()
                ]
            )
            service_module = importlib.import_module("services.task_lifecycle")
            with patch.dict(os.environ, {name: "" for name in cleared}):
                for name in cleared:
                    os.environ.pop(name, None)
                result = service_module.TaskLifecycleService(root).complete(
                    task_dir, allow_missing_evidence=True
                )
            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))

        self.assertTrue(result.ok, result.blockers)
        self.assertIsNone(data["meta"]["evidenceExempt"]["by"])
        lines = importlib.import_module(
            "services.lifecycle_checks"
        ).exemption_report_lines(data["meta"])
        self.assertTrue(any("by null" in line for line in lines), lines)
        self.assertFalse(any("someone-else" in line for line in lines), lines)

    def test_completion_without_exemptions_prints_no_exemption_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_allowed_file_task(root, task_dir, "review")
            self._write_session_task(root)

            result, stdout, stderr = self._run_complete(root)

            self.assertEqual(0, result, stderr)
            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertNotIn("Exempted:", stdout)
            # Nothing was waived, so the task carries no exemption record at
            # all and the renderer has nothing to show.
            self.assertEqual(
                [],
                importlib.import_module(
                    "services.lifecycle_checks"
                ).exemption_report_lines(data.get("meta")),
            )

    def test_archive_prints_the_same_exemption_details_completion_did(self) -> None:
        """Archiving must not shrink the record back to a count."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_ac_gate_task(root, task_dir, checked=True)
            self._write_session_task(root)
            completed, completion_stdout, stderr = self._run_complete(
                root,
                allow_missing_evidence=True,
            )
            self.assertEqual(0, completed, stderr)
            self._init_git_repo(root)
            self._commit_all(root, "baseline")
            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()) as archive_stderr,
                ):
                    code = self.task.cmd_archive(
                        argparse.Namespace(name="05-19-demo", commit=False)
                    )
            finally:
                os.chdir(previous_cwd)

            output = archive_stderr.getvalue()
            self.assertEqual(0, code, output)
            self.assertIn("Exemptions carried into the archive:", output)
            for line in importlib.import_module(
                "services.lifecycle_checks"
            ).exemption_report_lines(data["meta"]):
                self.assertIn(line, output)
                # The two surfaces render one record, so they agree verbatim.
                self.assertIn(line, completion_stdout)
            self.assertIn("  - AC-001", output)
            self.assertIn("by main", output)

    def _write_bound_subagent_review_fixture(
        self,
        root: Path,
        *,
        status: str = "in_progress",
        allowed_files: tuple[str, ...] = ("AGENTS.md",),
    ) -> Path:
        self._init_git_repo(root)
        workflow_dir = root / ".cowork-flow"
        task_dir = workflow_dir / "tasks" / "05-19-demo"
        (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
        (workflow_dir / ".developer").parent.mkdir(parents=True, exist_ok=True)
        (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
        self._write_allowed_file_task(root, task_dir, status, allowed_files=allowed_files)
        self._write_session_task(
            root,
            scope="subagent",
            runtime_context_id="runtime-demo",
        )
        self._commit_all(root, "baseline")
        (root / "AGENTS.md").write_text("# Rules changed by subagent\n", encoding="utf-8")
        return task_dir

    def test_cmd_review_blocks_protected_workflow_changes_for_bound_subagent_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._write_bound_subagent_review_fixture(root)

            result, _stdout, stderr = self._run_review(root)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(1, result, stderr)
            self.assertEqual("in_progress", data["status"])
            self.assertIn(
                "Protected workflow/spec file changed outside main session: AGENTS.md",
                stderr,
            )

    def test_cmd_review_allows_protected_workflow_changes_for_default_main_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            workflow_dir = root / ".cowork-flow"
            task_dir = workflow_dir / "tasks" / "05-19-demo"
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (workflow_dir / ".developer").parent.mkdir(parents=True, exist_ok=True)
            (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
            self._write_allowed_file_task(root, task_dir, "in_progress", allowed_files=("AGENTS.md",))
            self._write_session_task(root)
            self._commit_all(root, "baseline")
            (root / "AGENTS.md").write_text("# Rules changed by coordinator\n", encoding="utf-8")

            review_result, _review_stdout, review_stderr = self._run_review(root)
            complete_result, _complete_stdout, complete_stderr = self._run_complete(root)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(0, review_result, review_stderr)
            self.assertEqual(0, complete_result, complete_stderr)
            self.assertEqual("completed", data["status"])

    def test_lifecycle_checks_consume_explicit_execution_policy_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            workflow_dir = root / ".cowork-flow"
            task_dir = workflow_dir / "tasks" / "05-19-demo"
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            self._write_allowed_file_task(
                root,
                task_dir,
                "in_progress",
                allowed_files=("AGENTS.md",),
            )
            self._commit_all(root, "baseline")
            (root / "AGENTS.md").write_text(
                "# Rules changed by subagent\n",
                encoding="utf-8",
            )
            checks = importlib.import_module("services.lifecycle_checks")
            policy_module = importlib.import_module("services.lifecycle_policy")

            blocked = checks.LifecycleCheckRunner(root).review(
                task_dir,
                execution_policy=policy_module.LifecycleExecutionPolicy(
                    execution_scope="subagent",
                    allow_spec_file_modifications=False,
                ),
            )
            allowed = checks.LifecycleCheckRunner(root).review(
                task_dir,
                execution_policy=policy_module.LifecycleExecutionPolicy(
                    execution_scope="main",
                    allow_spec_file_modifications=True,
                ),
            )

            self.assertTrue(blocked.blocked)
            self.assertIn(
                "Protected workflow/spec file changed outside main session: AGENTS.md",
                blocked.blockers,
            )
            self.assertFalse(allowed.blocked)
            self.assertEqual(
                [
                    (
                        "protected_workflow_file",
                        "AGENTS.md",
                        "Protected workflow/spec file changed outside main session: AGENTS.md",
                    )
                ],
                [(issue.code, issue.path, issue.message) for issue in blocked.issues],
            )
            self.assertEqual([], list(allowed.issues))

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
            self.assertEqual(1, result, stderr.getvalue())
            self.assertEqual("in_progress", data["status"])
            self.assertIn("Protected workflow/spec file changed outside main session", stderr.getvalue())

    def test_checks_scope_git_changes_to_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            outer = Path(temp_dir)
            self._init_git_repo(outer)
            outer_src = outer / "src"
            outer_src.mkdir()
            (outer_src / "outer.py").write_text("VALUE = 'safe'\n", encoding="utf-8")
            self._commit_all(outer, "baseline")
            (outer_src / "outer.py").write_text("VALUE = 'changed'\n", encoding="utf-8")

            nested = outer / "nested-project"
            task_dir = nested / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_allowed_file_task(nested, task_dir, "in_progress")
            checks = importlib.import_module("services.lifecycle_checks")

            result = checks.LifecycleCheckRunner(nested).review(task_dir)

        self.assertFalse(result.blocked)
        self.assertEqual((), result.blockers)

    def test_cmd_review_allows_behavior_change_without_legacy_tdd_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_allowed_file_task(root, task_dir, "in_progress")
            (task_dir / "tdd.jsonl").write_text(
                "this is ignored, not parsed as workflow evidence\n",
                encoding="utf-8",
            )
            self._write_session_task(root)

            result, _stdout, stderr = self._run_review(root)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(0, result, stderr)
            self.assertEqual("review", data["status"])
            self.assertNotIn("TDD", stderr)

    def test_cmd_complete_blocks_without_review_without_status_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_allowed_file_task(root, task_dir, "in_progress")
            self._write_session_task(root)

            result, _stdout, stderr = self._run_complete(root)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(1, result, stderr)
            self.assertEqual("in_progress", data["status"])
            self.assertIsNone(data["completedAt"])
            self.assertIn("Task state transition blocked", stderr)


    def _write_baseline_task_with_manifest(self, root: Path, task_dir: Path, *, meta: dict) -> None:
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "task.json").write_text(
            json.dumps({"status": "in_progress", "meta": meta}),
            encoding="utf-8",
        )
        (task_dir / "decision-anchor.md").write_text(
            "# Demo\n\n## 目标\n\nExplicit scope.\n\n## 验收标准\n\n- AC-001: only planned files change.\n",
            encoding="utf-8",
        )
        (task_dir / "implement.jsonl").write_text(
            '{"file": "src/only_planned.py", "reason": "planned"}\n',
            encoding="utf-8",
        )

    def _git_repo_with_baseline(self, root: Path) -> str:
        self._init_git_repo(root)
        (root / "seed.txt").write_text("seed\n", encoding="utf-8")
        self._commit_all(root, "baseline")
        baseline = self._run_git(root, "rev-parse", "HEAD")
        src = root / "src"
        src.mkdir(parents=True, exist_ok=True)
        (src / "only_planned.py").write_text("PLANNED = 1\n", encoding="utf-8")
        self._commit_all(root, "planned baseline file")
        return baseline

    def test_review_flags_committed_unlisted_files_after_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = self._git_repo_with_baseline(root)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            self._write_baseline_task_with_manifest(
                root, task_dir, meta={"baselineCommit": baseline}
            )
            # Bookkeeping the framework writes for itself is not a reviewed
            # change, so the scope gate must stay quiet about it even in a
            # checkout that does not ignore .cowork-flow/ — this fixture has no
            # .gitignore, so every one of these paths is visible to git.
            for relative in (
                ".cowork-flow/.runtime/subagents/rtx_demo.json",
                ".cowork-flow/logs/run.log",
            ):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}\n", encoding="utf-8")
            # Sneak an unlisted file in via a commit: it must still surface.
            (root / "src" / "sneaky.py").write_text("SNEAKY = 1\n", encoding="utf-8")
            self._commit_all(root, "sneaky unlisted file")

            checks = importlib.import_module("services.lifecycle_checks")
            issues = checks._review_completion_issues(
                root, task_dir, allow_spec_file_modifications=False
            )

        # Exactly the unlisted source file: the committed sneaky edit must be
        # reported, and the task's own artifacts plus the runtime bookkeeping
        # under .cowork-flow/ must not be.
        self.assertEqual(
            [("unlisted_changed_file", "src/sneaky.py")],
            [(issue.code, issue.path) for issue in issues],
        )

    def test_review_without_baseline_degrades_to_status_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._git_repo_with_baseline(root)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            # No meta.baselineCommit: pre-baseline tasks see working-tree
            # changes only, and the committed sneaky file stays invisible.
            self._write_baseline_task_with_manifest(root, task_dir, meta={})
            (root / "src" / "sneaky.py").write_text("SNEAKY = 1\n", encoding="utf-8")
            self._commit_all(root, "sneaky unlisted file")

            checks = importlib.import_module("services.lifecycle_checks")
            issues = checks._review_completion_issues(
                root, task_dir, allow_spec_file_modifications=False
            )

        self.assertEqual([], issues)


if __name__ == "__main__":
    unittest.main()
