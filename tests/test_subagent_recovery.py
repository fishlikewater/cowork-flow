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
SAMPLE_PLAN = ROOT / "tests" / "fixtures" / "agent-team" / "sample-plan.md"


class SubagentRecoveryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        shutil.copytree(TEMPLATE, self.repo)
        self.runner = self.repo / ".cowork-flow" / "scripts" / "run.py"
        self.agent_team = self.repo / ".cowork-flow" / "scripts" / "agent_team.py"
        self.task_dir = self.repo / ".cowork-flow" / "tasks" / "05-21-demo"
        self.task_dir.mkdir(parents=True)
        (self.task_dir / "prd.md").write_text("# Demo\n", encoding="utf-8")
        for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
            (self.task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")
        self.plan_file = self.repo / ".cowork-flow" / "plans" / "sample-plan.md"
        self.plan_file.parent.mkdir(parents=True, exist_ok=True)
        self.plan_file.write_text(SAMPLE_PLAN.read_text(encoding="utf-8"), encoding="utf-8")
        (self.repo / ".cowork-flow" / "config.yaml").write_text(
            "agent_team:\n  enabled: true\n",
            encoding="utf-8",
        )

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

    def prepare(self) -> Path:
        result = self.run_agent_team("prepare", str(self.task_dir), "--plan", str(self.plan_file))
        self.assertEqual(0, result.returncode, result.stderr)
        coordinator_context = self.task_dir / "agent-team" / "coordinator.context.json"
        self.assertTrue(coordinator_context.is_file())
        return coordinator_context

    def test_agent_team_prepare_emits_coordinator_context(self) -> None:
        context_file = self.prepare()

        context = json.loads(context_file.read_text(encoding="utf-8"))

        self.assertEqual("coordinator", context["mode"])
        self.assertEqual(".cowork-flow/tasks/05-21-demo", context["taskDir"])
        self.assertIn("agent-team:next", context["capabilities"])
        self.assertIn("agent-team:collect", context["capabilities"])

    def test_no_context_cannot_run_agent_team_next(self) -> None:
        self.prepare()

        result = self.run_runner("agent-team", "next", str(self.task_dir))

        self.assertNotEqual(0, result.returncode)
        self.assertIn("requires coordinator execution context", result.stderr)

    def test_coordinator_context_can_run_agent_team_next(self) -> None:
        context_file = self.prepare()

        result = self.run_runner("--context-file", str(context_file), "agent-team", "next", str(self.task_dir))

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("T001-implementer", result.stdout)

    def test_coordinator_context_cannot_write_worker_report(self) -> None:
        context_file = self.prepare()
        payload = self.repo / "payload.json"
        payload.write_text('{"changedFiles": []}\n', encoding="utf-8")

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

        self.assertNotEqual(0, result.returncode)
        self.assertIn("worker-report requires worker execution context", result.stderr)

    def test_generic_subagent_init_and_resume_are_scoped(self) -> None:
        result = self.run_runner(
            "subagent",
            "init",
            "--title",
            "Investigate start filtering",
            "--role",
            "explorer",
            "--source",
            "auto",
            "--goal",
            "Analyze start preflight without modifying files",
            "--allowed-context",
            ".agent/skills/start/SKILL.md",
        )

        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        context_file = self.repo / payload["contextFile"]
        self.assertTrue(context_file.is_file())
        self.assertTrue((context_file.parent / "brief.md").is_file())
        self.assertTrue((context_file.parent / "status.json").is_file())
        self.assertTrue((context_file.parent / "events.jsonl").is_file())

        resume = self.run_runner("--context-file", str(context_file), "resume")

        self.assertEqual(0, resume.returncode, resume.stderr)
        self.assertIn("COWORK-FLOW SUBAGENT RESUME", resume.stdout)
        self.assertIn("Investigate start filtering", resume.stdout)
        self.assertIn("Analyze start preflight", resume.stdout)
        self.assertIn(".agent/skills/start/SKILL.md", resume.stdout)
        self.assertNotIn("RESUME CHECKLIST", resume.stdout)
        self.assertNotIn("CURRENT TASK", resume.stdout)

    def test_generic_subagent_context_cannot_run_agent_team_collect(self) -> None:
        self.prepare()
        result = self.run_runner(
            "subagent",
            "init",
            "--title",
            "Generic review",
            "--role",
            "reviewer",
        )
        self.assertEqual(0, result.returncode, result.stderr)
        context_file = self.repo / json.loads(result.stdout)["contextFile"]

        collect = self.run_runner(
            "--context-file",
            str(context_file),
            "agent-team",
            "collect",
            str(self.task_dir),
            "--assignment",
            "T001-implementer",
        )

        self.assertNotEqual(0, collect.returncode)
        self.assertIn("requires coordinator execution context", collect.stderr)


if __name__ == "__main__":
    unittest.main()
