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
SAMPLE_PLAN = ROOT / "tests" / "fixtures" / "agent-team" / "sample-plan.md"


class AgentTeamStateMachineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        shutil.copytree(TEMPLATE, self.repo)
        self.script = self.repo / ".cowork-flow" / "scripts" / "agent_team.py"
        self.task_dir = self.repo / ".cowork-flow" / "tasks" / "05-21-demo"
        self.task_dir.mkdir(parents=True)
        (self.task_dir / "prd.md").write_text("# Demo\n", encoding="utf-8")
        for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
            (self.task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")
        self.plan_file = self.repo / ".cowork-flow" / "plans" / "sample-plan.md"
        self.plan_file.parent.mkdir(parents=True, exist_ok=True)
        self.plan_file.write_text(SAMPLE_PLAN.read_text(encoding="utf-8"), encoding="utf-8")
        self.run_agent_team("prepare", str(self.task_dir), "--plan", str(self.plan_file))

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

    def status_data(self) -> dict:
        return json.loads((self.task_dir / "agent-team" / "status.json").read_text(encoding="utf-8"))

    def metrics_data(self) -> dict:
        return json.loads((self.task_dir / "agent-team" / "metrics.json").read_text(encoding="utf-8"))

    def result_payload(self) -> Path:
        path = self.repo / "result.json"
        path.write_text('{"changedFiles": ["src/shared/helper.js"]}\n', encoding="utf-8")
        return path

    def test_next_outputs_ready_assignments_only(self) -> None:
        result = self.run_agent_team("next", str(self.task_dir))

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("T001-implementer", result.stdout)
        self.assertIn("T003-implementer", result.stdout)
        self.assertNotIn("T001-spec-reviewer", result.stdout)

    def test_record_result_appends_attempt_history_and_unblocks_spec_review(self) -> None:
        result = self.run_agent_team(
            "record-result",
            str(self.task_dir),
            "--assignment",
            "T001-implementer",
            "--status",
            "done",
            "--file",
            str(self.result_payload()),
        )

        self.assertEqual(0, result.returncode, result.stderr)
        status = self.status_data()
        self.assertEqual("done", status["assignments"]["T001-implementer"]["status"])
        self.assertEqual(1, status["assignments"]["T001-implementer"]["attempts"])
        self.assertEqual("ready", status["assignments"]["T001-spec-reviewer"]["status"])
        metrics = self.metrics_data()
        self.assertEqual(1, metrics["attempts"])
        self.assertEqual(1, metrics["successfulAssignments"])

    def test_record_review_approved_unblocks_quality_review(self) -> None:
        self.run_agent_team(
            "record-result",
            str(self.task_dir),
            "--assignment",
            "T001-implementer",
            "--status",
            "done",
            "--file",
            str(self.result_payload()),
        )
        review = self.repo / "review.json"
        review.write_text('{"decision": "approved"}\n', encoding="utf-8")

        result = self.run_agent_team(
            "record-review",
            str(self.task_dir),
            "--assignment",
            "T001-spec-reviewer",
            "--status",
            "approved",
            "--file",
            str(review),
        )

        self.assertEqual(0, result.returncode, result.stderr)
        status = self.status_data()
        self.assertEqual("approved", status["assignments"]["T001-spec-reviewer"]["status"])
        self.assertEqual("ready", status["assignments"]["T001-quality-reviewer"]["status"])

    def test_retry_escalates_after_max_attempts(self) -> None:
        for _ in range(3):
            result = self.run_agent_team(
                "retry",
                str(self.task_dir),
                "--assignment",
                "T001-implementer",
                "--reason",
                "failed verification",
            )
            self.assertEqual(0, result.returncode, result.stderr)

        status = self.status_data()
        self.assertEqual("needs-coordinator-decision", status["assignments"]["T001-implementer"]["status"])
        self.assertEqual(3, status["assignments"]["T001-implementer"]["attempts"])

    def test_complete_fails_when_reviews_are_pending(self) -> None:
        result = self.run_agent_team("complete", str(self.task_dir))

        self.assertNotEqual(0, result.returncode)
        self.assertIn("pending", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
