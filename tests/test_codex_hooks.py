from __future__ import annotations

import importlib
import json
import os
import re
import shutil
import shlex
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
HOOK = TEMPLATE / ".codex" / "hooks" / "inject-workflow-state.py"
LEGACY_POST_ACK = "post" + "_ack_execution_grace_ms"


class CodexHooksTest(unittest.TestCase):
    def _make_project(self, root: Path) -> None:
        (root / ".cowork-flow").mkdir(parents=True)
        shutil.copytree(TEMPLATE / ".cowork-flow" / "scripts", root / ".cowork-flow" / "scripts")
        shutil.copyfile(TEMPLATE / ".cowork-flow" / "run", root / ".cowork-flow" / "run")
        shutil.copyfile(TEMPLATE / ".cowork-flow" / "run.cmd", root / ".cowork-flow" / "run.cmd")
        (root / ".cowork-flow" / "run").chmod(0o755)
        shutil.copytree(TEMPLATE / ".codex", root / ".codex")
        shutil.copyfile(TEMPLATE / ".cowork-flow" / "workflow.md", root / ".cowork-flow" / "workflow.md")
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
            "CODEX_SESSION_ID",
            "CODEX_THREAD_ID",
            "COWORK_FLOW_RUNTIME_CONTEXT_ID",
            "COWORK_FLOW_DISABLE_HOOKS",
            "COWORK_FLOW_HOOKS",
            "OPENCODE_SESSION_ID",
            "CLAUDE_SESSION_ID",
            "CLAUDE_CODE_SESSION_ID",
        ):
            env.pop(name, None)
        return env

    def _cleanup_script_imports(self, script_root: Path) -> None:
        if str(script_root) in sys.path:
            sys.path.remove(str(script_root))
        for module_name in (
            "common.active_task",
            "common.paths",
            "common.time_utils",
            "flow.migration_store",
            "flow.store",
            "flow",
            "patterns.base",
            "patterns",
            "common",
        ):
            sys.modules.pop(module_name, None)

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

    def _write_runtime_context(
        self,
        root: Path,
        runtime_id: str = "rtx_demo",
        task_dir: str = ".cowork-flow/tasks/05-29-demo",
        agent_type: str = "cowork-implement",
    ) -> None:
        script_root = root / ".cowork-flow" / "scripts"
        task_path = root / task_dir
        task_path.mkdir(parents=True)
        (task_path / "task.json").write_text('{"status": "in_progress"}\n', encoding="utf-8")
        sys.path.insert(0, str(script_root))
        try:
            paths = importlib.import_module("common.paths")
            flow_store = importlib.import_module("flow.store")
            with flow_store.FlowStore(str(paths.get_db_path(root))) as store:
                store.upsert_runtime_context(
                    {
                        "schema_version": 2,
                        "runtime_context_id": runtime_id,
                        "scope": "subagent",
                        "host": "codex",
                        "adapter": "codex.spawn_agent",
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
        finally:
            self._cleanup_script_imports(script_root)

    def _write_runtime_session(
        self,
        root: Path,
        context_key: str,
        task_dir: str,
        *,
        platform: str = "codex",
        status: str = "active",
    ) -> None:
        script_root = root / ".cowork-flow" / "scripts"
        sys.path.insert(0, str(script_root))
        try:
            paths = importlib.import_module("common.paths")
            flow_store = importlib.import_module("flow.store")
            with flow_store.FlowStore(str(paths.get_db_path(root))) as store:
                store.upsert_runtime_session(
                    context_key,
                    {
                        "scope": "main",
                        "active_task_path": task_dir,
                        "platform": platform,
                        "status": status,
                    },
                )
        finally:
            self._cleanup_script_imports(script_root)

    def _write_flow_task(
        self,
        root: Path,
        *,
        task_id: str = "demo",
        artifact_dir: str = "05-29-demo",
        status: str = "review",
    ) -> None:
        script = (
            "import sys\n"
            "from pathlib import Path\n"
            f"sys.path.insert(0, {str(root / '.cowork-flow' / 'scripts')!r})\n"
            "from flow.store import FlowStore\n"
            f"with FlowStore({str(root / '.cowork-flow' / 'cowork-flow.db')!r}) as store:\n"
            f"    store.create_task(id={task_id!r}, title='Demo', status={status!r}, creator='dev', assignee='dev')\n"
            f"    store.db.execute('UPDATE task SET artifact_dir = ? WHERE id = ?', ({artifact_dir!r}, {task_id!r}))\n"
            "    store.db.commit()\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_hook_emits_no_task_workflow_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)

            data = self._run_hook(root, {})

        output = data["hookSpecificOutput"]
        self.assertEqual("UserPromptSubmit", output["hookEventName"])
        context = output["additionalContext"]
        self.assertIn("<codex-dispatch-mode>sub-agent</codex-dispatch-mode>", context)
        self.assertIn("dispatch_mode_meaning: workflow dispatch hint, not current thread role", context)
        self.assertNotIn("<codex-mode>", context)
        self.assertIn('<cowork-runtime host="codex" adapter="codex.spawn_agent">', context)
        self.assertIn("<contract-digest fingerprint=", context)
        self.assertIn("COWORK_ENTRY_CONTRACT_V2", context)
        self.assertIn(".cowork-flow/spec/core/entry.md", context)
        self.assertIn("read_before:", context)
        self.assertIn("<workflow-state>", context)
        self.assertIn("Status: no_task", context)
        self.assertIn("requires creating or starting a task first", context)
        self.assertNotIn("<subagent-notice>", context)

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
                        "输出：中文，分为“可识别信号 / hook 行为 / 风险控制”，最多 400 字。"
                    )
                },
            )

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Status: no_task", context)
        self.assertNotIn("Status: delegated_subtask", context)
        self.assertIn("requires creating or starting a task first", context)

    def test_hook_binds_runtime_context_from_prompt_before_main_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            self._write_runtime_context(root, "rtx_prompt")

            data = self._run_hook(
                root,
                {
                    "session_id": "child-session",
                    "prompt": "cowork_runtime_context_id: rtx_prompt\nDo the work.",
                },
            )
            session = self._runtime_session(root, "codex_child-session")

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Status: delegated_subtask", context)
        self.assertIn("Source: runtime-context:rtx_prompt", context)
        self.assertIn("Task: .cowork-flow/tasks/05-29-demo", context)
        self.assertIn("Agent: cowork-implement", context)
        self.assertIn("Scope: subagent", context)
        self.assertNotIn("requires creating or starting a task first", context)
        self.assertIsNotNone(session)
        self.assertEqual("subagent", session["scope"])
        self.assertEqual("rtx_prompt", session["runtime_context_id"])

    def test_hook_binds_runtime_context_from_structured_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            self._write_runtime_context(root, "rtx_structured")

            data = self._run_hook(
                root,
                {
                    "session_id": "structured-child",
                    "cowork_runtime_context_id": "rtx_structured",
                    "prompt": "This prompt has no role labels.",
                },
            )

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Status: delegated_subtask", context)
        self.assertIn("Source: runtime-context:rtx_structured", context)

    def test_hook_prefers_prompt_host_context_key_over_session_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            self._write_runtime_context(root, "rtx_prompt_key")

            data = self._run_hook(
                root,
                {
                    "session_id": "child-session",
                    "prompt": (
                        "cowork_runtime_context_id: rtx_prompt_key\n"
                        "cowork_host_context_key: codex_prompt_key\n"
                        "Do the work."
                    ),
                },
            )
            session = self._runtime_session(root, "codex_prompt_key")
            runtime_context = self._runtime_context(root, "rtx_prompt_key")
            self.assertFalse(
                (root / ".cowork-flow" / ".runtime" / "sessions" / "codex_child-session.json").exists()
            )

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Status: delegated_subtask", context)
        self.assertIsNotNone(session)
        self.assertIsNotNone(runtime_context)
        self.assertEqual("subagent", session["scope"])
        self.assertEqual("rtx_prompt_key", session["runtime_context_id"])
        self.assertEqual("codex_prompt_key", runtime_context["bound_context_key"])

    def test_hook_invalid_runtime_context_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)

            data = self._run_hook(
                root,
                {
                    "prompt": (
                        "cowork_runtime_context_id: missing_runtime\n"
                        "Task text should not become main no-task bootstrap."
                    )
                },
            )

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Status: delegated_subtask", context)
        self.assertIn("runtime-context-invalid", context)
        self.assertNotIn("requires creating or starting a task first", context)

    def test_hook_closed_runtime_context_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            self._write_runtime_context(root, "rtx_closed")
            script_root = root / ".cowork-flow" / "scripts"
            sys.path.insert(0, str(script_root))
            try:
                paths = importlib.import_module("common.paths")
                flow_store = importlib.import_module("flow.store")
                with flow_store.FlowStore(str(paths.get_db_path(root))) as store:
                    context = store.get_runtime_context("rtx_closed")
                    context["status"] = "closed"
                    store.upsert_runtime_context(context)
            finally:
                self._cleanup_script_imports(script_root)

            data = self._run_hook(
                root,
                {
                    "session_id": "child-session",
                    "prompt": "cowork_runtime_context_id: rtx_closed",
                },
            )

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Status: delegated_subtask", context)
        self.assertIn("runtime-context-invalid:rtx_closed", context)
        self.assertIn("Runtime context is missing, closed, or invalid", context)
        self.assertIn("Do not run start/resume/task start/archive/commit/spawn.", context)
        self.assertNotIn("requires creating or starting a task first", context)

    def test_hook_treats_explorer_brief_as_delegated_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)

            data = self._run_hook(
                root,
                {
                    "prompt": (
                        "Task: inspect route wiring only.\n"
                        "Agent type: explorer\n"
                        "Constraint: do not run project start or resume; read only.\n"
                        "Output: concise findings with line references."
                    )
                },
            )

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Status: no_task", context)
        self.assertNotIn("Status: delegated_subtask", context)

    def test_hook_keeps_unclassified_nonempty_prompt_on_no_task_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)

            data = self._run_hook(root, {"prompt": "Inspect routing notes and report concise findings."})

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Status: no_task", context)
        self.assertRegex(context, r"Source: (missing-context|empty-session)")
        self.assertNotIn("Status: delegated_subtask", context)
        self.assertIn("requires creating or starting a task first", context)

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
            self._write_runtime_session(root, "codex_demo-session", ".cowork-flow/tasks/06-04-demo")

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
            self._write_runtime_session(root, "codex_demo-session", ".cowork-flow/tasks/06-04-demo")

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

    def test_hook_reads_workflow_state_templates_instead_of_workflow_md(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            (root / ".cowork-flow" / "workflow.md").write_text(
                "[workflow-state:no_task]\nwrong source\n[/workflow-state:no_task]\n",
                encoding="utf-8",
            )
            template_file = root / ".cowork-flow" / "spec" / "core" / "state-templates.md"
            template_file.write_text(
                template_file.read_text(encoding="utf-8").replace(
                    "No active task in this session. Read-only Q&A can be answered directly; only process as a delegated subtask when runtime context is bound or fail-closed. Implementation, refactoring, or multi-step work requires creating or starting a task first.",
                    "state-template-source-smoke",
                ),
                encoding="utf-8",
            )

            data = self._run_hook(root, {})

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("state-template-source-smoke", context)
        self.assertNotIn("wrong source", context)

    def test_hook_config_uses_cowork_flow_python_runner(self) -> None:
        hooks = json.loads((TEMPLATE / ".codex" / "hooks.json").read_text(encoding="utf-8"))
        command = hooks["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
        self.assertEqual(".cowork-flow/run python .codex/hooks/inject-workflow-state.py", command)
        self.assertFalse(command.startswith("python "))

    def test_hook_config_command_executes_without_bare_python(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            self._write_runtime_context(root, "rtx_hook_command")
            hooks = json.loads((root / ".codex" / "hooks.json").read_text(encoding="utf-8"))
            command = hooks["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]

            command_parts = shlex.split(command)
            if os.name == "nt":
                command_parts[0] = str(root / ".cowork-flow" / "run.cmd")
            result = subprocess.run(
                command_parts,
                input=json.dumps(
                    {
                        "cwd": str(root),
                        "session_id": "child-session",
                        "prompt": "cowork_runtime_context_id: rtx_hook_command",
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

    def test_hook_resolves_active_task_from_codex_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            task_dir = root / ".cowork-flow" / "tasks" / "05-29-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text('{"status": "in_progress"}\n', encoding="utf-8")
            self._write_runtime_session(root, "codex_demo-session", ".cowork-flow/tasks/05-29-demo")

            data = self._run_hook(root, {"session_id": "demo-session"})

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Task: .cowork-flow/tasks/05-29-demo", context)
        self.assertIn("Status: in_progress", context)
        self.assertIn("dispatches cowork-implement", context)

    def test_hook_reads_flow_only_active_task_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            task_dir = root / ".cowork-flow" / "tasks" / "05-29-demo"
            task_dir.mkdir(parents=True)
            self._write_flow_task(root, artifact_dir="05-29-demo", status="review")
            self._write_runtime_session(root, "codex_demo-session", ".cowork-flow/tasks/05-29-demo")

            data = self._run_hook(root, {"session_id": "demo-session"})

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Task: .cowork-flow/tasks/05-29-demo", context)
        self.assertIn("Status: review", context)
        self.assertNotIn("Status: stale", context)

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
        self.assertIn("<codex-dispatch-mode>inline</codex-dispatch-mode>", context)
        self.assertNotIn("<codex-mode>", context)

    def test_hook_emits_runtime_context_identity_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)

            data = self._run_hook(root, {})

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("<codex-runtime>", context)
        self.assertIn(
            "runtime_context_identity: formal subagent sessions bind before workflow-state injection",
            context,
        )
        self.assertNotIn(LEGACY_POST_ACK, context)

    def test_hook_ignores_unknown_codex_runtime_config_safely(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)
            (root / ".cowork-flow" / "config.yaml").write_text(
                "codex:\n  dispatch_mode: \"sub-agent\"\n  unknown_runtime_value: 12345\n",
                encoding="utf-8",
            )

            data = self._run_hook(root, {})

        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("<codex-dispatch-mode>sub-agent</codex-dispatch-mode>", context)
        self.assertIn("Status: no_task", context)
        self.assertNotIn(LEGACY_POST_ACK, context)

    def test_hook_contract_digest_fingerprint_tracks_spec_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_project(root)

            before = self._run_hook(root, {})["hookSpecificOutput"]["additionalContext"]
            spec_file = root / ".cowork-flow" / "spec" / "core" / "entry.md"
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
            Path(".codex/hooks/inject-workflow-state.py"),
            Path(".cowork-flow/scripts/common/config.py"),
            Path(".cowork-flow/scripts/common/active_task.py"),
            Path(".cowork-flow/scripts/common/entry_classifier.py"),
            Path(".cowork-flow/scripts/common/inject_workflow_state.py"),
            Path(".cowork-flow/spec/core/state-templates.md"),
        ):
            root_text = (ROOT / rel).read_text(encoding="utf-8")
            template_text = (TEMPLATE / rel).read_text(encoding="utf-8")
            self.assertEqual(root_text, template_text, f"{rel} root/template mismatch")


if __name__ == "__main__":
    unittest.main()
