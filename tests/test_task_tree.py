from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"


class TaskTreeServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        tree_module = importlib.import_module("services.task_tree")
        self.TaskTreeError = tree_module.TaskTreeError
        self.TaskTreeService = tree_module.TaskTreeService

    def _cleanup_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in (
            "services.task_tree",
            "application",
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

    def test_link_and_unlink_keep_both_sides_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tasks_dir = root / ".cowork-flow" / "tasks"
            tasks_dir.mkdir(parents=True)
            parent = self._write_task(
                tasks_dir,
                "07-10-parent",
                {"status": "in_progress", "children": [], "custom": "parent"},
            )
            child = self._write_task(
                tasks_dir,
                "07-10-child",
                {"status": "planning", "parent": None, "custom": "child"},
            )
            service = self.TaskTreeService(root)

            service.link(parent, child)
            self.assertEqual(["07-10-child"], self._read_task(parent)["children"])
            self.assertEqual("07-10-parent", self._read_task(child)["parent"])

            service.unlink(parent, child)
            self.assertEqual([], self._read_task(parent)["children"])
            self.assertIsNone(self._read_task(child)["parent"])
            self.assertEqual("parent", self._read_task(parent)["custom"])
            self.assertEqual("child", self._read_task(child)["custom"])

    def test_link_rejects_child_with_existing_parent_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tasks_dir = root / ".cowork-flow" / "tasks"
            tasks_dir.mkdir(parents=True)
            parent = self._write_task(
                tasks_dir,
                "07-10-parent",
                {"status": "in_progress", "children": []},
            )
            child = self._write_task(
                tasks_dir,
                "07-10-child",
                {"status": "planning", "parent": "07-10-other"},
            )
            service = self.TaskTreeService(root)

            with self.assertRaises(self.TaskTreeError) as raised:
                service.link(parent, child)

            self.assertEqual("TASK-TREE-PARENT-001", raised.exception.code)
            self.assertEqual([], self._read_task(parent)["children"])
            self.assertEqual("07-10-other", self._read_task(child)["parent"])

    def test_active_nodes_expose_hierarchy_and_progress(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tasks_dir = root / ".cowork-flow" / "tasks"
            tasks_dir.mkdir(parents=True)
            self._write_task(
                tasks_dir,
                "07-10-parent",
                {
                    "status": "in_progress",
                    "children": ["07-10-done", "07-10-open"],
                    "parent": None,
                },
            )
            self._write_task(
                tasks_dir,
                "07-10-done",
                {"status": "completed", "parent": "07-10-parent"},
            )
            self._write_task(
                tasks_dir,
                "07-10-open",
                {"status": "planning", "parent": "07-10-parent"},
            )
            service = self.TaskTreeService(root)

            nodes = service.active_nodes()

            self.assertEqual(("07-10-parent",), service.root_names(nodes))
            self.assertEqual(
                (1, 2),
                service.children_progress(
                    nodes["07-10-parent"].children,
                    nodes,
                ),
            )


if __name__ == "__main__":
    unittest.main()
