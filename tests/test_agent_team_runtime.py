from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"


class AgentTeamRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        shutil.copytree(TEMPLATE, self.repo)
        self.script = self.repo / ".cowork-flow" / "scripts" / "agent_team.py"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_agent_team(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self.script), *args],
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

    def test_init_creates_project_config_when_missing(self) -> None:
        shutil.rmtree(self.repo / ".cowork-flow" / "agent-team")

        result = self.run_agent_team("init")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((self.repo / ".cowork-flow" / "agent-team" / "agents.yaml").is_file())
        self.assertTrue((self.repo / ".cowork-flow" / "agent-team" / "adapters.yaml").is_file())
        self.assertTrue((self.repo / ".cowork-flow" / "agent-team" / "policy.yaml").is_file())
        self.assertIn("initialized", result.stdout)

    def test_init_preserves_existing_project_config(self) -> None:
        agents = self.repo / ".cowork-flow" / "agent-team" / "agents.yaml"
        agents.write_text("custom: true\n", encoding="utf-8")

        result = self.run_agent_team("init")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("custom: true\n", agents.read_text(encoding="utf-8"))
        self.assertIn("preserved", result.stdout)

    def test_prepare_is_blocked_when_agent_team_is_disabled_by_default(self) -> None:
        task_dir, plan_file = self.create_ready_task()

        result = self.run_agent_team("prepare", str(task_dir), "--plan", str(plan_file))

        self.assertNotEqual(0, result.returncode)
        self.assertIn("agent_team.enabled", result.stderr)
        self.assertFalse((task_dir / "agent-team").exists())

    def test_runtime_commands_are_blocked_when_agent_team_is_disabled_by_default(self) -> None:
        task_dir, plan_file = self.create_ready_task()
        cases: tuple[tuple[str, ...], ...] = (
            ("prepare", str(task_dir), "--plan", str(plan_file)),
            ("status", str(task_dir)),
            ("next", str(task_dir)),
            ("record-spawn", str(task_dir), "--assignment", "impl-1", "--task-name", "/root/impl-1"),
            ("record-result", str(task_dir), "--assignment", "impl-1", "--status", "done"),
            ("record-review", str(task_dir), "--assignment", "impl-1", "--status", "approved"),
            ("collect", str(task_dir), "--assignment", "impl-1"),
            ("retry", str(task_dir), "--assignment", "impl-1", "--reason", "needs_context"),
            ("complete", str(task_dir)),
        )

        coordinator_commands = {
            "next",
            "record-spawn",
            "record-result",
            "record-review",
            "collect",
            "retry",
            "complete",
        }
        for args in cases:
            with self.subTest(command=args[0]):
                command_args = args
                if args[0] in coordinator_commands:
                    command_args = ("--execution-mode", "coordinator", "--execution-task-dir", str(task_dir), *args)
                result = self.run_agent_team(*command_args)

                self.assertNotEqual(0, result.returncode)
                self.assertIn("agent_team.enabled", result.stderr)

    def test_prepare_runs_when_agent_team_is_enabled(self) -> None:
        (self.repo / ".cowork-flow" / "config.yaml").write_text(
            "agent_team:\n  enabled: true\n",
            encoding="utf-8",
        )
        task_dir, plan_file = self.create_ready_task()

        result = self.run_agent_team("prepare", str(task_dir), "--plan", str(plan_file))

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((task_dir / "agent-team" / "status.json").is_file())

    def test_prepare_writes_structured_codex_spawn_metadata(self) -> None:
        (self.repo / ".cowork-flow" / "config.yaml").write_text(
            "agent_team:\n  enabled: true\n",
            encoding="utf-8",
        )
        task_dir, plan_file = self.create_ready_task()

        result = self.run_agent_team("prepare", str(task_dir), "--plan", str(plan_file))

        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(
            (task_dir / "agent-team" / "adapters" / "codex.json").read_text(encoding="utf-8")
        )
        self.assertEqual("codex", payload["adapter"])
        self.assertEqual("coordinator-dispatched", payload["mode"])
        self.assertEqual(True, payload["spawnDefaults"]["spawnAgent"])
        self.assertEqual("none", payload["spawnDefaults"]["forkTurns"])
        self.assertEqual("assignment-file", payload["spawnDefaults"]["promptSource"])
        self.assertEqual(
            ["nickname", "task_name", "assignmentId"],
            payload["spawnResult"]["displayNamePreference"],
        )
        self.assertEqual(
            ["task_name", "nickname"],
            payload["spawnResult"]["captureFields"],
        )
        self.assertIn("record-spawn", payload["spawnResult"]["recordSpawnCommandTemplate"])
        self.assertEqual("worker", payload["assignments"][0]["agentType"])
        self.assertEqual("implementer", payload["assignments"][0]["recommendedAgent"])
        self.assertEqual(
            "implement_add_shared_helper",
            payload["assignments"][0]["suggestedTaskName"],
        )
        self.assertEqual("assignments/T001-implementer.md", payload["assignments"][0]["promptFile"])
        self.assertEqual("assignments/T001-implementer.context.json", payload["assignments"][0]["contextFile"])
        context_file = task_dir / "agent-team" / "assignments" / "T001-implementer.context.json"
        self.assertTrue(context_file.is_file())
        worker_context = json.loads(context_file.read_text(encoding="utf-8"))
        self.assertEqual("worker", worker_context["mode"])
        self.assertEqual(".cowork-flow/tasks/05-21-demo", worker_context["taskDir"])
        self.assertEqual("T001-implementer", worker_context["assignment"])
        self.assertEqual(
            ".cowork-flow/tasks/05-21-demo/agent-team/assignments/T001-implementer.md",
            worker_context["promptFile"],
        )


if __name__ == "__main__":
    unittest.main()
