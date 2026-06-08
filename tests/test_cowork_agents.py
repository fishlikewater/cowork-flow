from __future__ import annotations

import ast
import unittest
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.8-3.10
    tomllib = None


ROOT = Path(__file__).resolve().parents[1]
ENTRY_BOUNDARY = "entry" + "-boundary"


def load_agent_toml(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if tomllib is not None:
        return tomllib.loads(text)

    data: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            break
        key, separator, value = line.partition("=")
        key = key.strip()
        if separator and key in {"name", "description"}:
            parsed = ast.literal_eval(value.strip())
            if not isinstance(parsed, str):
                raise ValueError(f"{key} must be a string in {path}")
            data[key] = parsed

    if "name" in data:
        return data

    raise ValueError(f"missing top-level name in {path}")


class CoworkAgentsTest(unittest.TestCase):
    def test_skill_set_is_direct_and_fixed_agent_based(self) -> None:
        expected = {
            "before-dev",
            "brainstorming",
            "break-loop",
            "check",
            "continue",
            "finish-work",
            "meta",
            "party-mode",
            "python-design",
            "start",
            "update-spec",
            "writing-plans",
        }
        for base in (ROOT / ".agents" / "skills", ROOT / "template" / ".agents" / "skills"):
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
                data = load_agent_toml(path)
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
                         "finish-work", "meta", "party-mode", "python-design", "start",
                         "update-spec", "writing-plans"):
                self.assertTrue((base / "skills" / name / "SKILL.md").is_file())
            self.assertFalse((base / "skills" / ENTRY_BOUNDARY / "SKILL.md").exists())
        self.assertTrue((ROOT / "CLAUDE.md").is_file())
        self.assertTrue((ROOT / "template" / "CLAUDE.md").is_file())

    def test_claude_code_skills_mirror_agent_skills(self) -> None:
        for source_base, claude_base in (
            (ROOT / ".agents" / "skills", ROOT / ".claude" / "skills"),
            (ROOT / "template" / ".agents" / "skills", ROOT / "template" / ".claude" / "skills"),
        ):
            for source in source_base.glob("*/SKILL.md"):
                mirror = claude_base / source.parent.name / "SKILL.md"
                self.assertTrue(mirror.is_file(), str(mirror))
                self.assertEqual(
                    source.read_text(encoding="utf-8"),
                    mirror.read_text(encoding="utf-8"),
                    str(mirror),
                )

    def test_party_mode_skill_defines_bounded_advisory_roundtable(self) -> None:
        required_markers = (
            "manual advisory roundtable",
            "true child agents",
            "not simulated personas",
            "Select the smallest useful agent roster or review lenses",
            "Record why each selected voice is useful",
            "Round 1 uses fresh child contexts",
            "Child agents cannot see each other",
            "compact claim table: `claim_id`, owner, claim, evidence, counterclaim, evidence gap, and decision impact",
            "bind each prompt to one `claim_id`",
            "Follow-up rounds should prefer the same live child",
            "Send only the target claim, counterclaim, evidence gap",
            "`agree`, `reject`, or `revise`",
            "For Challenge rounds, the default stance is scrutiny.",
            "choose `agree` only after naming the evidence that compels agreement",
            "Spawn an extra child only when the effective roster or lens config allows it",
            "Opening round: independent first judgments.",
            "Challenge rounds: rebuttal, risk drilldown, or evidence repair on specific disagreements.",
            "Convergence rounds: decision check only. Verify, narrow, or choose.",
            "round phase policy, including when challenge may continue and when convergence must begin",
            "Round 2+ = Challenge while continue conditions still expose material disagreement",
            "Convergence begins when the coordinator can write one recommended direction",
            "After convergence begins, do not reopen exploration unless the user approves or new concrete evidence appears.",
            "`max_agents=3`",
            "`max_rounds=5`",
            "call arguments > task/change config > `.cowork-flow/config.yaml` > skill defaults",
            "continue conditions can be tightened but not removed",
            "stop conditions can be tightened but not removed",
            "core fields can be extended but not removed",
            "advisory only",
            "cannot satisfy formal Implement or Check completion",
        )
        child_schema = (
            "position:",
            "evidence:",
            "risk:",
            "tradeoff:",
            "rejected_option:",
            "acceptance_signal:",
            "what_would_change_my_mind:",
        )
        followup_schema = (
            "claim_id:",
            "responding_to:",
            "opposing_claim:",
            "position_delta:",
            "evidence_delta:",
            "still_disagree:",
        )
        coordinator_schema = (
            "effective_max_agents:",
            "effective_max_rounds:",
            "rounds_used:",
            "selected_agents:",
            "claim_table:",
            "agent_turns:",
            "consensus:",
            "disagreements:",
            "evidence:",
            "decision:",
            "rejected_options:",
            "acceptance_criteria:",
            "open_questions:",
            "early_stop_reason:",
            "stop_reason:",
            "selected agent or lens names and selection reasons",
            "compact transcript with round, agent or lens, `claim_id`, position, and `position_delta`",
        )
        for path in (
            ROOT / ".agents" / "skills" / "party-mode" / "SKILL.md",
            ROOT / "template" / ".agents" / "skills" / "party-mode" / "SKILL.md",
            ROOT / ".claude" / "skills" / "party-mode" / "SKILL.md",
            ROOT / "template" / ".claude" / "skills" / "party-mode" / "SKILL.md",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in required_markers + child_schema + followup_schema + coordinator_schema:
                self.assertIn(marker, text, f"{marker} missing from {path}")

    def test_agents_require_runtime_context_and_disable_multi_agent(self) -> None:
        for path in (
            ROOT / ".codex" / "agents" / "cowork-research.toml",
            ROOT / ".codex" / "agents" / "cowork-implement.toml",
            ROOT / ".codex" / "agents" / "cowork-check.toml",
            ROOT / "template" / ".codex" / "agents" / "cowork-research.toml",
            ROOT / "template" / ".codex" / "agents" / "cowork-implement.toml",
            ROOT / "template" / ".codex" / "agents" / "cowork-check.toml",
        ):
            data = load_agent_toml(path)
            description = data.get("description", "")
            self.assertIn("runtime-context", description, str(path))
            self.assertNotIn("Active task", description, str(path))
            self.assertNotIn("active task", description, str(path))
            self.assertNotIn("self-loads", description, str(path))

            text = path.read_text(encoding="utf-8")
            self.assertIn("cowork_runtime_context_id: <runtime_context_id>", text)
            self.assertIn("cowork_host_context_key: <host_context_key>", text)
            self.assertIn("subagent bind <runtime_context_id> <host_context_key>", text)
            self.assertIn("bound runtime context", text)
            self.assertIn("report needs_context", text)
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

    def test_agents_require_runtime_context_protocol(self) -> None:
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
                    "cowork_runtime_context_id: <runtime_context_id>",
                    "cowork_host_context_key: <host_context_key>",
                    "subagent bind <runtime_context_id> <host_context_key>",
                    ".cowork-flow/.runtime/subagents/<runtime_context_id>.json",
                    "before workflow state is injected",
                    "names another agent type",
                    "report needs_context",
                    f"`{agent_name}` subagent",
                )
                self.assertIn(workflow_role, text)
                for marker in required_markers:
                    self.assertIn(marker, text, f"{marker} missing from {path}")

    def test_doctor_checks_runtime_context_protocol(self) -> None:
        doctor = ROOT / ".cowork-flow" / "scripts" / "doctor.py"
        text = doctor.read_text(encoding="utf-8")
        for marker in (
            "COWORK_ENTRY_CONTRACT_V1",
            "RUNTIME_CONTEXT_DISPATCH_V2",
            "cowork_runtime_context_id",
            "bind_runtime_context",
            "runtime-context-invalid",
            "workflow-state-templates.md",
            "entry_classifier.py",
            "REQUIRED_RUNTIME_HOOK_SNIPPETS",
            "REQUIRED_WORKFLOW_STATE_TEMPLATE_SNIPPETS",
            "REQUIRED_FIXED_AGENT_DESCRIPTION_SNIPPET",
            "FORBIDDEN_FIXED_AGENT_DESCRIPTION_SNIPPETS",
            "FORBIDDEN_README_DISPATCH_SNIPPETS",
            "_check_file_omits",
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
            self.assertFalse((ROOT / ".agents" / "skills" / legacy_skill / "SKILL.md").exists())
            self.assertFalse(
                (ROOT / "template" / ".agents" / "skills" / legacy_skill / "SKILL.md").exists()
            )

    def test_external_codex_runner_is_not_part_of_fixed_agent_model(self) -> None:
        self.assertFalse((ROOT / ".cowork-flow" / "scripts" / "agent.py").exists())
        self.assertFalse((ROOT / "template" / ".cowork-flow" / "scripts" / "agent.py").exists())
