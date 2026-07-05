from __future__ import annotations

import ast
import shutil
import subprocess
import sys
import tempfile
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
            "game-design",
            "meta",
            "party-mode",
            "party-mode-v2",
            "python-design",
            "start",
            "tdd",
            "update-spec",
            "writing-plans",
        }
        # Skills single source of truth: template/skills/
        actual = {path.name for path in (ROOT / "template" / "skills").iterdir() if path.is_dir() and not path.name.startswith("bmad-")}
        self.assertEqual(expected, actual)

    def test_codex_agent_definitions_exist_in_template(self) -> None:
        base = ROOT / "template" / ".codex" / "agents"
        self.assertTrue((base / "cowork-research.toml").is_file())
        self.assertTrue((base / "cowork-implement.toml").is_file())
        self.assertTrue((base / "cowork-check.toml").is_file())
        self.assertTrue((base / "worker.toml").is_file())
        self.assertTrue((base / "default.toml").is_file())
        self.assertTrue((base / "explorer.toml").is_file())

        for path in (
            ROOT / "template" / ".codex" / "config.toml",
            ROOT / "template" / ".codex" / "hooks.json",
            ROOT / "template" / ".codex" / "hooks" / "inject-workflow-state.py",
        ):
            self.assertTrue(path.is_file(), str(path))

    def test_codex_agent_definitions_are_valid_toml(self) -> None:
        for path in (ROOT / "template" / ".codex" / "agents").glob("*.toml"):
            data = load_agent_toml(path)
            self.assertEqual(path.stem, data["name"], str(path))

    def test_opencode_agent_definitions_exist_in_template(self) -> None:
        base = ROOT / "template" / ".opencode"
        for name in ("cowork-research", "cowork-implement", "cowork-check"):
            self.assertTrue((base / "agents" / f"{name}.md").is_file())
            self.assertTrue((base / "commands" / f"{name}.md").is_file())
        self.assertTrue((base / "plugins" / "cowork-flow.js").is_file())

    def test_claude_code_agent_definitions_exist_in_template(self) -> None:
        base = ROOT / "template" / ".claude"
        for name in ("cowork-research", "cowork-implement", "cowork-check"):
            self.assertTrue((base / "agents" / f"{name}.md").is_file())
            self.assertTrue((base / "commands" / f"{name}.md").is_file())
        self.assertTrue((base / "settings.json").is_file())
        self.assertTrue((base / "hooks" / "inject-workflow-state.py").is_file())
        # Skills single source of truth: template/skills/
        for name in ("before-dev", "brainstorming", "break-loop", "check", "continue",
                     "finish-work", "meta", "party-mode", "party-mode-v2",
                     "python-design", "start", "tdd", "update-spec", "writing-plans"):
            self.assertTrue((ROOT / "template" / "skills" / name / "SKILL.md").is_file())
        self.assertFalse((ROOT / "template" / "skills" / ENTRY_BOUNDARY / "SKILL.md").exists())
        self.assertTrue((ROOT / "CLAUDE.md").is_file())
        self.assertTrue((ROOT / "template" / "CLAUDE.md").is_file())

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
            "A wait timeout is not a child timeout.",
            "When the discussion has converged or the user ends it, close live children after their final output is recorded.",
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
            "pending_children:",
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
        text = (ROOT / "template" / "skills" / "party-mode" / "SKILL.md").read_text(encoding="utf-8")
        for marker in required_markers + child_schema + followup_schema + coordinator_schema:
            self.assertIn(marker, text, f"{marker} missing from template/skills/party-mode/SKILL.md")

    def test_party_mode_v2_skill_is_thin_runtime_board_entrypoint(self) -> None:
        required_markers = (
            "thin entrypoint",
            "runtime board",
            "Python runtime is the source of truth",
            "The moderator does not forward",
            "Always use the runtime controller",
            "party-v2 init",
            "party-v2 monitor",
            "party-v2 view",
            "party-v2 post",
            "party-v2 respond",
            "party-v2 advance",
            "party-v2 record-action-result",
            "party-v2 finalize",
            "board API",
            "current-round only",
            "host-neutral next actions",
            "maintain",
            "revise",
            "concede",
            "Unsupported agreement, vague revision, and evidence-free rebuttal are invalid.",
            "advisory only",
            "cannot satisfy formal Implement or Check completion",
        )
        forbidden_markers = (
            "Round 1 uses fresh child contexts",
            "compact claim table",
            "Coordinator Output Schema",
            "spawn_agent",
            "wait_agent",
            "close_agent",
        )
        text = (ROOT / "template" / "skills" / "party-mode-v2" / "SKILL.md").read_text(encoding="utf-8")
        for marker in required_markers:
            self.assertIn(marker, text, f"{marker} missing from template/skills/party-mode-v2/SKILL.md")
        for marker in forbidden_markers:
            self.assertNotIn(marker, text, f"{marker} should stay out of thin V2 skill template/skills/party-mode-v2/SKILL.md")

    def test_agents_require_runtime_context_and_disable_multi_agent(self) -> None:
        for path in (
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

    def test_cowork_implement_requires_tdd_evidence(self) -> None:
        required_markers = (
            "red-green-refactor",
            "tdd.jsonl",
            "redCommand",
            "redExitCode",
            "greenCommand",
            "greenExitCode",
            "exemption",
        )
        for path in (
            ROOT / "template" / ".codex" / "agents" / "cowork-implement.toml",
        ):
            text = path.read_text(encoding="utf-8")
            for marker in required_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

    def test_cowork_check_requires_test_intent_review(self) -> None:
        required_markers = (
            "test_intent_review",
            "shallow tests",
            "meaningful behavior breaks",
            "PRD acceptance",
        )
        for path in (
            ROOT / "template" / ".codex" / "agents" / "cowork-check.toml",
        ):
            text = path.read_text(encoding="utf-8")
            missing = [marker for marker in required_markers if marker not in text]
            self.assertEqual([], missing, f"missing markers from {path}: {missing}")

    def test_default_agent_overrides_block_start_resume_drift(self) -> None:
        for path in (
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
        for agent_name, workflow_role in fixed_agents.items():
            path = ROOT / "template" / ".codex" / "agents" / f"{agent_name}.toml"
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

    def _run_doctor(self, cwd: Path) -> subprocess.CompletedProcess[str]:
        doctor = ROOT / "template" / ".cowork-flow" / "scripts" / "commands" / "doctor.py"
        return subprocess.run(
            [sys.executable, str(doctor), "--host-adapters"],
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=30,
        )

    def _build_deployed_workspace(self, temp_dir: str) -> Path:
        """Build a workspace that mirrors a deployed project layout.

        Doctor scans both `.cowork-flow/...` and `template/.cowork-flow/...`
        for spec files and schemas. We replicate the source repo's shape:
        `.cowork-flow/` + `template/` next to each other under the workspace.
        """
        workspace = Path(temp_dir)
        src_cowork = ROOT / "template" / ".cowork-flow"
        dst_cowork = workspace / ".cowork-flow"
        # Skip scripts/ since we're testing from source tree directly.
        shutil.copytree(
            src_cowork,
            dst_cowork,
            ignore=shutil.ignore_patterns("scripts", "__pycache__", "*.pyc"),
        )
        src_template = ROOT / "template"
        dst_template = workspace / "template"
        shutil.copytree(src_template, dst_template)
        # CLAUDE.md referenced relative to repo root in doctor.py.
        if (src_template / "CLAUDE.md").exists():
            shutil.copy2(src_template / "CLAUDE.md", workspace / "CLAUDE.md")
        if (src_template / "AGENTS.md").exists():
            shutil.copy2(src_template / "AGENTS.md", workspace / "AGENTS.md")
        return workspace

    def test_doctor_validates_template_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = self._build_deployed_workspace(temp_dir)
            result = self._run_doctor(workspace)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn("ERROR:", result.stderr)

    def test_doctor_finds_broken_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = self._build_deployed_workspace(temp_dir)
            # Remove a required snippet from one adapter to trigger doctor error.
            adapter = workspace / "template" / ".cowork-flow" / "adapters" / "claude-code" / "adapter.yaml"
            original = adapter.read_text(encoding="utf-8")
            broken = "\n".join(
                line for line in original.splitlines()
                if "capabilities:" not in line
            )
            assert broken != original
            adapter.write_text(broken, encoding="utf-8")
            result = self._run_doctor(workspace)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("ERROR:", result.stderr)

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
            self.assertFalse(
                (ROOT / "template" / "skills" / legacy_skill / "SKILL.md").exists()
            )

    def test_external_codex_runner_is_not_part_of_fixed_agent_model(self) -> None:
        self.assertFalse((ROOT / "template" / ".cowork-flow" / "scripts" / "agent.py").exists())
