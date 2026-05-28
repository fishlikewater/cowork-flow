from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
SAMPLE_PLAN = ROOT / "tests" / "fixtures" / "agent-team" / "sample-plan.md"


class AgentTeamStateMachineTest(unittest.TestCase):
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
        self.run_agent_team("prepare", str(self.task_dir), "--plan", str(self.plan_file))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_agent_team(self, *args: str) -> subprocess.CompletedProcess[str]:
        command_args = list(args)
        coordinator_commands = {
            "next",
            "record-spawn",
            "record-result",
            "record-review",
            "collect",
            "retry",
            "complete",
        }
        if command_args and command_args[0] in coordinator_commands:
            context_file = self.task_dir / "agent-team" / "coordinator.context.json"
            if context_file.is_file():
                command_args = ["--execution-context-file", str(context_file), *command_args]
        return subprocess.run(
            [sys.executable, str(self.script), *command_args],
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

    def context_file(self, assignment_id: str) -> Path:
        path = self.task_dir / "agent-team" / "assignments" / f"{assignment_id}.context.json"
        self.assertTrue(path.is_file())
        return path

    def test_next_outputs_ready_assignments_only(self) -> None:
        result = self.run_agent_team("next", str(self.task_dir))

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("T001-implementer", result.stdout)
        self.assertIn("T003-implementer", result.stdout)
        self.assertNotIn("T001-spec-reviewer", result.stdout)

    def test_record_spawn_persists_host_nickname_and_status_prefers_it(self) -> None:
        result = self.run_agent_team(
            "record-spawn",
            str(self.task_dir),
            "--assignment",
            "T001-implementer",
            "--task-name",
            "/root/t001_implementer",
            "--nickname",
            "Hilbert",
        )

        self.assertEqual(0, result.returncode, result.stderr)
        status = self.status_data()
        assignment = status["assignments"]["T001-implementer"]
        self.assertEqual("/root/t001_implementer", assignment["spawn_task_name"])
        self.assertEqual("Hilbert", assignment["spawn_nickname"])
        self.assertEqual("in_progress", assignment["status"])

        next_result = self.run_agent_team("next", str(self.task_dir))

        self.assertEqual(0, next_result.returncode, next_result.stderr)
        self.assertNotIn("T001-implementer", next_result.stdout)

        status_result = self.run_agent_team("status", str(self.task_dir), "--verbose")

        self.assertEqual(0, status_result.returncode, status_result.stderr)
        self.assertIn("T001-implementer", status_result.stdout)
        self.assertIn("label=Hilbert", status_result.stdout)
        self.assertIn("task_name=/root/t001_implementer", status_result.stdout)

    def test_record_spawn_rejects_pending_assignment(self) -> None:
        result = self.run_agent_team(
            "record-spawn",
            str(self.task_dir),
            "--assignment",
            "T001-spec-reviewer",
            "--task-name",
            "/root/t001_spec_reviewer",
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("assignment is not ready", result.stderr)
        status = self.status_data()
        assignment = status["assignments"]["T001-spec-reviewer"]
        self.assertEqual("pending", assignment["status"])
        self.assertIsNone(assignment["spawn_task_name"])

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

    def test_worker_report_writes_assignment_outbox_without_mutating_status(self) -> None:
        self.run_agent_team(
            "record-spawn",
            str(self.task_dir),
            "--assignment",
            "T001-implementer",
            "--task-name",
            "/root/t001_implementer",
        )

        result = self.run_agent_team(
            "--execution-context-file",
            str(self.context_file("T001-implementer")),
            "worker-report",
            "--status",
            "done",
            "--file",
            str(self.result_payload()),
        )

        self.assertEqual(0, result.returncode, result.stderr)
        outbox = self.task_dir / "agent-team" / "outbox" / "T001-implementer.json"
        self.assertTrue(outbox.is_file())
        report = json.loads(outbox.read_text(encoding="utf-8"))
        self.assertEqual("T001-implementer", report["assignment"])
        self.assertEqual("implementer", report["role"])
        self.assertEqual("done", report["status"])
        self.assertEqual({"changedFiles": ["src/shared/helper.js"]}, report["payload"])
        status = self.status_data()
        self.assertEqual("in_progress", status["assignments"]["T001-implementer"]["status"])
        self.assertEqual(0, status["assignments"]["T001-implementer"]["attempts"])
        self.assertFalse((self.task_dir / "agent-team" / "results" / "T001-implementer-attempt-1.json").exists())

    def test_worker_report_cannot_write_for_another_assignment(self) -> None:
        result = self.run_agent_team(
            "--execution-context-file",
            str(self.context_file("T001-implementer")),
            "worker-report",
            "--assignment",
            "T001-spec-reviewer",
            "--status",
            "done",
            "--file",
            str(self.result_payload()),
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("worker-report assignment must match worker context", result.stderr)
        self.assertFalse((self.task_dir / "agent-team" / "outbox" / "T001-spec-reviewer.json").exists())

    def test_collect_requires_worker_outbox_not_chat_answer(self) -> None:
        result = self.run_agent_team(
            "collect",
            str(self.task_dir),
            "--assignment",
            "T001-implementer",
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("worker report not found", result.stderr)
        status = self.status_data()
        self.assertEqual("ready", status["assignments"]["T001-implementer"]["status"])
        self.assertEqual(0, status["assignments"]["T001-implementer"]["attempts"])

    def test_collect_advances_status_from_worker_outbox(self) -> None:
        self.run_agent_team(
            "record-spawn",
            str(self.task_dir),
            "--assignment",
            "T001-implementer",
            "--task-name",
            "/root/t001_implementer",
        )
        report = self.run_agent_team(
            "--execution-context-file",
            str(self.context_file("T001-implementer")),
            "worker-report",
            "--status",
            "done",
            "--file",
            str(self.result_payload()),
        )
        self.assertEqual(0, report.returncode, report.stderr)

        result = self.run_agent_team(
            "collect",
            str(self.task_dir),
            "--assignment",
            "T001-implementer",
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("collected T001-implementer status=done", result.stdout)
        status = self.status_data()
        self.assertEqual("done", status["assignments"]["T001-implementer"]["status"])
        self.assertEqual(1, status["assignments"]["T001-implementer"]["attempts"])
        self.assertEqual("ready", status["assignments"]["T001-spec-reviewer"]["status"])
        copied = self.task_dir / "agent-team" / "results" / "T001-implementer-attempt-1.json"
        self.assertEqual(
            {"changedFiles": ["src/shared/helper.js"]},
            json.loads(copied.read_text(encoding="utf-8")),
        )

    def test_parallel_collect_preserves_all_assignment_state(self) -> None:
        payloads = {}
        for assignment_id in ("T001-implementer", "T003-implementer"):
            payload = self.repo / f"{assignment_id}.json"
            payload.write_text(json.dumps({"assignment": assignment_id}) + "\n", encoding="utf-8")
            payloads[assignment_id] = payload
            report = self.run_agent_team(
                "--execution-context-file",
                str(self.context_file(assignment_id)),
                "worker-report",
                "--status",
                "done",
                "--file",
                str(payload),
            )
            self.assertEqual(0, report.returncode, report.stderr)

        def collect(assignment_id: str) -> subprocess.CompletedProcess[str]:
            return self.run_agent_team("collect", str(self.task_dir), "--assignment", assignment_id)

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(collect, payloads))

        for result in results:
            self.assertEqual(0, result.returncode, result.stderr)

        status = self.status_data()
        self.assertEqual("done", status["assignments"]["T001-implementer"]["status"])
        self.assertEqual("done", status["assignments"]["T003-implementer"]["status"])
        self.assertEqual("ready", status["assignments"]["T001-spec-reviewer"]["status"])
        self.assertEqual("ready", status["assignments"]["T003-spec-reviewer"]["status"])
        metrics = self.metrics_data()
        self.assertEqual(2, metrics["attempts"])
        self.assertEqual(2, metrics["successfulAssignments"])
        for assignment_id in payloads:
            copied = self.task_dir / "agent-team" / "results" / f"{assignment_id}-attempt-1.json"
            self.assertEqual(
                {"assignment": assignment_id},
                json.loads(copied.read_text(encoding="utf-8")),
            )

    def test_collect_rejects_pending_assignment_outbox(self) -> None:
        outbox_dir = self.task_dir / "agent-team" / "outbox"
        outbox_dir.mkdir(exist_ok=True)
        (outbox_dir / "T001-spec-reviewer.json").write_text(
            '{"version": 1, "source": "worker-report", "assignment": "T001-spec-reviewer", "role": "spec-reviewer", "status": "approved", "payload": {"decision": "approved"}}\n',
            encoding="utf-8",
        )

        result = self.run_agent_team(
            "collect",
            str(self.task_dir),
            "--assignment",
            "T001-spec-reviewer",
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("assignment is not ready or in_progress", result.stderr)
        status = self.status_data()
        self.assertEqual("pending", status["assignments"]["T001-spec-reviewer"]["status"])
        self.assertEqual(0, status["assignments"]["T001-spec-reviewer"]["attempts"])

    def test_worker_report_rejects_pending_assignment(self) -> None:
        review = self.repo / "review.json"
        review.write_text('{"decision": "approved"}\n', encoding="utf-8")

        result = self.run_agent_team(
            "--execution-context-file",
            str(self.context_file("T001-spec-reviewer")),
            "worker-report",
            "--status",
            "approved",
            "--file",
            str(review),
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("assignment is not ready or in_progress", result.stderr)
        self.assertFalse((self.task_dir / "agent-team" / "outbox" / "T001-spec-reviewer.json").exists())
    def test_worker_report_approved_review_requires_approved_payload(self) -> None:
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

        result = self.run_agent_team(
            "--execution-context-file",
            str(self.context_file("T001-spec-reviewer")),
            "worker-report",
            "--status",
            "approved",
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("approved review requires --file", result.stderr)
        self.assertFalse((self.task_dir / "agent-team" / "outbox" / "T001-spec-reviewer.json").exists())

    def test_record_result_rejects_review_statuses(self) -> None:
        result = self.run_agent_team(
            "record-result",
            str(self.task_dir),
            "--assignment",
            "T001-implementer",
            "--status",
            "approved",
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("record-result status must be one of", result.stderr)
        status = self.status_data()
        self.assertEqual("ready", status["assignments"]["T001-implementer"]["status"])
        self.assertEqual(0, status["assignments"]["T001-implementer"]["attempts"])

    def test_record_review_rejects_result_statuses(self) -> None:
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

        result = self.run_agent_team(
            "record-review",
            str(self.task_dir),
            "--assignment",
            "T001-spec-reviewer",
            "--status",
            "done",
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("record-review status must be one of", result.stderr)
        status = self.status_data()
        self.assertEqual("ready", status["assignments"]["T001-spec-reviewer"]["status"])
        self.assertEqual(0, status["assignments"]["T001-spec-reviewer"]["attempts"])

    def test_record_review_approved_requires_payload(self) -> None:
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

        result = self.run_agent_team(
            "record-review",
            str(self.task_dir),
            "--assignment",
            "T001-spec-reviewer",
            "--status",
            "approved",
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("approved review requires --file", result.stderr)
        status = self.status_data()
        self.assertEqual("ready", status["assignments"]["T001-spec-reviewer"]["status"])
        self.assertEqual(0, status["assignments"]["T001-spec-reviewer"]["attempts"])

    def test_record_review_approved_rejects_payload_without_approved_decision(self) -> None:
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
        review.write_text('{"decision": "changes_requested"}\n', encoding="utf-8")

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

        self.assertNotEqual(0, result.returncode)
        self.assertIn("approved review payload must include", result.stderr)
        status = self.status_data()
        self.assertEqual("ready", status["assignments"]["T001-spec-reviewer"]["status"])
        self.assertEqual(0, status["assignments"]["T001-spec-reviewer"]["attempts"])

    def test_record_review_changes_requested_does_not_unlock_quality_review(self) -> None:
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

        result = self.run_agent_team(
            "record-review",
            str(self.task_dir),
            "--assignment",
            "T001-spec-reviewer",
            "--status",
            "changes_requested",
        )

        self.assertEqual(0, result.returncode, result.stderr)
        status = self.status_data()
        self.assertEqual("changes_requested", status["assignments"]["T001-spec-reviewer"]["status"])
        self.assertEqual("pending", status["assignments"]["T001-quality-reviewer"]["status"])
        metrics = self.metrics_data()
        self.assertEqual(1, metrics["reviewReworks"])

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
