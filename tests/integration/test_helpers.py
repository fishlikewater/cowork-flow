#!/usr/bin/env python3
"""
Helper functions for integration tests.
"""

import json
import subprocess
import sys
from pathlib import Path


def run_script(script_path: Path, *args, cwd: Path = None):
    """
    Run a Python script and return result.

    Args:
        script_path: Path to the script
        *args: Arguments to pass to the script
        cwd: Working directory

    Returns:
        subprocess.CompletedProcess
    """
    return subprocess.run(
        [sys.executable, str(script_path), *args],
        cwd=cwd or script_path.parent,
        capture_output=True,
        text=True,
    )


def assert_task_created(repo: Path, task_name: str):
    """
    Assert task was created successfully.

    Args:
        repo: Repository path
        task_name: Task name/slug
    """
    task_dir = repo / ".cowork-flow" / "tasks" / f"06-21-{task_name}"
    assert task_dir.exists(), f"Task directory not found: {task_dir}"
    assert (task_dir / "task.json").exists(), f"task.json not found in {task_dir}"

    with open(task_dir / "task.json", encoding="utf-8") as f:
        data = json.load(f)
    assert "title" in data, "task.json missing title"
    assert "status" in data, "task.json missing status"


def assert_change_created(repo: Path, change_name: str):
    """
    Assert change was created successfully.

    Args:
        repo: Repository path
        change_name: Change name/slug
    """
    change_dir = repo / ".cowork-flow" / "changes" / f"06-21-{change_name}"
    assert change_dir.exists(), f"Change directory not found: {change_dir}"
    assert (change_dir / "change.yaml").exists(), f"change.yaml not found in {change_dir}"


def read_task_json(repo: Path, task_name: str) -> dict:
    """
    Read task.json content.

    Args:
        repo: Repository path
        task_name: Task name/slug

    Returns:
        Task data dictionary
    """
    task_dir = repo / ".cowork-flow" / "tasks" / f"06-21-{task_name}"
    with open(task_dir / "task.json", encoding="utf-8") as f:
        return json.load(f)
