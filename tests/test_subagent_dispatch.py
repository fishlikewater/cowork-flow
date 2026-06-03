from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUBAGENT = ROOT / "template" / ".cowork-flow" / "scripts" / "subagent.py"


class SubagentDispatchTest(unittest.TestCase):
    def test_init_writes_lightweight_dispatch_envelope(self) -> None:
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
            self.assertEqual("fixed", payload["dispatchReliability"])
            self.assertIn("dispatchId", payload)
            self.assertIn("ackToken", payload)
            self.assertEqual(
                f"COWORK_ACK {payload['dispatchId']} {payload['ackToken']}",
                payload["expectedAck"],
            )
            self.assertIn("COWORK_DISPATCH_V1", payload["dispatchMessage"])
            self.assertIn("agent_type: cowork-research", payload["dispatchMessage"])
            self.assertIn("role: research", payload["dispatchMessage"])
            self.assertIn("task_dir: .cowork-flow/tasks/05-29-demo", payload["dispatchMessage"])
            self.assertIn("EXECUTE", payload["executeMessage"])
            self.assertTrue(payload["dispatchId"].startswith(payload["id"]))

            context_path = root / payload["contextFile"]
            context = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["agentType"], context["agentType"])
            self.assertEqual(payload["taskDir"], context["taskDir"])
            self.assertEqual(payload["dispatchReliability"], context["dispatchReliability"])
            self.assertEqual(payload["dispatchId"], context["dispatchId"])
            self.assertEqual(payload["ackToken"], context["ackToken"])
            self.assertEqual("planned", context["dispatchStatus"])

            brief = (root / context["briefFile"]).read_text(encoding="utf-8")
            self.assertIn("COWORK_DISPATCH_V1", brief)
            self.assertIn(f"dispatch_id: {payload['dispatchId']}", brief)
            self.assertIn(f"ack_token: {payload['ackToken']}", brief)
            self.assertIn("Return only: COWORK_ACK", brief)

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
            self.assertEqual("best-effort", payload["dispatchReliability"])
            self.assertIn("COWORK_DISPATCH_V1", payload["dispatchMessage"])
            self.assertIn("agent_type: worker", payload["dispatchMessage"])
            self.assertIn("best-effort", payload["dispatchMessage"])
            self.assertIn("COWORK_DISPATCH_END", payload["dispatchMessage"])
            self.assertIn("Return only: COWORK_ACK", payload["dispatchMessage"])

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


if __name__ == "__main__":
    unittest.main()
