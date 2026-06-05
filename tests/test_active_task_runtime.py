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

    def test_context_key_uses_opencode_session_when_cowork_missing(self) -> None:
        with patch.dict(os.environ, {"OPENCODE_SESSION_ID": "opc-123"}, clear=True):
            self.assertEqual("opencode_opc-123", self.active_task.resolve_context_key())

    def test_context_key_uses_claude_session_when_cowork_missing(self) -> None:
        with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "claude-123"}, clear=True):
            self.assertEqual("claude_claude-123", self.active_task.resolve_context_key())

    def test_context_key_missing_returns_none(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(self.active_task.resolve_context_key())

    def test_context_key_can_use_codex_hook_input(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                "codex_thread-123",
                self.active_task.resolve_context_key({"thread_id": "thread-123"}),
            )

    def test_context_key_can_use_opencode_hook_input(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                "opencode_opc-456",
                self.active_task.resolve_context_key({"opencode_session_id": "opc-456"}),
            )

    def test_context_key_can_use_claude_hook_input(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                "claude_claude-456",
                self.active_task.resolve_context_key({"claude_session_id": "claude-456"}),
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

    def test_set_active_task_marks_claude_platform(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()
            task_dir = root / ".cowork-flow" / "tasks" / "05-28-demo"
            task_dir.mkdir(parents=True)

            with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "main"}, clear=True):
                active = self.active_task.set_active_task(
                    root, ".cowork-flow/tasks/05-28-demo"
                )
                session_file = (
                    self.active_task.sessions_dir(root) / f"{active.context_key}.json"
                )
                session_data = json.loads(session_file.read_text(encoding="utf-8"))

            self.assertEqual("claude_main", active.context_key)
            self.assertEqual("claude-code", session_data.get("platform"))

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

    def test_runtime_context_id_can_be_resolved_from_prompt_input(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            runtime_id = self.active_task.resolve_runtime_context_id(
                {
                    "prompt": (
                        "cowork_runtime_context_id: rtx_20260604_demo\n"
                        "Task: inspect"
                    )
                }
            )

        self.assertEqual("rtx_20260604_demo", runtime_id)

    def test_bind_runtime_context_writes_host_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            context_dir = self.active_task.subagent_contexts_dir(root)
            context_dir.mkdir(parents=True)
            context_path = context_dir / "rtx_demo.json"
            context_path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "runtime_context_id": "rtx_demo",
                        "scope": "subagent",
                        "host": "codex",
                        "task_dir": ".cowork-flow/tasks/05-28-demo",
                        "status": "pending",
                        "bound_context_key": None,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            bound = self.active_task.bind_runtime_context(
                root,
                "rtx_demo",
                "codex_child",
            )

            self.assertIsNotNone(bound)
            session_file = self.active_task.sessions_dir(root) / "codex_child.json"
            session = json.loads(session_file.read_text(encoding="utf-8"))
            self.assertEqual("subagent", session["scope"])
            self.assertEqual("rtx_demo", session["runtime_context_id"])
            self.assertEqual(".cowork-flow/tasks/05-28-demo", session["active_task_path"])
            context = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertEqual("bound", context["status"])
            self.assertEqual("codex_child", context["bound_context_key"])

    def test_bind_runtime_context_prefers_prompt_host_context_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            context_dir = self.active_task.subagent_contexts_dir(root)
            context_dir.mkdir(parents=True)
            context_path = context_dir / "rtx_demo.json"
            context_path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "runtime_context_id": "rtx_demo",
                        "scope": "subagent",
                        "host": "codex",
                        "task_dir": ".cowork-flow/tasks/05-28-demo",
                        "status": "pending",
                        "bound_context_key": None,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            bound = self.active_task.bind_runtime_context(
                root,
                "rtx_demo",
                values={
                    "session_id": "child-session",
                    "prompt": (
                        "cowork_runtime_context_id: rtx_demo\n"
                        "cowork_host_context_key: codex_prompt_key"
                    ),
                },
            )

            self.assertIsNotNone(bound)
            self.assertTrue((self.active_task.sessions_dir(root) / "codex_prompt_key.json").is_file())
            self.assertFalse((self.active_task.sessions_dir(root) / "codex_child-session.json").exists())
            context = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertEqual("codex_prompt_key", context["bound_context_key"])

    def test_close_runtime_context_removes_bound_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            context_dir = self.active_task.subagent_contexts_dir(root)
            context_dir.mkdir(parents=True)
            sessions = self.active_task.sessions_dir(root)
            sessions.mkdir(parents=True)
            (context_dir / "rtx_demo.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "runtime_context_id": "rtx_demo",
                        "scope": "subagent",
                        "host": "codex",
                        "task_dir": ".cowork-flow/tasks/05-28-demo",
                        "status": "bound",
                        "bound_context_key": "codex_child",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (sessions / "codex_child.json").write_text("{}\n", encoding="utf-8")
            (sessions / "subagent_rtx_demo.json").write_text("{}\n", encoding="utf-8")

            closed = self.active_task.close_runtime_context(root, "rtx_demo")

            self.assertTrue(closed)
            self.assertFalse((sessions / "codex_child.json").exists())
            self.assertFalse((sessions / "subagent_rtx_demo.json").exists())
            context = json.loads((context_dir / "rtx_demo.json").read_text(encoding="utf-8"))
            self.assertEqual("closed", context["status"])
