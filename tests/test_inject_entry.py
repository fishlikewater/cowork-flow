from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
INJECT = TEMPLATE / ".cowork-flow" / "scripts" / "adapters" / "host" / "inject.py"
NO_TASK_GATE_TEXT = "MUST NOT 编辑文件、实现代码、重构代码、派发子代理。"
REBIND_HINTS_HEADER = "活动任务（可用 ./.cowork-flow/run task next <dir> 改绑）："
MISSING_TASK_TEXT = "Session 指向的任务目录不存在"
NOT_INITIALIZED_TEXT = "项目未初始化 cowork-flow 工作流"

ZCODE_POLICY_LINE = (
    "policy: repeat fingerprint every hook; "
    "read full spec files only before listed actions."
)
PYTHON_CORE_POLICY_LINE = (
    "policy: repeat this short digest every hook; "
    "read full spec files only before listed actions."
)


class InjectEntryTest(unittest.TestCase):
    """Host-neutral inject.py entry: one Python source renders every
    process-hook host's context; per-host differences ride --host only."""

    def _make_project(self, root: Path) -> None:
        (root / ".cowork-flow").mkdir(parents=True)
        shutil.copytree(
            TEMPLATE / ".cowork-flow" / "scripts", root / ".cowork-flow" / "scripts"
        )
        shutil.copytree(
            TEMPLATE / ".cowork-flow" / "spec", root / ".cowork-flow" / "spec"
        )
        (root / ".cowork-flow" / "config.yaml").write_text("{}\n", encoding="utf-8")
        (root / "AGENTS.md").write_text("# fixture\n", encoding="utf-8")

    def _run_inject(
        self,
        root: Path,
        payload: dict[str, object],
        host: str = "zcode",
        env_extra: dict[str, str] | None = None,
        project_dir: Path | None = None,
    ) -> subprocess.CompletedProcess:
        env = clean_hook_env()
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            [sys.executable, str(INJECT), "--host", host],
            input=json.dumps({"cwd": str(root), **payload}, ensure_ascii=False),
            text=True,
            encoding="utf-8",
            capture_output=True,
            cwd=project_dir or root,
            env=env,
            timeout=15,
        )

    def _run_json(
        self,
        root: Path,
        payload: dict[str, object],
        host: str = "zcode",
        env_extra: dict[str, str] | None = None,
    ) -> dict:
        result = self._run_inject(root, payload, host=host, env_extra=env_extra)
        self.assertEqual("", result.stderr, result.stderr)
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)

    def _write_session(
        self,
        root: Path,
        session_key: str,
        task_path: str,
        *,
        scope: str = "main",
        last_seen_at: str = "2026-09-08T00:00:00+00:00",
    ) -> None:
        task_dir = root / task_path
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "task.json").write_text(
            '{"status": "in_progress"}\n', encoding="utf-8"
        )
        sessions = root / ".cowork-flow" / ".runtime" / "sessions"
        sessions.mkdir(parents=True, exist_ok=True)
        (sessions / f"{session_key}.json").write_text(
            json.dumps(
                {
                    "active_task_path": task_path,
                    "scope": scope,
                    "last_seen_at": last_seen_at,
                }
            )
            + "\n",
            encoding="utf-8",
        )

    # -- digest shape per host ------------------------------------------------

    def test_zcode_session_start_full_digest_with_zcode_policy_wording(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)

            data = self._run_json(root, {"hook_event_name": "SessionStart"})

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn(
            '<cowork-runtime host="zcode" adapter="zcode.plugin">', context
        )
        self.assertIn(ZCODE_POLICY_LINE, context)
        self.assertNotIn(PYTHON_CORE_POLICY_LINE, context)
        self.assertIn("<contract-digest fingerprint=", context)
        self.assertIn('status="no_task"', context)

    def test_zcode_digest_drops_registry_warning_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            (
                root / ".cowork-flow" / "spec" / "runtime" / "contract-registry.json"
            ).unlink()

            data = self._run_json(root, {"hook_event_name": "SessionStart"})

        context = data["hookSpecificOutput"]["additionalContext"]
        # zcode drops the registry-warning line (context-injection.md)
        self.assertNotIn("warning:", context)
        self.assertIn(ZCODE_POLICY_LINE, context)

    def test_claude_host_digest_keeps_default_policy_and_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            (
                root / ".cowork-flow" / "spec" / "runtime" / "contract-registry.json"
            ).unlink()

            data = self._run_json(
                root, {"hook_event_name": "SessionStart"}, host="claude-code"
            )

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn(PYTHON_CORE_POLICY_LINE, context)
        self.assertIn("warning:", context)
        self.assertIn(
            '<cowork-runtime host="claude-code" adapter="claude-code.hooks">',
            context,
        )

    def test_zcode_user_prompt_gets_fingerprint_not_full_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)

            data = self._run_json(root, {})

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn("<cowork-runtime", context)
        self.assertRegex(context, r'<contract-fingerprint value="[0-9a-f]{16}"/>')
        self.assertIn('status="no_task"', context)
        self.assertIn(NO_TASK_GATE_TEXT, context)

    def test_codex_first_injection_full_then_fingerprint_via_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)

            first = self._run_json(root, {}, host="codex")

            sessions = root / ".cowork-flow" / ".runtime" / "sessions"
            sessions.mkdir(parents=True, exist_ok=True)
            (sessions / "codex_thread-1.json").write_text(
                '{"scope": "main"}\n', encoding="utf-8"
            )
            second = self._run_json(
                root, {"session_id": "thread-1"}, host="codex"
            )

        first_context = first["hookSpecificOutput"]["additionalContext"]
        second_context = second["hookSpecificOutput"]["additionalContext"]
        # No session-start event on codex: activation-file probe decides.
        self.assertIn("<contract-digest fingerprint=", first_context)
        self.assertNotIn("<cowork-runtime", second_context)
        self.assertRegex(
            second_context, r'<contract-fingerprint value="[0-9a-f]{16}"/>'
        )

    # -- envelopes ------------------------------------------------------------

    def test_zcode_post_tool_use_edit_emits_additional_context_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            self._write_session(root, "zcode_s1", ".cowork-flow/tasks/09-01-demo")

            result = self._run_inject(
                root,
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "Edit",
                    "tool_input": {"file_path": "src/outside.py"},
                    "session_id": "s1",
                },
                env_extra={"ZCODE_SESSION_ID": "s1"},
            )

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual(
            "PostToolUse", payload["hookSpecificOutput"]["hookEventName"]
        )
        context = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn(
            "src/outside.py is outside the task's declared scope", context
        )

    def test_zcode_post_tool_use_in_scope_edit_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            task_path = ".cowork-flow/tasks/09-01-demo"
            self._write_session(root, "zcode_s1", task_path)
            implement = root / task_path / "implement.jsonl"
            implement.write_text(
                '{"file": "src/in.py", "type": "file"}\n', encoding="utf-8"
            )

            result = self._run_inject(
                root,
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "Edit",
                    "tool_input": {"file_path": "src/in.py"},
                    "session_id": "s1",
                },
                env_extra={"ZCODE_SESSION_ID": "s1"},
            )

        self.assertEqual(0, result.returncode)
        self.assertEqual("", result.stdout.strip())

    def test_zcode_post_tool_use_bash_nonlifecycle_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            self._write_session(root, "zcode_s1", ".cowork-flow/tasks/09-01-demo")

            result = self._run_inject(
                root,
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "Bash",
                    "tool_input": {"command": "pytest tests/ -q"},
                    "session_id": "s1",
                },
                env_extra={"ZCODE_SESSION_ID": "s1"},
            )

        self.assertEqual(0, result.returncode)
        self.assertEqual("", result.stdout.strip())

    def test_zcode_post_tool_use_bash_lifecycle_refreshes_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            self._write_session(root, "zcode_s1", ".cowork-flow/tasks/09-01-demo")

            result = self._run_inject(
                root,
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "Bash",
                    "tool_input": {"command": "./.cowork-flow/run task next --json"},
                    "session_id": "s1",
                },
                env_extra={"ZCODE_SESSION_ID": "s1"},
            )

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        context = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn('status="in_progress"', context)
        self.assertRegex(
            context, r'<contract-fingerprint value="[0-9a-f]{16}"/>'
        )

    def test_claude_post_tool_use_spec_violation_reports_on_stderr_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            self._write_session(
                root, "claude_s1", ".cowork-flow/tasks/09-01-demo"
            )
            spec_dir = root / ".cowork-flow" / "spec" / "backend"
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "edit-gate.md").write_text(
                "---\n"
                "checks:\n"
                f"  - cmd: \"{sys.executable}\" -c \"import sys; print('boom'); sys.exit(1)\"\n"
                "    when: edit\n"
                "    files: src/\n"
                "---\n\n# gate\n",
                encoding="utf-8",
            )

            result = self._run_inject(
                root,
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "Edit",
                    "tool_input": {"file_path": "src/a.py"},
                    "session_id": "s1",
                },
                host="claude-code",
                env_extra={"CLAUDE_SESSION_ID": "s1"},
            )

        self.assertEqual(2, result.returncode, result.stderr)
        self.assertEqual("", result.stdout.strip())
        self.assertEqual(1, len(result.stderr.strip().splitlines()))
        self.assertIn("backend/edit-gate.md", result.stderr)

    # -- not initialized ------------------------------------------------------

    def test_zcode_without_workflow_root_emits_not_initialized(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plain = Path(temp_dir) / "plain"
            plain.mkdir()

            result = self._run_inject(plain, {}, project_dir=plain)

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        context = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn(NOT_INITIALIZED_TEXT, context)
        self.assertIn("Status: not_initialized", context)
        self.assertRegex(
            context, r'<contract-fingerprint value="[0-9a-f]{16}"/>'
        )

    def test_claude_without_workflow_root_stays_silent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plain = Path(temp_dir) / "plain"
            plain.mkdir()

            result = self._run_inject(
                plain, {}, host="claude-code", project_dir=plain
            )

        self.assertEqual(0, result.returncode)
        self.assertEqual("", result.stdout.strip())

    # -- zcode-only ported behaviors ------------------------------------------

    def test_zcode_no_task_body_includes_rebind_hints(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            other = root / ".cowork-flow" / "tasks" / "09-07-other"
            other.mkdir(parents=True)
            (other / "task.json").write_text(
                '{"status": "planning"}\n', encoding="utf-8"
            )

            data = self._run_json(root, {})

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn(REBIND_HINTS_HEADER, context)
        self.assertIn("- .cowork-flow/tasks/09-07-other (planning)", context)

    def test_claude_no_task_body_has_no_rebind_hints(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            other = root / ".cowork-flow" / "tasks" / "09-07-other"
            other.mkdir(parents=True)
            (other / "task.json").write_text(
                '{"status": "planning"}\n', encoding="utf-8"
            )

            data = self._run_json(root, {}, host="claude-code")

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn(REBIND_HINTS_HEADER, context)

    def test_missing_task_dir_renders_missing_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            sessions = root / ".cowork-flow" / ".runtime" / "sessions"
            sessions.mkdir(parents=True)
            (sessions / "zcode_gone.json").write_text(
                '{"active_task_path": ".cowork-flow/tasks/09-01-gone", "scope": "main"}\n',
                encoding="utf-8",
            )

            data = self._run_json(
                root,
                {"session_id": "gone"},
                env_extra={"ZCODE_SESSION_ID": "gone"},
            )

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn(MISSING_TASK_TEXT, context)
        self.assertIn('status="no_task"', context)

    def test_zcode_missing_session_key_falls_back_to_newest_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            self._write_session(
                root,
                "zcode_keeper",
                ".cowork-flow/tasks/09-01-keeper",
                last_seen_at="2026-09-08T01:00:00+00:00",
            )

            data = self._run_json(root, {})

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn('task=".cowork-flow/tasks/09-01-keeper"', context)
        self.assertIn('status="in_progress"', context)

    def test_zcode_essential_files_warning_appended(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            (root / "AGENTS.md").unlink()

            data = self._run_json(root, {})

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("⚠️ 缺少必要文件：AGENTS.md", context)

    def test_zcode_scope_warning_silent_for_subagent_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            self._write_session(
                root,
                "zcode_child",
                ".cowork-flow/tasks/09-01-demo",
                scope="subagent",
            )

            result = self._run_inject(
                root,
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "Edit",
                    "tool_input": {"file_path": "src/outside.py"},
                    "session_id": "child",
                },
                env_extra={"ZCODE_SESSION_ID": "child"},
            )

        self.assertEqual(0, result.returncode)
        self.assertEqual("", result.stdout.strip())

    def test_zcode_merged_scope_and_spec_warning_share_one_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            self._write_session(root, "zcode_s1", ".cowork-flow/tasks/09-01-demo")
            spec_dir = root / ".cowork-flow" / "spec" / "backend"
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "edit-gate.md").write_text(
                "---\n"
                "checks:\n"
                f"  - cmd: \"{sys.executable}\" -c \"import sys; print('gate-boom'); sys.exit(1)\"\n"
                "    when: edit\n"
                "    files: src/\n"
                "---\n\n# gate\n",
                encoding="utf-8",
            )

            result = self._run_inject(
                root,
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "Edit",
                    "tool_input": {"file_path": "src/outside.py"},
                    "session_id": "s1",
                },
                env_extra={"ZCODE_SESSION_ID": "s1"},
            )

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        context = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn("outside the task's declared scope", context)
        self.assertIn("backend/edit-gate.md", context)
        self.assertIn("gate-boom", context)

    def test_kill_switch_exits_silently(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)

            result = self._run_inject(
                root, {}, env_extra={"COWORK_FLOW_DISABLE_HOOKS": "1"}
            )

        self.assertEqual(0, result.returncode)
        self.assertEqual("", result.stdout.strip())


def clean_hook_env() -> dict[str, str]:
    env = os.environ.copy()
    for name in (
        "COWORK_FLOW_CONTEXT_ID",
        "COWORK_FLOW_HOST_CONTEXT_KEY",
        "COWORK_FLOW_RUNTIME_CONTEXT_ID",
        "COWORK_FLOW_DISABLE_HOOKS",
        "COWORK_FLOW_HOOKS",
        "ZCODE_SESSION_ID",
        "ZCODE_PROCESS_LABEL",
        "OPENCODE_SESSION_ID",
        "CLAUDE_SESSION_ID",
        "CLAUDE_CODE_SESSION_ID",
        "CODEX_SESSION_ID",
        "CODEX_THREAD_ID",
        "DSH_SESSION_ID",
        "CURSOR_PLUGIN_ROOT",
        "CLAUDE_PLUGIN_ROOT",
        "ZCODE_PROJECT_DIR",
        "CLAUDE_PROJECT_DIR",
    ):
        env.pop(name, None)
    return env


if __name__ == "__main__":
    unittest.main()
