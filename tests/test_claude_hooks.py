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
NO_TASK_GATE_TEXT = "MUST NOT 编辑文件、实现代码、重构代码、派发子代理。"


class ClaudeHooksTest(unittest.TestCase):
    CLAUDE_HOOK_COMMAND = (
        '"${CLAUDE_PROJECT_DIR:-.}/.cowork-flow/run" python '
        '"${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/inject-workflow-state.py"'
    )

    def _make_project(self, root: Path) -> None:
        (root / ".cowork-flow").mkdir(parents=True)
        shutil.copytree(TEMPLATE / ".cowork-flow" / "scripts", root / ".cowork-flow" / "scripts")
        shutil.copyfile(TEMPLATE / ".cowork-flow" / "run", root / ".cowork-flow" / "run")
        shutil.copyfile(TEMPLATE / ".cowork-flow" / "run.cmd", root / ".cowork-flow" / "run.cmd")
        (root / ".cowork-flow" / "run").chmod(0o755)
        shutil.copytree(TEMPLATE / ".claude", root / ".claude")
        shutil.copyfile(TEMPLATE / ".cowork-flow" / "config.yaml", root / ".cowork-flow" / "config.yaml")
        shutil.copytree(TEMPLATE / ".cowork-flow" / "spec", root / ".cowork-flow" / "spec")

    def _run_hook(self, root: Path, payload: dict[str, object]) -> dict:
        env = self._hook_env()
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

    def _run_hook_bytes(self, root: Path, payload: dict[str, object]) -> dict:
        env = self._hook_env()
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps({"cwd": str(root), **payload}, ensure_ascii=False).encode("utf-8"),
            capture_output=True,
            cwd=root,
            env=env,
            timeout=10,
        )
        self.assertEqual(b"", result.stderr)
        self.assertEqual(0, result.returncode)
        return json.loads(result.stdout.decode("utf-8"))

    def _hook_env(self) -> dict[str, str]:
        env = os.environ.copy()
        for name in (
            "COWORK_FLOW_CONTEXT_ID",
            "COWORK_FLOW_HOST_CONTEXT_KEY",
            "CLAUDE_SESSION_ID",
            "CODEX_SESSION_ID",
            "CODEX_THREAD_ID",
            "OPENCODE_SESSION_ID",
            "COWORK_FLOW_RUNTIME_CONTEXT_ID",
            "COWORK_FLOW_DISABLE_HOOKS",
            "COWORK_FLOW_HOOKS",
        ):
            env.pop(name, None)
        return env

    def _settings_command_parts(self, command: str, root: Path) -> list[str]:
        project_dir = root.as_posix()
        expanded = command.replace("${CLAUDE_PROJECT_DIR:-.}", project_dir)
        command_parts = shlex.split(expanded)
        expected_runner = f"{project_dir}/.cowork-flow/run"
        if os.name == "nt" and command_parts and command_parts[0] == expected_runner:
            command_parts[0] = str(root / ".cowork-flow" / "run.cmd")
        return command_parts

    def _write_runtime_context(
        self,
        root: Path,
        runtime_id: str = "rtx_demo",
        task_dir: str = ".cowork-flow/tasks/06-03-demo",
        agent_type: str = "cowork-implement",
    ) -> None:
        context_dir = root / ".cowork-flow" / ".runtime" / "subagents"
        context_dir.mkdir(parents=True)
        task_path = root / task_dir
        task_path.mkdir(parents=True)
        (task_path / "task.json").write_text('{"status": "in_progress"}\n', encoding="utf-8")
        (context_dir / f"{runtime_id}.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "runtime_context_id": runtime_id,
                    "scope": "subagent",
                    "host": "claude-code",
                    "adapter": "claude-code.hooks",
                    "agent_type": agent_type,
                    "role": "implement",
                    "task_dir": task_dir,
                    "status": "pending",
                    "transport": {"kind": "prompt", "key": "cowork_runtime_context_id"},
                    "assignment": {
                        "title": "Runtime child",
                        "goal": "Apply the assigned slice.",
                        "allowed_context": [],
                    },
                    "authority": {
                        "may_start_task": False,
                        "may_resume_main": False,
                        "may_archive": False,
                        "may_commit": False,
                        "may_spawn": False,
                    },
                    "bound_context_key": None,
                }
            )
            + "\n",
            encoding="utf-8",
        )

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
        self.assertIn(NO_TASK_GATE_TEXT, context)

    def test_hook_surfaces_contract_registry_warning_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            (root / ".cowork-flow" / "spec" / "runtime" / "contract-registry.json").unlink()

            data = self._run_hook(root, {})

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("warning:", context)
        self.assertIn("contract registry unavailable", context)

    def test_hook_keeps_bounded_prompt_on_no_task_without_runtime_context(self) -> None:
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
        self.assertIn("Status: no_task", context)
        self.assertNotIn("Status: delegated_subtask", context)
        self.assertIn(NO_TASK_GATE_TEXT, context)

    def test_hook_binds_runtime_context_from_prompt_before_main_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            self._write_runtime_context(root, "rtx_claude_prompt")

            data = self._run_hook(
                root,
                {
                    "session_id": "child-session",
                    "prompt": "cowork_runtime_context_id: rtx_claude_prompt",
                },
            )
            session = json.loads(
                (root / ".cowork-flow" / ".runtime" / "sessions" / "claude_child-session.json").read_text(
                    encoding="utf-8"
                )
            )

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Status: delegated_subtask", context)
        self.assertIn("Source: runtime-context:rtx_claude_prompt", context)
        self.assertIn("Task: .cowork-flow/tasks/06-03-demo", context)
        self.assertIn("Agent: cowork-implement", context)
        self.assertIn("Scope: subagent", context)
        self.assertNotIn(NO_TASK_GATE_TEXT, context)
        self.assertEqual("subagent", session["scope"])
        self.assertEqual("rtx_claude_prompt", session["runtime_context_id"])

    def test_hook_prefers_prompt_host_context_key_over_session_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            self._write_runtime_context(root, "rtx_claude_prompt_key")

            data = self._run_hook(
                root,
                {
                    "session_id": "child-session",
                    "prompt": (
                        "cowork_runtime_context_id: rtx_claude_prompt_key\n"
                        "cowork_host_context_key: claude_prompt_key"
                    ),
                },
            )
            session = json.loads(
                (root / ".cowork-flow" / ".runtime" / "sessions" / "claude_prompt_key.json").read_text(
                    encoding="utf-8"
                )
            )
            runtime_context = json.loads(
                (root / ".cowork-flow" / ".runtime" / "subagents" / "rtx_claude_prompt_key.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(
                (root / ".cowork-flow" / ".runtime" / "sessions" / "claude_child-session.json").exists()
            )

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Status: delegated_subtask", context)
        self.assertEqual("subagent", session["scope"])
        self.assertEqual("rtx_claude_prompt_key", session["runtime_context_id"])
        self.assertEqual("claude_prompt_key", runtime_context["bound_context_key"])

    def test_hook_invalid_runtime_context_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)

            data = self._run_hook(
                root,
                {
                    "session_id": "child-session",
                    "prompt": "cowork_runtime_context_id: missing_runtime",
                },
            )

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Status: delegated_subtask", context)
        self.assertIn("runtime-context-invalid", context)
        self.assertNotIn(NO_TASK_GATE_TEXT, context)

    def test_hook_keeps_unclassified_nonempty_prompt_on_no_task_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)

            data = self._run_hook(root, {"prompt": "Inspect routing notes and report concise findings."})

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Status: no_task", context)
        self.assertRegex(context, r"Source: (missing-context|empty-session)")
        self.assertNotIn("Status: delegated_subtask", context)
        self.assertIn(NO_TASK_GATE_TEXT, context)

    def test_hook_keeps_main_agent_question_from_becoming_delegated_subtask(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)

            data = self._run_hook(root, {"prompt": "为什么会有这种误解，我希望避免这种误解"})

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Status: no_task", context)
        self.assertNotIn("Status: delegated_subtask", context)

    def test_hook_reads_utf8_prompt_bytes_before_classification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            task_dir = root / ".cowork-flow" / "tasks" / "06-04-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text('{"status": "in_progress"}\n', encoding="utf-8")
            sessions = root / ".cowork-flow" / ".runtime" / "sessions"
            sessions.mkdir(parents=True)
            (sessions / "claude_demo-session.json").write_text(
                '{"active_task_path": ".cowork-flow/tasks/06-04-demo"}\n',
                encoding="utf-8",
            )

            data = self._run_hook_bytes(root, {"session_id": "demo-session", "prompt": "先归档提交"})

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Task: .cowork-flow/tasks/06-04-demo", context)
        self.assertIn("Status: in_progress", context)
        self.assertNotIn("Status: delegated_subtask", context)
        self.assertNotIn("Source: unclassified", context)

    def test_hook_honors_explicit_main_session_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            task_dir = root / ".cowork-flow" / "tasks" / "06-04-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text('{"status": "in_progress"}\n', encoding="utf-8")
            sessions = root / ".cowork-flow" / ".runtime" / "sessions"
            sessions.mkdir(parents=True)
            (sessions / "claude_demo-session.json").write_text(
                '{"active_task_path": ".cowork-flow/tasks/06-04-demo"}\n',
                encoding="utf-8",
            )

            data = self._run_hook_bytes(
                root,
                {
                    "session_id": "demo-session",
                    "prompt": "我现在就是主会话，查找一下这个bug怎么产生的",
                },
            )

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Task: .cowork-flow/tasks/06-04-demo", context)
        self.assertIn("Status: in_progress", context)
        self.assertNotIn("Status: delegated_subtask", context)
        self.assertNotIn("Source: unclassified", context)

    def test_hook_reads_workflow_state_templates_as_single_prompt_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            template_file = root / ".cowork-flow" / "spec" / "contracts" / "workflow-state-templates.md"
            template_file.write_text(
                template_file.read_text(encoding="utf-8").replace(
                    "MUST NOT 编辑文件、实现代码、重构代码、派发子代理。",
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

    def test_hook_resolves_active_task_from_claude_code_session_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            task_dir = root / ".cowork-flow" / "tasks" / "06-03-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text('{"status": "in_progress"}\n', encoding="utf-8")
            sessions = root / ".cowork-flow" / ".runtime" / "sessions"
            sessions.mkdir(parents=True)
            (sessions / "claude_code-session.json").write_text(
                '{"active_task_path": ".cowork-flow/tasks/06-03-demo"}\n',
                encoding="utf-8",
            )

            data = self._run_hook(root, {"claude_code_session_id": "code-session"})

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Task: .cowork-flow/tasks/06-03-demo", context)
        self.assertIn("Status: in_progress", context)
        self.assertIn("派发 cowork-implement", context)

    def test_settings_config_uses_cowork_flow_python_runner_for_both_events(self) -> None:
        settings = json.loads((TEMPLATE / ".claude" / "settings.json").read_text(encoding="utf-8"))
        for event_name in ("UserPromptSubmit", "SessionStart"):
            command = settings["hooks"][event_name][0]["hooks"][0]["command"]
            self.assertEqual(self.CLAUDE_HOOK_COMMAND, command)
            self.assertIn("${CLAUDE_PROJECT_DIR:-.}", command)
            self.assertFalse(command.startswith(".cowork-flow/run"))
            self.assertFalse(command.startswith("python "))

    def test_settings_command_executes_from_nested_cwd_without_bare_python(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            self._write_runtime_context(root, "rtx_claude_command")
            nested = root / "nested" / "work"
            nested.mkdir(parents=True)
            settings = json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8"))
            command = settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]

            try:
                result = subprocess.run(
                    self._settings_command_parts(command, root),
                    input=json.dumps(
                        {
                            "cwd": str(root),
                            "session_id": "child-session",
                            "prompt": "cowork_runtime_context_id: rtx_claude_command",
                        }
                    ),
                    text=True,
                    encoding="utf-8",
                    capture_output=True,
                    cwd=nested,
                    timeout=10,
                )
            except FileNotFoundError as exc:
                self.fail(f"hook command could not locate runner from nested cwd: {exc}")

        self.assertEqual("", result.stderr)
        self.assertEqual(0, result.returncode)
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Status: delegated_subtask", context)

    def test_hook_contract_digest_fingerprint_tracks_spec_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)

            before = self._run_hook(root, {})["hookSpecificOutput"]["additionalContext"]
            spec_file = root / ".cowork-flow" / "spec" / "contracts" / "workflow-state-templates.md"
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

    def test_hook_runtime_files_template_are_valid(self) -> None:
        # Verify template files exist
        self.assertTrue((TEMPLATE / ".claude/settings.json").is_file())
        self.assertTrue((TEMPLATE / ".claude/hooks/inject-workflow-state.py").is_file())
        self.assertTrue((TEMPLATE / ".cowork-flow/scripts/common/task/active_task.py").is_file())
        self.assertTrue((TEMPLATE / ".cowork-flow/spec/contracts/workflow-state-templates.md").is_file())


if __name__ == "__main__":
    unittest.main()
