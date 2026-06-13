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
        self.paths = importlib.import_module("common.paths")
        self.task = importlib.import_module("task")
        self.add_session = importlib.import_module("add_session")
        self.developer = importlib.import_module("common.developer")
        self.git_context = importlib.import_module("common.git_context")
        self.flow_store = importlib.import_module("flow.store")

    def _cleanup_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in (
            "task",
            "add_session",
            "common.active_task",
            "common.config",
            "common.developer",
            "common.git_context",
            "common.paths",
            "common.readiness",
            "common.task_utils",
            "flow.store",
            "flow",
            "common",
        ):
            sys.modules.pop(module_name, None)

    def _create_flow_task(
        self,
        root: Path,
        slug: str,
        status: str = "planning",
        *,
        pattern: str = "generic",
        meta: dict | None = None,
        parent_id: str | None = None,
    ) -> str:
        db_path = self.paths.get_db_path(root)
        with self.flow_store.FlowStore(str(db_path)) as store:
            store.create_task(
                id=slug,
                title=f"Test {slug}",
                status=status,
                pattern=pattern,
                creator="test",
                assignee="test",
                parent_id=parent_id,
                meta=meta,
            )
        return slug

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

    def test_task_id_resolution_accepts_absolute_task_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-18-demo"
            task_dir.mkdir(parents=True)

            task_id = self.task._resolve_task_id(str(task_dir), root)

            self.assertEqual("demo", task_id)

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
            self.assertTrue(task_dir.exists())
            self.assertFalse(doubled.exists())
            self.assertIn(slug, stdout.getvalue())

    def test_cmd_create_with_parent_creates_single_link(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            parent_dir = root / ".cowork-flow" / "tasks" / "05-19-parent"
            parent_dir.mkdir(parents=True)
            self._create_flow_task(root, "parent", "planning")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()) as stdout,
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_create(
                        argparse.Namespace(
                            title="Child task",
                            slug="child",
                            assignee="codex",
                            priority="P2",
                            description=None,
                            parent="parent",
                        )
                    )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(0, result, stderr.getvalue())
            self.assertIn(".cowork-flow/tasks/", stdout.getvalue())
            db_path = self.paths.get_db_path(root)
            with self.flow_store.FlowStore(str(db_path)) as store:
                children = store.list_children("parent")
            self.assertEqual(["child"], [task.id for task in children])

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

    def test_init_context_writes_claude_skill_paths_for_claude_only_project(
        self,
    ) -> None:
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
                for line in (task_dir / "check.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
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
                (task_dir / name).write_text(
                    '{"file": "AGENTS.md"}\n', encoding="utf-8"
                )

            self.assertEqual([], self.task._task_start_blockers(task_dir))

    def _write_ready_task_files(
        self, root: Path, task_dir: Path, parent: str | None = None
    ) -> None:
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

    def _write_l2_task_tree(self, root: Path) -> Path:
        parent_dir = root / ".cowork-flow" / "tasks" / "05-19-parent"
        child_dir = root / ".cowork-flow" / "tasks" / "05-19-child"
        self._write_ready_task_files(root, parent_dir)
        self._write_ready_task_files(root, child_dir, parent="05-19-parent")
        parent_data = json.loads((parent_dir / "task.json").read_text(encoding="utf-8"))
        parent_data["children"] = ["05-19-child"]
        (parent_dir / "task.json").write_text(json.dumps(parent_data), encoding="utf-8")
        db_path = self.paths.get_db_path(root)
        with self.flow_store.FlowStore(str(db_path)) as store:
            store.create_task(
                id="parent",
                title="Test parent",
                status="planning",
                creator="test",
                assignee="test",
            )
            store.create_task(
                id="child",
                title="Test child",
                status="planning",
                creator="test",
                assignee="test",
                parent_id="parent",
            )
        return child_dir

    def test_l2_readiness_passes_for_ready_linked_child_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            child_dir = self._write_l2_task_tree(root)
            self._write_l2_change_fixture(root)

            blockers = self.task._optional_readiness_blockers(root, child_dir)

            self.assertEqual([], blockers)

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
            self._write_l2_change_fixture(
                root, plan_link=".cowork-flow/plans/missing.md"
            )
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
            self.assertFalse(
                (root / ".cowork-flow" / ".runtime" / "sessions" / "main.json").exists()
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
            (task_dir / "task.json").write_text("{}", encoding="utf-8")
            (task_dir / "prd.md").write_text("# Demo\n", encoding="utf-8")
            (task_dir / "implement.jsonl").write_text("not-json\n", encoding="utf-8")
            for name in ("check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text(
                    '{"file": "AGENTS.md"}\n', encoding="utf-8"
                )

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
                (task_dir / name).write_text(
                    '{"file": "AGENTS.md"}\n', encoding="utf-8"
                )

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    patch.dict(os.environ, {}, clear=True),
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

    def test_cmd_start_updates_task_status_to_in_progress(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (task_dir / "prd.md").write_text("# Demo\n", encoding="utf-8")
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text(
                    '{"file": "AGENTS.md"}\n', encoding="utf-8"
                )

            # Create task in FlowStore
            from common.paths import get_db_path
            from flow.store import FlowStore

            db_path = str(root / ".cowork-flow" / "cowork-flow.db")
            with FlowStore(db_path) as store:
                store.create_task(id="demo", title="Demo", creator="d", assignee="d")

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

            self.assertEqual(0, result)
            with FlowStore(db_path) as store:
                task = store.get_task("demo")
                self.assertIsNotNone(task)
                self.assertEqual("in_progress", task.status)

    def test_cmd_start_rejects_pattern_invalid_transition(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-done"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (task_dir / "prd.md").write_text("# Done\n", encoding="utf-8")
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text(
                    '{"file": "AGENTS.md"}\n', encoding="utf-8"
                )
            self._create_flow_task(root, "done", "completed")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}),
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_start(
                        argparse.Namespace(dir=".cowork-flow/tasks/05-19-done")
                    )
            finally:
                os.chdir(previous_cwd)

            with self.flow_store.FlowStore(str(self.paths.get_db_path(root))) as store:
                task = store.get_task("done")
            self.assertEqual(1, result)
            self.assertIsNotNone(task)
            self.assertEqual("completed", task.status)
            self.assertIn("Pattern transition blocked", stderr.getvalue())

    def test_cmd_review_and_complete_update_active_task_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            self._create_flow_task(root, "demo", "in_progress")
            self._write_session_task(root)

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with (
                        contextlib.redirect_stdout(io.StringIO()),
                        contextlib.redirect_stderr(io.StringIO()),
                    ):
                        review_result = self.task.cmd_review(
                            argparse.Namespace(dir=None)
                        )
                        complete_result = self.task.cmd_complete(
                            argparse.Namespace(dir=None)
                        )
            finally:
                os.chdir(previous_cwd)

            db_path = self.paths.get_db_path(root)
            with self.flow_store.FlowStore(str(db_path)) as store:
                task = store.get_task("demo")
            self.assertEqual(0, review_result)
            self.assertEqual(0, complete_result)
            self.assertIsNotNone(task)
            self.assertEqual("completed", task.status)

    def test_cmd_review_and_complete_fail_when_flow_task_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-orphan"
            task_dir.mkdir(parents=True)

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    review_result = self.task.cmd_review(
                        argparse.Namespace(dir=".cowork-flow/tasks/05-19-orphan")
                    )
                    complete_result = self.task.cmd_complete(
                        argparse.Namespace(dir=".cowork-flow/tasks/05-19-orphan")
                    )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(1, review_result)
            self.assertEqual(1, complete_result)
            self.assertIn("Flow task not found", stderr.getvalue())

    def test_cmd_review_blocks_fan_out_parent_with_pending_child(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            parent_dir = root / ".cowork-flow" / "tasks" / "05-19-parent"
            parent_dir.mkdir(parents=True)
            self._create_flow_task(root, "parent", "in_progress", pattern="fan_out")
            self._create_flow_task(
                root,
                "child",
                "in_progress",
                parent_id="parent",
            )

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_review(
                        argparse.Namespace(dir=".cowork-flow/tasks/05-19-parent")
                    )
            finally:
                os.chdir(previous_cwd)

            with self.flow_store.FlowStore(str(self.paths.get_db_path(root))) as store:
                task = store.get_task("parent")
            self.assertEqual(1, result)
            self.assertIsNotNone(task)
            self.assertEqual("in_progress", task.status)
            self.assertIn("Pattern transition blocked", stderr.getvalue())

    def test_cmd_complete_advances_pipeline_stage_without_finishing_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-pipe"
            task_dir.mkdir(parents=True)
            self._create_flow_task(
                root,
                "pipe",
                "review",
                pattern="pipeline",
                meta={
                    "stages": [{"name": "implement"}, {"name": "check"}],
                    "current_stage": 0,
                },
            )

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    result = self.task.cmd_complete(
                        argparse.Namespace(dir=".cowork-flow/tasks/05-19-pipe")
                    )
            finally:
                os.chdir(previous_cwd)

            with self.flow_store.FlowStore(str(self.paths.get_db_path(root))) as store:
                task = store.get_task("pipe")
            self.assertEqual(0, result)
            self.assertIsNotNone(task)
            self.assertEqual("in_progress", task.status)
            self.assertEqual(1, task.meta["current_stage"])

    def test_cmd_unblock_requires_decision_for_human_loop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-human"
            task_dir.mkdir(parents=True)
            self._create_flow_task(
                root,
                "human",
                "in_progress",
                pattern="human_loop",
                meta={"decision_points": [{"question": "Choose"}]},
            )
            with self.flow_store.FlowStore(str(self.paths.get_db_path(root))) as store:
                store.block_task("human", "Choose")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_unblock(
                        argparse.Namespace(
                            dir=".cowork-flow/tasks/05-19-human",
                            decision=None,
                            force=False,
                        )
                    )
            finally:
                os.chdir(previous_cwd)

            with self.flow_store.FlowStore(str(self.paths.get_db_path(root))) as store:
                task = store.get_task("human")
            self.assertEqual(1, result)
            self.assertIsNotNone(task)
            self.assertEqual("blocked", task.status)
            self.assertIn("--decision", stderr.getvalue())

    def test_cmd_unblock_requires_force_for_non_human_loop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            self._create_flow_task(root, "demo", "in_progress")
            with self.flow_store.FlowStore(str(self.paths.get_db_path(root))) as store:
                store.block_task("demo", "Need manual unblock")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_unblock(
                        argparse.Namespace(
                            dir=".cowork-flow/tasks/05-19-demo",
                            decision="approved",
                            force=False,
                        )
                    )
            finally:
                os.chdir(previous_cwd)

            with self.flow_store.FlowStore(str(self.paths.get_db_path(root))) as store:
                task = store.get_task("demo")
            self.assertEqual(1, result)
            self.assertIsNotNone(task)
            self.assertEqual("blocked", task.status)
            self.assertIn("--force", stderr.getvalue())

    def test_cmd_block_and_unblock_fail_when_flow_task_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    block_result = self.task.cmd_block(
                        argparse.Namespace(dir="missing", reason="need decision")
                    )
                    unblock_result = self.task.cmd_unblock(
                        argparse.Namespace(
                            dir="missing",
                            decision="approved",
                            force=True,
                        )
                    )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(1, block_result)
            self.assertEqual(1, unblock_result)
            self.assertIn("missing", stderr.getvalue())

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
            self.assertIn(
                "Active task: .cowork-flow/tasks/05-19-demo", stdout.getvalue()
            )

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
            self.assertIn(
                "Next action: create or start a task before repository changes", output
            )
            self.assertIn("./.cowork-flow/run task create", output)
            self.assertFalse((root / ".cowork-flow" / "tasks").exists())

    def test_cmd_next_reports_planning_blockers_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            self._create_flow_task(root, "demo", "planning")
            (task_dir / "task.json").write_text(
                '{"status": "planning"}\n', encoding="utf-8"
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
            self._create_flow_task(root, "demo", "in_progress")
            (task_dir / "task.json").write_text(
                '{"status": "in_progress"}\n', encoding="utf-8"
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
            self.assertIn("Status: in_progress", output)
            self.assertIn("Next action: execute implementation plan", output)
            self.assertIn("cowork-implement", output)
            self.assertIn("./.cowork-flow/run subagent init", output)
            self.assertIn("cowork_runtime_context_id", output)

    def test_cmd_next_reports_pattern_action_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            parent_dir = root / ".cowork-flow" / "tasks" / "05-19-parent"
            parent_dir.mkdir(parents=True)
            self._create_flow_task(root, "parent", "in_progress", pattern="fan_out")
            self._create_flow_task(
                root,
                "child",
                "in_progress",
                parent_id="parent",
            )

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        result = self.task.cmd_next(
                            argparse.Namespace(dir=".cowork-flow/tasks/05-19-parent")
                        )
            finally:
                os.chdir(previous_cwd)

            output = stdout.getvalue()
            self.assertEqual(0, result)
            self.assertIn("Pattern action: wait_children", output)
            self.assertIn("child", output)
            with self.flow_store.FlowStore(str(self.paths.get_db_path(root))) as store:
                parent = store.get_task("parent")
            self.assertIsNotNone(parent)
            self.assertEqual("in_progress", parent.status)

    def test_cmd_next_reports_review_check_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            self._create_flow_task(root, "demo", "review")
            (task_dir / "task.json").write_text(
                '{"status": "review"}\n', encoding="utf-8"
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
            self.assertIn("Status: review", output)
            self.assertIn("Next action: verify implementation", output)
            self.assertIn("cowork-check", output)
            self.assertIn(
                "./.cowork-flow/run task complete .cowork-flow/tasks/05-19-demo", output
            )

    def test_cmd_next_completed_mentions_linked_change_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            self._create_flow_task(root, "demo", "completed")
            (task_dir / "task.json").write_text(
                '{"status": "completed"}\n', encoding="utf-8"
            )
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
            self._create_flow_task(root, "demo", "planning")
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                '{"status": "planning"}\n', encoding="utf-8"
            )
            (task_dir / "prd.md").write_text("# Demo\n", encoding="utf-8")
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text(
                    '{"file": "AGENTS.md"}\n', encoding="utf-8"
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
            self.assertIn("cowork-implement", output)
            self.assertIn("Blockers: none", output)
            self.assertNotIn("implement.jsonl: [OK]", output)

    def test_cmd_next_routes_inactive_ready_planning_task_to_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            self._create_flow_task(root, "demo", "planning")
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                '{"status": "planning"}\n', encoding="utf-8"
            )
            (task_dir / "prd.md").write_text("# Demo\n", encoding="utf-8")
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text(
                    '{"file": "AGENTS.md"}\n', encoding="utf-8"
                )

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
            self.assertIn(
                "./.cowork-flow/run task start .cowork-flow/tasks/05-19-demo", output
            )

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
            self._create_flow_task(root, "demo", "in_progress")
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
                    result = self.task.cmd_archive(
                        argparse.Namespace(name="05-19-demo", no_commit=True)
                    )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(0, result, stderr.getvalue())
            self.assertFalse(task_dir.exists())
            self.assertTrue((archive_dest / "task.json").is_file())
            self.assertIn(".cowork-flow/tasks/archive/", stdout.getvalue())

    def test_task_archive_fails_before_move_when_flow_task_missing(self) -> None:
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
            month = datetime.now().strftime("%Y-%m")
            archive_dest = tasks_dir / "archive" / month / "05-19-demo"

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_archive(
                        argparse.Namespace(
                            name="05-19-demo", commit=False, no_commit=True
                        )
                    )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(1, result)
            self.assertTrue(task_dir.exists())
            self.assertFalse(archive_dest.exists())
            self.assertIn("Flow task not found", stderr.getvalue())

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
            self._create_flow_task(root, "demo", "completed")
            change_dir = self._write_l2_change_fixture(
                root,
                level="L1",
                task_link=".cowork-flow/tasks/05-19-demo",
            )
            month = datetime.now().strftime("%Y-%m")
            task_archive_dest = tasks_dir / "archive" / month / "05-19-demo"
            change_archive_dest = (
                workflow_dir / "changes" / "archive" / month / change_dir.name
            )

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()) as stdout,
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_archive(
                        argparse.Namespace(
                            name="05-19-demo", commit=False, no_commit=True
                        )
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
            self.assertIn(
                "Archived linked change: 05-19-demo-change", stderr.getvalue()
            )
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
            self._create_flow_task(root, "demo", "completed")
            baseline = self._commit_all(root, "initial")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_archive(
                        argparse.Namespace(
                            name="05-19-demo", commit=False, no_commit=False
                        )
                    )
            finally:
                os.chdir(previous_cwd)

            head = self._run_git(root, "rev-parse", "HEAD")
            self.assertEqual(0, result, stderr.getvalue())
            self.assertEqual(baseline, head)
            self.assertNotIn("Auto-committed", stderr.getvalue())

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
            self._create_flow_task(root, "demo", "completed")
            baseline = self._commit_all(root, "initial")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    result = self.task.cmd_archive(
                        argparse.Namespace(
                            name="05-19-demo", commit=True, no_commit=False
                        )
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
                (task_dir / name).write_text(
                    '{"file": "AGENTS.md"}\n', encoding="utf-8"
                )
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
            self.assertIn(
                "Read active task PRD: .cowork-flow/tasks/05-19-demo/prd.md", output
            )
            self.assertIn(
                "List task context before reading details: ./.cowork-flow/run task list-context .cowork-flow/tasks/05-19-demo",
                output,
            )
            self.assertIn(
                "Read current plan status: .cowork-flow/plans/2026-05-19-demo.md",
                output,
            )
            self.assertIn(
                "Do not bulk-read .cowork-flow/spec/ or workspace journals", output
            )

    def test_context_json_includes_resume_checklist_without_file_contents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow_dir = root / ".cowork-flow"
            task_dir = workflow_dir / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (workflow_dir / ".developer").write_text("name=codex\n", encoding="utf-8")
            self._write_session_task(root)
            self._create_flow_task(root, "demo", "in_progress")
            (task_dir / "prd.md").write_text(
                "# Secret PRD body should not appear\n", encoding="utf-8"
            )
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text(
                    '{"file": "AGENTS.md"}\n', encoding="utf-8"
                )

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
            (task_dir / "prd.md").write_text(
                "# Secret PRD body should not appear\n", encoding="utf-8"
            )
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text(
                    '{"file": "AGENTS.md"}\n', encoding="utf-8"
                )

            env = os.environ.copy()
            env["COWORK_FLOW_CONTEXT_ID"] = "main"
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "resume.py")],
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
