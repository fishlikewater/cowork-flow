#!/usr/bin/env python3
"""
Basic integration test to verify framework works.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def test_temp_repo():
    """Test temp_repo creation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = Path(temp_dir) / "test-repo"
        template_dir = Path(__file__).parent.parent.parent / "template"
        if template_dir.exists():
            shutil.copytree(template_dir, repo)
        else:
            repo.mkdir()
            (repo / ".cowork-flow").mkdir()
        assert repo.exists()
        assert (repo / ".cowork-flow").exists()
        print("✓ test_temp_repo passed")


def test_run_script():
    """Test run_script helper."""
    with tempfile.TemporaryDirectory() as temp_dir:
        script = Path(temp_dir) / "test_script.py"
        script.write_text("print('hello')", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "hello" in result.stdout
        print("✓ test_run_script passed")


if __name__ == "__main__":
    test_temp_repo()
    test_run_script()
    print("\nAll framework tests passed!")
