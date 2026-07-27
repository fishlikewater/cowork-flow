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
        self.script = self.repo / ".cowork-flow" / "scripts" / "adapters" / "cli" / "change.py"

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

    def change_dir_for(self, slug: str) -> Path:
        date_prefix = datetime.now().strftime("%m-%d")
        return self.repo / ".cowork-flow" / "changes" / f"{date_prefix}-{slug}"

    def change_name_for(self, slug: str) -> str:
        return self.change_dir_for(slug).name

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
        date_prefix = datetime.now().strftime("%m-%d")
        dir_name = f"{date_prefix}-replace-auth"
        change_dir = self.repo / ".cowork-flow" / "changes" / dir_name
        self.assertIn(f"created {dir_name}", result.stdout)
        self.assertTrue((change_dir / "change.yaml").is_file())
        self.assertTrue((change_dir / "proposal.md").is_file())
        self.assertTrue((change_dir / "design.md").is_file())
        self.assertTrue((change_dir / "spec.md").is_file())
        self.assertFalse((change_dir / "specs").exists())
        metadata = self.read_metadata(dir_name)
        self.assertEqual(dir_name, metadata["slug"])
        self.assertEqual("draft", metadata["status"])
        self.assertEqual("L1", metadata["level"])
        self.assertEqual(False, metadata["documentation_only"])
        self.assertIsNone(metadata["plan"])
        self.assertIsNone(metadata["task"])
        datetime.fromisoformat(str(metadata["created_at"]))

    def test_create_keeps_existing_date_prefix(self) -> None:
        date_prefix = datetime.now().strftime("%m-%d")
        slug = f"{date_prefix}-replace-auth"

        result = self.run_change("create", slug)

        self.assertEqual(0, result.returncode, result.stderr)
        change_dir = self.repo / ".cowork-flow" / "changes" / slug
        doubled = self.repo / ".cowork-flow" / "changes" / f"{date_prefix}-{slug}"
        self.assertIn(f"created {slug}", result.stdout)
        self.assertTrue((change_dir / "change.yaml").is_file())
        self.assertFalse(doubled.exists())
        metadata = self.read_metadata(slug)
        self.assertEqual(slug, metadata["slug"])

    def test_create_rejects_invalid_slug(self) -> None:
        result = self.run_change("create", "Invalid_Slug")

        self.assertNotEqual(0, result.returncode)
        self.assertIn("slug", result.stderr)
        self.assertFalse((self.repo / ".cowork-flow" / "changes" / "Invalid_Slug").exists())

    def test_validate_reports_bad_metadata_and_missing_links(self) -> None:
        self.assertEqual(0, self.run_change("create", "broken-change").returncode)
        change_dir = self.change_dir_for("broken-change")
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

        failed = self.run_change("validate", self.change_name_for("broken-change"))

        self.assertNotEqual(0, failed.returncode)
        self.assertIn("proposal.md", failed.stderr)
        self.assertIn("status", failed.stderr)
        self.assertIn("level", failed.stderr)
        self.assertIn("plan", failed.stderr)
        self.assertIn(".cowork-flow/tasks/missing-task", failed.stderr)

    def test_validate_accepts_existing_unprefixed_change_directory(self) -> None:
        change_dir = self.repo / ".cowork-flow" / "changes" / "legacy-change"
        change_dir.mkdir(parents=True)
        (change_dir / "proposal.md").write_text("# Legacy change\n", encoding="utf-8")
        (change_dir / "spec.md").write_text("# Behavior\n\n- Keep legacy names valid.\n", encoding="utf-8")
        (change_dir / "design.md").write_text("", encoding="utf-8")
        (change_dir / "change.yaml").write_text(
            "slug: legacy-change\n"
            "status: draft\n"
            "level: L1\n"
            "created_at: 2026-05-22T00:00:00+08:00\n"
            "documentation_only: false\n"
            "plan: null\n"
            "task: null\n",
            encoding="utf-8",
        )

        passed = self.run_change("validate", "legacy-change")

        self.assertEqual(0, passed.returncode, passed.stderr)
        self.assertIn("legacy-change valid", passed.stdout)

    def test_validate_rejects_non_root_spec_md_files(self) -> None:
        self.assertEqual(0, self.run_change("create", "replace-auth").returncode)

        failed = self.run_change("validate", self.change_name_for("replace-auth"))
        self.assertNotEqual(0, failed.returncode)
        self.assertIn("spec.md", failed.stderr)

        notes = self.change_dir_for("replace-auth") / "notes.md"
        notes.write_text("# Backend notes\n\n- The API returns 200.\n", encoding="utf-8")

        still_failed = self.run_change("validate", self.change_name_for("replace-auth"))
        self.assertNotEqual(0, still_failed.returncode)
        self.assertIn("spec.md", still_failed.stderr)

        spec = self.change_dir_for("replace-auth") / "spec.md"
        spec.write_text("# Backend behavior\n\n- The API returns 200.\n", encoding="utf-8")

        passed = self.run_change("validate", self.change_name_for("replace-auth"))
        self.assertEqual(0, passed.returncode, passed.stderr)
        self.assertIn("valid", passed.stdout)

    def test_validate_allows_documentation_only_without_spec(self) -> None:
        self.assertEqual(0, self.run_change("create", "doc-only-change").returncode)
        change_yaml = self.change_dir_for("doc-only-change") / "change.yaml"
        content = change_yaml.read_text(encoding="utf-8")
        content = content.replace("documentation_only: false", "documentation_only: true")
        change_yaml.write_text(content, encoding="utf-8")

        passed = self.run_change("validate", self.change_name_for("doc-only-change"))
        self.assertEqual(0, passed.returncode, passed.stderr)
        self.assertIn("valid", passed.stdout)

    def test_validate_requires_design_for_l2_change(self) -> None:
        self.assertEqual(0, self.run_change("create", "cross-layer-auth", "--level", "L2").returncode)
        spec = self.change_dir_for("cross-layer-auth") / "spec.md"
        spec.write_text("# Cross-layer behavior\n\n- Frontend and backend share the same contract.\n", encoding="utf-8")

        failed = self.run_change("validate", self.change_name_for("cross-layer-auth"))
        self.assertNotEqual(0, failed.returncode)
        self.assertIn("design.md", failed.stderr)

        design = self.change_dir_for("cross-layer-auth") / "design.md"
        design.write_text("# Design\n\nUse one explicit API contract.\n", encoding="utf-8")

        passed = self.run_change("validate", self.change_name_for("cross-layer-auth"))
        self.assertEqual(0, passed.returncode, passed.stderr)

    def test_validate_accepts_active_status(self) -> None:
        self.assertEqual(0, self.run_change("create", "active-change").returncode)
        spec = self.change_dir_for("active-change") / "spec.md"
        spec.write_text("# Backend behavior\n\n- The API returns 200.\n", encoding="utf-8")

        change_yaml = self.change_dir_for("active-change") / "change.yaml"
        content = change_yaml.read_text(encoding="utf-8")
        content = content.replace("status: draft", "status: active")
        change_yaml.write_text(content, encoding="utf-8")

        passed = self.run_change("validate", self.change_name_for("active-change"))
        self.assertEqual(0, passed.returncode, passed.stderr)
        self.assertIn("valid", passed.stdout)

    def test_validate_accepts_prefixed_task_link(self) -> None:
        self.assertEqual(0, self.run_change("create", "replace-auth").returncode)
        change_dir = self.change_dir_for("replace-auth")
        spec = change_dir / "spec.md"
        spec.write_text("# Backend behavior\n\n- The API returns 200.\n", encoding="utf-8")
        change_yaml = change_dir / "change.yaml"
        content = change_yaml.read_text(encoding="utf-8")
        content = content.replace("task: null", "task: .cowork-flow/tasks/05-18-active")
        change_yaml.write_text(content, encoding="utf-8")
        (self.repo / ".cowork-flow" / "tasks" / "05-18-active").mkdir()

        passed = self.run_change("validate", self.change_name_for("replace-auth"))

        self.assertEqual(0, passed.returncode, passed.stderr)
        self.assertIn("valid", passed.stdout)

    def test_validate_reports_missing_repo_relative_task_without_double_prefix(self) -> None:
        self.assertEqual(0, self.run_change("create", "missing-task-link").returncode)
        change_dir = self.change_dir_for("missing-task-link")
        spec = change_dir / "spec.md"
        spec.write_text("# Backend behavior\n\n- Missing task links remain invalid.\n", encoding="utf-8")
        change_yaml = change_dir / "change.yaml"
        content = change_yaml.read_text(encoding="utf-8")
        content = content.replace("task: null", "task: .cowork-flow/tasks/missing-task")
        change_yaml.write_text(content, encoding="utf-8")

        failed = self.run_change("validate", self.change_name_for("missing-task-link"))

        self.assertNotEqual(0, failed.returncode)
        self.assertIn(".cowork-flow/tasks/missing-task", failed.stderr)
        self.assertNotIn(".cowork-flow/tasks/.cowork-flow/tasks/missing-task", failed.stderr)

    def test_archive_accepts_task_already_moved_to_archive(self) -> None:
        self.assertEqual(0, self.run_change("create", "replace-auth").returncode)
        change_dir = self.change_dir_for("replace-auth")
        spec = change_dir / "spec.md"
        spec.write_text("# Backend behavior\n\n- The API returns 200.\n", encoding="utf-8")
        task_dir = self.repo / ".cowork-flow" / "tasks" / "archive" / "2026-05" / "05-18-active"
        task_dir.mkdir(parents=True)
        change_yaml = change_dir / "change.yaml"
        content = change_yaml.read_text(encoding="utf-8")
        content = content.replace("task: null", "task: .cowork-flow/tasks/05-18-active")
        change_yaml.write_text(content, encoding="utf-8")

        archived = self.run_change("archive", self.change_name_for("replace-auth"))

        self.assertEqual(0, archived.returncode, archived.stderr)
        metadata = self.read_metadata(self.change_name_for("replace-auth"))
        self.assertEqual("archive/2026-05/05-18-active", metadata["task"])

    def test_archive_requires_valid_change_and_moves_to_month_archive(self) -> None:
        self.assertEqual(0, self.run_change("create", "replace-auth").returncode)
        spec = self.change_dir_for("replace-auth") / "spec.md"
        spec.write_text("# Backend behavior\n\n- The API returns 200.\n", encoding="utf-8")

        archived = self.run_change("archive", self.change_name_for("replace-auth"))

        self.assertEqual(0, archived.returncode, archived.stderr)
        self.assertFalse((self.change_dir_for("replace-auth")).exists())
        archive_root = self.repo / ".cowork-flow" / "changes" / "archive"
        matches = list(archive_root.glob(f"*/{self.change_name_for('replace-auth')}/change.yaml"))
        self.assertEqual(1, len(matches))
        metadata = self.read_metadata(self.change_name_for("replace-auth"))
        self.assertEqual("archived", metadata["status"])
        self.assertIn("archived_at", metadata)
        datetime.fromisoformat(str(metadata["archived_at"]))

    def test_archive_resumes_when_source_and_destination_match(self) -> None:
        self.assertEqual(0, self.run_change("create", "replace-auth").returncode)
        source = self.change_dir_for("replace-auth")
        spec = source / "spec.md"
        spec.write_text("# Backend behavior\n\n- The API returns 200.\n", encoding="utf-8")
        month = datetime.now().astimezone().strftime("%Y-%m")
        destination = self.repo / ".cowork-flow" / "changes" / "archive" / month / self.change_name_for("replace-auth")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination)

        archived = self.run_change("archive", self.change_name_for("replace-auth"))

        self.assertEqual(0, archived.returncode, archived.stderr)
        self.assertFalse(source.exists())
        self.assertTrue((destination / "change.yaml").is_file())
        metadata = self.read_metadata(self.change_name_for("replace-auth"))
        self.assertEqual("archived", metadata["status"])
        self.assertIn("archived_at", metadata)

    def test_archive_normalizes_archived_task_link(self) -> None:
        self.assertEqual(0, self.run_change("create", "replace-auth").returncode)
        change_dir = self.change_dir_for("replace-auth")
        spec = change_dir / "spec.md"
        spec.write_text("# Backend behavior\n\n- The API returns 200.\n", encoding="utf-8")
        task_dir = self.repo / ".cowork-flow" / "tasks" / "archive" / "2026-05" / "05-18-active"
        task_dir.mkdir(parents=True)
        change_yaml = change_dir / "change.yaml"
        content = change_yaml.read_text(encoding="utf-8")
        content = content.replace("task: null", "task: .cowork-flow/tasks/archive/2026-05/05-18-active")
        change_yaml.write_text(content, encoding="utf-8")

        archived = self.run_change("archive", self.change_name_for("replace-auth"))

        self.assertEqual(0, archived.returncode, archived.stderr)
        metadata = self.read_metadata(self.change_name_for("replace-auth"))
        self.assertEqual("archive/2026-05/05-18-active", metadata["task"])

    def test_list_prints_active_and_archived_changes(self) -> None:
        self.assertEqual(0, self.run_change("create", "replace-auth").returncode)
        spec = self.change_dir_for("replace-auth") / "spec.md"
        spec.write_text("# Backend behavior\n\n- The API returns 200.\n", encoding="utf-8")
        change_yaml = self.change_dir_for("replace-auth") / "change.yaml"
        content = change_yaml.read_text(encoding="utf-8")
        content = content.replace("plan: null", "plan: .cowork-flow/plans/2026-05-18-active.md")
        content = content.replace("task: null", "task: .cowork-flow/tasks/05-18-active")
        change_yaml.write_text(content, encoding="utf-8")
        (self.repo / ".cowork-flow" / "plans" / "2026-05-18-active.md").write_text(
            "# Active plan\n",
            encoding="utf-8",
        )
        (self.repo / ".cowork-flow" / "tasks" / "05-18-active").mkdir()

        self.assertEqual(0, self.run_change("archive", self.change_name_for("replace-auth")).returncode)

        self.assertEqual(0, self.run_change("create", "active-change").returncode)
        active_yaml = self.change_dir_for("active-change") / "change.yaml"
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
