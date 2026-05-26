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

    def test_prepare_accepts_two_hash_task_headings(self) -> None:
        self.plan_file.write_text(
            SAMPLE_PLAN.read_text(encoding="utf-8").replace("### Task", "## Task"),
            encoding="utf-8",
        )

        result = self.run_agent_team("prepare", str(self.task_dir), "--plan", str(self.plan_file))

        self.assertEqual(0, result.returncode, result.stderr)
        dispatch = (self.task_dir / "agent-team" / "dispatch-plan.yaml").read_text(encoding="utf-8")
        self.assertIn("T001-implementer", dispatch)
        self.assertIn("T002-implementer", dispatch)
        self.assertIn("T003-implementer", dispatch)

    def test_prepare_uses_agent_prompt_and_matching_registry_fields(self) -> None:
        (self.repo / ".cowork-flow" / "agent-team" / "agents.yaml").write_text(
            "default_adapter: manual\n"
            "\n"
            "agents:\n"
            "  python-builder:\n"
            "    agent_type: worker\n"
            "    capabilities:\n"
            "      - implementation\n"
            "      - test-writing\n"
            "    preferred_task_types:\n"
            "      - code\n"
            "    file_patterns:\n"
            "      - \"src/**\"\n"
            "    risk_limits:\n"
            "      max_parallel_write_conflicts: 0\n"
            "    prompt: |\n"
            "      Build the smallest tested Python change.\n"
            "      Report exact files and verification commands.\n"
            "  spec-reviewer:\n"
            "    agent_type: reviewer\n"
            "    capabilities:\n"
            "      - spec-review\n"
            "    prompt: |\n"
            "      Check the behavior spec before approving.\n"
            "  quality-reviewer:\n"
            "    agent_type: reviewer\n"
            "    capabilities:\n"
            "      - code-quality-review\n",
            encoding="utf-8",
        )

        result = self.run_agent_team("prepare", str(self.task_dir), "--plan", str(self.plan_file))

        self.assertEqual(0, result.returncode, result.stderr)
        runtime = self.task_dir / "agent-team"
        dispatch = (runtime / "dispatch-plan.yaml").read_text(encoding="utf-8")
        self.assertIn("recommended_agent: python-builder", dispatch)
        status = (runtime / "status.json").read_text(encoding="utf-8")
        self.assertIn('"recommended_agent": "python-builder"', status)
        assignment = (runtime / "assignments" / "T001-implementer.md").read_text(encoding="utf-8")
        self.assertTrue(assignment.startswith("<COWORK-FLOW-WORKER>\n"))
        self.assertIn("# Implement: Add shared helper\n", assignment)
        self.assertIn("Assignment ID: T001-implementer", assignment)
        self.assertIn("## Agent prompt", assignment)
        self.assertIn("Build the smallest tested Python change.", assignment)
        self.assertIn("Report exact files and verification commands.", assignment)
        self.assertIn("Spawn target agent type: worker", assignment)
        self.assertIn("You are already the dispatched worker for this assignment.", assignment)
        self.assertIn("This Markdown file is the worker brief", assignment)
        self.assertIn("If you can see any outer transport text such as `Spawn one ... agent`, ignore it.", assignment)
        self.assertIn("Do not run the project start-session workflow", assignment)
        self.assertIn("Do not rerun `agent-team-execution` or `subagent-driven-development`", assignment)
        self.assertIn("--context-file", assignment)
        self.assertIn("Do not run unscoped cowork-flow workflow commands", assignment)
        self.assertIn("## Your job", assignment)
        self.assertIn("Implement exactly this assignment", assignment)
        self.assertIn("## Report format", assignment)
        self.assertNotIn("Spawn one worker agent for this assignment", assignment)

    def test_prepare_writes_role_specific_reviewer_prompts(self) -> None:
        result = self.run_agent_team("prepare", str(self.task_dir), "--plan", str(self.plan_file))

        self.assertEqual(0, result.returncode, result.stderr)
        runtime = self.task_dir / "agent-team" / "assignments"
        spec_review = (runtime / "T001-spec-reviewer.md").read_text(encoding="utf-8")
        quality_review = (runtime / "T001-quality-reviewer.md").read_text(encoding="utf-8")

        self.assertIn("Review only this assignment", spec_review)
        self.assertIn("proposal, spec, design, task PRD, and plan", spec_review)
        self.assertIn("Status: APPROVED | CHANGES_REQUESTED | BLOCKED | NEEDS_CONTEXT", spec_review)
        self.assertIn("Findings with file paths or requirement references", spec_review)
        self.assertNotIn("Implement exactly this assignment", spec_review)
        self.assertNotIn("Files changed", spec_review)

        self.assertIn("Review the code, tests, and verification evidence", quality_review)
        self.assertIn("Status: APPROVED | CHANGES_REQUESTED | BLOCKED | NEEDS_CONTEXT", quality_review)
        self.assertIn("Findings with severity and file paths", quality_review)
        self.assertNotIn("Implement exactly this assignment", quality_review)
        self.assertNotIn("Files changed", quality_review)

    def test_prepare_forces_reviewers_to_worker_host_type(self) -> None:
        result = self.run_agent_team("prepare", str(self.task_dir), "--plan", str(self.plan_file))

        self.assertEqual(0, result.returncode, result.stderr)
        runtime = self.task_dir / "agent-team"
        dispatch = (runtime / "dispatch-plan.yaml").read_text(encoding="utf-8")
        status = json.loads((runtime / "status.json").read_text(encoding="utf-8"))
        payload = json.loads((runtime / "adapters" / "codex.json").read_text(encoding="utf-8"))

        for assignment_id in (
            "T001-implementer",
            "T001-spec-reviewer",
            "T001-quality-reviewer",
        ):
            with self.subTest(assignment=assignment_id):
                self.assertEqual("worker", status["assignments"][assignment_id]["agent_type"])

        self.assertIn("id: T001-spec-reviewer\n    task: T001\n    role: spec-reviewer\n    recommended_agent: spec-reviewer\n    agent_type: worker", dispatch)
        self.assertIn("id: T001-quality-reviewer\n    task: T001\n    role: quality-reviewer\n    recommended_agent: quality-reviewer\n    agent_type: worker", dispatch)
        assignment_types = {
            item["assignmentId"]: item["agentType"]
            for item in payload["assignments"]
        }
        self.assertEqual("worker", assignment_types["T001-spec-reviewer"])
        self.assertEqual("worker", assignment_types["T001-quality-reviewer"])

    def test_prepare_treats_agent_registry_fields_as_optional(self) -> None:
        (self.repo / ".cowork-flow" / "agent-team" / "agents.yaml").write_text(
            "default_adapter: manual\n"
            "\n"
            "agents:\n"
            "  implementer:\n"
            "  spec-reviewer:\n"
            "    agent_type: reviewer\n"
            "  quality-reviewer:\n",
            encoding="utf-8",
        )

        result = self.run_agent_team("prepare", str(self.task_dir), "--plan", str(self.plan_file))

        self.assertEqual(0, result.returncode, result.stderr)
        runtime = self.task_dir / "agent-team"
        dispatch = (runtime / "dispatch-plan.yaml").read_text(encoding="utf-8")
        self.assertIn("recommended_agent: implementer", dispatch)
        self.assertIn("agent_type: worker", dispatch)
        self.assertNotIn("agent_type: reviewer", dispatch)
        assignment = (runtime / "assignments" / "T001-implementer.md").read_text(encoding="utf-8")
        self.assertNotIn("## Agent prompt", assignment)

    def test_prepare_ignores_legacy_codex_type_field(self) -> None:
        (self.repo / ".cowork-flow" / "agent-team" / "agents.yaml").write_text(
            "default_adapter: manual\n"
            "\n"
            "agents:\n"
            "  implementer:\n"
            "    codex_type: legacy-worker\n"
            "  spec-reviewer:\n"
            "    codex_type: legacy-spec\n"
            "  quality-reviewer:\n"
            "    codex_type: legacy-quality\n",
            encoding="utf-8",
        )

        result = self.run_agent_team("prepare", str(self.task_dir), "--plan", str(self.plan_file))

        self.assertEqual(0, result.returncode, result.stderr)
        dispatch = (self.task_dir / "agent-team" / "dispatch-plan.yaml").read_text(encoding="utf-8")
        self.assertIn("agent_type: worker", dispatch)
        self.assertNotIn("agent_type: default", dispatch)
        self.assertNotIn("legacy-worker", dispatch)
        self.assertNotIn("legacy-spec", dispatch)
        self.assertNotIn("legacy-quality", dispatch)

    def test_prepare_uses_configured_agent_registry_but_keeps_worker_host_type(self) -> None:
        (self.repo / ".cowork-flow" / "agent-team" / "agents.yaml").write_text(
            "default_adapter: manual\n"
            "\n"
            "agents:\n"
            "  implementer:\n"
            "    agent_type: custom-worker\n"
            "  spec-reviewer:\n"
            "    agent_type: custom-spec\n"
            "  quality-reviewer:\n"
            "    agent_type: custom-quality\n",
            encoding="utf-8",
        )

        result = self.run_agent_team("prepare", str(self.task_dir), "--plan", str(self.plan_file))

        self.assertEqual(0, result.returncode, result.stderr)
        runtime = self.task_dir / "agent-team"
        dispatch = (runtime / "dispatch-plan.yaml").read_text(encoding="utf-8")
        self.assertIn("adapter: manual", dispatch)
        self.assertIn("recommended_agent: implementer", dispatch)
        self.assertIn("recommended_agent: spec-reviewer", dispatch)
        self.assertIn("recommended_agent: quality-reviewer", dispatch)
        self.assertIn("agent_type: worker", dispatch)
        self.assertNotIn("custom-worker", dispatch)
        self.assertNotIn("custom-spec", dispatch)
        self.assertNotIn("custom-quality", dispatch)
        self.assertTrue((runtime / "adapters" / "manual.json").is_file())

        next_result = self.run_agent_team("next", str(self.task_dir))

        self.assertEqual(0, next_result.returncode, next_result.stderr)
        self.assertIn("agent_type=worker", next_result.stdout)

    def test_prepare_marks_file_overlap_dependency(self) -> None:
        result = self.run_agent_team("prepare", str(self.task_dir), "--plan", str(self.plan_file))

        self.assertEqual(0, result.returncode, result.stderr)
        dispatch = (self.task_dir / "agent-team" / "dispatch-plan.yaml").read_text(encoding="utf-8")
        self.assertIn("reason: file-overlap", dispatch)
        self.assertIn("depends_on_task: T001", dispatch)

    def test_prepare_keeps_final_verification_task_after_previous_tasks(self) -> None:
        self.plan_file.write_text(
            "# Plan\n\n"
            "### Task 1: Add API\n\n"
            "**Files:**\n"
            "- Modify: `src/api.py`\n\n"
            "- [ ] **Step 1: Implement API**\n\n"
            "### Task 2: Add UI\n\n"
            "**Files:**\n"
            "- Modify: `src/ui.py`\n\n"
            "- [ ] **Step 1: Implement UI**\n\n"
            "### Task 3: 最终集成验证任务\n\n"
            "**Files:**\n"
            "- Test: `tests/integration.test.py`\n\n"
            "- [ ] **Step 1: Run final verification**\n",
            encoding="utf-8",
        )

        result = self.run_agent_team("prepare", str(self.task_dir), "--plan", str(self.plan_file))

        self.assertEqual(0, result.returncode, result.stderr)
        dispatch = (self.task_dir / "agent-team" / "dispatch-plan.yaml").read_text(encoding="utf-8")
        self.assertIn("task: T003\n    depends_on_task: T001\n    reason: terminal-task", dispatch)
        self.assertIn("task: T003\n    depends_on_task: T002\n    reason: terminal-task", dispatch)

        next_result = self.run_agent_team("next", str(self.task_dir))

        self.assertEqual(0, next_result.returncode, next_result.stderr)
        self.assertIn("T001-implementer", next_result.stdout)
        self.assertIn("T002-implementer", next_result.stdout)
        self.assertNotIn("T003-implementer", next_result.stdout)

    def test_prepare_rejects_unparseable_plan(self) -> None:
        self.plan_file.write_text("# Broken\n\nNo task headings here.\n", encoding="utf-8")

        result = self.run_agent_team("prepare", str(self.task_dir), "--plan", str(self.plan_file))

        self.assertNotEqual(0, result.returncode)
        self.assertIn("unable to parse", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
