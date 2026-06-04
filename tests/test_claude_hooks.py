from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
HOOK = TEMPLATE / ".claude" / "hooks" / "inject-workflow-state.py"


class ClaudeHooksTest(unittest.TestCase):
    def _make_project(self, root: Path) -> None:
        (root / ".cowork-flow").mkdir(parents=True)
        shutil.copytree(TEMPLATE / ".cowork-flow" / "scripts", root / ".cowork-flow" / "scripts")
        shutil.copyfile(TEMPLATE / ".cowork-flow" / "run", root / ".cowork-flow" / "run")
        shutil.copyfile(TEMPLATE / ".cowork-flow" / "run.cmd", root / ".cowork-flow" / "run.cmd")
        (root / ".cowork-flow" / "run").chmod(0o755)
        shutil.copytree(TEMPLATE / ".claude", root / ".claude")
        shutil.copyfile(TEMPLATE / ".cowork-flow" / "workflow.md", root / ".cowork-flow" / "workflow.md")
        shutil.copyfile(TEMPLATE / ".cowork-flow" / "config.yaml", root / ".cowork-flow" / "config.yaml")
        shutil.copytree(TEMPLATE / ".cowork-flow" / "spec", root / ".cowork-flow" / "spec")

    def _run_hook(self, root: Path, payload: dict[str, object]) -> dict:
        env = os.environ.copy()
        for name in (
            "COWORK_FLOW_CONTEXT_ID",
            "CLAUDE_SESSION_ID",
            "CODEX_SESSION_ID",
            "CODEX_THREAD_ID",
            "OPENCODE_SESSION_ID",
            "COWORK_FLOW_DISABLE_HOOKS",
            "COWORK_FLOW_HOOKS",
        ):
            env.pop(name, None)
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps({"cwd": str(root), **payload}),
            text=True,
            encoding="utf-8",
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
        self.assertIn("<claude-code-runtime>", context)
        self.assertIn('<cowork-runtime host="claude-code" adapter="claude-code.hooks">', context)
        self.assertIn("<contract-digest fingerprint=", context)
        self.assertIn("Status: no_task", context)
        self.assertIn("必须先创建或启动任务", context)

    def test_hook_emits_delegated_subtask_state_for_bounded_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)

            data = self._run_hook(
                root,
                {
                    "prompt": (
                        "这是一个有边界的委托任务，不是项目主会话启动请求。\n"
                        "任务：讨论 hook 如何避免把 subagent 拉回 no-task/start/resume 主流程。\n"
                        "约束：不要编辑文件，不要运行命令，不要派发 agent。\n"
                        "输出：中文，最多 400 字。"
                    )
                },
            )

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Status: delegated_subtask", context)
        self.assertIn("再执行委托输入", context)
        self.assertNotIn("必须先创建或启动任务", context)

    def test_hook_treats_dispatch_envelope_as_delegated_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)

            data = self._run_hook(
                root,
                {
                    "prompt": (
                        "COWORK_DISPATCH_V1\n"
                        "dispatch_id: d1\n"
                        "host: claude-code\n"
                        "agent_type: worker\n"
                        "ack_token: t1\n"
                        "COWORK_DISPATCH_END"
                    )
                },
            )

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Status: delegated_subtask", context)

    def test_hook_treats_unclassified_nonempty_prompt_as_delegated_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)

            data = self._run_hook(root, {"prompt": "Inspect routing notes and report concise findings."})

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Status: delegated_subtask", context)
        self.assertIn("Source: unclassified", context)
        self.assertNotIn("必须先创建或启动任务", context)

    def test_hook_reads_workflow_state_templates_instead_of_workflow_md(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            (root / ".cowork-flow" / "workflow.md").write_text(
                "[workflow-state:no_task]\nwrong source\n[/workflow-state:no_task]\n",
                encoding="utf-8",
            )
            template_file = root / ".cowork-flow" / "spec" / "workflow-state-templates.md"
            template_file.write_text(
                template_file.read_text(encoding="utf-8").replace(
                    "当前会话没有活动任务。只读问答可直接回答；如果收到委托子任务，直接执行委托 prompt，不要启动/恢复工作流。实现、重构或多步骤工作必须先创建或启动任务。",
                    "state-template-source-smoke",
                ),
                encoding="utf-8",
            )

            data = self._run_hook(root, {})

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("state-template-source-smoke", context)
        self.assertNotIn("wrong source", context)

    def test_session_start_emits_session_start_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)

            data = self._run_hook(root, {"hook_event_name": "SessionStart"})

        output = data["hookSpecificOutput"]
        self.assertEqual("SessionStart", output["hookEventName"])
        self.assertIn("Status: no_task", output["additionalContext"])

    def test_hook_resolves_active_task_from_claude_session_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            task_dir = root / ".cowork-flow" / "tasks" / "06-03-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text('{"status": "in_progress"}\n', encoding="utf-8")
            sessions = root / ".cowork-flow" / ".runtime" / "sessions"
            sessions.mkdir(parents=True)
            (sessions / "claude_demo-session.json").write_text(
                '{"active_task_path": ".cowork-flow/tasks/06-03-demo"}\n',
                encoding="utf-8",
            )

            data = self._run_hook(root, {"session_id": "demo-session"})

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Task: .cowork-flow/tasks/06-03-demo", context)
        self.assertIn("Status: in_progress", context)
        self.assertIn("派发 cowork-implement", context)

    def test_settings_config_uses_cowork_flow_python_runner_for_both_events(self) -> None:
        settings = json.loads((TEMPLATE / ".claude" / "settings.json").read_text(encoding="utf-8"))
        for event_name in ("UserPromptSubmit", "SessionStart"):
            command = settings["hooks"][event_name][0]["hooks"][0]["command"]
            self.assertEqual(".cowork-flow/run python .claude/hooks/inject-workflow-state.py", command)
            self.assertFalse(command.startswith("python "))

    def test_settings_command_executes_without_bare_python(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            settings = json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8"))
            command = settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]

            command_parts = shlex.split(command)
            if os.name == "nt":
                command_parts[0] = str(root / ".cowork-flow" / "run.cmd")
            result = subprocess.run(
                command_parts,
                input=json.dumps(
                    {
                        "cwd": str(root),
                        "prompt": (
                            "任务：讨论 hook 如何避免把 subagent 拉回主流程。\n"
                            "约束：不要编辑文件，不要运行命令。\n"
                            "输出：中文，最多 200 字。"
                        ),
                    }
                ),
                text=True,
                encoding="utf-8",
                capture_output=True,
                cwd=root,
                timeout=10,
            )

        self.assertEqual("", result.stderr)
        self.assertEqual(0, result.returncode)
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Status: delegated_subtask", context)

    def test_hook_contract_digest_fingerprint_tracks_spec_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)

            before = self._run_hook(root, {})["hookSpecificOutput"]["additionalContext"]
            spec_file = root / ".cowork-flow" / "spec" / "entry-contract.md"
            spec_file.write_text(
                spec_file.read_text(encoding="utf-8") + "\n<!-- fingerprint smoke -->\n",
                encoding="utf-8",
            )
            after = self._run_hook(root, {})["hookSpecificOutput"]["additionalContext"]

        before_match = re.search(r'<contract-digest fingerprint="([^"]+)">', before)
        after_match = re.search(r'<contract-digest fingerprint="([^"]+)">', after)
        self.assertIsNotNone(before_match)
        self.assertIsNotNone(after_match)
        self.assertNotEqual(before_match.group(1), after_match.group(1))

    def test_hook_runtime_files_root_and_template_are_synced(self) -> None:
        for rel in (
            Path(".claude/settings.json"),
            Path(".claude/hooks/inject-workflow-state.py"),
            Path(".cowork-flow/scripts/common/active_task.py"),
            Path(".cowork-flow/scripts/common/entry_classifier.py"),
            Path(".cowork-flow/spec/workflow-state-templates.md"),
        ):
            root_text = (ROOT / rel).read_text(encoding="utf-8")
            template_text = (TEMPLATE / rel).read_text(encoding="utf-8")
            self.assertEqual(root_text, template_text, f"{rel} root/template mismatch")


if __name__ == "__main__":
    unittest.main()
