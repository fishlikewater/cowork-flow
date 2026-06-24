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


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"


class FlowScriptPathsTest(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        self.paths = importlib.import_module("common.core.paths")
        self.task = importlib.import_module("commands.task")
        self.add_session = importlib.import_module("commands.add_session")
        self.developer = importlib.import_module("common.core.developer")
        self.git_context = importlib.import_module("common.git.git_context")

    def _cleanup_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in (
            "commands.task",
            "commands.add_session",
            "common.task.active_task",
            "common.core.config",
            "common.gates.coding_standards",
            "common.core.developer",
            "common.gates.gates",
            "common.git.git_context",
            "common.git.git_snapshot",
            "common.core.paths",
            "common.task.readiness",
            "common.task.state_machine",
            "common.task.task_utils",
            "common.gates.tdd_evidence",
            "common.gates.test_intent",
            "common.gates.validate_coding_standards",
            "common.gates.validate_implementation",
            "common.gates.validate_rules",
            "common",
        ):
            sys.modules.pop(module_name, None)

    def _write_session_task(
        self,
        root: Path,
        task_path: str = ".cowork-flow/tasks/05-19-demo",
        context_key: str = "main",
    ) -> None:
        sessions_dir = root / ".cowork-flow" / ".runtime" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        (sessions_dir / f"{context_key}.json").write_text(
            f'{{"active_task_path": "{task_path}"}}\n',
            encoding="utf-8",
        )
        rules_path = root / ".cowork-flow" / "spec" / "runtime" / "rules.json"
        if not rules_path.exists():
            self._write_rules_file(root, [])

    def _run_git(self, root: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return result.stdout.strip()

    def _init_git_repo(self, root: Path) -> None:
        self._run_git(root, "init")
        self._run_git(root, "config", "user.name", "Test User")
        self._run_git(root, "config", "user.email", "test@example.com")

    def _commit_all(self, root: Path, message: str) -> str:
        self._run_git(root, "add", "-A")
        self._run_git(root, "commit", "-m", message)
        return self._run_git(root, "rev-parse", "HEAD")

    def test_workflow_and_agents_directory_constants_are_current(self) -> None:
        self.assertEqual(".cowork-flow", self.paths.DIR_WORKFLOW)
        self.assertEqual(".agents", self.paths.DIR_AGENTS)
        self.assertEqual("changes", self.paths.DIR_CHANGES)

    def test_repo_root_detection_uses_cowork_flow_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            nested = root / "src" / "feature"
            nested.mkdir(parents=True)
            (root / ".cowork-flow").mkdir()

            self.assertEqual(root, self.paths.get_repo_root(nested))

    def test_task_relative_paths_accept_cowork_flow_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-18-demo"
            task_dir.mkdir(parents=True)

            resolved = self.task._resolve_task_dir(
                ".cowork-flow/tasks/05-18-demo",
                root,
            )

            self.assertEqual(task_dir, resolved)

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

            dir_name = f"{date_prefix}-demo-task"
            self.assertEqual(0, result)
            self.assertTrue((root / ".cowork-flow" / "tasks" / dir_name / "task.json").is_file())
            self.assertIn(dir_name, stdout.getvalue())

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

    def test_default_context_references_new_skill_directory(self) -> None:
        self.assertEqual(
            ".agents/skills/finish-work/SKILL.md",
            self.task._skill_path("finish-work"),
        )

    def test_skill_path_uses_claude_skills_for_claude_only_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()
            (root / ".claude").mkdir()

            self.assertEqual(
                ".claude/skills/check/SKILL.md",
                self.task._skill_path("check", root),
            )

    def test_skill_path_keeps_agent_skills_when_non_claude_hosts_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()
            (root / ".codex").mkdir()
            (root / ".claude").mkdir()

            self.assertEqual(
                ".agents/skills/check/SKILL.md",
                self.task._skill_path("check", root),
            )

    def test_init_context_writes_claude_skill_paths_for_claude_only_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "06-05-demo"
            task_dir.mkdir(parents=True)
            (root / ".claude").mkdir()

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    result = self.task.cmd_init_context(
                        argparse.Namespace(dir=str(task_dir), type="docs")
                    )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(0, result)
            check_entries = [
                json.loads(line)
                for line in (task_dir / "check.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(
                ".claude/skills/check/SKILL.md",
                check_entries[0]["file"],
            )

    def test_default_implement_context_includes_workflow_gates(self) -> None:
        files = [entry["file"] for entry in self.task.get_implement_base()]

        self.assertIn("AGENTS.md", files)
        self.assertIn(".cowork-flow/workflow.md", files)
        self.assertIn(".cowork-flow/spec/guides/index.md", files)
        self.assertIn(".cowork-flow/spec/guides/pre-implementation-checklist.md", files)

    def test_task_start_blockers_require_prd_and_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text("{}", encoding="utf-8")

            blockers = self.task._task_start_blockers(task_dir)

            self.assertIn("prd.md is missing or empty", blockers)
            self.assertIn("implement.jsonl is missing or empty", blockers)
            self.assertIn("check.jsonl is missing or empty", blockers)
            self.assertIn("debug.jsonl is missing or empty", blockers)

    def test_task_start_blockers_clear_when_prd_and_context_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text("{}", encoding="utf-8")
            (task_dir / "prd.md").write_text("# Demo\n", encoding="utf-8")
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")

            self.assertEqual([], self.task._task_start_blockers(task_dir))

    def _write_ready_task_files(self, root: Path, task_dir: Path, parent: str | None = None) -> None:
        task_dir.mkdir(parents=True, exist_ok=True)
        (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
        task_data = {
            "name": task_dir.name,
            "status": "planning",
            "parent": parent,
            "children": [],
        }
        (task_dir / "task.json").write_text(json.dumps(task_data), encoding="utf-8")
        (task_dir / "prd.md").write_text(
            "# Demo\n\n"
            "## Goal\n\nKeep the workflow safe.\n\n"
            "## Scope\n\nOnly readiness-gated workflow startup changes.\n\n"
            "## Non-goals\n\nNo unrelated runtime coordinator.\n\n"
            "## Key Assumptions\n\nExisting task metadata is authoritative.\n\n"
            "## Acceptance Criteria\n\nReadiness blockers are actionable.\n",
            encoding="utf-8",
        )
        for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
            (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")

    def _write_l2_change_fixture(
        self,
        root: Path,
        *,
        level: str = "L2",
        task_link: str | None = ".cowork-flow/tasks/05-19-parent",
        plan_link: str | None = ".cowork-flow/plans/2026-05-19-demo.md",
        design_text: str = "# Design\n\nUse an explicit gate.\n",
        spec_text: str = "# Spec\n\n## L2 Readiness Gate\n\n- Missing artifacts block start.\n",
    ) -> Path:
        change_dir = root / ".cowork-flow" / "changes" / "05-19-demo-change"
        change_dir.mkdir(parents=True)
        task_value = task_link if task_link is not None else "null"
        plan_value = plan_link if plan_link is not None else "null"
        (change_dir / "change.yaml").write_text(
            "slug: 05-19-demo-change\n"
            "status: active\n"
            f"level: {level}\n"
            "created_at: 2026-05-19T00:00:00+08:00\n"
            "documentation_only: false\n"
            f"plan: {plan_value}\n"
            f"task: {task_value}\n",
            encoding="utf-8",
        )
        (change_dir / "proposal.md").write_text(
            "# Demo change\n\n"
            "## Problem\n\nThe workflow can start L2 work too early.\n\n"
            "## Benefits\n\nUsers get safer cross-layer changes.\n\n"
            "## Non-goals\n\nNo heavy role system.\n",
            encoding="utf-8",
        )
        (change_dir / "spec.md").write_text(spec_text, encoding="utf-8")
        (change_dir / "design.md").write_text(design_text, encoding="utf-8")

        if plan_link is not None:
            plan_path = root / plan_link
            plan_path.parent.mkdir(parents=True, exist_ok=True)
            plan_path.write_text(
                "# Demo plan\n\n"
                "| Task |\n| --- |\n"
                "| `.cowork-flow/tasks/05-19-child` |\n\n"
                "## Verification\n\n"
                "- `python -m unittest discover -s tests`\n"
                "- `git diff --check`\n",
                encoding="utf-8",
            )
        return change_dir

    def _write_rules_file(self, root: Path, rules: list[dict]) -> None:
        rules_path = root / ".cowork-flow" / "spec" / "runtime" / "rules.json"
        rules_path.parent.mkdir(parents=True, exist_ok=True)
        rules_path.write_text(
            json.dumps({"schemaVersion": 1, "rules": rules}, ensure_ascii=False),
            encoding="utf-8",
        )

    def _workflow_rule(self, rule_id: str, scope: str) -> dict:
        return {
            "id": rule_id,
            "type": "phase_gate",
            "severity": "block",
            "scope": scope,
            "condition": f"{rule_id} condition",
            "message": f"{rule_id} blocked",
            "fix_hint": f"Fix {rule_id}",
            "source_file": ".cowork-flow/workflow.md",
            "source_anchor": f"{rule_id}-anchor",
            "enforcement": "validate_rules",
        }

    def _write_behavior_prd(self, task_dir: Path) -> None:
        (task_dir / "prd.md").write_text(
            "# Behavior task\n\n"
            "## 目标\n\n"
            "实现会改变 CLI/runtime 可观察行为。\n\n"
            "## 验收标准\n\n"
            "- AC-001: 缺少 red-green TDD evidence 时 review 失败。\n",
            encoding="utf-8",
        )

    def _write_valid_tdd_evidence(self, task_dir: Path) -> None:
        root = task_dir.parents[2]
        test_file = root / "tests" / "test_flow_script_paths.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(
            "import unittest\n\n"
            "class FlowScriptPathsTest(unittest.TestCase):\n"
            "    def test_cmd_review_blocks_behavior_change_without_tdd_evidence(self):\n"
            "        result = {'status': 'blocked', 'rule_id': 'TDD-RED-001'}\n"
            "        self.assertEqual('blocked', result['status'])\n"
            "        self.assertEqual('TDD-RED-001', result['rule_id'])\n",
            encoding="utf-8",
        )
        evidence = {
            "acceptanceId": "AC-001",
            "testFile": "tests/test_flow_script_paths.py",
            "testName": "test_cmd_review_blocks_behavior_change_without_tdd_evidence",
            "redCommand": "python -m unittest tests.test_flow_script_paths.FlowScriptPathsTest.test_cmd_review_blocks_behavior_change_without_tdd_evidence -v",
            "redExitCode": 1,
            "redOutputExcerpt": "TDD evidence file is missing",
            "failureReason": "review gate did not enforce missing TDD evidence",
            "whyThisTestMatters": "It proves behavior-change work cannot enter review without red-green evidence.",
            "greenCommand": "python -m unittest tests.test_flow_script_paths.FlowScriptPathsTest.test_cmd_review_blocks_behavior_change_without_tdd_evidence -v",
            "greenExitCode": 0,
            "broaderVerification": "python -m unittest tests.test_flow_script_paths -v",
        }
        (task_dir / "tdd.jsonl").write_text(
            json.dumps(evidence, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _write_non_behavior_review_task(
        self,
        root: Path,
        task_dir: Path,
        *,
        status: str = "in_progress",
    ) -> None:
        (root / ".cowork-flow" / ".developer").parent.mkdir(parents=True, exist_ok=True)
        (root / ".cowork-flow" / ".developer").write_text("name=codex\n", encoding="utf-8")
        (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "task.json").write_text(
            json.dumps({"status": status, "completedAt": None}),
            encoding="utf-8",
        )
        (task_dir / "prd.md").write_text(
            "# Docs task\n\n"
            "## 验收标准\n\n"
            "- AC-001: 文档措辞更新。\n",
            encoding="utf-8",
        )
        for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
            (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")
        self._write_session_task(root)

    def _write_encoding_violation_changes(self, root: Path) -> None:
        src_dir = root / "src"
        scripts_dir = root / "scripts"
        src_dir.mkdir()
        scripts_dir.mkdir()

        modified_py = src_dir / "modified.py"
        staged_js = src_dir / "staged.js"
        modified_py.write_text("VALUE = 'safe'\n", encoding="utf-8")
        staged_js.write_text("export const value = 'safe';\n", encoding="utf-8")
        self._commit_all(root, "baseline")

        modified_py.write_text("DATA = open('data.txt').read()\n", encoding="utf-8")
        staged_js.write_text(
            "import { readFile } from 'node:fs/promises';\n"
            "await readFile('data.txt');\n",
            encoding="utf-8",
        )
        self._run_git(root, "add", "src/staged.js")
        (scripts_dir / "untracked.ps1").write_text(
            "$value = Get-Content .\\data.txt\n",
            encoding="utf-8",
        )

    def _write_l2_task_tree(self, root: Path) -> Path:
        parent_dir = root / ".cowork-flow" / "tasks" / "05-19-parent"
        child_dir = root / ".cowork-flow" / "tasks" / "05-19-child"
        self._write_ready_task_files(root, parent_dir)
        self._write_ready_task_files(root, child_dir, parent="05-19-parent")
        parent_data = json.loads((parent_dir / "task.json").read_text(encoding="utf-8"))
        parent_data["children"] = ["05-19-child"]
        (parent_dir / "task.json").write_text(json.dumps(parent_data), encoding="utf-8")
        return child_dir

    def test_l2_readiness_passes_for_ready_linked_child_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            child_dir = self._write_l2_task_tree(root)
            self._write_l2_change_fixture(root)

            blockers = self.task._optional_readiness_blockers(root, child_dir)

            self.assertEqual([], blockers)

    def test_validate_rules_accepts_current_task_link_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            child_dir = self._write_l2_task_tree(root)
            self._write_l2_change_fixture(
                root,
                task_link=".cowork-flow/tasks/05-19-child",
            )
            self._write_rules_file(
                root,
                [
                    self._workflow_rule("R-WF-001", "task_start"),
                    self._workflow_rule("R-WF-002", "task_start"),
                    self._workflow_rule("R-WF-003", "task_start"),
                    self._workflow_rule("R-WF-004", "task_start"),
                    self._workflow_rule("R-WF-005", "task_start"),
                ],
            )
            validator = importlib.import_module("common.gates.validate_rules")

            violations = validator.validate_rules(root, "task_start", child_dir)

            self.assertEqual([], violations)

    def test_validate_rules_uses_explicit_utf8_for_rule_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_ready_task_files(root, task_dir)
            task_data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            task_data["status"] = "in_progress"
            (task_dir / "task.json").write_text(
                json.dumps(task_data, ensure_ascii=False),
                encoding="utf-8",
            )
            rule = self._workflow_rule("R-WF-007", "task_complete")
            rule["message"] = "🚦 check gate blocked"
            self._write_rules_file(root, [rule])
            validator = importlib.import_module("common.gates.validate_rules")
            real_open = open

            def strict_text_open(file, mode="r", *args, **kwargs):
                if "b" not in mode and "encoding" not in kwargs:
                    raise AssertionError(f"missing explicit encoding for {file}")
                return real_open(file, mode, *args, **kwargs)

            with patch("builtins.open", side_effect=strict_text_open):
                violations = validator.validate_rules(root, "task_complete", task_dir)
                validator.log_violations(violations, "task_complete", task_dir, root)

            self.assertEqual(["R-WF-007"], [v["rule_id"] for v in violations])

    def test_validate_rules_blocks_missing_runtime_rules_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_ready_task_files(root, task_dir)
            validator = importlib.import_module("common.gates.validate_rules")

            violations = validator.validate_rules(root, "task_review", task_dir)

            self.assertEqual(["RULES-CONFIG-001"], [v["rule_id"] for v in violations])
            self.assertEqual("block", violations[0]["severity"])
            self.assertIn(
                ".cowork-flow/spec/runtime/rules.json",
                violations[0]["file"].replace("\\", "/"),
            )

    def test_validate_rules_blocks_incomplete_runtime_rule_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_ready_task_files(root, task_dir)
            incomplete_rule = self._workflow_rule("R-WF-007", "task_complete")
            incomplete_rule.pop("message")
            self._write_rules_file(root, [incomplete_rule])
            validator = importlib.import_module("common.gates.validate_rules")

            violations = validator.validate_rules(root, "task_complete", task_dir)

            self.assertEqual(["RULES-CONFIG-004"], [v["rule_id"] for v in violations])
            self.assertEqual("block", violations[0]["severity"])
            self.assertIn("message", violations[0]["message"])

    def test_rule_scope_contract_includes_task_review(self) -> None:
        for schema_path in (
            ROOT / ".cowork-flow" / "spec" / "schemas" / "rules.schema.json",
            ROOT / "template" / ".cowork-flow" / "spec" / "schemas" / "rules.schema.json",
        ):
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            rule_item = schema["properties"]["rules"]["items"]
            required = rule_item["required"]
            scope_enum = rule_item["properties"]["scope"]["enum"]
            source_requirements = rule_item["anyOf"]
            self.assertIn({"required": ["source_anchor"]}, source_requirements)
            self.assertIn({"required": ["source_excerpt"]}, source_requirements)
            self.assertIn("enforcement", required)
            self.assertIn("task_review", scope_enum)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_ready_task_files(root, task_dir)
            self._write_rules_file(root, [])
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "common" / "gates" / "validate_rules.py"),
                    "task_review",
                    "--repo-root",
                    str(root),
                    "--task-dir",
                    str(task_dir),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(0, result.returncode, result.stderr)

    def test_gate_runner_wraps_existing_validator_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            self._write_ready_task_files(root, task_dir)
            task_data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            task_data["status"] = "in_progress"
            (task_dir / "task.json").write_text(
                json.dumps(task_data, ensure_ascii=False),
                encoding="utf-8",
            )
            self._write_rules_file(root, [self._workflow_rule("R-WF-007", "task_complete")])
            gates = importlib.import_module("common.gates.gates")

            result = gates.GateRunner(root).run("task_complete", task_dir)

            self.assertTrue(result.blocked)
            self.assertEqual(1, result.exit_code)
            self.assertEqual(["R-WF-007"], [v["rule_id"] for v in result.violations])

    def test_task_state_machine_requires_review_before_complete(self) -> None:
        state_machine = importlib.import_module("common.task.state_machine")

        self.assertEqual([], state_machine.transition_blockers("review", "completed"))
        self.assertEqual([], state_machine.transition_blockers("checking", "completed"))
        self.assertIn(
            "task review",
            "\n".join(state_machine.transition_blockers("in_progress", "completed")),
        )

    def test_l2_readiness_reports_missing_design_spec_plan_and_task_link(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            child_dir = self._write_l2_task_tree(root)
            change_dir = self._write_l2_change_fixture(
                root,
                task_link=None,
                plan_link=".cowork-flow/plans/2026-05-19-demo.md",
                design_text="",
                spec_text="",
            )

            blockers = self.task._optional_readiness_blockers(root, child_dir)

            joined = "\n".join(blockers)
            self.assertIn("change.yaml task link is missing", joined)
            self.assertIn("design.md is missing or empty", joined)
            self.assertIn("spec.md is missing or empty", joined)
            self.assertIn(change_dir.name, joined)

    def test_l2_readiness_reports_missing_plan_for_linked_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            child_dir = self._write_l2_task_tree(root)
            self._write_l2_change_fixture(root, plan_link=".cowork-flow/plans/missing.md")
            (root / ".cowork-flow" / "plans" / "missing.md").unlink()

            blockers = self.task._optional_readiness_blockers(root, child_dir)

            joined = "\n".join(blockers)
            self.assertIn("plan points to missing path", joined)

    def test_l2_readiness_bypasses_non_l2_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            child_dir = self._write_l2_task_tree(root)
            self._write_l2_change_fixture(
                root,
                level="L1",
                design_text="",
                spec_text="",
            )

            blockers = self.task._optional_readiness_blockers(root, child_dir)

            self.assertEqual([], blockers)

    def test_cmd_start_blocks_l2_readiness_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            child_dir = self._write_l2_task_tree(root)
            self._write_l2_change_fixture(root, design_text="")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}),
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_start(
                        argparse.Namespace(dir=".cowork-flow/tasks/05-19-child")
                    )
            finally:
                os.chdir(previous_cwd)

            data = json.loads((child_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(1, result)
            self.assertEqual("planning", data["status"])
            self.assertIn("Task readiness failed", stderr.getvalue())
            self.assertFalse((root / ".cowork-flow" / ".runtime" / "sessions" / "main.json").exists())

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
            (task_dir / "task.json").write_text("{}", encoding="utf-8")
            (task_dir / "prd.md").write_text("# Demo\n", encoding="utf-8")
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

    def test_cmd_start_requires_session_context_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (task_dir / "task.json").write_text("{}", encoding="utf-8")
            (task_dir / "prd.md").write_text("# Demo\n", encoding="utf-8")
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")
            self._write_rules_file(root, [])

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
            (task_dir / "task.json").write_text('{"status": "planning"}\n', encoding="utf-8")
            (task_dir / "prd.md").write_text("# Demo\n", encoding="utf-8")
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")
            self._write_rules_file(root, [])

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

    def test_cmd_review_blocks_implementation_violations_without_status_mutation(self) -> None:
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

    def test_implementation_gate_uses_runtime_rule_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (task_dir / "prd.md").write_text("# Demo\n", encoding="utf-8")
            self._write_rules_file(
                root,
                [
                    {
                        **self._workflow_rule("R-AG-002", "all"),
                        "type": "forbidden_action",
                        "enforcement": "validate_implementation",
                        "message": "custom spec mutation block",
                        "fix_hint": "custom fix from runtime rules",
                    }
                ],
            )
            self._commit_all(root, "baseline")
            (root / "AGENTS.md").write_text("# Changed rules\n", encoding="utf-8")
            implementation = importlib.import_module("common.gates.validate_implementation")

            violations = implementation.validate_implementation(root, task_dir)

            self.assertEqual(["R-AG-002"], [v["rule_id"] for v in violations])
            self.assertEqual("custom spec mutation block", violations[0]["message"])
            self.assertEqual("custom fix from runtime rules", violations[0]["fix_hint"])

    def test_cmd_review_allows_spec_changes_for_coordinator_execution(self) -> None:
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
            self.assertEqual(0, result, stderr.getvalue())
            self.assertEqual("review", data["status"])

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
            (task_dir / "prd.md").write_text("# Nested task\n", encoding="utf-8")

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
            self.assertIn("Coding standards", stderr_text)
            for path in ("src/modified.py", "src/staged.js", "scripts/untracked.ps1"):
                self.assertIn(path, stderr_text)

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

            self.assertIn("Backend Coding Standards", summary)
            self.assertTrue(calls)
            self.assertEqual("utf-8", calls[0].get("encoding"))
            self.assertEqual("replace", calls[0].get("errors"))

    def test_cmd_review_blocks_shallow_tdd_test_intent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            shallow_assert = "self.assert" + "True(True)"
            (tests_dir / "test_noise.py").write_text(
                "import unittest\n\n"
                "class NoiseTest(unittest.TestCase):\n"
                "    def test_noise(self):\n"
                f"        {shallow_assert}\n",
                encoding="utf-8",
            )
            (task_dir / "task.json").write_text(
                '{"status": "in_progress", "completedAt": null}\n',
                encoding="utf-8",
            )
            self._write_behavior_prd(task_dir)
            evidence = {
                "acceptanceId": "AC-001",
                "testFile": "tests/test_noise.py",
                "testName": "test_noise",
                "redCommand": "python -m unittest tests.test_noise.NoiseTest.test_noise -v",
                "redExitCode": 1,
                "redOutputExcerpt": "review gate did not block shallow test",
                "failureReason": "test intent gate did not reject a trivial truth assertion",
                "whyThisTestMatters": "It proves shallow tests cannot satisfy TDD review.",
                "greenCommand": "python -m unittest tests.test_noise.NoiseTest.test_noise -v",
                "greenExitCode": 0,
                "broaderVerification": "python -m unittest tests.test_flow_script_paths -v",
            }
            (task_dir / "tdd.jsonl").write_text(
                json.dumps(evidence, ensure_ascii=False) + "\n",
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
                        result = self.task.cmd_review(argparse.Namespace(dir=None))
            finally:
                os.chdir(previous_cwd)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(1, result)
            self.assertEqual("in_progress", data["status"])
            self.assertIn("assert " + "True", stderr.getvalue())

    def test_test_intent_warns_without_blocking_ambiguous_assertions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_ambiguous.py").write_text(
                "import unittest\n\n"
                "class AmbiguousTest(unittest.TestCase):\n"
                "    def test_result_exists(self):\n"
                "        result = {'status': 'blocked'}\n"
                "        self.assertIsNotNone(result)\n",
                encoding="utf-8",
            )
            (task_dir / "task.json").write_text(
                '{"status": "in_progress", "completedAt": null}\n',
                encoding="utf-8",
            )
            self._write_behavior_prd(task_dir)
            evidence = {
                "acceptanceId": "AC-001",
                "testFile": "tests/test_ambiguous.py",
                "testName": "test_result_exists",
                "redCommand": "python -m unittest tests.test_ambiguous.AmbiguousTest.test_result_exists -v",
                "redExitCode": 1,
                "redOutputExcerpt": "test intent did not warn on weak assertion",
                "failureReason": "test intent gate did not flag ambiguous assertion depth",
                "whyThisTestMatters": "It proves suspicious-but-not-obviously-empty tests are reviewed without being blocked.",
                "greenCommand": "python -m unittest tests.test_ambiguous.AmbiguousTest.test_result_exists -v",
                "greenExitCode": 0,
                "broaderVerification": "python -m unittest tests.test_flow_script_paths -v",
            }
            (task_dir / "tdd.jsonl").write_text(
                json.dumps(evidence, ensure_ascii=False) + "\n",
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
                        result = self.task.cmd_review(argparse.Namespace(dir=None))
            finally:
                os.chdir(previous_cwd)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(0, result, stderr.getvalue())
            self.assertEqual("review", data["status"])
            self.assertIn("Warning: Test intent review warnings", stderr.getvalue())
            self.assertIn("assertIsNotNone", stderr.getvalue())

    def test_test_intent_ignores_shallow_fixture_outside_target_test(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_behavior.py").write_text(
                "import unittest\n\n"
                "SHALLOW_FIXTURE = 'self.assertTrue(True)'\n\n"
                "class BehaviorTest(unittest.TestCase):\n"
                "    def test_real_behavior(self):\n"
                "        result = {'status': 'blocked'}\n"
                "        self.assertEqual('blocked', result['status'])\n",
                encoding="utf-8",
            )
            self._write_behavior_prd(task_dir)
            evidence = {
                "acceptanceId": "AC-001",
                "testFile": "tests/test_behavior.py",
                "testName": "test_real_behavior",
                "redCommand": "python -m unittest tests.test_behavior.BehaviorTest.test_real_behavior -v",
                "redExitCode": 1,
                "redOutputExcerpt": "target behavior missing",
                "failureReason": "target behavior was not implemented",
                "whyThisTestMatters": "It proves fixture text outside the target test does not cause false positives.",
                "greenCommand": "python -m unittest tests.test_behavior.BehaviorTest.test_real_behavior -v",
                "greenExitCode": 0,
                "broaderVerification": "python -m unittest tests.test_flow_script_paths -v",
            }
            (task_dir / "tdd.jsonl").write_text(
                json.dumps(evidence, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            test_intent = importlib.import_module("common.gates.test_intent")

            self.assertEqual([], test_intent.validate_test_intent(root, task_dir))

    def test_test_intent_handles_utf8_bom_when_targeting_test_function(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_behavior.py").write_text(
                "\ufeffimport unittest\n\n"
                "SHALLOW_FIXTURE = 'self.assertTrue(True)'\n\n"
                "class BehaviorTest(unittest.TestCase):\n"
                "    def test_real_behavior(self):\n"
                "        result = {'status': 'blocked'}\n"
                "        self.assertEqual('blocked', result['status'])\n",
                encoding="utf-8",
            )
            evidence = {
                "acceptanceId": "AC-001",
                "testFile": "tests/test_behavior.py",
                "testName": "BehaviorTest.test_real_behavior",
                "redCommand": "python -m unittest tests.test_behavior.BehaviorTest.test_real_behavior -v",
                "redExitCode": 1,
                "redOutputExcerpt": "target behavior missing",
                "failureReason": "target behavior was not implemented",
                "whyThisTestMatters": "It proves UTF-8 BOM does not make test intent scan the whole file.",
                "greenCommand": "python -m unittest tests.test_behavior.BehaviorTest.test_real_behavior -v",
                "greenExitCode": 0,
                "broaderVerification": "python -m unittest tests.test_flow_script_paths -v",
            }
            (task_dir / "tdd.jsonl").write_text(
                json.dumps(evidence, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            test_intent = importlib.import_module("common.gates.test_intent")

            self.assertEqual([], test_intent.validate_test_intent(root, task_dir))

    def test_test_intent_ignores_shallow_marker_inside_fixture_string(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_behavior.py").write_text(
                "import unittest\n\n"
                "class BehaviorTest(unittest.TestCase):\n"
                "    def test_real_behavior(self):\n"
                "        fixture = 'self.assertTrue(True)'\n"
                "        result = {'status': 'blocked'}\n"
                "        self.assertEqual('blocked', result['status'])\n",
                encoding="utf-8",
            )
            evidence = {
                "acceptanceId": "AC-001",
                "testFile": "tests/test_behavior.py",
                "testName": "BehaviorTest.test_real_behavior",
                "redCommand": "python -m unittest tests.test_behavior.BehaviorTest.test_real_behavior -v",
                "redExitCode": 1,
                "redOutputExcerpt": "target behavior missing",
                "failureReason": "target behavior was not implemented",
                "whyThisTestMatters": "It proves fixture strings do not masquerade as shallow test assertions.",
                "greenCommand": "python -m unittest tests.test_behavior.BehaviorTest.test_real_behavior -v",
                "greenExitCode": 0,
                "broaderVerification": "python -m unittest tests.test_flow_script_paths -v",
            }
            (task_dir / "tdd.jsonl").write_text(
                json.dumps(evidence, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            test_intent = importlib.import_module("common.gates.test_intent")

            self.assertEqual([], test_intent.validate_test_intent(root, task_dir))

    def test_test_intent_blocks_unresolved_test_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            test_file = root / "tests" / "test_real.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text(
                "import unittest\n\n"
                "class RealTest(unittest.TestCase):\n"
                "    def test_real_behavior(self):\n"
                "        result = {'status': 'blocked'}\n"
                "        self.assertEqual('blocked', result['status'])\n",
                encoding="utf-8",
            )
            evidence = {
                "acceptanceId": "AC-001",
                "testFile": "tests/test_real.py",
                "testName": "MissingTest.test_real_behavior",
                "redCommand": "python -m unittest tests.test_real.MissingTest.test_real_behavior -v",
                "redExitCode": 1,
                "redOutputExcerpt": "missing target behavior",
                "failureReason": "target behavior was not implemented",
                "whyThisTestMatters": "It proves evidence points at the exact behavior test.",
                "greenCommand": "python -m unittest tests.test_real.RealTest.test_real_behavior -v",
                "greenExitCode": 0,
                "broaderVerification": "python -m unittest tests.test_real -v",
            }
            (task_dir / "tdd.jsonl").write_text(
                json.dumps(evidence, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            test_intent = importlib.import_module("common.gates.test_intent")

            violations = test_intent.validate_test_intent(root, task_dir)

            self.assertEqual(["TEST-INTENT-005"], [v["rule_id"] for v in violations])

    def test_tdd_evidence_accepts_documentation_exemption(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-docs"
            task_dir.mkdir(parents=True)
            (task_dir / "prd.md").write_text(
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
            self.assertIn("prd.md is missing or empty", output)
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
            (task_dir / "prd.md").write_text(
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
            (task_dir / "prd.md").write_text(
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
            (task_dir / "prd.md").write_text("# Demo\n", encoding="utf-8")
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
            (task_dir / "prd.md").write_text("# Demo\n", encoding="utf-8")
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

    def test_task_archive_resumes_when_source_and_destination_match(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow_dir = root / ".cowork-flow"
            tasks_dir = workflow_dir / "tasks"
            task_dir = tasks_dir / "05-19-demo"
            task_dir.mkdir(parents=True)
            (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                '{"name": "demo", "status": "in_progress", "assignee": "codex"}',
                encoding="utf-8",
            )
            month = datetime.now().strftime("%Y-%m")
            archive_dest = tasks_dir / "archive" / month / "05-19-demo"
            archive_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(task_dir, archive_dest)

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()) as stdout,
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_archive(argparse.Namespace(name="05-19-demo"))
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(0, result, stderr.getvalue())
            self.assertFalse(task_dir.exists())
            self.assertTrue((archive_dest / "task.json").is_file())
            self.assertIn(".cowork-flow/tasks/archive/", stdout.getvalue())

    def test_task_archive_archives_linked_active_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow_dir = root / ".cowork-flow"
            tasks_dir = workflow_dir / "tasks"
            task_dir = tasks_dir / "05-19-demo"
            task_dir.mkdir(parents=True)
            (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                '{"name": "demo", "status": "completed", "assignee": "codex"}',
                encoding="utf-8",
            )
            change_dir = self._write_l2_change_fixture(
                root,
                level="L1",
                task_link=".cowork-flow/tasks/05-19-demo",
            )
            month = datetime.now().strftime("%Y-%m")
            task_archive_dest = tasks_dir / "archive" / month / "05-19-demo"
            change_archive_dest = workflow_dir / "changes" / "archive" / month / change_dir.name

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()) as stdout,
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_archive(
                        argparse.Namespace(name="05-19-demo", commit=False)
                    )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(0, result, stderr.getvalue())
            self.assertFalse(task_dir.exists())
            self.assertTrue((task_archive_dest / "task.json").is_file())
            self.assertFalse(change_dir.exists())
            self.assertTrue((change_archive_dest / "change.yaml").is_file())
            metadata = (change_archive_dest / "change.yaml").read_text(encoding="utf-8")
            self.assertIn("status: archived", metadata)
            self.assertIn("task: archive/", metadata)
            self.assertIn("05-19-demo", metadata)
            self.assertIn("Archived linked change: 05-19-demo-change", stderr.getvalue())
            self.assertIn(".cowork-flow/tasks/archive/", stdout.getvalue())

    def test_task_archive_does_not_commit_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            workflow_dir = root / ".cowork-flow"
            tasks_dir = workflow_dir / "tasks"
            task_dir = tasks_dir / "05-19-demo"
            task_dir.mkdir(parents=True)
            (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                '{"name": "demo", "status": "completed", "assignee": "codex"}',
                encoding="utf-8",
            )
            baseline = self._commit_all(root, "initial")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_archive(
                        argparse.Namespace(name="05-19-demo", commit=False)
                    )
            finally:
                os.chdir(previous_cwd)

            head = self._run_git(root, "rev-parse", "HEAD")
            self.assertEqual(0, result, stderr.getvalue())
            self.assertEqual(baseline, head)
            self.assertNotIn("Auto-committed", stderr.getvalue())

    def test_task_archive_rejects_removed_no_commit_flag(self) -> None:
        with patch.object(sys, "argv", ["task.py", "archive", "05-19-demo", "--no-commit"]):
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                with self.assertRaises(SystemExit) as raised:
                    self.task.main()

        self.assertEqual(2, raised.exception.code)
        self.assertIn("unrecognized arguments: --no-commit", stderr.getvalue())

    def test_add_session_rejects_removed_no_commit_flag(self) -> None:
        with patch.object(
            sys,
            "argv",
            ["add_session.py", "--title", "Demo", "--no-commit"],
        ):
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                with self.assertRaises(SystemExit) as raised:
                    self.add_session.main()

        self.assertEqual(2, raised.exception.code)
        self.assertIn("unrecognized arguments: --no-commit", stderr.getvalue())

    def test_task_archive_commit_flag_auto_commits(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            workflow_dir = root / ".cowork-flow"
            tasks_dir = workflow_dir / "tasks"
            task_dir = tasks_dir / "05-19-demo"
            task_dir.mkdir(parents=True)
            (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                '{"name": "demo", "status": "completed", "assignee": "codex"}',
                encoding="utf-8",
            )
            baseline = self._commit_all(root, "initial")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_archive(
                        argparse.Namespace(name="05-19-demo", commit=True)
                    )
            finally:
                os.chdir(previous_cwd)

            head = self._run_git(root, "rev-parse", "HEAD")
            message = self._run_git(root, "log", "-1", "--pretty=%s")
            self.assertEqual(0, result, stderr.getvalue())
            self.assertNotEqual(baseline, head)
            self.assertEqual("chore(task): archive 05-19-demo", message)
            self.assertIn("Auto-committed", stderr.getvalue())

    def test_add_session_does_not_commit_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            workflow_dir = root / ".cowork-flow"
            workflow_dir.mkdir()
            (workflow_dir / "tasks").mkdir()
            self.developer.init_developer("codex", root)
            baseline = self._commit_all(root, "initial")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with contextlib.redirect_stderr(io.StringIO()) as stderr:
                    result = self.add_session.add_session(
                        "Demo session",
                        commit="-",
                        summary="Record closeout.",
                        extra_content="- Updated metadata.",
                    )
            finally:
                os.chdir(previous_cwd)

            head = self._run_git(root, "rev-parse", "HEAD")
            status = self._run_git(root, "status", "--short")
            self.assertEqual(0, result, stderr.getvalue())
            self.assertEqual(baseline, head)
            self.assertIn(".cowork-flow/workspace/codex/", status)
            self.assertNotIn("Metadata auto-committed", stderr.getvalue())

    def test_add_session_auto_commit_flag_commits_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._init_git_repo(root)
            workflow_dir = root / ".cowork-flow"
            workflow_dir.mkdir()
            (workflow_dir / "tasks").mkdir()
            self.developer.init_developer("codex", root)
            baseline = self._commit_all(root, "initial")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with contextlib.redirect_stderr(io.StringIO()) as stderr:
                    result = self.add_session.add_session(
                        "Demo session",
                        commit="-",
                        summary="Record closeout.",
                        extra_content="- Updated metadata.",
                        auto_commit=True,
                    )
            finally:
                os.chdir(previous_cwd)

            head = self._run_git(root, "rev-parse", "HEAD")
            message = self._run_git(root, "log", "-1", "--pretty=%s")
            self.assertEqual(0, result, stderr.getvalue())
            self.assertNotEqual(baseline, head)
            self.assertEqual("chore: record journal", message)
            self.assertIn("Metadata auto-committed", stderr.getvalue())

    def test_context_text_includes_minimal_resume_checklist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow_dir = root / ".cowork-flow"
            task_dir = workflow_dir / "tasks" / "05-19-demo"
            plan_file = workflow_dir / "plans" / "2026-05-19-demo.md"
            task_dir.mkdir(parents=True)
            plan_file.parent.mkdir(parents=True)
            (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
            self._write_session_task(root)
            (task_dir / "task.json").write_text(
                '{"name": "demo", "status": "in_progress", "assignee": "codex"}',
                encoding="utf-8",
            )
            (task_dir / "prd.md").write_text("# Demo\n", encoding="utf-8")
            (task_dir / "implement.jsonl").write_text(
                '{"file": ".cowork-flow/plans/2026-05-19-demo.md"}\n',
                encoding="utf-8",
            )
            for name in ("check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")
            plan_file.write_text(
                "## Current Execution Status\nResume from task 2.\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                output = self.git_context.get_context_text(root)

            self.assertIn("## RESUME CHECKLIST", output)
            self.assertIn(
                "Recovery entrypoint (rerun only if context is stale): ./.cowork-flow/run resume",
                output,
            )
            self.assertIn("Read active task PRD: .cowork-flow/tasks/05-19-demo/prd.md", output)
            self.assertIn("List task context before reading details: ./.cowork-flow/run task list-context .cowork-flow/tasks/05-19-demo", output)
            self.assertIn("Read current plan status: .cowork-flow/plans/2026-05-19-demo.md", output)
            self.assertIn("Do not bulk-read .cowork-flow/spec/ or workspace journals", output)

    def test_context_json_includes_resume_checklist_without_file_contents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow_dir = root / ".cowork-flow"
            task_dir = workflow_dir / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
            self._write_session_task(root)
            (task_dir / "task.json").write_text(
                '{"name": "demo", "status": "in_progress", "assignee": "codex"}',
                encoding="utf-8",
            )
            (task_dir / "prd.md").write_text("# Secret PRD body should not appear\n", encoding="utf-8")
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")

            with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                context = self.git_context.get_context_json(root)
                record_context = self.git_context.get_context_record_json(root)

            self.assertIn("activeTask", record_context)
            self.assertNotIn("currentTask", record_context)
            self.assertEqual(
                ".cowork-flow/tasks/05-19-demo",
                record_context["activeTask"]["path"],
            )
            self.assertIn("resumeChecklist", context)
            self.assertEqual(
                "./.cowork-flow/run resume",
                context["resumeChecklist"]["commands"][0],
            )
            self.assertIn(
                ".cowork-flow/tasks/05-19-demo/prd.md",
                context["resumeChecklist"]["readFiles"],
            )

    def test_resume_script_outputs_resume_checklist_without_file_contents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow_dir = root / ".cowork-flow"
            task_dir = workflow_dir / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
            self._write_session_task(root)
            (task_dir / "task.json").write_text(
                '{"name": "demo", "status": "in_progress", "assignee": "codex"}',
                encoding="utf-8",
            )
            (task_dir / "prd.md").write_text("# Secret PRD body should not appear\n", encoding="utf-8")
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")

            env = os.environ.copy()
            env["COWORK_FLOW_CONTEXT_ID"] = "main"
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "commands" / "resume.py")],
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )

            self.assertEqual(0, result.returncode)
            self.assertIn("COWORK-FLOW RESUME", result.stdout)
            self.assertIn("## RESUME CHECKLIST", result.stdout)
            self.assertNotIn("Secret PRD body", result.stdout)


if __name__ == "__main__":
    unittest.main()
