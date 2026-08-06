from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "template" / ".cowork-flow" / "scripts"


class ContextPathPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        module = importlib.import_module("services.context_paths")
        self.normalize_context_path = module.normalize_context_path
        self.normalize_context_file_scope_entry = module.normalize_context_file_scope_entry
        self.TaskContextError = module.TaskContextError

    def _cleanup_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in (
            "services.context_paths",
            "infra.paths",
        ):
            sys.modules.pop(module_name, None)

    def test_normalize_rejects_unsafe_paths_and_bad_entry_types(self) -> None:
        bad_paths = (
            "/absolute.py",
            "C:/absolute.py",
            "../outside.py",
            "src//double.py",
            "src/*.py",
            "src/planned.py/",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for bad_path in bad_paths:
                with self.subTest(path=bad_path):
                    with self.assertRaises(self.TaskContextError) as raised:
                        self.normalize_context_path(root, bad_path, "planned-file")
                    self.assertEqual("TASK-CONTEXT-PATH-002", raised.exception.code)

            with self.assertRaises(self.TaskContextError) as raised:
                self.normalize_context_path(root, "src/file.py", "mystery")
            self.assertEqual("TASK-CONTEXT-TYPE-001", raised.exception.code)

    def test_normalize_preserves_canonical_repo_relative_forms(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "docs").mkdir()

            planned, planned_path = self.normalize_context_path(
                root,
                r".\src\future.py",
                "planned-file",
            )
            directory, directory_path = self.normalize_context_path(
                root,
                "./docs/",
                "directory",
            )

            self.assertEqual("src/future.py", planned)
            self.assertEqual(root / "src" / "future.py", planned_path)
            self.assertEqual("docs/", directory)
            self.assertEqual(root / "docs", directory_path)

    def test_file_scope_reuses_path_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "src").mkdir()

            normalized, error = self.normalize_context_file_scope_entry(
                root,
                {"file": r"src\future.py", "type": "planned-file"},
            )
            directory, directory_error = self.normalize_context_file_scope_entry(
                root,
                {"file": "src/", "type": "directory"},
            )
            unsafe, unsafe_error = self.normalize_context_file_scope_entry(
                root,
                {"file": "../outside.py"},
            )

            self.assertEqual("src/future.py", normalized)
            self.assertIsNone(error)
            self.assertIsNone(directory)
            self.assertIsNone(directory_error)
            self.assertIsNone(unsafe)
            self.assertEqual("non-canonical path '../outside.py'", unsafe_error)


if __name__ == "__main__":
    unittest.main()
