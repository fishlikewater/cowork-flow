"""Migration script tests."""
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".cowork-flow" / "scripts"))
from flow.migrate import run_migration
from flow.store import FlowStore


def _make_fake_tasks(tmpdir: Path):
    tasks_dir = tmpdir / ".cowork-flow" / "tasks"
    tasks_dir.mkdir(parents=True)
    t1 = tasks_dir / "01-01-old-task"
    t1.mkdir()
    (t1 / "task.json").write_text(json.dumps({
        "id": "old-task", "name": "old-task",
        "title": "Old task", "description": "desc",
        "status": "completed", "priority": "P2",
        "creator": "dev1", "assignee": "dev1",
        "completedAt": "2026-01-01", "commit": "abc123",
        "parent": None, "children": ["01-02-child"],
        "dev_type": "backend", "scope": "module",
        "relatedFiles": [], "notes": "some notes",
    }), encoding="utf-8")
    t2 = tasks_dir / "01-02-child"
    t2.mkdir()
    (t2 / "task.json").write_text(json.dumps({
        "id": "child-task", "title": "Child task",
        "status": "in_progress",
        "creator": "dev1", "assignee": "dev1",
        "parent": None, "children": [],
    }), encoding="utf-8")
    return tasks_dir


def test_migrate_basic(tmp_path):
    tasks_dir = _make_fake_tasks(tmp_path)
    db_path = str(tmp_path / "test.db")
    success, warnings, detail = run_migration(tasks_dir, db_path)
    assert success
    assert detail["tasks_migrated"] == 2
    assert len(warnings) == 0


def test_migrate_orphan_child(tmp_path):
    tasks_dir = tmp_path / ".cowork-flow" / "tasks"
    tasks_dir.mkdir(parents=True)
    t1 = tasks_dir / "01-01-parent"
    t1.mkdir()
    (t1 / "task.json").write_text(json.dumps({
        "id": "parent", "title": "parent", "status": "planning",
        "creator": "dev1", "assignee": "dev1",
        "children": ["01-02-gone"],
    }), encoding="utf-8")
    db_path = str(tmp_path / "test.db")
    success, warnings, detail = run_migration(tasks_dir, db_path)
    assert success
    assert len(warnings) >= 1


def test_migrate_empty_dir(tmp_path):
    tasks_dir = tmp_path / ".cowork-flow" / "tasks"
    tasks_dir.mkdir(parents=True)
    db_path = str(tmp_path / "test.db")
    success, warnings, detail = run_migration(tasks_dir, db_path)
    assert success
    assert detail["tasks_migrated"] == 0

def test_migrate_child_before_parent_restores_relationship(tmp_path):
    tasks_dir = tmp_path / ".cowork-flow" / "tasks"
    tasks_dir.mkdir(parents=True)
    child = tasks_dir / "01-01-child"
    parent = tasks_dir / "02-01-parent"
    child.mkdir()
    parent.mkdir()
    (child / "task.json").write_text(json.dumps({
        "id": "child", "title": "Child", "status": "planning",
        "creator": "dev1", "assignee": "dev1",
        "parent": "parent", "children": [],
    }), encoding="utf-8")
    (parent / "task.json").write_text(json.dumps({
        "id": "parent", "title": "Parent", "status": "planning",
        "creator": "dev1", "assignee": "dev1",
        "children": ["01-01-child"],
    }), encoding="utf-8")

    db_path = str(tmp_path / "test.db")
    success, warnings, detail = run_migration(tasks_dir, db_path)

    assert success
    assert warnings == []
    assert detail["tasks_migrated"] == 2
    with FlowStore(db_path) as store:
        migrated_child = store.get_task("child")
        assert migrated_child is not None
        assert migrated_child.parent_id == "parent"
        assert [task.id for task in store.list_children("parent")] == ["child"]

def test_migrate_rolls_back_whole_batch_on_hard_failure(tmp_path):
    tasks_dir = tmp_path / ".cowork-flow" / "tasks"
    tasks_dir.mkdir(parents=True)
    first = tasks_dir / "01-01-first"
    duplicate = tasks_dir / "02-01-duplicate"
    first.mkdir()
    duplicate.mkdir()
    task_json = {
        "id": "same-id", "title": "Task", "status": "planning",
        "creator": "dev1", "assignee": "dev1",
    }
    (first / "task.json").write_text(json.dumps(task_json), encoding="utf-8")
    (duplicate / "task.json").write_text(json.dumps(task_json), encoding="utf-8")

    db_path = str(tmp_path / "test.db")
    with pytest.raises(sqlite3.IntegrityError):
        run_migration(tasks_dir, db_path)

    with FlowStore(db_path) as store:
        assert store.list_tasks() == []

class FlowMigrateCliAcceptanceTest(unittest.TestCase):
    def _write_old_task(
        self,
        task_dir: Path,
        *,
        task_id: str,
        title: str,
        status: str = "planning",
        children: list[str] | None = None,
    ) -> None:
        task_dir.mkdir(parents=True)
        (task_dir / "task.json").write_text(
            json.dumps(
                {
                    "id": task_id,
                    "title": title,
                    "status": status,
                    "creator": "legacy",
                    "assignee": "legacy",
                    "children": children or [],
                }
            ),
            encoding="utf-8",
        )

    def test_repo_gitignore_covers_local_generated_artifacts(self) -> None:
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".codegraph/", gitignore)
        self.assertIn("template/.cowork-flow/.runtime/", gitignore)

    def test_flow_migrate_cli_migrates_old_project_and_preserves_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "old-project"
            workflow = project / ".cowork-flow"
            shutil.copytree(ROOT / "template" / ".cowork-flow", workflow)
            shutil.rmtree(workflow / "tasks")
            tasks_dir = workflow / "tasks"
            tasks_dir.mkdir(parents=True)
            self._write_old_task(
                tasks_dir / "01-01-parent",
                task_id="parent",
                title="Legacy parent",
                children=["01-02-child"],
            )
            self._write_old_task(
                tasks_dir / "01-02-child",
                task_id="child",
                title="Legacy child",
                status="completed",
            )

            result = subprocess.run(
                [sys.executable, str(workflow / "scripts" / "run.py"), "flow-migrate"],
                cwd=project,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("Migrated 2 tasks", result.stdout)
            self.assertTrue((workflow / "tasks.backup" / "01-01-parent" / "task.json").is_file())
            self.assertTrue((workflow / "tasks" / "archive").is_dir())
            self.assertFalse((workflow / "tasks" / "01-01-parent").exists())
            gitignore = (project / ".gitignore").read_text(encoding="utf-8")
            self.assertIn("tasks.backup/", gitignore)
            self.assertIn(".cowork-flow/cowork-flow.db", gitignore)
            with FlowStore(str(workflow / "cowork-flow.db")) as store:
                self.assertEqual(["child", "parent"], sorted(task.id for task in store.list_tasks()))
                self.assertEqual(["child"], [task.id for task in store.list_children("parent")])
