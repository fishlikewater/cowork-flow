from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
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

    def read_metadata(self, slug: str) -> dict[str, object]:
        metadata: dict[str, object] = {}
        path = self.repo / ".cowork-flow" / "changes" / slug / "change.yaml"
        if not path.is_file():
            archive_root = self.repo / ".cowork-flow" / "changes" / "archive"
            matches = list(archive_root.glob(f"*/{slug}/change.yaml"))
            self.assertEqual(1, len(matches))
            path = matches[0]
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or ":" not in line:
                continue
            key, value = line.split(":", 1)
            value = value.strip()
            if value == "null":
                metadata[key.strip()] = None
            elif value == "true":
                metadata[key.strip()] = True
            elif value == "false":
                metadata[key.strip()] = False
            else:
                metadata[key.strip()] = value
        return metadata

    def test_create_generates_change_scaffold(self) -> None:
        result = self.run_change("create", "replace-auth")

        self.assertEqual(0, result.returncode, result.stderr)
        change_dir = self.repo / ".cowork-flow" / "changes" / "replace-auth"
        self.assertTrue((change_dir / "change.yaml").is_file())
        self.assertTrue((change_dir / "proposal.md").is_file())
        self.assertTrue((change_dir / "design.md").is_file())
        self.assertTrue((change_dir / "spec.md").is_file())
        self.assertFalse((change_dir / "specs").exists())
        metadata = self.read_metadata("replace-auth")
        self.assertEqual("replace-auth", metadata["slug"])
        self.assertEqual("draft", metadata["status"])
        self.assertEqual("L1", metadata["level"])
        self.assertEqual(False, metadata["documentation_only"])
        self.assertIsNone(metadata["plan"])
        self.assertIsNone(metadata["task"])
        datetime.fromisoformat(str(metadata["created_at"]))

    def test_create_rejects_invalid_slug(self) -> None:
        result = self.run_change("create", "Invalid_Slug")

        self.assertNotEqual(0, result.returncode)
        self.assertIn("slug", result.stderr)
        self.assertFalse((self.repo / ".cowork-flow" / "changes" / "Invalid_Slug").exists())

    def test_validate_reports_bad_metadata_and_missing_links(self) -> None:
        self.assertEqual(0, self.run_change("create", "broken-change").returncode)
        change_dir = self.repo / ".cowork-flow" / "changes" / "broken-change"
        (change_dir / "proposal.md").write_text("", encoding="utf-8")
        spec = change_dir / "spec.md"
        spec.write_text("# Backend behavior\n\n- The API returns 200.\n", encoding="utf-8")
        change_yaml = change_dir / "change.yaml"
        content = change_yaml.read_text(encoding="utf-8")
        content = content.replace("status: draft", "status: paused")
        content = content.replace("level: L1", "level: L9")
        content = content.replace("plan: null", "plan: missing-plan.md")
        content = content.replace("task: null", "task: missing-task")
        change_yaml.write_text(content, encoding="utf-8")

        failed = self.run_change("validate", "broken-change")

        self.assertNotEqual(0, failed.returncode)
        self.assertIn("proposal.md", failed.stderr)
        self.assertIn("status", failed.stderr)
        self.assertIn("level", failed.stderr)
        self.assertIn("plan", failed.stderr)
        self.assertIn("task", failed.stderr)

    def test_validate_rejects_non_root_spec_md_files(self) -> None:
        self.assertEqual(0, self.run_change("create", "replace-auth").returncode)

        failed = self.run_change("validate", "replace-auth")
        self.assertNotEqual(0, failed.returncode)
        self.assertIn("spec.md", failed.stderr)

        notes = self.repo / ".cowork-flow" / "changes" / "replace-auth" / "notes.md"
        notes.write_text("# Backend notes\n\n- The API returns 200.\n", encoding="utf-8")

        still_failed = self.run_change("validate", "replace-auth")
        self.assertNotEqual(0, still_failed.returncode)
        self.assertIn("spec.md", still_failed.stderr)

        spec = self.repo / ".cowork-flow" / "changes" / "replace-auth" / "spec.md"
        spec.write_text("# Backend behavior\n\n- The API returns 200.\n", encoding="utf-8")

        passed = self.run_change("validate", "replace-auth")
        self.assertEqual(0, passed.returncode, passed.stderr)
        self.assertIn("valid", passed.stdout)

    def test_validate_allows_documentation_only_without_spec(self) -> None:
        self.assertEqual(0, self.run_change("create", "doc-only-change").returncode)
        change_yaml = self.repo / ".cowork-flow" / "changes" / "doc-only-change" / "change.yaml"
        content = change_yaml.read_text(encoding="utf-8")
        content = content.replace("documentation_only: false", "documentation_only: true")
        change_yaml.write_text(content, encoding="utf-8")

        passed = self.run_change("validate", "doc-only-change")
        self.assertEqual(0, passed.returncode, passed.stderr)
        self.assertIn("valid", passed.stdout)

    def test_validate_requires_design_for_l2_change(self) -> None:
        self.assertEqual(0, self.run_change("create", "cross-layer-auth", "--level", "L2").returncode)
        spec = self.repo / ".cowork-flow" / "changes" / "cross-layer-auth" / "spec.md"
        spec.write_text("# Cross-layer behavior\n\n- Frontend and backend share the same contract.\n", encoding="utf-8")

        failed = self.run_change("validate", "cross-layer-auth")
        self.assertNotEqual(0, failed.returncode)
        self.assertIn("design.md", failed.stderr)

        design = self.repo / ".cowork-flow" / "changes" / "cross-layer-auth" / "design.md"
        design.write_text("# Design\n\nUse one explicit API contract.\n", encoding="utf-8")

        passed = self.run_change("validate", "cross-layer-auth")
        self.assertEqual(0, passed.returncode, passed.stderr)

    def test_validate_accepts_active_status(self) -> None:
        self.assertEqual(0, self.run_change("create", "active-change").returncode)
        spec = self.repo / ".cowork-flow" / "changes" / "active-change" / "spec.md"
        spec.write_text("# Backend behavior\n\n- The API returns 200.\n", encoding="utf-8")

        change_yaml = self.repo / ".cowork-flow" / "changes" / "active-change" / "change.yaml"
        content = change_yaml.read_text(encoding="utf-8")
        content = content.replace("status: draft", "status: active")
        change_yaml.write_text(content, encoding="utf-8")

        passed = self.run_change("validate", "active-change")
        self.assertEqual(0, passed.returncode, passed.stderr)
        self.assertIn("valid", passed.stdout)

    def test_archive_requires_valid_change_and_moves_to_month_archive(self) -> None:
        self.assertEqual(0, self.run_change("create", "replace-auth").returncode)
        spec = self.repo / ".cowork-flow" / "changes" / "replace-auth" / "spec.md"
        spec.write_text("# Backend behavior\n\n- The API returns 200.\n", encoding="utf-8")

        archived = self.run_change("archive", "replace-auth")

        self.assertEqual(0, archived.returncode, archived.stderr)
        self.assertFalse((self.repo / ".cowork-flow" / "changes" / "replace-auth").exists())
        archive_root = self.repo / ".cowork-flow" / "changes" / "archive"
        matches = list(archive_root.glob("*/replace-auth/change.yaml"))
        self.assertEqual(1, len(matches))
        metadata = self.read_metadata("replace-auth")
        self.assertEqual("archived", metadata["status"])
        self.assertIn("archived_at", metadata)
        datetime.fromisoformat(str(metadata["archived_at"]))

    def test_list_prints_active_and_archived_changes(self) -> None:
        self.assertEqual(0, self.run_change("create", "replace-auth").returncode)
        spec = self.repo / ".cowork-flow" / "changes" / "replace-auth" / "spec.md"
        spec.write_text("# Backend behavior\n\n- The API returns 200.\n", encoding="utf-8")
        change_yaml = self.repo / ".cowork-flow" / "changes" / "replace-auth" / "change.yaml"
        content = change_yaml.read_text(encoding="utf-8")
        content = content.replace("plan: null", "plan: .cowork-flow/plans/2026-05-18-active.md")
        content = content.replace("task: null", "task: .cowork-flow/tasks/05-18-active")
        change_yaml.write_text(content, encoding="utf-8")
        (self.repo / ".cowork-flow" / "plans" / "2026-05-18-active.md").write_text(
            "# Active plan\n",
            encoding="utf-8",
        )
        (self.repo / ".cowork-flow" / "tasks" / "05-18-active").mkdir()

        self.assertEqual(0, self.run_change("archive", "replace-auth").returncode)

        self.assertEqual(0, self.run_change("create", "active-change").returncode)
        active_yaml = self.repo / ".cowork-flow" / "changes" / "active-change" / "change.yaml"
        active_content = active_yaml.read_text(encoding="utf-8")
        active_content = active_content.replace("status: draft", "status: active")
        active_yaml.write_text(active_content, encoding="utf-8")

        listed = self.run_change("list")

        self.assertEqual(0, listed.returncode, listed.stderr)
        self.assertIn("active-change", listed.stdout)
        self.assertIn("status=active", listed.stdout)
        self.assertIn("replace-auth", listed.stdout)
        self.assertIn("archived", listed.stdout)
        self.assertIn("plan=.cowork-flow/plans/2026-05-18-active.md", listed.stdout)
        self.assertIn("task=.cowork-flow/tasks/05-18-active", listed.stdout)


if __name__ == "__main__":
    unittest.main()
