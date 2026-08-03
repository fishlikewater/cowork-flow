from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUBAGENT = ROOT / "template" / ".cowork-flow" / "scripts" / "adapters" / "cli" / "subagent.py"


class SubagentDispatchTest(unittest.TestCase):
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

            context_path = root / payload["runtimeContextFile"]
            context = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertEqual(2, context["schema_version"])
            self.assertEqual("subagent", context["scope"])
            self.assertEqual(payload["runtimeContextId"], context["runtime_context_id"])
            self.assertEqual(payload["agentType"], context["agent_type"])
            self.assertEqual(payload["taskDir"], context["task_dir"])
            self.assertEqual("pending", context["status"])
            self.assertEqual(
                {"kind": "prompt", "key": "cowork_runtime_context_id"},
                context["transport"],
            )

            session_path = root / payload["logicalSessionFile"]
            session = json.loads(session_path.read_text(encoding="utf-8"))
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
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
            payload = json.loads(result.stdout)
            self.assertEqual(".cowork-flow/tasks/05-29-demo", payload["taskDir"])
            self.assertEqual("formal", payload["dispatchKind"])

    def test_init_detects_zcode_host_and_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()

            env = {
                **os.environ,
                "ZCODE_SESSION_ID": "zc-main",
            }
            for name in (
                "CLAUDE_CODE_SESSION_ID",
                "CLAUDE_SESSION_ID",
                "CODEX_SESSION_ID",
                "CODEX_THREAD_ID",
                "OPENCODE_SESSION_ID",
            ):
                env.pop(name, None)

            result = subprocess.run(
                [
                    sys.executable,
                    str(SUBAGENT),
                    "--execution-task-dir",
                    ".cowork-flow/tasks/05-29-demo",
                    "init",
                    "--title",
                    "ZCode check",
                    "--role",
                    "check",
                    "--agent-type",
                    "cowork-check",
                ],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
                env=env,
            )

            self.assertEqual(0, result.returncode, msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
            payload = json.loads(result.stdout)
            self.assertTrue(payload["hostContextKey"].startswith("zcode_"))

            context = json.loads((root / payload["runtimeContextFile"]).read_text(encoding="utf-8"))
            self.assertEqual("zcode", context["host"])
            self.assertEqual("zcode.plugin", context["adapter"])
            self.assertEqual("cowork-check", context["agent_type"])

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
                capture_output=True,
                check=True,
            )
            payload = json.loads(init_result.stdout)
            runtime_id = payload["runtimeContextId"]
            context_path = root / payload["runtimeContextFile"]
            context = json.loads(context_path.read_text(encoding="utf-8"))
            context["bound_context_key"] = "codex_child"
            context_path.write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8")
            host_session = root / ".cowork-flow" / ".runtime" / "sessions" / "codex_child.json"
            host_session.write_text("{}", encoding="utf-8")

            close_result = subprocess.run(
                [sys.executable, str(SUBAGENT), "close", runtime_id],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, close_result.returncode, msg=close_result.stderr)
            closed = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertEqual("closed", closed["status"])
            self.assertFalse(host_session.exists())
            self.assertFalse((root / payload["logicalSessionFile"]).exists())

            repeated = subprocess.run(
                [sys.executable, str(SUBAGENT), "close", runtime_id],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, repeated.returncode, msg=repeated.stderr)
            self.assertFalse(host_session.exists())
            self.assertFalse((root / payload["logicalSessionFile"]).exists())


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
                capture_output=True,
                check=True,
            )
            runtime_id = json.loads(init_result.stdout)["runtimeContextId"]

            first = subprocess.run(
                [sys.executable, str(SUBAGENT), "bind", runtime_id, "codex_child"],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            second = subprocess.run(
                [sys.executable, str(SUBAGENT), "bind", runtime_id, "codex_child"],
                cwd=root,
                text=True,
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
                capture_output=True,
                check=True,
            )
            runtime_id = json.loads(init_result.stdout)["runtimeContextId"]

            first = subprocess.run(
                [sys.executable, str(SUBAGENT), "bind", runtime_id, "codex_first"],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            second = subprocess.run(
                [sys.executable, str(SUBAGENT), "bind", runtime_id, "codex_second"],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, first.returncode, msg=first.stderr)
            self.assertNotEqual(0, second.returncode)
            self.assertIn("RUNTIME-BIND-001", second.stderr)
            self.assertIn("already bound to codex_first", second.stderr)
            context = json.loads(
                (root / ".cowork-flow" / ".runtime" / "subagents" / f"{runtime_id}.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual("codex_first", context["bound_context_key"])

    def test_bind_missing_context_key_does_not_create_runtime_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()

            result = subprocess.run(
                [sys.executable, str(SUBAGENT), "bind", "rtx_missing"],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(0, result.returncode)
            self.assertFalse((root / ".cowork-flow" / ".runtime").exists())

if __name__ == "__main__":
    unittest.main()
