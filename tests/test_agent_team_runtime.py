from __future__ import annotations

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
            ("record-result", str(task_dir), "--assignment", "impl-1", "--status", "done"),
            ("record-review", str(task_dir), "--assignment", "impl-1", "--status", "approved"),
            ("retry", str(task_dir), "--assignment", "impl-1", "--reason", "needs_context"),
            ("complete", str(task_dir)),
        )

        for args in cases:
            with self.subTest(command=args[0]):
                result = self.run_agent_team(*args)

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


if __name__ == "__main__":
    unittest.main()
