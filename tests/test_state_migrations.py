from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
FIXTURES = ROOT / "tests" / "fixtures" / "migrations"


class StateMigrationTest(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        self.active_task = importlib.import_module("kernel.session_state")
        runtime_module = importlib.import_module(
            "services.runtime_context"
        )
        repository_module = importlib.import_module(
            "kernel.task_repository"
        )
        self.RuntimeContextService = runtime_module.RuntimeContextService
        self.TaskRepository = repository_module.TaskRepository

    def _cleanup_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in tuple(sys.modules):
            if module_name in {"services", "kernel", "adapters"} or module_name.startswith(
                ("services.", "kernel.", "adapters.")
            ):
                sys.modules.pop(module_name, None)

    @staticmethod
    def _fixture(name: str) -> dict:
        return json.loads(
            (FIXTURES / name).read_text(encoding="utf-8")
        )

    def test_historical_unscoped_host_session_remains_main_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            session_path = (
                root
                / ".cowork-flow"
                / ".runtime"
                / "sessions"
                / "main.json"
            )
            session_path.parent.mkdir(parents=True)
            session_path.write_text(
                json.dumps(
                    self._fixture("historical-main-session-v1.json"),
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {"COWORK_FLOW_CONTEXT_ID": "main"},
                clear=True,
            ):
                self.assertEqual(
                    ".cowork-flow/tasks/historical-task",
                    self.active_task.get_active_task(root).task_path,
                )
                self.assertTrue(self.active_task.is_main_session(root))

    def test_historical_runtime_context_binds_without_losing_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime_path = (
                root
                / ".cowork-flow"
                / ".runtime"
                / "subagents"
                / "rtx_historical.json"
            )
            runtime_path.parent.mkdir(parents=True)
            runtime_path.write_text(
                json.dumps(
                    self._fixture("historical-runtime-context-v1.json"),
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            result = self.RuntimeContextService(root).bind(
                "rtx_historical",
                "codex_historical-host",
            )

            self.assertEqual("bound", result["status"])
            self.assertEqual("历史运行时上下文", result["persisted_note"])
            host_session = json.loads(
                (
                    root
                    / ".cowork-flow"
                    / ".runtime"
                    / "sessions"
                    / "codex_historical-host.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(2, host_session["schema_version"])
            self.assertEqual("subagent", host_session["scope"])

    def test_historical_task_save_preserves_unknown_fields_and_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "historical-task"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                json.dumps(
                    self._fixture("historical-task-v1.json"),
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            saved = self.TaskRepository(root).save(
                task_dir,
                {"status": "review"},
            )

            self.assertEqual("review", saved["status"])
            self.assertEqual("历史任务", saved["title"])
            self.assertEqual("必须保留", saved["unknown_persisted_field"])


if __name__ == "__main__":
    unittest.main()
