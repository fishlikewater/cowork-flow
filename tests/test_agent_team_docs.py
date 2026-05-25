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

    def test_template_agents_mentions_agent_team_runtime(self) -> None:
        agents = (TEMPLATE / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn(".agent/skills/start", agents)
        self.assertIn(".cowork-flow/", agents)
        self.assertIn("workflow.md", agents)


if __name__ == "__main__":
    unittest.main()
