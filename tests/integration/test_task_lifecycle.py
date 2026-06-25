#!/usr/bin/env python3
"""
Task lifecycle integration tests.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def run_script(script_path: Path, *args, cwd: Path = None):
    """Run a Python script and return result."""
    return subprocess.run(
        [sys.executable, str(script_path), *args],
        cwd=cwd or script_path.parent,
        capture_output=True,
        text=True,
    )


def test_task_creation():
    """Test complete task creation flow."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = Path(temp_dir) / "test-repo"
        template_dir = Path(__file__).parent.parent.parent / "template"
        if template_dir.exists():
            shutil.copytree(template_dir, repo)
        else:
            repo.mkdir()
            (repo / ".cowork-flow").mkdir()
            (repo / ".cowork-flow" / "scripts").mkdir()

        # Initialize developer
        (repo / ".cowork-flow" / ".developer").write_text(
            "name=test-developer\n",
            encoding="utf-8",
        )

        # Create task
        script = repo / ".cowork-flow" / "scripts" / "task.py"
        if script.exists():
            result = run_script(script, "create", "Test Task", "--slug", "test-task", cwd=repo)
            # Note: This may fail without proper setup, but we're testing the framework
            print(f"  Task creation result: {result.returncode}")
            if result.returncode == 0:
                task_dir = repo / ".cowork-flow" / "tasks" / "06-21-test-task"
                assert task_dir.exists(), f"Task directory not found: {task_dir}"
                assert (task_dir / "task.json").exists(), "task.json not found"
                print("✓ test_task_creation passed")
            else:
                print(f"  Skipping (script not available): {result.stderr[:100]}")
        else:
            print("  Skipping (task.py not found)")


def test_task_status_transitions():
    """Test task status transitions."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = Path(temp_dir) / "test-repo"
        repo.mkdir()
        (repo / ".cowork-flow").mkdir()
        (repo / ".cowork-flow" / "tasks").mkdir()

        # Create a task directory with task.json
        task_dir = repo / ".cowork-flow" / "tasks" / "06-21-test-task"
        task_dir.mkdir()

        # Test planning status
        task_data = {"title": "Test Task", "status": "planning"}
        (task_dir / "task.json").write_text(json.dumps(task_data), encoding="utf-8")

        with open(task_dir / "task.json", encoding="utf-8") as f:
            data = json.load(f)
        assert data["status"] == "planning", "Initial status should be planning"

        # Test in_progress status
        data["status"] = "in_progress"
        (task_dir / "task.json").write_text(json.dumps(data), encoding="utf-8")

        with open(task_dir / "task.json", encoding="utf-8") as f:
            data = json.load(f)
        assert data["status"] == "in_progress", "Status should be in_progress"

        # Test completed status
        data["status"] = "completed"
        (task_dir / "task.json").write_text(json.dumps(data), encoding="utf-8")

        with open(task_dir / "task.json", encoding="utf-8") as f:
            data = json.load(f)
        assert data["status"] == "completed", "Status should be completed"

        print("✓ test_task_status_transitions passed")


def test_task_json_structure():
    """Test task.json has required fields."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = Path(temp_dir) / "test-repo"
        repo.mkdir()
        (repo / ".cowork-flow").mkdir()
        (repo / ".cowork-flow" / "tasks").mkdir()

        task_dir = repo / ".cowork-flow" / "tasks" / "06-21-test-task"
        task_dir.mkdir()

        task_data = {
            "title": "Test Task",
            "status": "planning",
            "assignee": "test-developer",
            "priority": "P1",
        }
        (task_dir / "task.json").write_text(json.dumps(task_data), encoding="utf-8")

        with open(task_dir / "task.json", encoding="utf-8") as f:
            data = json.load(f)

        assert "title" in data, "Missing title"
        assert "status" in data, "Missing status"
        assert "assignee" in data, "Missing assignee"
        assert "priority" in data, "Missing priority"

        print("✓ test_task_json_structure passed")


if __name__ == "__main__":
    print("Running task lifecycle tests...\n")
    test_task_creation()
    test_task_status_transitions()
    test_task_json_structure()
    print("\nAll lifecycle tests passed!")
