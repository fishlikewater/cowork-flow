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


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"


class FlowScriptTestCase(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        self.paths = importlib.import_module("infra.paths")
        self.task = importlib.import_module("adapters.cli.task")
        self.developer = importlib.import_module("infra.developer_profile")
        self.git_context = importlib.import_module("adapters.git.git_context")

    def _cleanup_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in (
            "adapters.cli.task",
            "adapters.cli.task_archive_commands",
            "adapters.cli.task_navigation",
            "adapters.cli.task_support",
            "adapters.cli.task_tree_commands",
            "services.task_archive",
            "services.task_context",
            "services.task_lifecycle",
            "services.task_tree",
            "application",
            "runtime.session_state",
            "infra.config",
            "infra.developer_profile",
            "infra.quality_sources",
            "adapters.git.git_context",
            "infra.git_snapshot",
            "infra.paths",
            "services.readiness",
            "kernel.task_state",
            "services.task_repository",
            "services.task_utils",
            "adapters.review.test_intent",
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
