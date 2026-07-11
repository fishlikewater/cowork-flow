from __future__ import annotations

import json
import importlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
SUBAGENT = SCRIPTS / "subagent.py"


class SubagentDispatchTest(unittest.TestCase):
    def _cleanup_template_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in (
            "common.active_task",
            "common.execution_context",
            "common.paths",
            "common.time_utils",
            "flow.store",
            "flow",
            "patterns.base",
            "patterns",
            "common",
        ):
            sys.modules.pop(module_name, None)

    def _create_flow_task(
        self,
        root: Path,
        task_id: str,
        artifact_dir: str,
        *,
        status: str = "planning",
        parent_id: str | None = None,
    ) -> None:
        (root / ".cowork-flow" / "tasks" / artifact_dir).mkdir(parents=True, exist_ok=True)
        sys.path.insert(0, str(SCRIPTS))
        try:
            paths = importlib.import_module("common.paths")
            flow_store = importlib.import_module("flow.store")
            with flow_store.FlowStore(str(paths.get_db_path(root))) as store:
                store.create_task(
                    id=task_id,
                    artifact_dir=artifact_dir,
                    title=f"Task {task_id}",
                    status=status,
                    creator="test",
                    assignee="test",
                    parent_id=parent_id,
                )
        finally:
            self._cleanup_template_imports()

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

    def _runtime_contexts_for_task(self, root: Path, task_id: str) -> list[dict]:
        db = sqlite3.connect(root / ".cowork-flow" / "cowork-flow.db")
        try:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT * FROM runtime_context WHERE task_id = ?",
                (task_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            db.close()

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

    def test_init_writes_runtime_context_and_logical_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()

            result = subprocess.run(
                [
                    sys.executable,
                    str(SUBAGENT),
                    "--execution-task-dir",
                    ".cowork-flow/tasks/05-29-demo",
                    "init",
                    "--title",
                    "API probe",
                    "--role",
                    "research",
                    "--agent-type",
                    "cowork-research",
                    "--goal",
                    "Inspect API routes",
                    "--allowed-context",
                    "src/api.py",
                ],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
            payload = json.loads(result.stdout)
            self.assertEqual("cowork-research", payload["agentType"])
            self.assertEqual(".cowork-flow/tasks/05-29-demo", payload["taskDir"])
            self.assertEqual("formal", payload["dispatchKind"])
            self.assertIn("runtimeContextId", payload)
            self.assertEqual(payload["runtimeContextId"], payload["cowork_runtime_context_id"])
            self.assertEqual(payload["hostContextKey"], payload["cowork_host_context_key"])
            self.assertTrue(payload["hostContextKey"].startswith("codex_"))
            self.assertEqual(
                (
                    f"cowork_runtime_context_id: {payload['runtimeContextId']}\n"
                    f"cowork_host_context_key: {payload['hostContextKey']}"
                ),
                payload["promptTransport"],
            )
            self.assertEqual(
                f".cowork-flow/run subagent bind {payload['runtimeContextId']} {payload['hostContextKey']}",
                payload["bindCommand"],
            )
            self.assertNotIn("dispatchMessage", payload)
            self.assertNotIn("executeMessage", payload)
            self.assertNotIn("ackToken", payload)
            self.assertEqual("db", payload["runtimeContextSource"])
            self.assertIn("logicalSessionKey", payload)
            self.assertNotIn("logicalSessionFile", payload)
            self.assertNotIn("runtimeContextFile", payload)
            self.assertEqual("created_pending_bind", payload["runtimeContextStatus"])
            self.assertEqual(
                "not_created_by_cowork_flow_cli",
                payload["childCreationStatus"],
            )
            context = self._runtime_context(root, payload["runtimeContextId"])
            self.assertIsNotNone(context)
            self.assertEqual("subagent", context["scope"])
            self.assertEqual(payload["agentType"], context["agent_type"])
            self.assertEqual(payload["taskDir"], context["task_dir"])
            self.assertEqual("pending", context["status"])

            session = self._runtime_session(root, payload["logicalSessionKey"])
            self.assertIsNotNone(session)
            self.assertEqual("subagent", session["scope"])
            self.assertEqual(payload["runtimeContextId"], session["runtime_context_id"])
            self.assertEqual(".cowork-flow/tasks/05-29-demo", session["active_task_path"])
            self.assertEqual("pending_bind", session["status"])

    def test_init_accepts_execution_task_dir_inside_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()

            result = subprocess.run(
                [
                    sys.executable,
                    str(SUBAGENT),
                    "init",
                    "--execution-task-dir",
                    ".cowork-flow/tasks/05-29-demo",
                    "--title",
                    "API probe",
                    "--role",
                    "research",
                    "--agent-type",
                    "cowork-research",
                ],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
            payload = json.loads(result.stdout)
            self.assertEqual(".cowork-flow/tasks/05-29-demo", payload["taskDir"])
            self.assertEqual("formal", payload["dispatchKind"])

    def test_init_emits_project_anchored_bind_command_for_claude_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()

            result = subprocess.run(
                [
                    sys.executable,
                    str(SUBAGENT),
                    "init",
                    "--execution-task-dir",
                    ".cowork-flow/tasks/05-29-demo",
                    "--title",
                    "Claude probe",
                    "--role",
                    "implement",
                    "--agent-type",
                    "cowork-implement",
                    "--host",
                    "claude-code",
                    "--adapter",
                    "claude-code.subagent",
                ],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
            payload = json.loads(result.stdout)
            self.assertTrue(payload["hostContextKey"].startswith("claude_"))
            self.assertEqual(
                (
                    f"${{CLAUDE_PROJECT_DIR:-.}}/.cowork-flow/run subagent bind "
                    f"{payload['runtimeContextId']} {payload['hostContextKey']}"
                ),
                payload["bindCommand"],
            )

    def test_dispatch_codex_emits_spawn_payload_with_required_bind_step(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()
            self._create_flow_task(root, "demo", "05-29-demo")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SUBAGENT),
                    "dispatch-codex",
                    "--execution-task-dir",
                    ".cowork-flow/tasks/05-29-demo",
                    "--title",
                    "Check demo",
                    "--role",
                    "check",
                    "--agent-type",
                    "cowork-check",
                ],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
            payload = json.loads(result.stdout)
            self.assertEqual("cowork-check", payload["agent_type"])
            self.assertEqual("none", payload["fork_turns"])
            self.assertTrue(payload["task_name"].startswith("rtx_"))
            self.assertNotIn("-", payload["task_name"])
            self.assertEqual(payload["runtimeContextId"], payload["cowork_runtime_context_id"])
            self.assertEqual(payload["hostContextKey"], payload["cowork_host_context_key"])
            self.assertEqual("payload_prepared_child_not_created", payload["hostDispatchState"])
            self.assertEqual("not_created_by_cowork_flow_cli", payload["childCreationStatus"])
            self.assertEqual("spawn_agent", payload["hostPrimitive"])
            self.assertIn("Call host spawn_agent", payload["parentNextAction"])
            self.assertIn(
                "confirm the host child appears in the host child list or wait result",
                payload["parentVerification"],
            )
            self.assertIn(payload["runtimeContextId"], payload["message"])
            self.assertIn(payload["hostContextKey"], payload["message"])
            self.assertIn(".\\.cowork-flow\\run.cmd subagent bind", payload["message"])
            self.assertIn("Do not continue formal work if bind fails.", payload["message"])
            self.assertEqual(
                f".cowork-flow/run subagent bind {payload['runtimeContextId']} {payload['hostContextKey']}",
                payload["bindCommand"],
            )
            # P1-A: runtime_context is now sole authority; agent_run writes removed
            rc = self._runtime_context(root, payload["runtimeContextId"])
            self.assertIsNotNone(rc)
            self.assertEqual(payload["runtimeContextId"], rc["id"])
            self.assertEqual("demo", rc["task_id"])
            self.assertEqual("cowork-check", rc["agent_type"])
            self.assertEqual("pending", rc["status"])

    def test_direct_formal_init_creates_and_updates_runtime_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()
            self._create_flow_task(root, "demo", "05-29-demo")

            init_result = subprocess.run(
                [
                    sys.executable,
                    str(SUBAGENT),
                    "init",
                    "--execution-task-dir",
                    ".cowork-flow/tasks/05-29-demo",
                    "--title",
                    "Implement demo",
                    "--role",
                    "implement",
                    "--agent-type",
                    "cowork-implement",
                ],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, init_result.returncode, msg=init_result.stderr)
            payload = json.loads(init_result.stdout)

            # Verify runtime_context was created
            rc = self._runtime_context(root, payload["runtimeContextId"])
            self.assertIsNotNone(rc)
            self.assertEqual(payload["runtimeContextId"], rc["id"])
            self.assertEqual("demo", rc["task_id"])
            self.assertEqual("cowork-implement", rc["agent_type"])
            self.assertEqual("pending", rc["status"])

            bind_result = subprocess.run(
                [sys.executable, str(SUBAGENT), "bind", payload["runtimeContextId"], payload["hostContextKey"]],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, bind_result.returncode, msg=bind_result.stderr)
            rc_after_bind = self._runtime_context(root, payload["runtimeContextId"])
            self.assertEqual("bound", rc_after_bind["status"])
            self.assertEqual(payload["hostContextKey"], rc_after_bind["bound_context_key"])

            close_result = subprocess.run(
                [sys.executable, str(SUBAGENT), "close", payload["runtimeContextId"]],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, close_result.returncode, msg=close_result.stderr)
            rc_after_close = self._runtime_context(root, payload["runtimeContextId"])
            self.assertEqual("closed", rc_after_close["status"])

    def test_init_rejects_fixed_agent_role_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()

            result = subprocess.run(
                [
                    sys.executable,
                    str(SUBAGENT),
                    "--execution-task-dir",
                    ".cowork-flow/tasks/05-29-demo",
                    "init",
                    "--title",
                    "Bad dispatch",
                    "--role",
                    "cowork-check",
                    "--agent-type",
                    "cowork-implement",
                ],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(0, result.returncode)
            self.assertIn("agent-type cowork-implement cannot use role cowork-check", result.stderr)

    def test_init_rejects_fixed_agent_workflow_role_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()

            result = subprocess.run(
                [
                    sys.executable,
                    str(SUBAGENT),
                    "--execution-task-dir",
                    ".cowork-flow/tasks/05-29-demo",
                    "init",
                    "--title",
                    "Bad workflow role dispatch",
                    "--role",
                    "check",
                    "--agent-type",
                    "cowork-implement",
                ],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(0, result.returncode)
            self.assertIn("agent-type cowork-implement cannot use role check", result.stderr)

    def test_init_rejects_fixed_agent_without_task_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()

            result = subprocess.run(
                [
                    sys.executable,
                    str(SUBAGENT),
                    "init",
                    "--title",
                    "Missing task",
                    "--role",
                    "check",
                    "--agent-type",
                    "cowork-check",
                ],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(0, result.returncode)
            self.assertIn("fixed agent dispatch requires --execution-task-dir", result.stderr)

    def test_init_marks_generic_worker_best_effort(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()

            result = subprocess.run(
                [
                    sys.executable,
                    str(SUBAGENT),
                    "init",
                    "--title",
                    "Smoke worker",
                    "--role",
                    "generic-worker",
                    "--agent-type",
                    "worker",
                ],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
            payload = json.loads(result.stdout)
            self.assertEqual("worker", payload["agentType"])
            self.assertEqual("advisory", payload["dispatchKind"])
            self.assertIn("runtimeContextId", payload)
            self.assertNotIn("dispatchMessage", payload)
            self.assertNotIn("expectedAck", payload)

    def test_init_rejects_generic_worker_with_fixed_role(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()

            result = subprocess.run(
                [
                    sys.executable,
                    str(SUBAGENT),
                    "init",
                    "--title",
                    "Bad worker",
                    "--role",
                    "cowork-check",
                    "--agent-type",
                    "worker",
                ],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(0, result.returncode)
            self.assertIn("agent-type worker requires non-fixed role", result.stderr)

    def test_close_removes_runtime_session_bindings_and_marks_context_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()

            init_result = subprocess.run(
                [
                    sys.executable,
                    str(SUBAGENT),
                    "--execution-task-dir",
                    ".cowork-flow/tasks/05-29-demo",
                    "init",
                    "--title",
                    "Close me",
                    "--role",
                    "research",
                    "--agent-type",
                    "cowork-research",
                ],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=True,
            )
            payload = json.loads(init_result.stdout)
            runtime_id = payload["runtimeContextId"]
            bind_result = subprocess.run(
                [sys.executable, str(SUBAGENT), "bind", runtime_id, "codex_child"],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, bind_result.returncode, msg=bind_result.stderr)
            self.assertIsNotNone(self._runtime_session(root, "codex_child"))
            self.assertIsNotNone(self._runtime_session(root, payload["logicalSessionKey"]))

            close_result = subprocess.run(
                [sys.executable, str(SUBAGENT), "close", runtime_id],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, close_result.returncode, msg=close_result.stderr)
            closed = self._runtime_context(root, runtime_id)
            self.assertIsNotNone(closed)
            self.assertEqual("closed", closed["status"])
            self.assertIsNone(self._runtime_session(root, "codex_child"))
            self.assertIsNone(self._runtime_session(root, payload["logicalSessionKey"]))


    def test_bind_is_idempotent_for_same_context_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()

            init_result = subprocess.run(
                [
                    sys.executable,
                    str(SUBAGENT),
                    "--execution-task-dir",
                    ".cowork-flow/tasks/05-29-demo",
                    "init",
                    "--title",
                    "Bind me",
                    "--role",
                    "check",
                    "--agent-type",
                    "cowork-check",
                ],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=True,
            )
            runtime_id = json.loads(init_result.stdout)["runtimeContextId"]

            first = subprocess.run(
                [sys.executable, str(SUBAGENT), "bind", runtime_id, "codex_child"],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            second = subprocess.run(
                [sys.executable, str(SUBAGENT), "bind", runtime_id, "codex_child"],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, first.returncode, msg=first.stderr)
            self.assertEqual(0, second.returncode, msg=second.stderr)
            context = json.loads(second.stdout)
            self.assertEqual("bound", context["status"])
            self.assertEqual("codex_child", context["bound_context_key"])

    def test_bind_rejects_different_context_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()

            init_result = subprocess.run(
                [
                    sys.executable,
                    str(SUBAGENT),
                    "--execution-task-dir",
                    ".cowork-flow/tasks/05-29-demo",
                    "init",
                    "--title",
                    "Reject rebind",
                    "--role",
                    "check",
                    "--agent-type",
                    "cowork-check",
                ],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=True,
            )
            runtime_id = json.loads(init_result.stdout)["runtimeContextId"]

            first = subprocess.run(
                [sys.executable, str(SUBAGENT), "bind", runtime_id, "codex_first"],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            second = subprocess.run(
                [sys.executable, str(SUBAGENT), "bind", runtime_id, "codex_second"],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, first.returncode, msg=first.stderr)
            self.assertNotEqual(0, second.returncode)
            self.assertIn("already bound to codex_first", second.stderr)
            context = self._runtime_context(root, runtime_id)
            self.assertIsNotNone(context)
            self.assertEqual("codex_first", context["bound_context_key"])

    def test_spawn_family_creates_missing_runs_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()
            self._create_flow_task(root, "parent", "05-29-parent")
            self._create_flow_task(
                root,
                "child-a",
                "05-29-child-a",
                parent_id="parent",
            )
            self._create_flow_task(
                root,
                "child-b",
                "05-29-child-b",
                status="completed",
                parent_id="parent",
            )

            first = subprocess.run(
                [
                    sys.executable,
                    str(SUBAGENT),
                    "spawn-family",
                    "parent",
                    "--agent-type",
                    "cowork-implement",
                ],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            second = subprocess.run(
                [
                    sys.executable,
                    str(SUBAGENT),
                    "spawn-family",
                    "parent",
                    "--agent-type",
                    "cowork-implement",
                ],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, first.returncode, msg=first.stderr)
            created = {item["task_id"]: item for item in json.loads(first.stdout)}
            self.assertEqual("pending", created["child-a"]["status"])
            self.assertEqual("skipped_done", created["child-b"]["status"])
            self.assertNotIn("runtimeContextFile", created["child-a"])
            runtime_context = self._runtime_context(root, created["child-a"]["runtimeContextId"])
            self.assertIsNotNone(runtime_context)
            self.assertEqual(
                ".cowork-flow/tasks/05-29-child-a",
                runtime_context["task_dir"],
            )

            self.assertEqual(0, second.returncode, msg=second.stderr)
            repeated = {item["task_id"]: item for item in json.loads(second.stdout)}
            self.assertEqual("already_running", repeated["child-a"]["status"])
            # P1-A: runtime_context is sole authority; verify child-a has a runtime_context row
            rtcs = self._runtime_contexts_for_task(root, "child-a")
            self.assertEqual(1, len(rtcs))
            self.assertEqual("pending", rtcs[0]["status"])

    def test_check_family_tracks_pending_success_and_failed_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()
            self._create_flow_task(root, "parent", "05-29-parent")
            self._create_flow_task(root, "child-a", "05-29-child-a", parent_id="parent")

            spawn = subprocess.run(
                [
                    sys.executable,
                    str(SUBAGENT),
                    "spawn-family",
                    "parent",
                    "--agent-type",
                    "cowork-implement",
                ],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, spawn.returncode, msg=spawn.stderr)
            spawn_payload = json.loads(spawn.stdout)[0]
            runtime_id = spawn_payload["runtimeContextId"]
            host_context_key = spawn_payload["hostContextKey"]

            pending = subprocess.run(
                [sys.executable, str(SUBAGENT), "check-family", "parent"],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, pending.returncode)
            pending_payload = json.loads(pending.stdout)
            self.assertFalse(pending_payload["all_done"])
            self.assertEqual(["child-a"], [item["task_id"] for item in pending_payload["pending"]])

            success_update = subprocess.run(
                [sys.executable, str(SUBAGENT), "update", runtime_id, "--status", "success"],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, success_update.returncode, msg=success_update.stderr)
            unbound_success = subprocess.run(
                [sys.executable, str(SUBAGENT), "check-family", "parent"],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, unbound_success.returncode)
            unbound_payload = json.loads(unbound_success.stdout)
            self.assertFalse(unbound_payload["all_done"])
            self.assertEqual(
                ["child-a"],
                [item["task_id"] for item in unbound_payload["unbound_rejected"]],
            )
            self.assertIn("bound_context_key", unbound_success.stderr)

            bind = subprocess.run(
                [sys.executable, str(SUBAGENT), "bind", runtime_id, host_context_key],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, bind.returncode, msg=bind.stderr)

            success_update = subprocess.run(
                [sys.executable, str(SUBAGENT), "update", runtime_id, "--status", "success"],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, success_update.returncode, msg=success_update.stderr)
            success = subprocess.run(
                [sys.executable, str(SUBAGENT), "check-family", "parent"],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, success.returncode, msg=success.stderr)
            self.assertTrue(json.loads(success.stdout)["all_done"])

            failed_update = subprocess.run(
                [sys.executable, str(SUBAGENT), "update", runtime_id, "--status", "failed"],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, failed_update.returncode, msg=failed_update.stderr)
            failed = subprocess.run(
                [sys.executable, str(SUBAGENT), "check-family", "parent"],
                cwd=root,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, failed.returncode)
            self.assertEqual(["child-a"], [item["task_id"] for item in json.loads(failed.stdout)["failed"]])

if __name__ == "__main__":
    unittest.main()
