from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkflowParallelSessionsTest(unittest.TestCase):
    def test_workflow_uses_fixed_agent_mainline(self) -> None:
        text = (ROOT / ".cowork-flow" / "workflow.md").read_text(encoding="utf-8")
        self.assertIn("cowork-research", text)
        self.assertIn("cowork-implement", text)
        self.assertIn("cowork-check", text)
        self.assertIn("spawn_agent", text)
        self.assertIn("fork_turns=\"none\"", text)
        self.assertIn("[workflow-state:no_task]", text)
        self.assertIn("[workflow-state:planning]", text)
        self.assertIn("[workflow-state:in_progress]", text)
        self.assertIn("[workflow-state:completed]", text)
        self.assertIn("wait_agent", text)
        self.assertIn("list_agents", text)
        self.assertIn("close_agent", text)
        self.assertNotIn("agent run cowork-implement", text)
        self.assertNotIn("codex exec", text)
        self.assertNotIn("agent" + "-team prepare", text)
        self.assertNotIn("agent" + "-team next", text)

    def test_workflow_requires_dispatch_ack_gate(self) -> None:
        required_markers = (
            "COWORK_DISPATCH_V1",
            "COWORK_DISPATCH_END",
            "COWORK_ACK",
            "followup_task",
            "ack_token",
            "dispatch_id",
            "Missing or mismatched `COWORK_ACK` means the task is not dispatched.",
        )
        for path in (
            ROOT / ".cowork-flow" / "workflow.md",
            ROOT / "template" / ".cowork-flow" / "workflow.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in required_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

    def test_workflow_limits_generic_worker_to_best_effort(self) -> None:
        required_markers = (
            "Formal execution uses `cowork-research`, `cowork-implement`, or `cowork-check`.",
            "Generic `worker` dispatch is best-effort only.",
            "If a generic worker does not ACK after one retry, close it and do not execute the task.",
        )
        for path in (
            ROOT / ".cowork-flow" / "workflow.md",
            ROOT / "template" / ".cowork-flow" / "workflow.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in required_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

    def test_start_skill_routes_to_fixed_agents(self) -> None:
        text = (ROOT / ".agent" / "skills" / "start" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Plan -> Implement -> Check -> Finish", text)
        self.assertIn("Active task:", text)
        self.assertNotIn("agent" + "-team-execution", text)
        self.assertNotIn("specific assignment", text)
        self.assertIn("bounded delegated task", text)

    def test_start_skill_mentions_parallel_session_model(self) -> None:
        for path in (
            ROOT / ".agent" / "skills" / "start" / "SKILL.md",
            ROOT / "template" / ".agent" / "skills" / "start" / "SKILL.md",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("parallel sessions", text)
            self.assertIn("separate `git worktree`", text)
            self.assertIn("low-conflict slices", text)
            self.assertIn("final integrated verification", text)

    def test_entry_boundary_matches_fixed_agent_prompts(self) -> None:
        for path in (
            ROOT / ".agent" / "skills" / "entry-boundary" / "SKILL.md",
            ROOT / "template" / ".agent" / "skills" / "entry-boundary" / "SKILL.md",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("Active task:", text)
            self.assertIn("bounded delegated task", text)
            self.assertNotIn("assignment-source", text)

    def test_doctor_subagent_safety_matches_entry_boundary_model(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / ".cowork-flow" / "scripts" / "doctor.py"),
                "--subagent-safety",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            0,
            result.returncode,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )

    def test_writing_plans_routes_to_fixed_agents(self) -> None:
        for path in (
            ROOT / ".agent" / "skills" / "writing-plans" / "SKILL.md",
            ROOT / "template" / ".agent" / "skills" / "writing-plans" / "SKILL.md",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("cowork-implement", text)
            self.assertIn("cowork-check", text)
            self.assertIn("Active task:", text)
            self.assertIn("spawn_agent", text)
            self.assertIn("fork_turns=\"none\"", text)
            self.assertNotIn("subagent-driven-development", text)

    def test_template_workflow_matches_new_terms(self) -> None:
        text = (ROOT / "template" / ".cowork-flow" / "workflow.md").read_text(encoding="utf-8")
        self.assertIn("cowork-implement", text)
        self.assertNotIn("agent" + "-team prepare", text)

    def test_workflow_documents_parallel_operations(self) -> None:
        for path in (
            ROOT / ".cowork-flow" / "workflow.md",
            ROOT / "template" / ".cowork-flow" / "workflow.md",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("parallel sessions", text)
            self.assertIn("用户无需在需求输入时声明是否并行", text)
            self.assertIn("Plan 阶段由主会话评估并行可行性", text)
            self.assertIn("开发计划必须明确执行策略", text)
            self.assertIn("git worktree", text)
            self.assertIn("low-conflict slices", text)
            self.assertIn("file ownership", text)
            self.assertIn("dependencies", text)
            self.assertIn("expected outputs", text)
            self.assertIn("final integrated verification", text)

    def test_writing_plan_skills_require_parallel_scope_fields(self) -> None:
        for path in (
            ROOT / ".agent" / "skills" / "writing-plans" / "SKILL.md",
            ROOT / "template" / ".agent" / "skills" / "writing-plans" / "SKILL.md",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("Parallel work items", text)
            self.assertIn("Do not require the user to predeclare parallel execution", text)
            self.assertIn("Every plan must state the execution strategy", text)
            self.assertIn("file ownership", text)
            self.assertIn("dependencies", text)
            self.assertIn("expected outputs", text)
            self.assertIn("verification commands", text)
