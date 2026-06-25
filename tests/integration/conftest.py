#!/usr/bin/env python3
"""
Pytest fixtures for integration tests.
"""

import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_repo():
    """Create temporary repo with cowork-flow template."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = Path(temp_dir) / "test-repo"
        template_dir = Path(__file__).parent.parent.parent / "template"
        if template_dir.exists():
            shutil.copytree(template_dir, repo)
        else:
            repo.mkdir()
            (repo / ".cowork-flow").mkdir()
        yield repo


@pytest.fixture
def initialized_repo(temp_repo):
    """Create initialized repo with developer."""
    dev_file = temp_repo / ".cowork-flow" / ".developer"
    dev_file.write_text("name=test-developer\n", encoding="utf-8")
    yield temp_repo


@pytest.fixture
def repo_with_task(temp_repo):
    """Create repo with a test task."""
    tasks_dir = temp_repo / ".cowork-flow" / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    task_dir = tasks_dir / "06-21-test-task"
    task_dir.mkdir()
    (task_dir / "task.json").write_text(
        '{"title": "Test Task", "status": "planning"}',
        encoding="utf-8",
    )
    yield temp_repo
