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
        context_module = importlib.import_module("services.task_context")
        self.TaskContextService = context_module.TaskContextService
        self.TaskContextError = context_module.TaskContextError
        self.get_check_context = context_module.get_check_context

    def _cleanup_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in (
            "services.task_context",
            "application",
            "infra.files",
            "infra.quality_sources",
            "infra.paths",
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

    def test_validate_accepts_deleted_file_context_for_missing_or_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._prepare_root(root)
            existing = root / "obsolete.py"
            existing.write_text("VALUE = 1\n", encoding="utf-8")
            entries = [
                {
                    "file": "obsolete.py",
                    "reason": "Delete obsolete file",
                    "type": "deleted-file",
                },
                {
                    "file": "src/already_deleted.py",
                    "reason": "Already deleted in working tree",
                    "type": "deleted-file",
                },
            ]
            (task_dir / "implement.jsonl").write_text(
                "\n".join(json.dumps(entry, ensure_ascii=False) for entry in entries) + "\n",
                encoding="utf-8",
            )

            issues = self.TaskContextService(root).validate(task_dir)

            self.assertEqual([], list(issues))

    def test_deleted_file_context_rejects_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._prepare_root(root)
            (root / "src").mkdir(exist_ok=True)
            (task_dir / "implement.jsonl").write_text(
                json.dumps(
                    {
                        "file": "src",
                        "reason": "Directory is not a deleted file",
                        "type": "deleted-file",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            issues = self.TaskContextService(root).validate(task_dir)

            self.assertEqual(["invalid_path"], [issue.code for issue in issues])
            self.assertIn("Deleted file is a directory", issues[0].message)

    def test_missing_file_issue_reports_fact_without_cli_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._prepare_root(root)
            (task_dir / "implement.jsonl").write_text(
                json.dumps(
                    {"file": "src/future.py", "reason": "Planned source"},
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            issues = self.TaskContextService(root).validate(task_dir)

            self.assertEqual(["file_not_found"], [issue.code for issue in issues])
            self.assertEqual("File not found: src/future.py", issues[0].message)

    def test_initialize_creates_task_local_placeholder_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._prepare_root(root)
            report = task_dir / "workflow-smoke-audit.md"
            source = root / "src" / "future.py"
            (task_dir / "implement.jsonl").write_text(
                json.dumps(
                    {
                        "file": ".cowork-flow/tasks/07-10-demo/workflow-smoke-audit.md",
                        "reason": "Task-local report",
                    },
                    ensure_ascii=False,
                )
                + "\n"
                + json.dumps(
                    {
                        "file": "src/future.py",
                        "reason": "Normal missing source must remain missing",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            result = self.TaskContextService(root).initialize(task_dir, "backend")

            self.assertEqual(("check.jsonl", "debug.jsonl"), result.created)
            self.assertTrue(report.is_file())
            self.assertEqual("", report.read_text(encoding="utf-8"))
            self.assertFalse(source.exists())

    def test_start_placeholder_helper_reports_created_paths_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._prepare_root(root)
            report = task_dir / "notes" / "audit.md"
            (task_dir / "implement.jsonl").write_text(
                json.dumps(
                    {
                        "file": ".cowork-flow/tasks/07-10-demo/notes/audit.md",
                        "reason": "Task-local nested report",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            service = self.TaskContextService(root)

            first = service.ensure_task_artifact_placeholders(task_dir)
            second = service.ensure_task_artifact_placeholders(task_dir)

            self.assertEqual((".cowork-flow/tasks/07-10-demo/notes/audit.md",), first)
            self.assertEqual((), second)
            self.assertTrue(report.is_file())

    def test_start_blockers_do_not_require_review_or_debug_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._prepare_root(root)
            (task_dir / "task.json").write_text(
                '{"status": "planning"}\n',
                encoding="utf-8",
            )
            (task_dir / "decision-anchor.md").write_text(
                "## 目标\n\nDemo\n",
                encoding="utf-8",
            )
            (task_dir / "implement.jsonl").write_text(
                '{"file": "AGENTS.md", "reason": "Demo"}\n',
                encoding="utf-8",
            )

            blockers = self.TaskContextService(root).start_blockers(task_dir)

            self.assertEqual((), blockers)

    def test_initialize_does_not_create_task_local_review_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._prepare_root(root)
            service = self.TaskContextService(root)

            service.initialize(task_dir, "backend")

            entries = service.entries(task_dir, "implement")
            files = {entry.get("file") for entry in entries}
            self.assertFalse(
                any(
                    str(file or "").startswith(
                        ".cowork-flow/tasks/07-10-demo/"
                    )
                    for file in files
                )
            )
            self.assertEqual(
                {"implement.jsonl", "check.jsonl", "debug.jsonl"},
                {path.name for path in task_dir.iterdir() if path.is_file()},
            )

    def test_check_context_uses_quality_sources_from_domain_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._prepare_root(root)
            del task_dir
            backend_dir = root / ".cowork-flow" / "spec" / "backend"
            references_dir = root / ".cowork-flow" / "spec" / "references"
            references_dir.mkdir(parents=True)
            (backend_dir / "index.md").write_text(
                "# Backend\n\n"
                "| 文档 | 用途 |\n"
                "|---|---|\n"
                "| [目录结构](./directory-structure.md) | structure |\n"
                "| [质量规范](./quality-guidelines.md) | quality |\n",
                encoding="utf-8",
            )
            (backend_dir / "directory-structure.md").write_text("# Structure\n", encoding="utf-8")
            (backend_dir / "quality-guidelines.md").write_text("# Quality\n", encoding="utf-8")
            (backend_dir / "unlinked.md").write_text("# Should not load\n", encoding="utf-8")
            (references_dir / "definition-of-done.md").write_text("# DoD\n", encoding="utf-8")
            (references_dir / "testing-checklist.md").write_text("# Testing\n", encoding="utf-8")

            files = {entry["file"] for entry in self.get_check_context(root, "backend")}
            expected = {
                ".cowork-flow/spec/backend/index.md",
                ".cowork-flow/spec/backend/directory-structure.md",
                ".cowork-flow/spec/backend/quality-guidelines.md",
                ".cowork-flow/spec/references/definition-of-done.md",
                ".cowork-flow/spec/references/testing-checklist.md",
            }
            forbidden = {
                ".cowork-flow/spec/backend/unlinked.md",
                ".cowork-flow/spec/",
            }

            self.assertEqual(expected, files & expected)
            self.assertEqual(set(), files & forbidden)

    def test_check_context_skill_order_is_manifest_agnostic_and_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_dir = root / ".agents" / "skills" / "aaa-check"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("# AAA Check\n", encoding="utf-8")
            (skill_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "skill": "aaa-check",
                        "context": [
                            {
                                "contexts": ["check"],
                                "devTypes": ["backend"],
                                "reason": "Dynamic check Skill",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            entries = self.get_check_context(root, "backend")

        skill_files = [
            entry["file"]
            for entry in entries
            if "/skills/" in entry["file"]
        ]
        self.assertIn(".agents/skills/aaa-check/SKILL.md", skill_files)
        self.assertEqual(sorted(skill_files), skill_files)

    def test_quality_sources_include_security_reference_for_sensitive_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            references_dir = root / ".cowork-flow" / "spec" / "references"
            references_dir.mkdir(parents=True)
            (references_dir / "definition-of-done.md").write_text("# DoD\n", encoding="utf-8")
            (references_dir / "testing-checklist.md").write_text("# Testing\n", encoding="utf-8")
            (references_dir / "security-checklist.md").write_text("# Security\n", encoding="utf-8")
            quality_sources = importlib.import_module("infra.quality_sources")

            entries = quality_sources.quality_source_entries(
                root,
                "backend",
                paths=("src/auth/session.py",),
            )

            expected = {".cowork-flow/spec/references/security-checklist.md"}
            self.assertEqual(
                expected,
                {entry["file"] for entry in entries} & expected,
            )

    def test_live_and_template_context_implementations_match_when_present(self) -> None:
        relative_files = (
            "services/task_context.py",
            "services/lifecycle_checks.py",
            "adapters/cli/task_context_commands.py",
            "adapters/cli/task_parser.py",
        )
        present_files = [
            relative_file
            for relative_file in relative_files
            if (ROOT / ".cowork-flow" / "scripts" / relative_file).is_file()
        ]
        if not present_files:
            self.skipTest("local live runtime files are absent")

        for relative_file in present_files:
            with self.subTest(file=relative_file):
                live = ROOT / ".cowork-flow" / "scripts" / relative_file
                template = ROOT / "template" / ".cowork-flow" / "scripts" / relative_file
                self.assertEqual(
                    live.read_text(encoding="utf-8"),
                    template.read_text(encoding="utf-8"),
                )


if __name__ == "__main__":
    unittest.main()
