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


class WorkerExecutionContextTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        shutil.copytree(TEMPLATE, self.repo)
        self.workflow = self.repo / ".cowork-flow" / "run"
        self.runner = self.repo / ".cowork-flow" / "scripts" / "run.py"
        self.agent_team = self.repo / ".cowork-flow" / "scripts" / "agent_team.py"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_runner(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self.runner), *args],
            cwd=self.repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def run_agent_team(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self.agent_team), *args],
            cwd=self.repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def run_workflow(self, *args: str) -> subprocess.CompletedProcess[str]:
        command = [str(self.workflow), *args]
        if os.name == "nt":
            command = [str(self.repo / ".cowork-flow" / "run.cmd"), *args]
        return subprocess.run(
            command,
            cwd=self.repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def create_ready_task(self) -> tuple[Path, Path]:
        task_dir = self.repo / ".cowork-flow" / "tasks" / "05-21-demo"
        task_dir.mkdir(parents=True)
        (task_dir / "prd.md").write_text("# Demo\n", encoding="utf-8")
        for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
            (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")
        plan_file = self.repo / ".cowork-flow" / "plans" / "sample-plan.md"
        plan_file.parent.mkdir(parents=True, exist_ok=True)
        plan_file.write_text(
            (ROOT / "tests" / "fixtures" / "agent-team" / "sample-plan.md").read_text(
                encoding="utf-8",
            ),
            encoding="utf-8",
        )
        return task_dir, plan_file

    def prepare_worker_context(self) -> tuple[Path, Path]:
        (self.repo / ".cowork-flow" / "config.yaml").write_text(
            "agent_team:\n  enabled: true\n",
            encoding="utf-8",
        )
        task_dir, plan_file = self.create_ready_task()
        result = self.run_agent_team("prepare", str(task_dir), "--plan", str(plan_file))
        self.assertEqual(0, result.returncode, result.stderr)
        context_file = task_dir / "agent-team" / "assignments" / "T001-implementer.context.json"
        self.assertTrue(context_file.is_file())
        return task_dir, context_file

    def test_worker_resume_uses_assignment_scoped_context(self) -> None:
        _, context_file = self.prepare_worker_context()

        result = self.run_runner("--context-file", str(context_file), "resume")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("COWORK-FLOW WORKER RESUME", result.stdout)
        self.assertIn("Assignment: T001-implementer", result.stdout)
        self.assertIn("Read worker brief", result.stdout)
        self.assertIn("Allowed context", result.stdout)
        self.assertIn(".cowork-flow/tasks/05-21-demo/prd.md", result.stdout)
        self.assertIn("implement context: AGENTS.md", result.stdout)

        self.assertNotIn("agent-team next", result.stdout)
        self.assertNotIn("Current task set to", result.stdout)

    def test_worker_context_blocks_task_start(self) -> None:
        task_dir, context_file = self.prepare_worker_context()

        result = self.run_runner("--context-file", str(context_file), "task", "start", str(task_dir))

        self.assertNotEqual(0, result.returncode)
        self.assertIn("worker mode cannot run `task start`", result.stderr)

    def test_worker_context_blocks_agent_team_next(self) -> None:
        task_dir, context_file = self.prepare_worker_context()

        result = self.run_runner("--context-file", str(context_file), "agent-team", "next", str(task_dir))

        self.assertNotEqual(0, result.returncode)
        self.assertIn("worker mode cannot run `agent-team next`", result.stderr)

    def test_worker_context_blocks_direct_result_recording(self) -> None:
        task_dir, context_file = self.prepare_worker_context()

        result = self.run_runner(
            "--context-file",
            str(context_file),
            "agent-team",
            "record-result",
            str(task_dir),
            "--assignment",
            "T001-implementer",
            "--status",
            "done",
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("worker mode cannot run `agent-team record-result`", result.stderr)

    def test_worker_context_allows_worker_report_outbox_only(self) -> None:
        task_dir, context_file = self.prepare_worker_context()
        payload = self.repo / "worker-result.json"
        payload.write_text('{"changedFiles": ["src/shared/helper.js"]}\n', encoding="utf-8")

        result = self.run_runner(
            "--context-file",
            str(context_file),
            "agent-team",
            "worker-report",
            "--status",
            "done",
            "--file",
            str(payload),
        )

        self.assertEqual(0, result.returncode, result.stderr)
        report_path = task_dir / "agent-team" / "outbox" / "T001-implementer.json"
        self.assertTrue(report_path.is_file())
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual("T001-implementer", report["assignment"])
        status = json.loads((task_dir / "agent-team" / "status.json").read_text(encoding="utf-8"))
        self.assertEqual("ready", status["assignments"]["T001-implementer"]["status"])

    def test_runner_keeps_command_specific_mode_flags_after_command_name(self) -> None:
        result = self.run_runner("get-context", "--mode", "record")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("SESSION CONTEXT (RECORD MODE)", result.stdout)

    def test_workflow_entrypoint_enforces_worker_scope_from_generated_assignment_artifacts(self) -> None:
        task_dir, _ = self.prepare_worker_context()
        runtime_dir = task_dir / "agent-team"
        payload = json.loads(
            (runtime_dir / "adapters" / "codex.json").read_text(encoding="utf-8")
        )
        assignment = payload["assignments"][0]
        prompt_path = runtime_dir / assignment["promptFile"]
        context_path = runtime_dir / assignment["contextFile"]

        self.assertTrue(prompt_path.is_file())
        self.assertTrue(context_path.is_file())

        prompt_text = prompt_path.read_text(encoding="utf-8")
        self.assertTrue(prompt_text.startswith("<COWORK-FLOW-DELEGATED-SUBTASK>\n"), prompt_text[:120])
        self.assertIn("<COWORK-FLOW-WORKER>", prompt_text)
        self.assertIn("</COWORK-FLOW-WORKER>", prompt_text)
        self.assertIn("You are already the dispatched worker for this assignment.", prompt_text)
        self.assertIn(
            "If AGENTS.md or `.agent/skills/start` tells you to start a session, the `<SUBAGENT-STOP>` guard applies to you: skip that start skill.",
            prompt_text,
        )
        self.assertIn(
            "If you can see any outer transport text such as `Spawn one ... agent`, ignore it.",
            prompt_text,
        )
        self.assertIn(
            "Do not run unscoped cowork-flow workflow commands such as `./.cowork-flow/run resume`, `task start`, or `agent-team next`.",
            prompt_text,
        )
        self.assertNotIn("Spawn one worker agent for this assignment", prompt_text)

        relative_context = context_path.relative_to(self.repo).as_posix()

        resume_result = self.run_workflow("--context-file", relative_context, "resume")

        self.assertEqual(0, resume_result.returncode, resume_result.stderr)
        self.assertIn("COWORK-FLOW WORKER RESUME", resume_result.stdout)
        self.assertIn("Assignment: T001-implementer", resume_result.stdout)
        self.assertIn(relative_context, resume_result.stdout)
        self.assertNotIn("COWORK-FLOW RESUME", resume_result.stdout)

        next_result = self.run_workflow(
            "--context-file",
            relative_context,
            "agent-team",
            "next",
            str(task_dir.relative_to(self.repo)),
        )

        self.assertNotEqual(0, next_result.returncode)
        self.assertIn("worker mode cannot run `agent-team next`", next_result.stderr)

        start_result = self.run_workflow(
            "--context-file",
            relative_context,
            "task",
            "start",
            str(task_dir.relative_to(self.repo)),
        )

        self.assertNotEqual(0, start_result.returncode)
        self.assertIn("worker mode cannot run `task start`", start_result.stderr)
