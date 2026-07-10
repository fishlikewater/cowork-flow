from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = (
    Path(__file__).resolve().parents[1]
    / "template"
    / ".cowork-flow"
    / "scripts"
)
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


class StateStoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        state_module = importlib.import_module(
            "common.storage.state_store"
        )
        operation_module = importlib.import_module(
            "common.storage.operation_log"
        )
        unit_module = importlib.import_module(
            "common.storage.unit_of_work"
        )
        cls.StateStore = state_module.StateStore
        cls.StateStoreError = state_module.StateStoreError
        cls.OperationLog = operation_module.OperationLog
        cls.UnitOfWork = unit_module.UnitOfWork

    def test_replace_rejects_stale_revision_and_preserves_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.json"
            store = self.StateStore()

            first = store.replace(
                path,
                {"value": "初始"},
                expected_revision=0,
                operation_id="op-1",
            )
            second = store.replace(
                path,
                {"value": "更新"},
                expected_revision=first.revision,
                operation_id="op-2",
            )

            with self.assertRaises(self.StateStoreError) as captured:
                store.replace(
                    path,
                    {"value": "陈旧"},
                    expected_revision=first.revision,
                    operation_id="op-stale",
                )

            persisted = store.load(path)
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual("STATE-CONFLICT-001", captured.exception.code)
            self.assertEqual(2, second.revision)
            self.assertEqual("更新", persisted.data["value"])
            self.assertEqual(2, raw["_state"]["revision"])

    def test_corrupt_json_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.json"
            path.write_text("{not-json", encoding="utf-8")

            with self.assertRaises(self.StateStoreError) as captured:
                self.StateStore().load(path)

            self.assertEqual("STATE-LOAD-002", captured.exception.code)
            self.assertEqual(
                "{not-json",
                path.read_text(encoding="utf-8"),
            )

    def test_unit_of_work_recovers_after_partial_apply(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first_path = root / "first.json"
            second_path = root / "second.json"
            store = self.StateStore()
            store.replace(
                first_path,
                {"value": "first-before"},
                expected_revision=0,
                operation_id="seed-first",
            )
            store.replace(
                second_path,
                {"value": "second-before"},
                expected_revision=0,
                operation_id="seed-second",
            )

            def interrupt_after_first(index: int, _mutation: object) -> None:
                if index == 0:
                    raise RuntimeError("simulated crash")

            unit = self.UnitOfWork(
                root,
                operation_id="op-recover",
                kind="test",
                fault_injector=interrupt_after_first,
            )
            unit.replace(first_path, {"value": "first-after"})
            unit.replace(second_path, {"value": "second-after"})

            with self.assertRaises(RuntimeError):
                unit.commit()

            recovered = self.UnitOfWork.recover_all(root)
            operation = self.OperationLog(root).load("op-recover")
            self.assertEqual(("op-recover",), recovered)
            self.assertEqual(
                "first-after",
                store.load(first_path).data["value"],
            )
            self.assertEqual(
                "second-after",
                store.load(second_path).data["value"],
            )
            self.assertEqual("committed", operation["phase"])


if __name__ == "__main__":
    unittest.main()
