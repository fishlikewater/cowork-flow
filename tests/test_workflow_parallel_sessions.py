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
            self.assertIn("file ownership", text)
            self.assertIn("dependencies", text)
            self.assertIn("expected outputs", text)
            self.assertIn("verification commands", text)
