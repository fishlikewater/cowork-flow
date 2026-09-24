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
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
            self.addCleanup(sys.path.remove, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        tree_module = importlib.import_module("services.task_tree")
        self.TaskTreeError = tree_module.TaskTreeError
        self.TaskTreeService = tree_module.TaskTreeService

    def _cleanup_imports(self) -> None:
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

    def test_link_rejects_a_cycle_without_mutating_relationships(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tasks_dir = root / ".cowork-flow" / "tasks"
            tasks_dir.mkdir(parents=True)
            first = self._write_task(
                tasks_dir,
                "07-10-a",
                {"status": "in_progress", "children": [], "parent": None},
            )
            second = self._write_task(
                tasks_dir,
                "07-10-b",
                {"status": "planning", "children": [], "parent": None},
            )
            third = self._write_task(
                tasks_dir,
                "07-10-c",
                {"status": "planning", "children": [], "parent": None},
            )
            service = self.TaskTreeService(root)
            service.link(first, second)
            service.link(second, third)

            with self.assertRaises(self.TaskTreeError) as raised:
                service.link(third, first)

            self.assertEqual("TASK-TREE-CYCLE-001", raised.exception.code)
            self.assertEqual("07-10-b", self._read_task(first)["children"][0])
            self.assertEqual("07-10-a", self._read_task(second)["parent"])
            self.assertEqual("07-10-b", self._read_task(third)["parent"])

    def test_link_conflict_restores_parent_without_overwriting_concurrent_child(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tasks_dir = root / ".cowork-flow" / "tasks"
            tasks_dir.mkdir(parents=True)
            parent = self._write_task(
                tasks_dir,
                "07-10-parent",
                {"status": "in_progress", "children": [], "parent": None},
            )
            child = self._write_task(
                tasks_dir,
                "07-10-child",
                {"status": "planning", "children": [], "parent": None},
            )
            store_module = importlib.import_module("infra.storage.state_store")
            parent_json = parent / "task.json"
            child_json = child / "task.json"

            class ConflictingStore(store_module.StateStore):
                def __init__(self) -> None:
                    super().__init__()
                    self.injected = False

                def replace(self, path, data, *, expected_revision, operation_id):
                    result = super().replace(
                        path,
                        data,
                        expected_revision=expected_revision,
                        operation_id=operation_id,
                    )
                    if Path(path) == parent_json and not self.injected:
                        current = self.load(child_json)
                        super().replace(
                            child_json,
                            {**current.data, "concurrent": True},
                            expected_revision=current.revision,
                            operation_id="external-child-update",
                        )
                        self.injected = True
                    return result

            store = ConflictingStore()
            repository_module = importlib.import_module("services.task_repository")
            operation_module = importlib.import_module("infra.storage.operation_log")
            repository = repository_module.TaskRepository(
                root,
                state_store=store,
            )
            service = self.TaskTreeService(root, repository=repository)

            with self.assertRaises(self.TaskTreeError) as raised:
                service.link(parent, child)

            parent_data = self._read_task(parent)
            child_data = self._read_task(child)
            self.assertEqual("TASK-TREE-WRITE-001", raised.exception.code)
            self.assertEqual([], parent_data["children"])
            self.assertIsNone(child_data["parent"])
            self.assertTrue(child_data["concurrent"])
            operation_files = list(
                (root / ".cowork-flow" / ".runtime" / "operations").glob("*.json")
            )
            self.assertEqual(1, len(operation_files))
            operation = operation_module.OperationLog(root, state_store=store).load(
                operation_files[0].stem
            )
            self.assertEqual("conflicted", operation["phase"])

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
