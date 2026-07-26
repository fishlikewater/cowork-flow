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


class FlowScriptTestCase(unittest.TestCase):
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
            "commands.task_archive_commands",
            "commands.task_navigation",
            "commands.task_support",
            "commands.task_tree_commands",
            "application.task_archive",
            "application.task_context",
            "application.task_lifecycle",
            "application.task_tree",
            "application",
            "common.task.active_task",
            "common.core.config",
            "common.gates.coding_standards",
            "common.core.developer",
            "common.core.quality_sources",
            "common.gates.gates",
            "common.git.git_context",
            "common.git.git_snapshot",
            "common.core.paths",
            "common.task.readiness",
            "common.task.state_machine",
            "common.task.task_repository",
            "common.task.task_utils",
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
        scope: str = "main",
        runtime_context_id: str | None = None,
    ) -> None:
        sessions_dir = root / ".cowork-flow" / ".runtime" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        session_data = {
            "active_task_path": task_path,
            "scope": scope,
        }
        if runtime_context_id is not None:
            session_data["runtime_context_id"] = runtime_context_id
        (sessions_dir / f"{context_key}.json").write_text(
            json.dumps(session_data) + "\n",
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
        (task_dir / "decision-anchor.md").write_text(
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
        (task_dir / "decision-review.jsonl").write_text(
            json.dumps(
                {
                    "acceptanceId": "AC-001",
                    "claim": "The readiness gate blocks unready L2 tasks.",
                    "contract": "Only accepted fresh-context evidence permits start.",
                    "reviewerContext": "fresh",
                    "findings": [],
                    "resolution": "accepted",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

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
                "- `./.cowork-flow/run python -m unittest discover -s tests`\n"
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
        validator, parameters = {
            "R-WF-001": ("runtime.l2_required_file", {"filename": "proposal.md"}),
            "R-WF-002": ("runtime.l2_required_file", {"filename": "spec.md"}),
            "R-WF-003": ("runtime.l2_required_file", {"filename": "design.md"}),
            "R-WF-004": ("runtime.l2_plan_link", {}),
            "R-WF-005": ("runtime.l2_task_link", {}),
            "R-WF-007": (
                "runtime.task_status",
                {"allowed_statuses": ["review"]},
            ),
            "R-WF-008": (
                "runtime.decision_anchor",
                {"required_sections": ["目标", "验收标准"]},
            ),
            "R-AG-002": ("implementation.spec_files", {}),
            "R-AG-005": ("implementation.allowed_files", {}),
            "R-AG-006": ("implementation.premature_abstraction", {}),
        }.get(rule_id, ("runtime.unknown", {}))
        return {
            "id": rule_id,
            "type": "phase_gate",
            "severity": "block",
            "scope": scope,
            "condition": f"{rule_id} condition",
            "message": f"{rule_id} blocked",
            "fix_hint": f"Fix {rule_id}",
            "source_file": "AGENTS.md",
            "source_anchor": f"{rule_id}-anchor",
            "enforcement": "validate_rules",
            "validator": validator,
            "parameters": parameters,
        }

    def _write_behavior_prd(self, task_dir: Path) -> None:
        (task_dir / "decision-anchor.md").write_text(
            "# Behavior task\n\n"
            "## 目标\n\n"
            "实现会改变用户可观察行为。\n\n"
            "## 验收标准\n\n"
            "- AC-001: 行为变更有对应测试和验证记录。\n",
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
        (task_dir / "decision-anchor.md").write_text(
            "# Docs task\n\n"
            "## 验收标准\n\n"
            "- AC-001: 文档措辞更新。\n",
            encoding="utf-8",
        )
        for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
            (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")
        # 确保 .cowork-flow/spec/runtime/rules.json 存在
        rules_path = root / ".cowork-flow" / "spec" / "runtime" / "rules.json"
        if not rules_path.exists():
            rules_path.parent.mkdir(parents=True, exist_ok=True)
            template_rules = ROOT / "template" / ".cowork-flow" / "spec" / "runtime" / "rules.json"
            if template_rules.exists():
                import shutil
                shutil.copy(template_rules, rules_path)
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
