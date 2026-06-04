from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"


class ProjectContextTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        shutil.copytree(TEMPLATE, self.repo)
        self.script = self.repo / ".cowork-flow" / "scripts" / "project_context.py"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_context(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self.script), *args],
            cwd=self.repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_refresh_creates_project_context(self) -> None:
        result = self.run_context("refresh")

        context_file = self.repo / ".cowork-flow" / "project-context.md"
        text = context_file.read_text(encoding="utf-8")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("refreshed .cowork-flow/project-context.md", result.stdout)
        self.assertIn("# Project Context", text)
        self.assertIn("## Generated Context", text)
        self.assertIn("## Manual Notes", text)
        self.assertIn("## Project Identity", text)
        self.assertIn("## Workflow Commands", text)
        self.assertIn("## Host Adapters", text)

    def test_refresh_is_idempotent(self) -> None:
        first = self.run_context("refresh")
        self.assertEqual(0, first.returncode, first.stderr)
        context_file = self.repo / ".cowork-flow" / "project-context.md"
        first_text = context_file.read_text(encoding="utf-8")

        second = self.run_context("refresh")
        second_text = context_file.read_text(encoding="utf-8")

        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual(first_text, second_text)

    def test_refresh_preserves_manual_notes(self) -> None:
        context_file = self.repo / ".cowork-flow" / "project-context.md"
        context_file.write_text(
            "# Project Context\n\n"
            "<!-- COWORK-FLOW:PROJECT-CONTEXT:START -->\n"
            "old generated text\n"
            "<!-- COWORK-FLOW:PROJECT-CONTEXT:END -->\n\n"
            "## Manual Notes\n\n"
            "- Keep this operator note.\n",
            encoding="utf-8",
        )

        result = self.run_context("refresh")
        text = context_file.read_text(encoding="utf-8")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn("old generated text", text)
        self.assertIn("- Keep this operator note.", text)

    def test_refresh_tolerates_missing_optional_files(self) -> None:
        package_json = self.repo / "package.json"
        if package_json.exists():
            package_json.unlink()
        shutil.rmtree(self.repo / ".codex")

        result = self.run_context("refresh")
        text = (self.repo / ".cowork-flow" / "project-context.md").read_text(encoding="utf-8")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("package.json: missing", text)
        self.assertIn("`.codex`: missing", text)


if __name__ == "__main__":
    unittest.main()
