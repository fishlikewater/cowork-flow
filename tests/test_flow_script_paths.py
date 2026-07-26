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


class FlowScriptPathsTest(FlowScriptTestCase):
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

    def test_default_context_references_new_skill_directory(self) -> None:
        # When only CLAUDE.md exists (no .codex/.opencode), skill path uses .claude/skills/.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()
            (root / "CLAUDE.md").write_text("# project instructions", encoding="utf-8")
            self.assertEqual(
                ".claude/skills/cowork-flow/SKILL.md",
                self.task._skill_path("cowork-flow", root),
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
            except Exception:
                pass
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(0, result)
            check_entries = [
                json.loads(line)
                for line in (task_dir / "check.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(
                ".claude/skills/task-review/SKILL.md",
                check_entries[0]["file"],
            )
            check_files = [entry["file"] for entry in check_entries]
            self.assertIn(
                ".claude/skills/cowork-flow/SKILL.md",
                check_files,
            )
            self.assertNotIn(
                ".claude/skills/finish-work/SKILL.md",
                check_files,
            )

    def test_default_implement_context_includes_workflow_gates(self) -> None:
        files = [entry["file"] for entry in self.task.get_implement_base()]

        self.assertIn("AGENTS.md", files)
        self.assertIn(".cowork-flow/spec/guides/index.md", files)
        self.assertIn(".cowork-flow/spec/guides/pre-implementation-checklist.md", files)
