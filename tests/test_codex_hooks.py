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
HOOK = TEMPLATE / ".codex" / "hooks" / "inject-workflow-state.py"


class CodexHooksTest(unittest.TestCase):
    def _make_project(self, root: Path) -> None:
        (root / ".cowork-flow").mkdir(parents=True)
        shutil.copytree(TEMPLATE / ".cowork-flow" / "scripts", root / ".cowork-flow" / "scripts")
        shutil.copyfile(TEMPLATE / ".cowork-flow" / "workflow.md", root / ".cowork-flow" / "workflow.md")
        shutil.copyfile(TEMPLATE / ".cowork-flow" / "config.yaml", root / ".cowork-flow" / "config.yaml")

    def _run_hook(self, root: Path, payload: dict[str, object]) -> dict:
        env = os.environ.copy()
        for name in (
            "COWORK_FLOW_CONTEXT_ID",
            "CODEX_SESSION_ID",
            "CODEX_THREAD_ID",
            "COWORK_FLOW_DISABLE_HOOKS",
            "COWORK_FLOW_HOOKS",
        ):
            env.pop(name, None)
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps({"cwd": str(root), **payload}),
            text=True,
            capture_output=True,
            cwd=root,
            env=env,
            timeout=10,
        )
        self.assertEqual("", result.stderr)
        self.assertEqual(0, result.returncode)
        return json.loads(result.stdout)

    def test_hook_emits_no_task_workflow_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)

            data = self._run_hook(root, {})

        output = data["hookSpecificOutput"]
        self.assertEqual("UserPromptSubmit", output["hookEventName"])
        context = output["additionalContext"]
        self.assertIn("<codex-mode>sub-agent</codex-mode>", context)
        self.assertIn("<workflow-state>", context)
        self.assertIn("Status: no_task", context)
        self.assertIn("create or start a task first", context)
        self.assertNotIn("<subagent-notice>", context)

    def test_hook_resolves_active_task_from_codex_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            task_dir = root / ".cowork-flow" / "tasks" / "05-29-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text('{"status": "in_progress"}\n', encoding="utf-8")
            sessions = root / ".cowork-flow" / ".runtime" / "sessions"
            sessions.mkdir(parents=True)
            (sessions / "codex_demo-session.json").write_text(
                '{"active_task_path": ".cowork-flow/tasks/05-29-demo"}\n',
                encoding="utf-8",
            )

            data = self._run_hook(root, {"session_id": "demo-session"})

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Task: .cowork-flow/tasks/05-29-demo", context)
        self.assertIn("Status: in_progress", context)
        self.assertIn("dispatches cowork-implement", context)

    def test_hook_reads_codex_dispatch_mode_from_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            (root / ".cowork-flow" / "config.yaml").write_text(
                "codex:\n  dispatch_mode: \"inline\"\n",
                encoding="utf-8",
            )

            data = self._run_hook(root, {})

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("<codex-mode>inline</codex-mode>", context)


if __name__ == "__main__":
    unittest.main()
