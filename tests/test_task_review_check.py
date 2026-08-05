from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
REVIEW_CHECK = ROOT / "template" / "skills" / "task-review" / "scripts" / "review_check.py"


class TaskReviewCheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPTS))
        spec = importlib.util.spec_from_file_location("task_review_check_script", REVIEW_CHECK)
        if spec is None or spec.loader is None:
            raise AssertionError("cannot load review_check.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.module = module

    @classmethod
    def tearDownClass(cls) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in (
            "adapters.review.test_intent",
            "infra.git_snapshot",
            "infra.quality_sources",
            "services.lifecycle_checks",
            "services.task_context",
        ):
            sys.modules.pop(module_name, None)

    def _run_git(self, root: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return result.stdout.strip()

    def _init_git_repo(self, root: Path) -> None:
        self._run_git(root, "init")
        self._run_git(root, "config", "user.name", "Test User")
        self._run_git(root, "config", "user.email", "test@example.com")

    def _commit_all(self, root: Path, message: str) -> None:
        self._run_git(root, "add", "-A")
        self._run_git(root, "commit", "-m", message)

    def _write_task(self, root: Path) -> Path:
        task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
        task_dir.mkdir(parents=True)
        (task_dir / "task.json").write_text(
            json.dumps({"status": "review", "dev_type": "backend"}),
            encoding="utf-8",
        )
        (task_dir / "decision-anchor.md").write_text(
            "# Demo\n\n## 目标\n\nReview helper.\n\n## 验收标准\n\n- AC-001: advisory only.\n",
            encoding="utf-8",
        )
        (task_dir / "implement.jsonl").write_text(
            json.dumps({"file": "src/app.py", "reason": "Implementation"})
            + "\n"
            + json.dumps({"file": "tests/test_app.py", "reason": "Regression"})
            + "\n",
            encoding="utf-8",
        )
        (task_dir / "check.jsonl").write_text(
            json.dumps(
                {
                    "file": ".cowork-flow/spec/backend/quality-guidelines.md",
                    "reason": "Review quality guidance",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return task_dir

    def _write_specs(self, root: Path) -> None:
        backend = root / ".cowork-flow" / "spec" / "backend"
        references = root / ".cowork-flow" / "spec" / "references"
        backend.mkdir(parents=True)
        references.mkdir(parents=True)
        (backend / "index.md").write_text(
            "# Backend\n\n| 文档 | 用途 |\n|---|---|\n| [质量规范](./quality-guidelines.md) | quality |\n",
            encoding="utf-8",
        )
        (backend / "quality-guidelines.md").write_text("# Quality\n", encoding="utf-8")
        (references / "definition-of-done.md").write_text("# DoD\n", encoding="utf-8")
        (references / "testing-checklist.md").write_text("# Testing\n", encoding="utf-8")

    def _task_file_snapshot(self, task_dir: Path) -> dict[str, bytes]:
        return {
            str(path.relative_to(task_dir)): path.read_bytes()
            for path in sorted(task_dir.rglob("*"))
            if path.is_file()
        }

    def _assert_no_verdict_keys(self, value: Any) -> None:
        forbidden = {"pass", "fail", "blocked", "blockers", "status"}
        if isinstance(value, dict):
            for key, child in value.items():
                self.assertNotIn(key, forbidden)
                self._assert_no_verdict_keys(child)
        elif isinstance(value, list):
            for child in value:
                self._assert_no_verdict_keys(child)

    def test_review_check_reports_advisory_facts_without_writing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            self._init_git_repo(root)
            task_dir = self._write_task(root)
            self._write_specs(root)
            (root / "src").mkdir()
            (root / "tests").mkdir()
            (root / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
            (root / "tests" / "test_app.py").write_text(
                "def test_value_changes():\n    assert VALUE == 1\n",
                encoding="utf-8",
            )
            self._commit_all(root, "baseline")
            (root / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
            (root / "tests" / "test_app.py").write_text(
                "def test_value_changes():\n    assert True\n",
                encoding="utf-8",
            )
            before = self._task_file_snapshot(task_dir)

            with unittest.mock.patch.dict(
                os.environ,
                {"COWORK_FLOW_CONTEXT_ID": "subagent_case"},
            ):
                report = self.module.build_report(root, task_dir)

            self.assertEqual("advisory", report["mode"])
            self._assert_no_verdict_keys(report)
            self.assertEqual(before, self._task_file_snapshot(task_dir))
            self.assertFalse((task_dir / "review.jsonl").exists())
            self.assertFalse((task_dir / "quality-review.jsonl").exists())
            self.assertEqual(
                {"src/app.py", "tests/test_app.py"},
                set(report["changedFiles"]),
            )
            self.assertEqual([], report["scopeFacts"]["unlistedChangedFiles"])
            self.assertEqual([], report["scopeFacts"]["protectedWorkflowFiles"])
            self.assertIn(
                ".cowork-flow/spec/backend/quality-guidelines.md",
                {entry["file"] for entry in report["specSources"]},
            )
            self.assertEqual(
                ["tests/test_app.py"],
                report["testIntentSignals"]["changedTestFiles"],
            )
            self.assertEqual(
                ["block"],
                [
                    signal["signal"]
                    for signal in report["testIntentSignals"]["shallowAssertionSignals"]
                ],
            )
            self.assertEqual(
                [
                    {
                        "code": "shallow_assertion_signal",
                        "severity": "warning",
                        "path": "tests/test_app.py",
                        "source": "test-intent",
                        "signal": "block",
                    }
                ],
                [
                    {
                        "code": issue["code"],
                        "severity": issue["severity"],
                        "path": issue["path"],
                        "source": issue["source"],
                        "signal": issue["signal"],
                    }
                    for issue in report["normalizedIssues"]
                ],
            )
            self.assertIn("test intent helper flagged", report["normalizedIssues"][0]["message"])

    def test_review_check_classifies_structured_lifecycle_scope_issues(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            self._init_git_repo(root)
            task_dir = self._write_task(root)
            self._write_specs(root)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            self._commit_all(root, "baseline")
            (root / "src" / "extra.py").write_text("VALUE = 2\n", encoding="utf-8")
            (root / "AGENTS.md").write_text("# Rules changed\n", encoding="utf-8")

            with unittest.mock.patch.dict(
                os.environ,
                {"COWORK_FLOW_CONTEXT_ID": "subagent_case"},
            ):
                report = self.module.build_report(root, task_dir)
            scope_facts = self.module._scope_facts(
                root,
                task_dir,
                allow_spec_file_modifications=False,
            )
            lifecycle_result = self.module.LifecycleCheckRunner(root).review(
                task_dir,
                allow_spec_file_modifications=False,
            )

            self.assertEqual(
                ["src/extra.py"],
                scope_facts["unlistedChangedFiles"],
            )
            self.assertEqual(
                ["AGENTS.md"],
                scope_facts["protectedWorkflowFiles"],
            )
            self.assertEqual([], scope_facts["contextIssues"])
            lifecycle_issues = [
                issue for issue in report["normalizedIssues"] if issue["source"] == "lifecycle"
            ]
            self.assertEqual(
                [
                    ("protected_workflow_file", "error", "AGENTS.md"),
                    ("unlisted_changed_file", "error", "AGENTS.md"),
                    ("unlisted_changed_file", "error", "src/extra.py"),
                ],
                sorted(
                    (
                        issue["code"],
                        issue["severity"],
                        issue["path"],
                    )
                    for issue in lifecycle_issues
                ),
            )
            self.assertEqual(
                [],
                [issue for issue in lifecycle_issues if not issue["message"]],
            )
            self.assertTrue(lifecycle_result.blocked)
            self.assertEqual(
                {
                    ("protected_workflow_file", "AGENTS.md"),
                    ("unlisted_changed_file", "AGENTS.md"),
                    ("unlisted_changed_file", "src/extra.py"),
                },
                {(issue.code, issue.path) for issue in lifecycle_result.issues},
            )
            self.assertEqual(
                {(issue["code"], issue["path"]) for issue in lifecycle_issues},
                {(issue.code, issue.path) for issue in lifecycle_result.issues},
            )

    def test_review_check_normalizes_context_issues(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            self._init_git_repo(root)
            task_dir = self._write_task(root)
            self._write_specs(root)
            (task_dir / "implement.jsonl").write_text("{invalid json}\n", encoding="utf-8")
            self._commit_all(root, "baseline")

            report = self.module.build_report(root, task_dir)

            self.assertEqual(
                [
                    "Invalid implement.jsonl JSON at line 1",
                    "implement.jsonl contains no valid file-scope entries",
                ],
                report["scopeFacts"]["contextIssues"],
            )
            self.assertEqual(
                [
                    {
                        "code": "invalid_implement_jsonl_json",
                        "severity": "error",
                        "path": "",
                        "source": "lifecycle",
                    },
                    {
                        "code": "empty_implement_jsonl_file_scope",
                        "severity": "error",
                        "path": "",
                        "source": "lifecycle",
                    },
                ],
                [
                    {
                        "code": issue["code"],
                        "severity": issue["severity"],
                        "path": issue["path"],
                        "source": issue["source"],
                    }
                    for issue in report["normalizedIssues"]
                ],
            )


if __name__ == "__main__":
    unittest.main()
