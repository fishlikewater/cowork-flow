from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
SERVER_PATH = SCRIPTS / "adapters" / "mcp" / "state_server.py"


def _load_module():
    # Mirror the direct-script execution context: sys.path[0] is the
    # script's own directory, where _bootstrap.py lives.
    if str(SERVER_PATH.parent) not in sys.path:
        sys.path.insert(0, str(SERVER_PATH.parent))
    spec = importlib.util.spec_from_file_location(
        "mcp_state_server_under_test", SERVER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_project(root: Path) -> Path:
    task_dir = root / ".cowork-flow" / "tasks" / "08-29-demo"
    task_dir.mkdir(parents=True)
    (task_dir / "task.json").write_text(
        json.dumps(
            {
                "status": "in_progress",
                "title": "Demo",
                "assignee": "zhangxiang",
                "executor": "ci-bot",
                "meta": {"planFile": ".cowork-flow/plans/demo.md"},
            }
        ),
        encoding="utf-8",
    )
    anchor = (
        "# Decision Anchor\n\n"
        "## 目标\n\n"
        "Serve facts over MCP.\n\n"
        "## 验收标准\n\n"
        "- [ ] AC-001: read-only tools work\n\n"
        "## 被拒方案\n\n"
        "- **方案B（写工具）**: 拒绝——只读立场\n"
    )
    (task_dir / "decision-anchor.md").write_text(anchor, encoding="utf-8")
    sessions = root / ".cowork-flow" / ".runtime" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "zcode_probe.json").write_text(
        json.dumps({"active_task_path": ".cowork-flow/tasks/08-29-demo"}),
        encoding="utf-8",
    )
    return task_dir


class HandleRequestTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module()

    def test_initialize_echoes_client_protocol_version(self) -> None:
        response = self.module.handle_request(
            Path("/tmp"),
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "clientInfo": {"name": "probe"},
                },
            },
        )
        self.assertEqual(1, response["id"])
        self.assertEqual("2024-11-05", response["result"]["protocolVersion"])
        self.assertEqual(
            "cowork-flow-facts", response["result"]["serverInfo"]["name"]
        )
        self.assertIn("tools", response["result"]["capabilities"])

    def test_tools_list_declares_two_read_only_tools(self) -> None:
        response = self.module.handle_request(
            Path("/tmp"), {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        )
        names = [tool["name"] for tool in response["result"]["tools"]]
        self.assertEqual(["task_state", "task_list"], names)
        for tool in response["result"]["tools"]:
            self.assertIn("inputSchema", tool)

    def test_tools_call_task_state_returns_fact_view(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_project(root)

            response = self.module.handle_request(
                root,
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "task_state",
                        "arguments": {"task": "08-29-demo"},
                    },
                },
            )

        self.assertNotIn("error", response)
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual("in_progress", payload["task"]["status"])
        self.assertEqual("ci-bot", payload["task"]["executor"])
        self.assertTrue(payload["decisionAnchor"]["exists"])
        self.assertEqual(1, len(payload["decisionAnchor"]["acceptanceCriteria"]))
        self.assertEqual(["方案B（写工具）"], payload["decisionAnchor"]["rejectedOptions"])

    def test_tools_call_unknown_task_reports_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            response = self.module.handle_request(
                Path(temp_dir),
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "task_state",
                        "arguments": {"task": "08-29-missing"},
                    },
                },
            )
        self.assertTrue(response["result"]["isError"])
        self.assertIn("ValueError", response["result"]["content"][0]["text"])

    def test_unknown_method_returns_rpc_error_and_notifications_stay_silent(self) -> None:
        error = self.module.handle_request(
            Path("/tmp"), {"jsonrpc": "2.0", "id": 5, "method": "resources/list"}
        )
        self.assertEqual(-32601, error["error"]["code"])

        notification = self.module.handle_request(
            Path("/tmp"),
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        self.assertIsNone(notification)


class StdioSessionTest(unittest.TestCase):
    def test_end_to_end_spawn_conversation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_project(root)
            env = {
                **os.environ,
                "PYTHONPATH": str(SCRIPTS),
            }
            requests = "\n".join(
                (
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {"protocolVersion": "2025-06-18"},
                        }
                    ),
                    json.dumps(
                        {"jsonrpc": "2.0", "method": "notifications/initialized"}
                    ),
                    json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 3,
                            "method": "tools/call",
                            "params": {"name": "task_list", "arguments": {}},
                        }
                    ),
                    json.dumps({"jsonrpc": "2.0", "id": 4, "method": "ping"}),
                )
            )
            result = subprocess.run(
                [sys.executable, str(SERVER_PATH)],
                input=requests,
                text=True,
                encoding="utf-8",
                capture_output=True,
                cwd=root,
                env=env,
                timeout=30,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        replies = [
            json.loads(line)
            for line in result.stdout.splitlines()
            if line.strip()
        ]
        # The notification must not produce a reply: 4 requests -> 4 replies.
        self.assertEqual(4, len(replies))
        self.assertEqual("2025-06-18", replies[0]["result"]["protocolVersion"])
        names = [tool["name"] for tool in replies[1]["result"]["tools"]]
        self.assertEqual(["task_state", "task_list"], names)
        listing = json.loads(replies[2]["result"]["content"][0]["text"])
        self.assertEqual(1, listing["count"])
        self.assertEqual("08-29-demo", listing["tasks"][0]["name"])
        self.assertEqual({}, replies[3]["result"])


if __name__ == "__main__":
    unittest.main()