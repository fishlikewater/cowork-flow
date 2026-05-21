from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
SAMPLE_PLAN = ROOT / "tests" / "fixtures" / "agent-team" / "sample-plan.md"


class AgentTeamPlanParserTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        shutil.copytree(TEMPLATE, self.repo)
        (self.repo / ".cowork-flow" / "config.yaml").write_text(
            "agent_team:\n  enabled: true\n",
            encoding="utf-8",
        )
        self.script = self.repo / ".cowork-flow" / "scripts" / "agent_team.py"
        self.task_dir = self.repo / ".cowork-flow" / "tasks" / "05-21-demo"
        self.task_dir.mkdir(parents=True)
        (self.task_dir / "prd.md").write_text("# Demo\n", encoding="utf-8")
        for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
            (self.task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")
        self.plan_file = self.repo / ".cowork-flow" / "plans" / "sample-plan.md"
        self.plan_file.parent.mkdir(parents=True, exist_ok=True)
        self.plan_file.write_text(SAMPLE_PLAN.read_text(encoding="utf-8"), encoding="utf-8")

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

    def test_prepare_parses_standard_plan_and_writes_runtime_files(self) -> None:
        result = self.run_agent_team("prepare", str(self.task_dir), "--plan", str(self.plan_file))

        self.assertEqual(0, result.returncode, result.stderr)
        runtime = self.task_dir / "agent-team"
        self.assertTrue((runtime / "dispatch-plan.yaml").is_file())
        self.assertTrue((runtime / "status.json").is_file())
        self.assertTrue((runtime / "metrics.json").is_file())
        self.assertTrue((runtime / "adapters" / "codex.json").is_file())
        self.assertTrue((runtime / "assignments" / "T001-implementer.md").is_file())
        dispatch = (runtime / "dispatch-plan.yaml").read_text(encoding="utf-8")
        self.assertIn("T001-implementer", dispatch)
        self.assertIn("T001-spec-reviewer", dispatch)
        self.assertIn("T001-quality-reviewer", dispatch)
        self.assertIn("recommended_agent: implementer", dispatch)

    def test_prepare_marks_file_overlap_dependency(self) -> None:
        result = self.run_agent_team("prepare", str(self.task_dir), "--plan", str(self.plan_file))

        self.assertEqual(0, result.returncode, result.stderr)
        dispatch = (self.task_dir / "agent-team" / "dispatch-plan.yaml").read_text(encoding="utf-8")
        self.assertIn("reason: file-overlap", dispatch)
        self.assertIn("depends_on_task: T001", dispatch)

    def test_prepare_rejects_unparseable_plan(self) -> None:
        self.plan_file.write_text("# Broken\n\nNo task headings here.\n", encoding="utf-8")

        result = self.run_agent_team("prepare", str(self.task_dir), "--plan", str(self.plan_file))

        self.assertNotEqual(0, result.returncode)
        self.assertIn("unable to parse", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
