from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CoworkAgentsTest(unittest.TestCase):
    def test_skill_set_is_direct_and_fixed_agent_based(self) -> None:
        expected = {
            "before-dev",
            "brainstorming",
            "break-loop",
            "check",
            "continue",
            "entry-boundary",
            "finish-work",
            "meta",
            "python-design",
            "start",
            "update-spec",
            "writing-plans",
        }
        for base in (ROOT / ".agent" / "skills", ROOT / "template" / ".agent" / "skills"):
            actual = {path.name for path in base.iterdir() if path.is_dir()}
            self.assertEqual(expected, actual)

    def test_codex_agent_definitions_exist_in_root_and_template(self) -> None:
        for base in (ROOT / ".codex" / "agents", ROOT / "template" / ".codex" / "agents"):
            self.assertTrue((base / "cowork-research.toml").is_file())
            self.assertTrue((base / "cowork-implement.toml").is_file())
            self.assertTrue((base / "cowork-check.toml").is_file())
            self.assertTrue((base / "worker.toml").is_file())
            self.assertTrue((base / "default.toml").is_file())
            self.assertTrue((base / "explorer.toml").is_file())

        for path in (
            ROOT / ".codex" / "config.toml",
            ROOT / ".codex" / "hooks.json",
            ROOT / ".codex" / "hooks" / "inject-workflow-state.py",
            ROOT / "template" / ".codex" / "config.toml",
            ROOT / "template" / ".codex" / "hooks.json",
            ROOT / "template" / ".codex" / "hooks" / "inject-workflow-state.py",
        ):
            self.assertTrue(path.is_file(), str(path))

    def test_codex_agent_definitions_are_valid_toml(self) -> None:
        for base in (ROOT / ".codex" / "agents", ROOT / "template" / ".codex" / "agents"):
            for path in base.glob("*.toml"):
                data = tomllib.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(path.stem, data["name"], str(path))

    def test_opencode_agent_definitions_exist_in_root_and_template(self) -> None:
        for base in (ROOT / ".opencode", ROOT / "template" / ".opencode"):
            for name in ("cowork-research", "cowork-implement", "cowork-check"):
                self.assertTrue((base / "agents" / f"{name}.md").is_file())
                self.assertTrue((base / "commands" / f"{name}.md").is_file())
            self.assertTrue((base / "plugins" / "cowork-flow.js").is_file())

    def test_claude_code_agent_definitions_exist_in_root_and_template(self) -> None:
        for base in (ROOT / ".claude", ROOT / "template" / ".claude"):
            for name in ("cowork-research", "cowork-implement", "cowork-check"):
                self.assertTrue((base / "agents" / f"{name}.md").is_file())
                self.assertTrue((base / "commands" / f"{name}.md").is_file())
            self.assertTrue((base / "settings.json").is_file())
            self.assertTrue((base / "hooks" / "inject-workflow-state.py").is_file())
            for name in ("before-dev", "brainstorming", "break-loop", "check", "continue",
                         "entry-boundary", "finish-work", "meta", "python-design", "start",
                         "update-spec", "writing-plans"):
                self.assertTrue((base / "skills" / name / "SKILL.md").is_file())
        self.assertTrue((ROOT / "CLAUDE.md").is_file())
        self.assertTrue((ROOT / "template" / "CLAUDE.md").is_file())

    def test_claude_code_skills_mirror_agent_skills(self) -> None:
        for source_base, claude_base in (
            (ROOT / ".agent" / "skills", ROOT / ".claude" / "skills"),
            (ROOT / "template" / ".agent" / "skills", ROOT / "template" / ".claude" / "skills"),
        ):
            for source in source_base.glob("*/SKILL.md"):
                mirror = claude_base / source.parent.name / "SKILL.md"
                self.assertTrue(mirror.is_file(), str(mirror))
                self.assertEqual(
                    source.read_text(encoding="utf-8"),
                    mirror.read_text(encoding="utf-8"),
                    str(mirror),
                )

    def test_agents_require_active_task_and_disable_multi_agent(self) -> None:
        for path in (
            ROOT / ".codex" / "agents" / "cowork-research.toml",
            ROOT / ".codex" / "agents" / "cowork-implement.toml",
            ROOT / ".codex" / "agents" / "cowork-check.toml",
            ROOT / "template" / ".codex" / "agents" / "cowork-research.toml",
            ROOT / "template" / ".codex" / "agents" / "cowork-implement.toml",
            ROOT / "template" / ".codex" / "agents" / "cowork-check.toml",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("Active task:", text)
            self.assertIn("MUST NOT spawn", text)
            self.assertIn("multi_agent = false", text)
            self.assertIn("enabled = false", text)

    def test_default_agent_overrides_block_start_resume_drift(self) -> None:
        for path in (
            ROOT / ".codex" / "agents" / "worker.toml",
            ROOT / ".codex" / "agents" / "default.toml",
            ROOT / ".codex" / "agents" / "explorer.toml",
            ROOT / "template" / ".codex" / "agents" / "worker.toml",
            ROOT / "template" / ".codex" / "agents" / "default.toml",
            ROOT / "template" / ".codex" / "agents" / "explorer.toml",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("bootstrap", text)
            self.assertIn("start", text)
            self.assertIn("resume", text)
            self.assertIn("multi_agent = false", text)
            self.assertIn("enabled = false", text)

    def test_agents_require_dispatch_ack_protocol(self) -> None:
        fixed_agents = {
            "cowork-research": "research",
            "cowork-implement": "implement",
            "cowork-check": "check",
        }
        for base in (ROOT / ".codex" / "agents", ROOT / "template" / ".codex" / "agents"):
            for agent_name, workflow_role in fixed_agents.items():
                path = base / f"{agent_name}.toml"
                text = path.read_text(encoding="utf-8")
                required_markers = (
                    "COWORK_DISPATCH_V1",
                    "COWORK_DISPATCH_END",
                    "COWORK_ACK",
                    "dispatch_id",
                    "ack_token",
                    "EXECUTE <dispatch_id>",
                    "mismatched dispatch_id",
                    f"agent_type: {agent_name}",
                    f"role: {workflow_role}",
                    f"agent_type is not `{agent_name}`",
                    f"legacy role `{agent_name}` is accepted",
                    "role names another fixed agent",
                )
                for marker in required_markers:
                    self.assertIn(marker, text, f"{marker} missing from {path}")

    def test_doctor_checks_fixed_agent_protocol(self) -> None:
        doctor = ROOT / ".cowork-flow" / "scripts" / "doctor.py"
        text = doctor.read_text(encoding="utf-8")
        for marker in (
            "COWORK_DISPATCH_V1",
            "COWORK_DELEGATION_V1",
            "COWORK_ENTRY_CONTRACT_V1",
            "COWORK_ACK",
            "EXECUTE <dispatch_id>",
            "agent_type is not",
            "workflow-state-templates.md",
            "entry_classifier.py",
            "REQUIRED_CODEX_HOOK_SCRIPT_SNIPPETS",
            "REQUIRED_WORKFLOW_STATE_TEMPLATE_SNIPPETS",
            "cmd_host_adapters",
            ".cowork-flow/adapters/claude-code/adapter.yaml",
            ".claude/agents/cowork-implement.md",
            ".claude/skills/start/SKILL.md",
            ".claude/settings.json",
            ".claude/hooks/inject-workflow-state.py",
        ):
            self.assertIn(marker, text)

    def test_legacy_execution_skill_removed(self) -> None:
        legacy_skills = (
            "agent" + "-team-execution",
            "dispatching-parallel-agents",
            "subagent-driven-development",
            "requesting-code-review",
            "using-superpowers",
            "check-cross-layer",
            "record-session",
            "executing-plans",
            "finishing-a-development-branch",
            "receiving-code-review",
            "systematic-debugging",
            "test-driven-development",
            "using-git-worktrees",
            "verification-before-completion",
            "writing-skills",
        )
        for legacy_skill in legacy_skills:
            self.assertFalse((ROOT / ".agent" / "skills" / legacy_skill / "SKILL.md").exists())
            self.assertFalse(
                (ROOT / "template" / ".agent" / "skills" / legacy_skill / "SKILL.md").exists()
            )

    def test_external_codex_runner_is_not_part_of_fixed_agent_model(self) -> None:
        self.assertFalse((ROOT / ".cowork-flow" / "scripts" / "agent.py").exists())
        self.assertFalse((ROOT / "template" / ".cowork-flow" / "scripts" / "agent.py").exists())
