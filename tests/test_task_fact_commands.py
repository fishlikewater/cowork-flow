from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
TASK_CLI = TEMPLATE / ".cowork-flow" / "scripts" / "adapters" / "cli" / "task.py"


class TaskFactCommandsTest(unittest.TestCase):
    """`task scope` / `task specs` are read-only fact commands sharing the
    services facade with the MCP task_scope/task_specs tools."""

    def _make_project(self, root: Path) -> None:
        (root / ".cowork-flow").mkdir(parents=True)
        shutil.copytree(
            TEMPLATE / ".cowork-flow" / "scripts",
            root / ".cowork-flow" / "scripts",
        )
        task_dir = root / ".cowork-flow" / "tasks" / "09-08-facts"
        task_dir.mkdir(parents=True)
        (task_dir / "task.json").write_text(
            '{"status": "in_progress", "dev_type": "backend"}\n',
            encoding="utf-8",
        )
        (task_dir / "implement.jsonl").write_text(
            '{"file": "src/a.py", "type": "file"}\n'
            '{"file": ".cowork-flow/spec/backend", "type": "directory"}\n',
            encoding="utf-8",
        )
        sessions = root / ".cowork-flow" / ".runtime" / "sessions"
        sessions.mkdir(parents=True)
        (sessions / "facts.json").write_text(
            json.dumps({"active_task_path": ".cowork-flow/tasks/09-08-facts"})
            + "\n",
            encoding="utf-8",
        )

    def _run(self, root: Path, *cli_args: str) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["COWORK_FLOW_CONTEXT_ID"] = "facts"
        for name in (
            "ZCODE_SESSION_ID",
            "CLAUDE_SESSION_ID",
            "CODEX_SESSION_ID",
            "OPENCODE_SESSION_ID",
            "COWORK_FLOW_RUNTIME_CONTEXT_ID",
        ):
            env.pop(name, None)
        return subprocess.run(
            [sys.executable, str(TASK_CLI), *cli_args],
            text=True,
            encoding="utf-8",
            capture_output=True,
            cwd=root,
            env=env,
            timeout=20,
        )

    def test_scope_reports_whitelist_and_per_path_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)

            listed = self._run(root, "scope")
            verdict = self._run(root, "scope", "--path", "src/other.py")

        self.assertEqual(0, listed.returncode, listed.stderr)
        payload = json.loads(listed.stdout)
        self.assertEqual("09-08-facts", payload["taskDir"])
        self.assertEqual(1, payload["count"])
        self.assertEqual("src/a.py", payload["whitelist"][0]["file"])

        self.assertEqual(0, verdict.returncode, verdict.stderr)
        verdict_payload = json.loads(verdict.stdout)
        self.assertEqual("src/other.py", verdict_payload["path"])
        self.assertFalse(verdict_payload["inScope"])

    def test_specs_dispatches_by_dev_type_and_matches_mcp_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)

            result = self._run(root, "specs")

        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("09-08-facts", payload["taskDir"])
        self.assertEqual("backend", payload["devType"])
        self.assertEqual(payload["count"], len(payload["specs"]))
        self.assertTrue(payload["count"] > 0)

    def test_scope_without_task_or_session_reports_no_active_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir(parents=True)
            shutil.copytree(
                TEMPLATE / ".cowork-flow" / "scripts",
                root / ".cowork-flow" / "scripts",
            )

            result = self._run(root, "scope")

        self.assertEqual(1, result.returncode)
        self.assertEqual("no-active-task", json.loads(result.stdout)["error"])


if __name__ == "__main__":
    unittest.main()
