from __future__ import annotations

import importlib
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
TEMPLATE = ROOT / "template"

# Fixed-subagent bodies per platform, and where they live. Every host reads
# skills from a project directory (`skillReadRoot`), so a body must reference
# that root; a machine-level plugin copy is the host's own channel, never a path
# our bodies point at.
PLATFORM_AGENT_SOURCES = {
    "codex": (TEMPLATE / ".codex" / "agents", "*.toml"),
    "opencode": (TEMPLATE / ".opencode" / "agents", "*.md"),
    "claude-code": (TEMPLATE / ".claude" / "agents", "*.md"),
    "kimi-code": (TEMPLATE / ".kimi-code" / "agents", "*.md"),
    "qoder": (ROOT / "presets" / "qoder" / "agents", "*.md"),
    "zcode": (ROOT / "presets" / "zcode" / "agents", "*.md"),
}
# Declarations that are still carried by convention rather than by a local
# probe. Adding a new unverified declaration must show up here on purpose.
# Currently empty: every host's discovery path is backed by a local probe (see
# the evidence strings in host-assets.json).
ASSUMED_DISCOVERY: dict[str, str] = {}
SKILL_REFERENCE = re.compile(r"[\w./-]*skills/[\w-]+/SKILL\.md")


class HostSkillsGateTest(unittest.TestCase):
    """A host's fixed subagents must read skills where that host reads them.

    This is the regression gate for the qoder incident: its agents pointed at
    `.cowork-flow/skills` while the host only ever discovers `.agents/skills`,
    so the declaration looked delivered while the host saw nothing.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.added_scripts_path = str(SCRIPTS) not in sys.path
        if cls.added_scripts_path:
            sys.path.insert(0, str(SCRIPTS))
        cls.host_manifest = importlib.import_module("adapters.host.host_manifest")

    @classmethod
    def tearDownClass(cls) -> None:
        sys.modules.pop("adapters.host.host_manifest", None)
        if cls.added_scripts_path and str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))

    def _manifest(self):
        return self.host_manifest.load_host_manifest(TEMPLATE)

    def _references(self, directory: Path, pattern: str) -> list[tuple[Path, str]]:
        found: list[tuple[Path, str]] = []
        for path in sorted(directory.glob(pattern)):
            if not path.is_file():
                continue
            for reference in SKILL_REFERENCE.findall(path.read_text(encoding="utf-8")):
                found.append((path, reference))
        return found

    def test_fixed_agent_skill_paths_match_the_declared_read_root(self) -> None:
        manifest = self._manifest()

        for platform_id, (directory, pattern) in PLATFORM_AGENT_SOURCES.items():
            platform = manifest.platform(platform_id)
            references = self._references(directory, pattern)
            self.assertNotEqual([], references, f"{platform_id}: no skill references found")

            expected = f"{platform.skill_read_root}/"
            self.assertEqual(
                [],
                [
                    f"{path.name} references {reference} while this host "
                    f"reads {expected}"
                    for path, reference in references
                    if not reference.startswith(expected)
                ],
                platform_id,
            )

    def test_discovery_evidence_is_verified_or_registered_as_assumed(self) -> None:
        manifest = self._manifest()
        assumed: dict[str, str] = {}

        for platform in manifest.platforms:
            for discovery in platform.skill_discovery:
                if discovery.evidence.startswith("assumed:"):
                    self.assertIsNotNone(
                        discovery.path,
                        f"{platform.id}: assumed discovery must name a path",
                    )
                    assumed[platform.id] = discovery.path
                else:
                    self.assertTrue(
                        discovery.evidence.startswith("verified:"),
                        f"{platform.id}: evidence must start with verified: or assumed:",
                    )

        self.assertEqual(ASSUMED_DISCOVERY, assumed)

    def test_qoder_reads_and_discovers_the_same_path(self) -> None:
        qoder = self._manifest().platform("qoder")

        self.assertEqual(".agents/skills", qoder.skill_read_root)
        self.assertEqual(
            [(".agents/skills", "project")],
            [(discovery.path, discovery.scope) for discovery in qoder.skill_discovery],
        )

    def test_review_report_carries_clause_command_and_negative_proof(self) -> None:
        """The three keys are the review report's contract, not prose.

        They are what makes a finding verifiable: without `command` and
        `negativeProof` a "pass" is the agent's own word.
        """
        skill = (
            TEMPLATE / "skills" / "task-review" / "SKILL.md"
        ).read_text(encoding="utf-8")

        self.assertIn("## Review Report Format", skill)
        # Scope the keys to the section that defines them: naming them
        # elsewhere in the skill is not the contract. Each key needs its own
        # definition bullet — a bare mention in the surrounding prose or in
        # the JSON example would otherwise keep a deleted definition passing.
        section = skill.split("## Review Report Format", 1)[1].split("\n## ", 1)[0]
        lines = [line.strip() for line in section.splitlines()]
        for marker in ("clause", "command", "negativeProof"):
            self.assertTrue(
                any(line.startswith(f"- `{marker}`:") for line in lines),
                f"`{marker}` has no definition bullet in Review Report Format",
            )
        # The receipt path must name the same keys where they are used.
        receipt_cli = (
            SCRIPTS / "adapters" / "cli" / "subagent.py"
        ).read_text(encoding="utf-8")
        for marker in ("clause", "command", "negativeProof"):
            self.assertIn(marker, receipt_cli, f"{marker} missing from check-review")

    def test_spec_check_contract_states_the_same_triple(self) -> None:
        contract = (
            TEMPLATE
            / ".cowork-flow"
            / "spec"
            / "contracts"
            / "spec-checks.md"
        ).read_text(encoding="utf-8")

        self.assertIn("条款 → 命令 → 反例", contract)
        for marker in ("`clause`", "`command`", "`negativeProof`"):
            self.assertIn(marker, contract, f"{marker} missing from the contract")

    def test_template_ships_no_spec_check_declarations(self) -> None:
        """A shipped declaration would be `unchecked` in every install.

        The template cannot know a project's toolchain, so a template-owned
        `checks:` entry either blocks `complete` for everyone or is a
        decorative always-pass. Declarations belong to the project.
        """
        module = importlib.import_module("services.spec_check")
        try:
            collected = module.collect_spec_declarations(TEMPLATE)
        finally:
            sys.modules.pop("services.spec_check", None)

        self.assertEqual(
            [],
            [
                (spec.spec, decl.cmd)
                for spec in collected
                for decl in spec.decls
            ],
        )
        self.assertEqual([], [spec.errors for spec in collected if spec.errors])

    def _skill_manifests(self) -> list:
        module = importlib.import_module("infra.skill_manifest")
        try:
            return module.load_skill_manifests(TEMPLATE)
        finally:
            sys.modules.pop("infra.skill_manifest", None)

    def test_only_one_skill_owns_the_doubt_cycle(self) -> None:
        """decision-audit duplicated adversarial-review's review loop.

        Two owners of the same entry point is what made the review surface
        ambiguous; a second owner must fail here rather than be discovered in
        a session.
        """
        owners = [
            path.parent.name
            for path in sorted((TEMPLATE / "skills").glob("*/SKILL.md"))
            if "**DOUBT**" in path.read_text(encoding="utf-8")
            and "**RECONCILE**" in path.read_text(encoding="utf-8")
        ]

        self.assertEqual(["adversarial-review"], owners)

    def test_template_ships_no_game_domain_guide_or_spec(self) -> None:
        """Game guidance is a project concern, not a framework default."""
        self.assertFalse((TEMPLATE / "skills" / "game-design").exists())
        self.assertFalse((TEMPLATE / ".cowork-flow" / "spec" / "game").exists())
        self.assertEqual(
            [],
            [
                pattern
                for manifest in self._skill_manifests()
                for rule in manifest.context_rules
                for pattern in rule.path_patterns
                if "game" in pattern.lower()
            ],
        )

    def test_maintenance_guide_is_scoped_to_the_source_checkout(self) -> None:
        """An installed project edits `.cowork-flow/**` on every single task.

        Routing the maintenance guide on those paths armed it for ordinary
        project work; only trees that exist in the framework checkout may
        arm it.
        """
        rules = [
            rule
            for manifest in self._skill_manifests()
            if manifest.skill == "cowork-flow-maintenance"
            for rule in manifest.context_rules
        ]

        self.assertEqual(1, len(rules))
        patterns = list(rules[0].path_patterns)
        self.assertEqual(
            [],
            [pattern for pattern in patterns if pattern.startswith(".cowork-flow")],
            "an installed project's own .cowork-flow edits must not arm this guide",
        )
        self.assertEqual(
            [],
            [
                pattern
                for pattern in patterns
                if pattern.split("/")[0] not in {"template", "presets"}
            ],
            "only framework-checkout trees may arm this guide",
        )

    def test_batch_execution_does_not_call_check_jsonl_review_evidence(self) -> None:
        text = (
            TEMPLATE / "skills" / "batch-execution" / "SKILL.md"
        ).read_text(encoding="utf-8")

        self.assertNotIn("review evidence", text)
        self.assertIn("review results belong in `review.jsonl`", text)

    def test_task_planning_gate_names_the_plan_as_the_task_list(self) -> None:
        """The plan owns the task list; `implement.jsonl` owns this task's scope.

        `implement.jsonl` is the current task's context index — the files in
        scope and the spec pointers it needs — so a gate condition of "every
        task in `implement.jsonl`" is unsatisfiable. Guard the corrected
        wording so it cannot drift back.
        """
        skill = (
            TEMPLATE / "skills" / "task-planning" / "SKILL.md"
        ).read_text(encoding="utf-8")

        self.assertIn("## Plan Approval Gate", skill)
        # Scope the check to the gate: naming the plan elsewhere in the skill
        # would not satisfy the condition the gate states.
        section = skill.split("## Plan Approval Gate", 1)[1].split("\n## ", 1)[0]
        self.assertNotIn("Every task in `implement.jsonl`", section)
        self.assertIn("Every task in the plan", section)


if __name__ == "__main__":
    unittest.main()
