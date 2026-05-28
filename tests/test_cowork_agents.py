from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CoworkAgentsTest(unittest.TestCase):
    def test_codex_agent_definitions_exist_in_root_and_template(self) -> None:
        for base in (ROOT / ".codex" / "agents", ROOT / "template" / ".codex" / "agents"):
            self.assertTrue((base / "cowork-research.toml").is_file())
            self.assertTrue((base / "cowork-implement.toml").is_file())
            self.assertTrue((base / "cowork-check.toml").is_file())

    def test_agents_require_active_task_and_disable_multi_agent(self) -> None:
        for path in (
            ROOT / ".codex" / "agents" / "cowork-implement.toml",
            ROOT / ".codex" / "agents" / "cowork-check.toml",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("Active task:", text)
            self.assertIn("MUST NOT spawn", text)
            self.assertIn("multi_agent = false", text)
            self.assertIn("enabled = false", text)

    def test_legacy_execution_skill_removed(self) -> None:
        legacy_skill = "agent" + "-team-execution"
        self.assertFalse((ROOT / ".agent" / "skills" / legacy_skill / "SKILL.md").exists())
        self.assertFalse(
            (ROOT / "template" / ".agent" / "skills" / legacy_skill / "SKILL.md").exists()
        )
