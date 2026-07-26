from __future__ import annotations

import ast
import json
import re
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


def template_skill_ids() -> set[str]:
    return {
        path.parent.name
        for path in (ROOT / "template" / "skills").glob("*/SKILL.md")
    }


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
    def _assert_shared_party_mode_boundaries(self, skill_text: str, link: str) -> None:
        self.assertIn(link, skill_text)
        shared_text = (
            ROOT / "template" / "skills" / "party-mode" / "SHARED-BOUNDARIES.md"
        ).read_text(encoding="utf-8")
        normalized = re.sub(r"\s+", " ", shared_text).lower()
        self.assertIn("advisory", normalized)
        self.assertRegex(
            normalized,
            r"(?:cannot|must not|does not).*formal implement or check completion",
        )

    def test_skill_set_is_direct_and_fixed_agent_based(self) -> None:
        expected = {
            "adversarial-review",
            "agent-dispatch",
            "batch-execution",
            "brainstorming",
            "cowork-flow",
            "cowork-flow-maintenance",
            "decision-audit",
            "failure-analysis",
            "game-design",
            "party-mode",
            "python-runtime-design",
            "runtime-health",
            "spec-sync",
            "task-planning",
            "task-review",
            "test-first",
        }
        actual = {
            path.name
            for path in (ROOT / "template" / "skills").iterdir()
            if path.is_dir() and not path.name.startswith("bmad-")
        }
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

    def test_codex_agent_wrappers_do_not_inline_runtime_gate_commands(self) -> None:
        for path in (
            ROOT / "template" / ".codex" / "agents" / "cowork-implement.toml",
            ROOT / "template" / ".codex" / "agents" / "cowork-check.toml",
        ):
            text = path.read_text(encoding="utf-8")
            targets = re.findall(r"(?<![\w.-])(\.cowork-flow/[A-Za-z0-9_./-]+\.py)", text)
            self.assertEqual([], targets, f"runtime gate command leaked into {path}")
            self.assertIn("agent-dispatch", text)
            self.assertNotIn("бк", text, f"unexpected mixed-script text in {path}")

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
        for skill_id in template_skill_ids():
            self.assertTrue((ROOT / "template" / "skills" / skill_id / "SKILL.md").is_file())
        self.assertFalse((ROOT / "template" / "skills" / ENTRY_BOUNDARY / "SKILL.md").exists())
        self.assertTrue((ROOT / "CLAUDE.md").is_file())
        self.assertTrue((ROOT / "template" / "CLAUDE.md").is_file())

    def test_party_mode_skill_is_single_runtime_board_entrypoint(self) -> None:
        required_markers = (
            "single public Party Mode entrypoint",
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
        )
        forbidden_markers = (
            "Round 1 uses fresh child contexts",
            "compact claim table",
            "Coordinator Output Schema",
            "manual fallback",
            "manual advisory roundtable",
            "spawn_agent",
            "wait_agent",
            "close_agent",
        )
        text = (ROOT / "template" / "skills" / "party-mode" / "SKILL.md").read_text(encoding="utf-8")
        for marker in required_markers:
            self.assertIn(marker, text, f"{marker} missing from template/skills/party-mode/SKILL.md")
        for marker in forbidden_markers:
            self.assertNotIn(marker, text, f"{marker} should stay out of template/skills/party-mode/SKILL.md")
        self.assertFalse(
            (ROOT / "template" / "skills" / "party-mode-v2" / "SKILL.md").exists()
        )
        self._assert_shared_party_mode_boundaries(
            text,
            "See [SHARED-BOUNDARIES.md](SHARED-BOUNDARIES.md)",
        )

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
            self.assertIn("agent-dispatch", text)
            self.assertIn("needs_context", text)
            self.assertIn("MUST NOT spawn", text)
            self.assertIn("multi_agent = false", text)
            self.assertIn("enabled = false", text)

    def test_cowork_implement_forbids_tdd_evidence_artifacts(self) -> None:
        required_markers = (
            "TDD evidence records",
            "`tdd.jsonl`",
            "verification commands",
        )
        forbidden_markers = (
            "redExitCode",
            "greenExitCode",
            ".cowork-flow/spec/protocols/tdd.md",
            "tdd_exemption",
        )
        for path in (
            ROOT / "template" / ".codex" / "agents" / "cowork-implement.toml",
        ):
            prompt = path.read_text(encoding="utf-8")
            for marker in required_markers:
                self.assertIn(marker, prompt, f"{marker} missing from {path}")
            for marker in forbidden_markers:
                self.assertNotIn(marker, prompt, f"{marker} should stay out of {path}")

    def test_cowork_check_requires_test_intent_review(self) -> None:
        required_markers = (
            "test intent review",
            "shallow tests",
            "target behavior breaks",
            "acceptance IDs",
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

    def test_agents_require_agent_dispatch_skill(self) -> None:
        fixed_agents = {
            "cowork-research": "research",
            "cowork-implement": "implement",
            "cowork-check": "check",
        }
        for agent_name, workflow_role in fixed_agents.items():
            path = ROOT / "template" / ".codex" / "agents" / f"{agent_name}.toml"
            text = path.read_text(encoding="utf-8")
            required_markers = (
                ".agents/skills/agent-dispatch/SKILL.md",
                "needs_context",
                "MUST NOT spawn",
                f"`{agent_name}` subagent",
            )
            self.assertIn(workflow_role, text)
            for marker in required_markers:
                self.assertIn(marker, text, f"{marker} missing from {path}")

    def test_fixed_agents_share_required_skill_contracts(self) -> None:
        role_contracts = {
            "cowork-implement": (
                "decision-audit/SKILL.md",
                "spec-sync/SKILL.md",
                "verification commands",
                "acceptance IDs",
            ),
            "cowork-check": (
                "task-review/SKILL.md",
                "decision-audit/SKILL.md",
                "spec-sync/SKILL.md",
                "test intent review",
                "findings",
                "resolution",
                "acceptance IDs",
            ),
        }
        role_paths = {
            role: (
                ROOT / "template" / ".codex" / "agents" / f"{role}.toml",
                ROOT / "template" / ".claude" / "agents" / f"{role}.md",
                ROOT / "template" / ".opencode" / "agents" / f"{role}.md",
            )
            for role in role_contracts
        }

        for role, paths in role_paths.items():
            for path in paths:
                text = path.read_text(encoding="utf-8")
                missing = [
                    marker for marker in role_contracts[role] if marker not in text
                ]
                self.assertEqual(
                    [],
                    missing,
                    f"{role} required Skill contract drift in {path}: {missing}",
                )

    def test_fixed_agents_require_review_skill_without_dynamic_validator_claims(self) -> None:
        role_paths = (
            ROOT / "template" / ".codex" / "agents" / "cowork-implement.toml",
            ROOT / "template" / ".codex" / "agents" / "cowork-check.toml",
            ROOT / "template" / ".claude" / "agents" / "cowork-implement.md",
            ROOT / "template" / ".claude" / "agents" / "cowork-check.md",
            ROOT / "template" / ".opencode" / "agents" / "cowork-implement.md",
            ROOT / "template" / ".opencode" / "agents" / "cowork-check.md",
        )
        required_markers = (
            "agent-dispatch",
            "needs_context",
        )
        forbidden_markers = (
            "quality" + "-review",
            "quality" + "_review",
            "activate validators dynamically",
            "active validators",
            "not just documentation but active validators",
            "Read .",
        )
        review_skill = (
            ROOT / "template" / "skills" / "task-review" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("review result", review_skill)
        self.assertIn("not dynamic hard validators", review_skill)

        for path in role_paths:
            text = path.read_text(encoding="utf-8")
            missing = [marker for marker in required_markers if marker not in text]
            self.assertEqual([], missing, f"review prompt drift in {path}: {missing}")
            for marker in forbidden_markers:
                self.assertNotIn(marker, text, f"{marker} should stay out of {path}")

    def _run_doctor(self, cwd: Path) -> subprocess.CompletedProcess[str]:
        doctor = ROOT / "template" / "skills" / "runtime-health" / "scripts" / "doctor.py"
        return subprocess.run(
            [sys.executable, str(doctor), "--host-adapters"],
            cwd=cwd,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=30,
        )

    def test_subagent_safety_doctor_accepts_current_codex_hook_command(self) -> None:
        doctor = (
            ROOT
            / "template"
            / "skills"
            / "runtime-health"
            / "scripts"
            / "doctor.py"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = self._build_deployed_workspace(temp_dir)
            result = subprocess.run(
                [sys.executable, str(doctor), "--subagent-safety"],
                cwd=workspace,
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=30,
            )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

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
