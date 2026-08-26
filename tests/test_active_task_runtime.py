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
        self.active_task = importlib.import_module("runtime.session_state")
        self.runtime_context = importlib.import_module("services.workflow_runtime")

    def _cleanup_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in (
            "runtime.session_state",
            "infra.paths",
            "services.workflow_runtime",
        ):
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

    def test_context_key_uses_zcode_session_when_cowork_missing(self) -> None:
        with patch.dict(os.environ, {"ZCODE_SESSION_ID": "zc-123"}, clear=True):
            self.assertEqual("zcode_zc-123", self.active_task.resolve_context_key())

    def test_context_key_uses_zcode_process_label_when_session_missing(self) -> None:
        with patch.dict(os.environ, {"ZCODE_PROCESS_LABEL": "local-1"}, clear=True):
            self.assertEqual("zcode_local-1", self.active_task.resolve_context_key())

    def test_provenance_marks_process_fallback(self) -> None:
        with patch.dict(os.environ, {"ZCODE_PROCESS_LABEL": "local-1"}, clear=True):
            key, provenance = (
                self.active_task.resolve_context_key_with_provenance()
            )
        self.assertEqual("zcode_local-1", key)
        self.assertEqual(
            self.active_task.PROVENANCE_PROCESS_FALLBACK,
            provenance,
        )

    def test_provenance_marks_explicit_env(self) -> None:
        with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}, clear=True):
            key, provenance = (
                self.active_task.resolve_context_key_with_provenance()
            )
        self.assertEqual("main", key)
        self.assertEqual(self.active_task.PROVENANCE_EXPLICIT, provenance)

    def test_provenance_marks_host_session_env_over_input(self) -> None:
        with patch.dict(os.environ, {"DSH_SESSION_ID": "session-123"}, clear=True):
            _, provenance = self.active_task.resolve_context_key_with_provenance(
                {"session_id": "sess-input"}
            )
        self.assertEqual(self.active_task.PROVENANCE_HOST_SESSION, provenance)

    def test_provenance_missing_when_no_identity(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            key, provenance = (
                self.active_task.resolve_context_key_with_provenance(
                    {"unrelated": "value"}
                )
            )
        self.assertIsNone(key)
        self.assertEqual(self.active_task.PROVENANCE_MISSING, provenance)

    def test_get_active_task_reports_fallback_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()
            task_dir = root / ".cowork-flow" / "tasks" / "05-28-demo"
            task_dir.mkdir(parents=True)

            with patch.dict(os.environ, {"ZCODE_PROCESS_LABEL": "local-1"}, clear=True):
                self.active_task.set_active_task(
                    root, ".cowork-flow/tasks/05-28-demo"
                )
                active = self.active_task.get_active_task(root)

        self.assertEqual(".cowork-flow/tasks/05-28-demo", active.task_path)
        self.assertEqual(
            self.active_task.PROVENANCE_PROCESS_FALLBACK,
            active.provenance,
        )

    def test_set_active_task_writes_identity_provenance_only_for_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()
            task_dir = root / ".cowork-flow" / "tasks" / "05-28-demo"
            task_dir.mkdir(parents=True)

            with patch.dict(os.environ, {"ZCODE_PROCESS_LABEL": "local-1"}, clear=True):
                fallback = self.active_task.set_active_task(
                    root, ".cowork-flow/tasks/05-28-demo"
                )
                assert fallback is not None
                session_file = (
                    self.active_task.sessions_dir(root)
                    / f"{fallback.context_key}.json"
                )
                session_data = json.loads(
                    session_file.read_text(encoding="utf-8")
                )
                self.assertEqual(
                    "process_fallback",
                    session_data.get("identity_provenance"),
                )

            with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}, clear=True):
                trusted = self.active_task.set_active_task(
                    root, ".cowork-flow/tasks/05-28-demo"
                )
                assert trusted is not None
                trusted_file = (
                    self.active_task.sessions_dir(root)
                    / f"{trusted.context_key}.json"
                )
                trusted_data = json.loads(
                    trusted_file.read_text(encoding="utf-8")
                )
                self.assertNotIn("identity_provenance", trusted_data)

    def test_context_key_prefers_zcode_session_over_process_label(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ZCODE_PROCESS_LABEL": "local-1",
                "ZCODE_SESSION_ID": "sess-123",
            },
            clear=True,
        ):
            self.assertEqual("zcode_sess-123", self.active_task.resolve_context_key())

    def test_context_key_maps_zcode_hook_session_id_input(self) -> None:
        with patch.dict(os.environ, {"ZCODE_SESSION_ID": "sess-hook"}, clear=True):
            self.assertEqual(
                "zcode_sess-123",
                self.active_task._resolve_input_context_key(
                    {"session_id": "sess-123"}
                ),
            )

    def test_context_key_maps_zcode_hook_session_id_camel_input(self) -> None:
        with patch.dict(os.environ, {"ZCODE_SESSION_ID": "sess-hook"}, clear=True):
            self.assertEqual(
                "zcode_sess-456",
                self.active_task._resolve_input_context_key(
                    {"sessionId": "sess-456"}
                ),
            )

    def test_context_key_zcode_input_without_session_returns_none(self) -> None:
        with patch.dict(os.environ, {"ZCODE_SESSION_ID": "sess-hook"}, clear=True):
            self.assertIsNone(
                self.active_task._resolve_input_context_key(
                    {"thread_id": "thread-123"}
                )
            )

    def test_platform_from_context_key_maps_zcode(self) -> None:
        self.assertEqual(
            "zcode",
            self.active_task.platform_from_context_key("zcode_sess-123"),
        )
        self.assertEqual(
            "manual",
            self.active_task.platform_from_context_key("unknown_key"),
        )

    def test_platform_from_context_key_maps_dsh(self) -> None:
        self.assertEqual(
            "dsh",
            self.active_task.platform_from_context_key("dsh_rtx-1"),
        )
        self.assertEqual(
            "dsh",
            self.active_task.platform_from_context_key("dsh_main_session"),
        )

    def test_context_key_uses_dsh_session_when_cowork_missing(self) -> None:
        with patch.dict(os.environ, {"DSH_SESSION_ID": "session-123"}, clear=True):
            self.assertEqual("dsh_session-123", self.active_task.resolve_context_key())

    def test_cowork_env_precedes_dsh_session_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "COWORK_FLOW_CONTEXT_ID": "main window",
                "DSH_SESSION_ID": "session-123",
            },
            clear=True,
        ):
            self.assertEqual("main_window", self.active_task.resolve_context_key())

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

    def test_context_key_can_use_zcode_hook_input(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                "zcode_zc-456",
                self.active_task.resolve_context_key({"zcode_session_id": "zc-456"}),
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

            bound = self.runtime_context.bind_runtime_context(
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

    def test_bind_runtime_context_writes_dsh_host_session(self) -> None:
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
                        "host": "dsh",
                        "task_dir": ".cowork-flow/tasks/08-14-dsh-platform-label-fix",
                        "status": "pending",
                        "bound_context_key": None,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            bound = self.runtime_context.bind_runtime_context(
                root,
                "rtx_demo",
                "dsh_child",
            )

            self.assertIsNotNone(bound)
            session_file = self.active_task.sessions_dir(root) / "dsh_child.json"
            session = json.loads(session_file.read_text(encoding="utf-8"))
            self.assertEqual("subagent", session["scope"])
            self.assertEqual("rtx_demo", session["runtime_context_id"])
            self.assertEqual("dsh", session["platform"])
            self.assertEqual(
                ".cowork-flow/tasks/08-14-dsh-platform-label-fix",
                session["active_task_path"],
            )
            context = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertEqual("bound", context["status"])
            self.assertEqual("dsh_child", context["bound_context_key"])

    def test_bind_runtime_context_writes_zcode_host_session(self) -> None:
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
                        "host": "zcode",
                        "task_dir": ".cowork-flow/tasks/08-14-zcode-platform",
                        "status": "pending",
                        "bound_context_key": None,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            bound = self.runtime_context.bind_runtime_context(
                root,
                "rtx_demo",
                "zcode_child",
            )

            self.assertIsNotNone(bound)
            session_file = self.active_task.sessions_dir(root) / "zcode_child.json"
            session = json.loads(session_file.read_text(encoding="utf-8"))
            self.assertEqual("subagent", session["scope"])
            self.assertEqual("rtx_demo", session["runtime_context_id"])
            self.assertEqual("zcode", session["platform"])
            self.assertEqual(
                ".cowork-flow/tasks/08-14-zcode-platform",
                session["active_task_path"],
            )
            context = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertEqual("bound", context["status"])
            self.assertEqual("zcode_child", context["bound_context_key"])

    def test_platform_from_context_key_has_single_definition(self) -> None:
        session_state_source = (
            ROOT
            / "template"
            / ".cowork-flow"
            / "scripts"
            / "runtime"
            / "session_state.py"
        ).read_text(encoding="utf-8")
        workflow_runtime_source = (
            ROOT
            / "template"
            / ".cowork-flow"
            / "scripts"
            / "services"
            / "workflow_runtime.py"
        ).read_text(encoding="utf-8")

        definitions = (
            session_state_source + workflow_runtime_source
        ).count("def platform_from_context_key")
        self.assertEqual(1, definitions)
        self.assertNotIn(
            "def _platform_from_context_key",
            workflow_runtime_source,
        )

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

            bound = self.runtime_context.bind_runtime_context(
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

            closed = self.runtime_context.close_runtime_context(root, "rtx_demo")

            self.assertTrue(closed)
            self.assertFalse((sessions / "codex_child.json").exists())
            self.assertFalse((sessions / "subagent_rtx_demo.json").exists())
            context = json.loads((context_dir / "rtx_demo.json").read_text(encoding="utf-8"))
            self.assertEqual("closed", context["status"])

    def test_corrupt_session_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sessions = self.active_task.sessions_dir(root)
            sessions.mkdir(parents=True)
            session_path = sessions / "codex_main.json"
            session_path.write_text("{broken", encoding="utf-8")

            with patch.dict(os.environ, {"CODEX_SESSION_ID": "main"}, clear=True):
                active = self.active_task.get_active_task(root)

            self.assertIsNone(active.task_path)
            self.assertEqual("empty-session", active.source)
            self.assertTrue(session_path.exists())
            self.assertEqual("{broken", session_path.read_text(encoding="utf-8"))


class RuntimeContextTransactionTest(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        self.active_task = importlib.import_module("runtime.session_state")
        self.runtime_context = importlib.import_module(
            "services.workflow_runtime"
        )

    def _cleanup_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in (
            "services.workflow_runtime",
            "application",
            "runtime.session_state",
            "infra.storage.unit_of_work",
            "infra.storage.operation_log",
            "infra.storage.state_store",
            "infra.paths",
            "common",
        ):
            sys.modules.pop(module_name, None)

    @staticmethod
    def _fail_after_first(index, _mutation) -> None:
        if index == 0:
            raise RuntimeError("simulated crash")

    @staticmethod
    def _context() -> dict:
        return {
            "schema_version": 2,
            "runtime_context_id": "rtx_demo",
            "scope": "subagent",
            "host": "codex",
            "task_dir": ".cowork-flow/tasks/05-28-demo",
            "status": "pending",
            "bound_context_key": None,
        }

    def test_runtime_context_initialize_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = self.runtime_context.RuntimeContextService(root)

            first = service.initialize("rtx_demo", self._context())
            second = service.initialize("rtx_demo", self._context())

            self.assertEqual("subagent_rtx_demo", first.logical_context_key)
            self.assertEqual(first.logical_context_key, second.logical_context_key)
            self.assertEqual(first.context, second.context)
            self.assertTrue(
                self.active_task.runtime_context_path(root, "rtx_demo").is_file()
            )
            self.assertTrue(
                (
                    self.active_task.sessions_dir(root)
                    / "subagent_rtx_demo.json"
                ).is_file()
            )

    def test_runtime_context_initialize_rejects_conflicting_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = self.runtime_context.RuntimeContextService(root)
            service.initialize("rtx_demo", self._context())
            conflict = self._context()
            conflict["task_dir"] = ".cowork-flow/tasks/05-28-other"

            with self.assertRaises(
                self.runtime_context.RuntimeContextError
            ) as raised:
                service.initialize("rtx_demo", conflict)

            self.assertEqual("RUNTIME-INIT-001", raised.exception.code)
            context = json.loads(
                self.active_task.runtime_context_path(root, "rtx_demo").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(".cowork-flow/tasks/05-28-demo", context["task_dir"])

    def test_runtime_context_bind_rejects_different_host_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = self.runtime_context.RuntimeContextService(root)
            service.initialize("rtx_demo", self._context())
            service.bind("rtx_demo", "codex_child")

            with self.assertRaises(
                self.runtime_context.RuntimeContextError
            ) as raised:
                service.bind("rtx_demo", "codex_other")

            self.assertEqual("RUNTIME-BIND-001", raised.exception.code)
            context = json.loads(
                self.active_task.runtime_context_path(root, "rtx_demo").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual("codex_child", context["bound_context_key"])
            self.assertFalse(
                (self.active_task.sessions_dir(root) / "codex_other.json").exists()
            )

    def test_runtime_context_close_deletes_session_files_and_is_repeatable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = self.runtime_context.RuntimeContextService(root)
            service.initialize("rtx_demo", self._context())
            service.bind("rtx_demo", "codex_child")
            sessions = self.active_task.sessions_dir(root)
            bound_path = sessions / "codex_child.json"
            logical_path = sessions / "subagent_rtx_demo.json"
            self.assertTrue(bound_path.is_file())
            self.assertTrue(logical_path.is_file())

            self.assertTrue(service.close("rtx_demo"))
            self.assertFalse(bound_path.exists())
            self.assertFalse(logical_path.exists())
            context_path = self.active_task.runtime_context_path(root, "rtx_demo")
            context = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertEqual("closed", context["status"])

            self.assertTrue(service.close("rtx_demo"))
            self.assertFalse(bound_path.exists())
            self.assertFalse(logical_path.exists())
            context = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertEqual("closed", context["status"])

    def test_load_recovers_pending_runtime_context_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()
            service = self.runtime_context.RuntimeContextService(
                root,
                fault_injector=self._fail_after_first,
            )

            with self.assertRaises(RuntimeError):
                service.initialize("rtx_demo", self._context())

            logical_path = (
                self.active_task.sessions_dir(root) / "subagent_rtx_demo.json"
            )
            self.assertFalse(logical_path.exists())

            loaded = self.runtime_context.RuntimeContextService(root).load(
                "rtx_demo"
            )

            self.assertEqual("pending", loaded["status"])
            self.assertTrue(logical_path.is_file())
            session = json.loads(logical_path.read_text(encoding="utf-8"))
            self.assertEqual("pending_bind", session["status"])

    def test_update_recovers_pending_runtime_context_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            context_path = self.active_task.runtime_context_path(root, "rtx_demo")
            context_path.parent.mkdir(parents=True)
            context_path.write_text(
                json.dumps(self._context(), ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            service = self.runtime_context.RuntimeContextService(
                root,
                fault_injector=self._fail_after_first,
            )

            with self.assertRaises(RuntimeError):
                service.bind("rtx_demo", "codex_child")

            updated = self.runtime_context.RuntimeContextService(root).update(
                "rtx_demo",
                status="observed",
                note="after recovery",
            )

            self.assertIsNotNone(updated)
            self.assertEqual("observed", updated["status"])
            self.assertEqual("codex_child", updated["bound_context_key"])
            self.assertTrue(
                (self.active_task.sessions_dir(root) / "codex_child.json").is_file()
            )

    def test_corrupt_runtime_recovery_metadata_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            operation_dir = root / ".cowork-flow" / ".runtime" / "operations"
            operation_dir.mkdir(parents=True)
            operation_path = operation_dir / "runtime-broken.json"
            operation_path.write_text("{broken", encoding="utf-8")

            with self.assertRaises(
                self.runtime_context.RuntimeContextError
            ) as raised:
                self.runtime_context.RuntimeContextService(root).load("rtx_demo")

            self.assertEqual("RUNTIME-RECOVERY-001", raised.exception.code)
            self.assertTrue(operation_path.exists())

    def test_init_recovers_after_runtime_context_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()
            service = self.runtime_context.RuntimeContextService(
                root,
                fault_injector=self._fail_after_first,
            )

            with self.assertRaises(RuntimeError):
                service.initialize("rtx_demo", self._context())

            context_path = self.active_task.runtime_context_path(root, "rtx_demo")
            logical_path = (
                self.active_task.sessions_dir(root) / "subagent_rtx_demo.json"
            )
            self.assertTrue(context_path.exists())
            self.assertFalse(logical_path.exists())

            result = self.runtime_context.RuntimeContextService(root).initialize(
                "rtx_demo",
                self._context(),
            )

            self.assertEqual("subagent_rtx_demo", result.logical_context_key)
            self.assertTrue(logical_path.exists())
            session = json.loads(logical_path.read_text(encoding="utf-8"))
            self.assertEqual("pending_bind", session["status"])

    def test_bind_recovers_after_host_session_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            context_path = self.active_task.runtime_context_path(root, "rtx_demo")
            context_path.parent.mkdir(parents=True)
            context_path.write_text(
                json.dumps(self._context(), ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            service = self.runtime_context.RuntimeContextService(
                root,
                fault_injector=self._fail_after_first,
            )

            with self.assertRaises(RuntimeError):
                service.bind("rtx_demo", "codex_child")

            host_path = self.active_task.sessions_dir(root) / "codex_child.json"
            self.assertTrue(host_path.exists())
            partial = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertEqual("pending", partial["status"])

            bound = self.runtime_context.RuntimeContextService(root).bind(
                "rtx_demo",
                "codex_child",
            )

            self.assertIsNotNone(bound)
            self.assertEqual("bound", bound["status"])
            self.assertEqual("codex_child", bound["bound_context_key"])

    def test_close_recovers_after_host_session_delete(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            context = self._context()
            context["status"] = "bound"
            context["bound_context_key"] = "codex_child"
            context_path = self.active_task.runtime_context_path(root, "rtx_demo")
            context_path.parent.mkdir(parents=True)
            context_path.write_text(
                json.dumps(context, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            sessions = self.active_task.sessions_dir(root)
            sessions.mkdir(parents=True)
            host_path = sessions / "codex_child.json"
            logical_path = sessions / "subagent_rtx_demo.json"
            host_path.write_text("{}\n", encoding="utf-8")
            logical_path.write_text("{}\n", encoding="utf-8")
            service = self.runtime_context.RuntimeContextService(
                root,
                fault_injector=self._fail_after_first,
            )

            with self.assertRaises(RuntimeError):
                service.close("rtx_demo")

            self.assertFalse(host_path.exists())
            self.assertTrue(logical_path.exists())
            partial = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertEqual("bound", partial["status"])

            closed = self.runtime_context.RuntimeContextService(root).close(
                "rtx_demo"
            )

            self.assertTrue(closed)
            self.assertFalse(host_path.exists())
            self.assertFalse(logical_path.exists())
            final = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertEqual("closed", final["status"])
