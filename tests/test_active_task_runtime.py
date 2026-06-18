from __future__ import annotations

import importlib
import os
import sqlite3
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
        for module_name in (
            "common.active_task",
            "common.paths",
            "common.time_utils",
            "flow.store",
            "flow",
            "patterns.base",
            "patterns",
            "common",
        ):
            sys.modules.pop(module_name, None)

    def _runtime_session(self, root: Path, context_key: str) -> dict | None:
        db = sqlite3.connect(root / ".cowork-flow" / "cowork-flow.db")
        try:
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT * FROM runtime_session WHERE context_key = ?",
                (context_key,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            db.close()

    def _runtime_context(self, root: Path, runtime_context_id: str) -> dict | None:
        db = sqlite3.connect(root / ".cowork-flow" / "cowork-flow.db")
        try:
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT * FROM runtime_context WHERE id = ?",
                (runtime_context_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            db.close()

    def _upsert_runtime_context(self, root: Path, payload: dict) -> None:
        with self.active_task._store(root) as store:
            store.upsert_runtime_context(payload)

    def _upsert_runtime_session(self, root: Path, context_key: str, payload: dict) -> None:
        with self.active_task._store(root) as store:
            store.upsert_runtime_session(context_key, payload)

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

    def test_context_key_uses_claude_code_session_when_claude_missing(self) -> None:
        with patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": "code-123"}, clear=True):
            self.assertEqual("claude_code-123", self.active_task.resolve_context_key())

    def test_claude_session_env_precedes_claude_code_session_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "CLAUDE_SESSION_ID": "claude-123",
                "CLAUDE_CODE_SESSION_ID": "code-123",
            },
            clear=True,
        ):
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

    def test_context_key_can_use_opencode_session_id_input(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                "opencode_opc-789",
                self.active_task.resolve_context_key({"sessionID": "opc-789"}),
            )

    def test_context_key_can_use_claude_hook_input(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                "claude_claude-456",
                self.active_task.resolve_context_key({"claude_session_id": "claude-456"}),
            )

    def test_context_key_can_use_claude_code_hook_input(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                "claude_code-456",
                self.active_task.resolve_context_key({"claude_code_session_id": "code-456"}),
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
                session_file = root / ".cowork-flow" / ".runtime" / "sessions" / f"{active.context_key}.json"
                session_data = self._runtime_session(root, active.context_key)
                self.assertEqual(".cowork-flow/tasks/05-28-demo", active.task_path)
                self.assertFalse(session_file.exists())
                self.assertIsNotNone(session_data)
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
                self.assertIsNone(self._runtime_session(root, active.context_key))
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
                session_data = self._runtime_session(root, active.context_key)

            self.assertEqual("claude_main", active.context_key)
            self.assertIsNotNone(session_data)
            self.assertEqual("claude-code", session_data.get("platform"))

    def test_clear_task_from_sessions_removes_matching_db_sessions_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()
            self._upsert_runtime_session(
                root,
                "db_main",
                {
                    "scope": "main",
                    "active_task_path": ".cowork-flow/tasks/05-28-demo",
                    "platform": "codex",
                    "status": "active",
                },
            )
            self._upsert_runtime_session(
                root,
                "db_other",
                {
                    "scope": "main",
                    "active_task_path": ".cowork-flow/tasks/05-28-other",
                    "platform": "codex",
                    "status": "active",
                },
            )

            cleared = self.active_task.clear_task_from_sessions(
                root, ".cowork-flow/tasks/05-28-demo"
            )

            self.assertEqual(1, cleared)
            self.assertIsNone(self._runtime_session(root, "db_main"))
            self.assertIsNotNone(self._runtime_session(root, "db_other"))

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

    def test_read_runtime_context_uses_db_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._upsert_runtime_context(
                root,
                {
                    "runtime_context_id": "rtx_demo",
                    "scope": "subagent",
                    "host": "codex",
                    "adapter": "codex.spawn_agent",
                    "agent_type": "cowork-check",
                    "role": "check",
                    "dispatch_kind": "formal",
                    "status": "pending",
                },
            )

            first = self.active_task.read_runtime_context(root, "rtx_demo")
            second = self.active_task.read_runtime_context(root, "rtx_demo")

            self.assertEqual("pending", first["status"])
            self.assertEqual(first["runtime_context_id"], second["runtime_context_id"])
            db = sqlite3.connect(root / ".cowork-flow" / "cowork-flow.db")
            try:
                count = db.execute("SELECT COUNT(*) FROM runtime_context WHERE id = 'rtx_demo'").fetchone()[0]
            finally:
                db.close()
            self.assertEqual(1, count)

    def test_bind_runtime_context_writes_host_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._upsert_runtime_context(
                root,
                {
                    "runtime_context_id": "rtx_demo",
                    "scope": "subagent",
                    "host": "codex",
                    "task_dir": ".cowork-flow/tasks/05-28-demo",
                    "status": "pending",
                    "bound_context_key": None,
                },
            )

            bound = self.active_task.bind_runtime_context(
                root,
                "rtx_demo",
                "codex_child",
            )

            self.assertIsNotNone(bound)
            session_file = root / ".cowork-flow" / ".runtime" / "sessions" / "codex_child.json"
            context_file = root / ".cowork-flow" / ".runtime" / "subagents" / "rtx_demo.json"
            session = self._runtime_session(root, "codex_child")
            self.assertFalse(session_file.exists())
            self.assertFalse(context_file.exists())
            self.assertIsNotNone(session)
            self.assertEqual("subagent", session["scope"])
            self.assertEqual("rtx_demo", session["runtime_context_id"])
            self.assertEqual(".cowork-flow/tasks/05-28-demo", session["active_task_path"])
            context = self._runtime_context(root, "rtx_demo")
            self.assertIsNotNone(context)
            self.assertEqual("bound", context["status"])
            self.assertEqual("codex_child", context["bound_context_key"])

    def test_bind_runtime_context_prefers_prompt_host_context_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._upsert_runtime_context(
                root,
                {
                    "runtime_context_id": "rtx_demo",
                    "scope": "subagent",
                    "host": "codex",
                    "task_dir": ".cowork-flow/tasks/05-28-demo",
                    "status": "pending",
                    "bound_context_key": None,
                },
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
            self.assertIsNotNone(self._runtime_session(root, "codex_prompt_key"))
            self.assertFalse((root / ".cowork-flow" / ".runtime" / "sessions" / "codex_child-session.json").exists())
            context = self._runtime_context(root, "rtx_demo")
            self.assertIsNotNone(context)
            self.assertEqual("codex_prompt_key", context["bound_context_key"])

    def test_close_runtime_context_removes_bound_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._upsert_runtime_context(
                root,
                {
                    "runtime_context_id": "rtx_demo",
                    "scope": "subagent",
                    "host": "codex",
                    "task_dir": ".cowork-flow/tasks/05-28-demo",
                    "status": "bound",
                    "bound_context_key": "codex_child",
                },
            )
            self._upsert_runtime_session(
                root,
                "codex_child",
                {
                    "scope": "subagent",
                    "runtime_context_id": "rtx_demo",
                    "active_task_path": ".cowork-flow/tasks/05-28-demo",
                    "platform": "codex",
                    "status": "bound",
                },
            )
            self._upsert_runtime_session(
                root,
                "subagent_rtx_demo",
                {
                    "scope": "subagent",
                    "runtime_context_id": "rtx_demo",
                    "active_task_path": ".cowork-flow/tasks/05-28-demo",
                    "platform": "codex",
                    "status": "pending_bind",
                },
            )

            closed = self.active_task.close_runtime_context(root, "rtx_demo")

            self.assertTrue(closed)
            context = self._runtime_context(root, "rtx_demo")
            self.assertIsNotNone(context)
            self.assertEqual("closed", context["status"])
            self.assertIsNone(self._runtime_session(root, "codex_child"))
            self.assertIsNone(self._runtime_session(root, "subagent_rtx_demo"))
