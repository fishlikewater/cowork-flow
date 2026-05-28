from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"


class AgentTeamDocsTest(unittest.TestCase):
    def test_readme_documents_agent_team_command_and_codex_adapter(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("./.cowork-flow/run agent-team", readme)
        self.assertIn("codex", readme.lower())
        self.assertIn("agent_team.enabled", readme)

    def test_workflow_documents_agent_team_plan_execution(self) -> None:
        for path in (
            ROOT / ".cowork-flow" / "workflow.md",
            TEMPLATE / ".cowork-flow" / "workflow.md",
        ):
            workflow = path.read_text(encoding="utf-8")
            self.assertIn("agent-team prepare", workflow)
            self.assertIn("agent-team next", workflow)
            self.assertIn("agent_team.enabled", workflow)
            self.assertIn("是否存在适合", workflow)
            self.assertIn("独立任务", workflow)
            self.assertIn("不适合", workflow)
            self.assertIn("不得为了满足流程形式而强行拆分高耦合任务", workflow)

    def test_start_skill_references_agent_team_execution(self) -> None:
        for path in (
            ROOT / ".agent" / "skills" / "start" / "SKILL.md",
            TEMPLATE / ".agent" / "skills" / "start" / "SKILL.md",
        ):
            skill = path.read_text(encoding="utf-8")
            self.assertIn("agent-team-execution", skill)
            self.assertIn("agent-team complete", skill)

    def test_start_skill_skips_for_dispatched_subagents(self) -> None:
        for path in (
            ROOT / ".agent" / "skills" / "start" / "SKILL.md",
            TEMPLATE / ".agent" / "skills" / "start" / "SKILL.md",
        ):
            skill = path.read_text(encoding="utf-8")
            self.assertIn("<SUBAGENT-STOP>", skill)
            self.assertIn("If you were dispatched as a subagent", skill)
            self.assertIn("current user message", skill)
            self.assertIn("skip this skill", skill)
            self.assertIn("HARD ENTRY GATE", skill)
            self.assertIn("MAIN_SESSION", skill)
            self.assertIn("DELEGATED_SUBTASK", skill)
            self.assertIn("UNCERTAIN", skill)
            self.assertIn("scoped recovery", skill)

    def test_agent_team_execution_skill_uses_codex_subagent_orchestration_language(self) -> None:
        for path in (
            ROOT / ".agent" / "skills" / "agent-team-execution" / "SKILL.md",
            TEMPLATE / ".agent" / "skills" / "agent-team-execution" / "SKILL.md",
        ):
            skill = path.read_text(encoding="utf-8")
            self.assertIn("fresh worker per assignment", skill.lower())
            self.assertIn("worker result handling", skill.lower())
            self.assertIn("worker-report", skill)
            self.assertIn("role-specific report format", skill)
            self.assertIn("outbox", skill)
            self.assertIn("collect", skill)
            self.assertIn("adapter_failed", skill)
            self.assertIn("Do not record `done` or `approved`", skill)
            self.assertIn("Do not wait indefinitely", skill)
            self.assertIn("close the child thread", skill)
            self.assertIn("--reason adapter_failed", skill)
            self.assertIn("record-result", skill)
            self.assertIn("record-review", skill)
            self.assertIn("spawn_agent", skill)
            self.assertIn("wait_agent", skill)
            self.assertIn("close_agent", skill)
            self.assertIn(".context.json", skill)
            self.assertIn("nickname", skill)
            self.assertIn("record-spawn", skill)
            self.assertIn("suggestedTaskName", skill)
            self.assertIn("wait for all requested results", skill)
            self.assertIn("fork_turns: none", skill)
            self.assertIn("agent_type", skill)
            self.assertIn("built-in Codex agent types include `default`, `worker`, and `explorer", skill)
            self.assertIn("recommended_agent", skill)
            self.assertIn("Do not invent your own alias", skill)
            self.assertIn("Subagent Evidence Gate", skill)
            self.assertIn("Do not treat wording in the final answer as evidence", skill)
            self.assertIn("item type shows an agent thread", skill)
            self.assertIn("If no subagent evidence appears", skill)
            self.assertIn("child `message` must be the assignment prompt body", skill)
            self.assertIn("Do not prepend coordinator dispatch wording", skill)
            self.assertIn("Only fall back to manual", skill)
            self.assertIn("worker host identity", skill)
            self.assertIn("coordinator collects the persisted outbox", skill)
            self.assertIn("allowedContext", skill)
            self.assertIn("assignment-scoped context", skill)
            self.assertIn("ready or in_progress", skill)
            self.assertNotIn("Use this wording for each ready batch", skill)
            self.assertNotIn("Spawn one <agent_type> agent per ready assignment", skill)


    def test_entry_boundary_skill_routes_delegated_subtasks_to_scoped_recovery(self) -> None:
        for path in (
            ROOT / ".agent" / "skills" / "entry-boundary" / "SKILL.md",
            TEMPLATE / ".agent" / "skills" / "entry-boundary" / "SKILL.md",
        ):
            skill = path.read_text(encoding="utf-8")
            self.assertIn("MAIN_SESSION", skill)
            self.assertIn("DELEGATED_SUBTASK", skill)
            self.assertIn("UNCERTAIN", skill)
            self.assertIn("scoped recovery", skill)
            self.assertIn("--context-file <context.json> resume", skill)
            self.assertIn("must not activate tasks", skill)
            self.assertIn("Delegated signals override main-session signals", skill)
            self.assertIn("concrete task, working directory, commands, and output format", skill)
            self.assertIn("assignment prompt is the first source of truth", skill)
            self.assertIn("Classify the actual user or delegation task message", skill)
            self.assertIn("leaf executor", skill)
            self.assertIn("Do not call spawn_agent, wait_agent, close_agent, or list_agents", skill)
            self.assertIn("unless the assignment explicitly says coordinator", skill)

    def test_start_skill_is_hard_gate_after_entry_boundary(self) -> None:
        for path in (
            ROOT / ".agent" / "skills" / "start" / "SKILL.md",
            TEMPLATE / ".agent" / "skills" / "start" / "SKILL.md",
        ):
            skill = path.read_text(encoding="utf-8")
            self.assertIn("HARD ENTRY GATE", skill)
            self.assertIn("Do not reclassify delegated work as MAIN_SESSION", skill)
            self.assertIn("If entry-boundary returned DELEGATED_SUBTASK or UNCERTAIN, stop immediately", skill)

    def test_agents_keeps_entry_boundary_guidance_lightweight(self) -> None:
        for path in (ROOT / "AGENTS.md", TEMPLATE / "AGENTS.md"):
            agents = path.read_text(encoding="utf-8")
            self.assertIn(".cowork-flow/workflow.md", agents)
            self.assertIn(".cowork-flow/spec/", agents)
            self.assertNotIn("worker-report", agents)
            self.assertNotIn("coordinator.context.json", agents)
            self.assertNotIn("outbox", agents)
            self.assertNotIn("Classify the actual user or delegation task message", agents)

    def test_template_agents_mentions_agent_team_runtime(self) -> None:
        agents = (TEMPLATE / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn(".cowork-flow/", agents)
        self.assertIn("workflow.md", agents)


if __name__ == "__main__":
    unittest.main()



