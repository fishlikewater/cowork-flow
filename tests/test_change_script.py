from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"


class ChangeScriptTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        shutil.copytree(TEMPLATE, self.repo)
        self.script = self.repo / ".cowork-flow" / "scripts" / "change.py"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_change(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self.script), *args],
            cwd=self.repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_create_generates_change_scaffold(self) -> None:
        result = self.run_change("create", "replace-auth")

        self.assertEqual(0, result.returncode, result.stderr)
        change_dir = self.repo / ".cowork-flow" / "changes" / "replace-auth"
        self.assertTrue((change_dir / "change.yaml").is_file())
        self.assertTrue((change_dir / "proposal.md").is_file())
        self.assertTrue((change_dir / "design.md").is_file())
        self.assertTrue((change_dir / "specs" / ".gitkeep").is_file())
        self.assertIn("slug: replace-auth", (change_dir / "change.yaml").read_text())

    def test_validate_requires_non_empty_behavior_spec_unless_documentation_only(self) -> None:
        self.assertEqual(0, self.run_change("create", "replace-auth").returncode)

        failed = self.run_change("validate", "replace-auth")
        self.assertNotEqual(0, failed.returncode)
        self.assertIn("specs", failed.stderr)

        spec = self.repo / ".cowork-flow" / "changes" / "replace-auth" / "specs" / "backend" / "spec.md"
        spec.parent.mkdir(parents=True)
        spec.write_text("# Backend behavior\n\n- The API returns 200.\n", encoding="utf-8")

        passed = self.run_change("validate", "replace-auth")
        self.assertEqual(0, passed.returncode, passed.stderr)
        self.assertIn("valid", passed.stdout)

    def test_validate_requires_design_for_l2_change(self) -> None:
        self.assertEqual(0, self.run_change("create", "cross-layer-auth", "--level", "L2").returncode)
        spec = self.repo / ".cowork-flow" / "changes" / "cross-layer-auth" / "specs" / "backend" / "spec.md"
        spec.parent.mkdir(parents=True)
        spec.write_text("# Cross-layer behavior\n\n- Frontend and backend share the same contract.\n", encoding="utf-8")

        failed = self.run_change("validate", "cross-layer-auth")
        self.assertNotEqual(0, failed.returncode)
        self.assertIn("design.md", failed.stderr)

        design = self.repo / ".cowork-flow" / "changes" / "cross-layer-auth" / "design.md"
        design.write_text("# Design\n\nUse one explicit API contract.\n", encoding="utf-8")

        passed = self.run_change("validate", "cross-layer-auth")
        self.assertEqual(0, passed.returncode, passed.stderr)

    def test_archive_requires_valid_change_and_moves_to_month_archive(self) -> None:
        self.assertEqual(0, self.run_change("create", "replace-auth").returncode)
        spec = self.repo / ".cowork-flow" / "changes" / "replace-auth" / "specs" / "backend" / "spec.md"
        spec.parent.mkdir(parents=True)
        spec.write_text("# Backend behavior\n\n- The API returns 200.\n", encoding="utf-8")

        archived = self.run_change("archive", "replace-auth")

        self.assertEqual(0, archived.returncode, archived.stderr)
        self.assertFalse((self.repo / ".cowork-flow" / "changes" / "replace-auth").exists())
        archive_root = self.repo / ".cowork-flow" / "changes" / "archive"
        matches = list(archive_root.glob("*/replace-auth/change.yaml"))
        self.assertEqual(1, len(matches))

    def test_list_prints_active_changes(self) -> None:
        self.assertEqual(0, self.run_change("create", "replace-auth").returncode)

        listed = self.run_change("list")

        self.assertEqual(0, listed.returncode, listed.stderr)
        self.assertIn("replace-auth", listed.stdout)
        self.assertIn("draft", listed.stdout)


if __name__ == "__main__":
    unittest.main()
