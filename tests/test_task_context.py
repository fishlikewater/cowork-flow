from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"


class TaskContextServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        context_module = importlib.import_module("application.task_context")
        self.TaskContextService = context_module.TaskContextService
        self.TaskContextError = context_module.TaskContextError

    def _cleanup_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in (
            "application.task_context",
            "application",
            "common.core.files",
            "common.core.paths",
            "common",
        ):
            sys.modules.pop(module_name, None)

    @staticmethod
    def _prepare_root(root: Path) -> Path:
        task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
        task_dir.mkdir(parents=True)
        spec_dir = root / ".cowork-flow" / "spec" / "backend"
        spec_dir.mkdir(parents=True)
        (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
        (root / ".cowork-flow" / "workflow.md").write_text(
            "# Workflow\n",
            encoding="utf-8",
        )
        (spec_dir / "index.md").write_text("# Backend\n", encoding="utf-8")
        return task_dir

    def test_initialize_preserves_existing_context_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._prepare_root(root)
            custom = '{"file":"自定义.md","reason":"保留"}\n'
            (task_dir / "implement.jsonl").write_text(
                custom,
                encoding="utf-8",
            )
            service = self.TaskContextService(root)

            result = service.initialize(task_dir, "backend")

            self.assertEqual(("check.jsonl", "debug.jsonl"), result.created)
            self.assertEqual(("implement.jsonl",), result.skipped)
            self.assertEqual(
                custom,
                (task_dir / "implement.jsonl").read_text(encoding="utf-8"),
            )
            self.assertTrue((task_dir / "check.jsonl").is_file())
            self.assertTrue((task_dir / "debug.jsonl").is_file())

    def test_add_entry_deduplicates_and_preserves_utf8_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._prepare_root(root)
            docs_dir = root / "docs"
            docs_dir.mkdir()
            target = docs_dir / "说明.md"
            target.write_text("# 说明\n", encoding="utf-8")
            service = self.TaskContextService(root)

            first = service.add(
                task_dir,
                "implement",
                "docs/说明.md",
                "中文原因",
            )
            second = service.add(
                task_dir,
                "implement",
                "docs/说明.md",
                "重复原因",
            )

            self.assertTrue(first.added)
            self.assertFalse(second.added)
            entries = service.entries(task_dir, "implement")
            self.assertEqual(1, len(entries))
            self.assertEqual("中文原因", entries[0]["reason"])
            self.assertEqual("docs/说明.md", entries[0]["file"])

    def test_validate_returns_structured_json_and_path_issues(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._prepare_root(root)
            (task_dir / "implement.jsonl").write_text(
                "{invalid\n"
                + json.dumps(
                    {"file": "missing.md", "reason": "missing"},
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            service = self.TaskContextService(root)

            issues = service.validate(task_dir)

            self.assertEqual(2, len(issues))
            self.assertEqual(
                ["invalid_json", "file_not_found"],
                [issue.code for issue in issues],
            )
            self.assertEqual([1, 2], [issue.line for issue in issues])

    def test_add_allows_explicit_planned_file_without_creating_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._prepare_root(root)
            service = self.TaskContextService(root)

            result = service.add(
                task_dir,
                "implement",
                "src/new_module.py",
                "Planned source file",
                entry_type="planned-file",
            )

            self.assertTrue(result.added)
            self.assertEqual("planned-file", result.entry_type)
            self.assertFalse((root / "src" / "new_module.py").exists())
            self.assertEqual(
                [
                    {
                        "file": "src/new_module.py",
                        "reason": "Planned source file",
                        "type": "planned-file",
                    }
                ],
                service.entries(task_dir, "implement"),
            )

    def test_add_missing_path_without_planned_type_still_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._prepare_root(root)

            with self.assertRaises(self.TaskContextError) as raised:
                self.TaskContextService(root).add(
                    task_dir,
                    "implement",
                    "src/typo.py",
                    "Must not be inferred",
                )

            self.assertEqual("TASK-CONTEXT-PATH-001", raised.exception.code)

    def test_planned_file_rejects_unsafe_or_non_file_paths(self) -> None:
        invalid_paths = (
            "../outside.py",
            "C:/outside.py",
            "//server/share.py",
            "src/*.py",
            "src/new_module.py/",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._prepare_root(root)
            service = self.TaskContextService(root)

            for invalid_path in invalid_paths:
                with self.subTest(path=invalid_path):
                    with self.assertRaises(self.TaskContextError) as raised:
                        service.add(
                            task_dir,
                            "implement",
                            invalid_path,
                            "Unsafe planned path",
                            entry_type="planned-file",
                        )
                    self.assertEqual("TASK-CONTEXT-PATH-002", raised.exception.code)

    def test_validate_accepts_missing_planned_file_and_rejects_unknown_type(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._prepare_root(root)
            existing = root / "existing.py"
            existing.write_text("VALUE = 1\n", encoding="utf-8")
            entries = [
                {
                    "file": "src/future.py",
                    "reason": "Planned source",
                    "type": "planned-file",
                },
                {
                    "file": "existing.py",
                    "reason": "Unknown type must fail",
                    "type": "mystery",
                },
            ]
            (task_dir / "implement.jsonl").write_text(
                "\n".join(json.dumps(entry, ensure_ascii=False) for entry in entries) + "\n",
                encoding="utf-8",
            )

            issues = self.TaskContextService(root).validate(task_dir)

            self.assertEqual(["invalid_entry_type"], [issue.code for issue in issues])
            self.assertEqual([2], [issue.line for issue in issues])

    def test_live_and_template_context_implementations_match(self) -> None:
        relative_files = (
            "application/task_context.py",
            "common/gates/validate_implementation.py",
            "commands/task_context_commands.py",
            "commands/task_parser.py",
        )

        for relative_file in relative_files:
            with self.subTest(file=relative_file):
                live = ROOT / ".cowork-flow" / "scripts" / relative_file
                template = ROOT / "template" / ".cowork-flow" / "scripts" / relative_file
                self.assertEqual(
                    live.read_text(encoding="utf-8"),
                    template.read_text(encoding="utf-8"),
                )


if __name__ == "__main__":
    unittest.main()
