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


class ActiveTaskRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        self.active_task = importlib.import_module("common.active_task")

    def _cleanup_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in ("common.active_task", "common.paths", "common"):
            sys.modules.pop(module_name, None)

    def test_context_key_uses_cowork_env_first(self) -> None:
        with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main window"}, clear=True):
            self.assertEqual("main_window", self.active_task.resolve_context_key())

    def test_context_key_uses_codex_session_when_cowork_missing(self) -> None:
        with patch.dict(os.environ, {"CODEX_SESSION_ID": "abc-123"}, clear=True):
            self.assertEqual("codex_abc-123", self.active_task.resolve_context_key())

    def test_context_key_missing_returns_none(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(self.active_task.resolve_context_key())

    def test_context_key_can_use_codex_hook_input(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                "codex_thread-123",
                self.active_task.resolve_context_key({"thread_id": "thread-123"}),
            )

    def test_set_and_get_active_task_require_context_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()
            task_dir = root / ".cowork-flow" / "tasks" / "05-28-demo"
            task_dir.mkdir(parents=True)

            with patch.dict(os.environ, {}, clear=True):
                self.assertIsNone(
                    self.active_task.set_active_task(root, ".cowork-flow/tasks/05-28-demo")
                )
                self.assertIsNone(self.active_task.get_active_task(root).task_path)

    def test_set_get_and_clear_active_task_for_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()
            task_dir = root / ".cowork-flow" / "tasks" / "05-28-demo"
            task_dir.mkdir(parents=True)

            with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}, clear=True):
                active = self.active_task.set_active_task(
                    root, ".cowork-flow/tasks/05-28-demo"
                )
                session_file = (
                    self.active_task.sessions_dir(root) / f"{active.context_key}.json"
                )
                session_data = json.loads(session_file.read_text(encoding="utf-8"))
                self.assertEqual(".cowork-flow/tasks/05-28-demo", active.task_path)
                self.assertEqual(
                    ".cowork-flow/tasks/05-28-demo",
                    session_data.get("active_task_path"),
                )
                self.assertNotIn("current_task", session_data)
                self.assertEqual(
                    ".cowork-flow/tasks/05-28-demo",
                    self.active_task.get_active_task(root).task_path,
                )
                self.active_task.clear_active_task(root)
                self.assertIsNone(self.active_task.get_active_task(root).task_path)

    def test_clear_task_from_sessions_removes_matching_pointers_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sessions = self.active_task.sessions_dir(root)
            sessions.mkdir(parents=True)
            (sessions / "main.json").write_text(
                '{"active_task_path": ".cowork-flow/tasks/05-28-demo"}\n',
                encoding="utf-8",
            )
            (sessions / "other.json").write_text(
                '{"active_task_path": ".cowork-flow/tasks/05-28-other"}\n',
                encoding="utf-8",
            )

            cleared = self.active_task.clear_task_from_sessions(
                root, ".cowork-flow/tasks/05-28-demo"
            )

            self.assertEqual(1, cleared)
            self.assertFalse((sessions / "main.json").exists())
            self.assertTrue((sessions / "other.json").exists())
