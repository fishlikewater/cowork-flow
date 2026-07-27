from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"


class TaskArchiveServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        archive_module = importlib.import_module("services.task_archive")
        self.TaskArchiveError = archive_module.TaskArchiveError
        self.TaskArchiveService = archive_module.TaskArchiveService

    def _cleanup_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in (
            "services.task_archive",
            "application",
            "runtime.session_state",
            "infra.archive_utils",
            "services.task_repository",
            "services.task_utils",
            "infra.files",
            "infra.paths",
            "common",
        ):
            sys.modules.pop(module_name, None)

    @staticmethod
    def _write_task(tasks_dir: Path, name: str, data: dict) -> Path:
        task_dir = tasks_dir / name
        task_dir.mkdir(parents=True)
        (task_dir / "task.json").write_text(
            json.dumps(data, ensure_ascii=False),
            encoding="utf-8",
        )
        return task_dir

    @staticmethod
    def _read_task(task_dir: Path) -> dict:
        return json.loads(
            (task_dir / "task.json").read_text(encoding="utf-8")
        )

    def test_archive_updates_parent_and_child_relationships(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tasks_dir = root / ".cowork-flow" / "tasks"
            tasks_dir.mkdir(parents=True)
            parent = self._write_task(
                tasks_dir,
                "07-10-parent",
                {
                    "status": "in_progress",
                    "children": ["07-10-target"],
                    "custom": "parent",
                },
            )
            target = self._write_task(
                tasks_dir,
                "07-10-target",
                {
                    "status": "completed",
                    "parent": "07-10-parent",
                    "children": ["07-10-child"],
                    "custom": "target",
                },
            )
            child = self._write_task(
                tasks_dir,
                "07-10-child",
                {
                    "status": "planning",
                    "parent": "07-10-target",
                    "custom": "child",
                },
            )
            service = self.TaskArchiveService(root)

            result = service.archive(target, archived_at="2026-07-10")

            expected = (
                tasks_dir
                / "archive"
                / "2026-07"
                / "07-10-target"
            )
            self.assertEqual(expected, result.destination)
            self.assertFalse(target.exists())
            self.assertEqual("target", self._read_task(expected)["custom"])
            self.assertEqual([], self._read_task(parent)["children"])
            self.assertEqual("parent", self._read_task(parent)["custom"])
            self.assertIsNone(self._read_task(child)["parent"])
            self.assertEqual("child", self._read_task(child)["custom"])

    def test_archive_rejects_non_completed_task_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tasks_dir = root / ".cowork-flow" / "tasks"
            tasks_dir.mkdir(parents=True)
            task_dir = self._write_task(
                tasks_dir,
                "07-10-demo",
                {"status": "in_progress", "custom": "keep"},
            )
            service = self.TaskArchiveService(root)

            with self.assertRaises(self.TaskArchiveError) as raised:
                service.archive(task_dir, archived_at="2026-07-10")

            self.assertEqual("TASK-ARCHIVE-STATUS-001", raised.exception.code)
            self.assertTrue(task_dir.is_dir())
            self.assertEqual("keep", self._read_task(task_dir)["custom"])

    def test_archive_normalizes_task_context_self_references(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tasks_dir = root / ".cowork-flow" / "tasks"
            tasks_dir.mkdir(parents=True)
            task_dir = self._write_task(
                tasks_dir,
                "07-10-demo",
                {"status": "completed"},
            )
            active_path = ".cowork-flow/tasks/07-10-demo"
            entries = (
                {"file": active_path, "reason": "task root"},
                {
                    "file": f"{active_path}/decision-anchor.md",
                    "reason": "task artifact",
                },
                {"file": "src/example.py", "reason": "project file"},
            )
            (task_dir / "implement.jsonl").write_text(
                "".join(json.dumps(entry) + "\n" for entry in entries),
                encoding="utf-8",
            )

            result = self.TaskArchiveService(root).archive(
                task_dir,
                archived_at="2026-07-10",
            )

            archived_path = (
                ".cowork-flow/tasks/archive/2026-07/07-10-demo"
            )
            archived_entries = [
                json.loads(line)
                for line in (result.destination / "implement.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertEqual(archived_path, archived_entries[0]["file"])
            self.assertEqual(
                f"{archived_path}/decision-anchor.md",
                archived_entries[1]["file"],
            )
            self.assertEqual("src/example.py", archived_entries[2]["file"])

    def test_archive_preserves_task_local_review_notes_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tasks_dir = root / ".cowork-flow" / "tasks"
            tasks_dir.mkdir(parents=True)
            task_dir = self._write_task(
                tasks_dir,
                "07-10-demo",
                {"status": "completed"},
            )
            note = {
                "id": "REVIEW-NOTE-001",
                "type": "review-note",
                "files": ["src/example.py"],
                "summary": "Archived task-local review notes remain traceable.",
            }
            (task_dir / "review-notes.jsonl").write_text(
                json.dumps(note, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            result = self.TaskArchiveService(root).archive(
                task_dir,
                archived_at="2026-07-10",
            )

            archived_note = json.loads(
                (result.destination / "review-notes.jsonl").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual("REVIEW-NOTE-001", archived_note["id"])
            self.assertEqual("review-note", archived_note["type"])

    def test_archive_rollback_restores_original_context_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tasks_dir = root / ".cowork-flow" / "tasks"
            tasks_dir.mkdir(parents=True)
            task_dir = self._write_task(
                tasks_dir,
                "07-10-demo",
                {"status": "completed"},
            )
            context_file = task_dir / "implement.jsonl"
            original = (
                b'{"file": ".cowork-flow/tasks/07-10-demo", '
                b'"reason": "keep exact bytes"}\n'
            )
            context_file.write_bytes(original)
            destination = (
                tasks_dir / "archive" / "2026-07" / "07-10-demo"
            )

            with self.assertRaises(self.TaskArchiveError):
                self.TaskArchiveService(root).archive(
                    task_dir,
                    archived_at="2026-07-10",
                    finalize=lambda: False,
                )

            self.assertTrue(task_dir.is_dir())
            self.assertFalse(destination.exists())
            self.assertEqual(original, context_file.read_bytes())


if __name__ == "__main__":
    unittest.main()
