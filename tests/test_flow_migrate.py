"""Migration script tests."""
import json
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".cowork-flow" / "scripts"))
from flow.migrate import run_migration


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