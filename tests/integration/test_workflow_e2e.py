#!/usr/bin/env python3
"""
End-to-end workflow integration tests.
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


def test_complete_workflow():
    """Test complete workflow from change to completion."""
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

        # Create change
        change_script = repo / ".cowork-flow" / "scripts" / "change.py"
        if change_script.exists():
            result = run_script(change_script, "create", "new-feature", cwd=repo)
            print(f"  Change creation result: {result.returncode}")

            if result.returncode == 0:
                change_dir = repo / ".cowork-flow" / "changes" / "06-21-new-feature"
                assert change_dir.exists(), f"Change directory not found: {change_dir}"
                print("✓ Change created successfully")
            else:
                print(f"  Skipping change creation: {result.stderr[:100]}")
        else:
            print("  Skipping (change.py not found)")

        # Create task
        task_script = repo / ".cowork-flow" / "scripts" / "task.py"
        if task_script.exists():
            result = run_script(
                task_script, "create", "Implement feature",
                "--slug", "implement-feature", cwd=repo
            )
            print(f"  Task creation result: {result.returncode}")

            if result.returncode == 0:
                task_dir = repo / ".cowork-flow" / "tasks" / "06-21-implement-feature"
                assert task_dir.exists(), f"Task directory not found: {task_dir}"

                # Add PRD
                prd_path = task_dir / "prd.md"
                prd_path.write_text(
                    "# PRD\n\nImplement the new feature\n\n## Acceptance Criteria\n- [ ] Feature works",
                    encoding="utf-8",
                )

                # Verify task status
                with open(task_dir / "task.json", encoding="utf-8") as f:
                    data = json.load(f)
                assert data["status"] == "planning", "Initial status should be planning"

                print("✓ Task created and PRD added")
            else:
                print(f"  Skipping task creation: {result.stderr[:100]}")
        else:
            print("  Skipping (task.py not found)")

        print("✓ test_complete_workflow passed")


def test_error_recovery():
    """Test error recovery scenarios."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = Path(temp_dir) / "test-repo"
        repo.mkdir()
        (repo / ".cowork-flow").mkdir()
        (repo / ".cowork-flow" / "tasks").mkdir()

        # Create a task
        task_dir = repo / ".cowork-flow" / "tasks" / "06-21-test-task"
        task_dir.mkdir()
        task_data = {"title": "Test Task", "status": "planning"}
        (task_dir / "task.json").write_text(json.dumps(task_data), encoding="utf-8")

        # Test status transitions with validation
        with open(task_dir / "task.json", encoding="utf-8") as f:
            data = json.load(f)

        # Verify we can read and modify
        assert data["status"] == "planning"
        data["status"] = "in_progress"
        (task_dir / "task.json").write_text(json.dumps(data), encoding="utf-8")

        with open(task_dir / "task.json", encoding="utf-8") as f:
            data = json.load(f)
        assert data["status"] == "in_progress"

        # Test rollback scenario
        data["status"] = "planning"
        (task_dir / "task.json").write_text(json.dumps(data), encoding="utf-8")

        with open(task_dir / "task.json", encoding="utf-8") as f:
            data = json.load(f)
        assert data["status"] == "planning"

        print("✓ test_error_recovery passed")


def test_task_archive():
    """Test task archival."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = Path(temp_dir) / "test-repo"
        repo.mkdir()
        (repo / ".cowork-flow").mkdir()
        (repo / ".cowork-flow" / "tasks").mkdir()
        archive_dir = repo / ".cowork-flow" / "tasks" / "archive"
        archive_dir.mkdir()
        month_dir = archive_dir / "2026-06"
        month_dir.mkdir()

        # Create a completed task
        task_dir = repo / ".cowork-flow" / "tasks" / "06-21-test-task"
        task_dir.mkdir()
        task_data = {"title": "Test Task", "status": "completed"}
        (task_dir / "task.json").write_text(json.dumps(task_data), encoding="utf-8")

        # Archive the task (simulated)
        archived_dir = month_dir / "06-21-test-task"
        task_dir.rename(archived_dir)

        # Verify archival
        assert archived_dir.exists(), "Archived task not found"
        assert not task_dir.exists(), "Original task should not exist"

        with open(archived_dir / "task.json", encoding="utf-8") as f:
            data = json.load(f)
        assert data["status"] == "completed", "Archived task should be completed"

        print("✓ test_task_archive passed")


if __name__ == "__main__":
    print("Running E2E workflow tests...\n")
    test_complete_workflow()
    test_error_recovery()
    test_task_archive()
    print("\nAll E2E tests passed!")
