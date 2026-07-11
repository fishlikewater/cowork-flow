#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared fixtures for integration tests.

Provides:
    temp_repo          — bare temp dir with .cowork-flow/scripts copied
    initialized_repo   — temp_repo + .cowork-flow/.developer
    repo_with_task     — initialized_repo + a test task directory
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
ROOT_SCRIPTS = ROOT / ".cowork-flow" / "scripts"
SPEC_DIR = ROOT / ".cowork-flow" / "spec"
TEMPLATE_SPEC = ROOT / "template" / ".cowork-flow" / "spec"


class TempRepo:
    """Creates a temporary project directory for integration testing."""

    def __init__(self, use_root_scripts: bool = True):
        self.tmp = Path(tempfile.mkdtemp(prefix="cowork_integ_"))
        self.repo_root = self.tmp
        src_scripts = ROOT_SCRIPTS if use_root_scripts else TEMPLATE_SCRIPTS
        self._copy_scripts(src_scripts)
        self._copy_spec()

    def _copy_scripts(self, src: Path):
        dest = self.repo_root / ".cowork-flow" / "scripts"
        dest.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.copytree(src, dest, dirs_exist_ok=True)

    def _copy_spec(self):
        dest = self.repo_root / ".cowork-flow" / "spec"
        dest.mkdir(parents=True, exist_ok=True)
        if SPEC_DIR.exists():
            shutil.copytree(SPEC_DIR, dest, dirs_exist_ok=True)

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_file(self, rel_path: str, content: str):
        p = self.repo_root / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def init_developer(self, name: str = "test-developer"):
        flow_dir = self.repo_root / ".cowork-flow"
        flow_dir.mkdir(parents=True, exist_ok=True)
        dev_file = flow_dir / ".developer"
        dev_file.write_text(name, encoding="utf-8")

    def create_task_dir(self, slug: str, prd_content: str = "Test task") -> Path:
        tasks_dir = self.repo_root / ".cowork-flow" / "tasks"
        task_dir = tasks_dir / slug
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "prd.md").write_text(prd_content, encoding="utf-8")
        return task_dir


class IntegrationTestCase(unittest.TestCase):
    """Base class for integration tests with automatic cleanup."""

    def setUp(self):
        self.repo = TempRepo()
        self.addCleanup(self.repo.cleanup)

    def script_path(self, name: str) -> Path:
        """Return path to a script in the temp repo."""
        return self.repo.repo_root / ".cowork-flow" / "scripts" / name

    def run_script(self, script_name: str, args: list[str], cwd=None) -> tuple[int, str, str]:
        """Run a Python script and return (returncode, stdout, stderr)."""
        import subprocess
        script_path = self.script_path(script_name)
        if not script_path.exists():
            # Try common subdirectory
            for subdir in ("common", "flow", "patterns"):
                candidate = self.repo.repo_root / ".cowork-flow" / "scripts" / subdir / script_name
                if candidate.exists():
                    script_path = candidate
                    break
        result = subprocess.run(
            [sys.executable, str(script_path)] + args,
            cwd=str(cwd or self.repo.repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return result.returncode, result.stdout, result.stderr


# Pytest-compatible fixtures (for mixed test suites)

try:
    import pytest

    @pytest.fixture
    def temp_repo():
        repo = TempRepo()
        yield repo
        repo.cleanup()

    @pytest.fixture
    def initialized_repo(temp_repo):
        temp_repo.init_developer()
        return temp_repo

    @pytest.fixture
    def repo_with_task(initialized_repo):
        task_dir = initialized_repo.create_task_dir("06-26-test-task")
        return initialized_repo, task_dir

except ImportError:
    pass
