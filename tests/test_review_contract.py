from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from tests.flow_test_support import ROOT


TEMPLATE = ROOT / "template"
SPEC = TEMPLATE / ".cowork-flow" / "spec"
INSTANCE_SPEC = ROOT / ".cowork-flow" / "spec"

# A contract declares its gate codes in a table whose first column is the code.
_CODE_CELL = re.compile(r"^\|\s*`([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+)`\s*\|")
_CODE = re.compile(r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+\b")
# `LIFECYCLE-AC-001/002/003` is how the index compresses a run of codes.
_CODE_RUN = re.compile(r"\b([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*)-(\d+)((?:/\d+)+)")
_INDEX_ENTRY = re.compile(r"^- `([a-z0-9-]+\.md)`:")


def _expand_code_run(match: re.Match) -> str:
    """`-AC-001/002/003` -> `-AC-001 -AC-002 -AC-003` for the set comparison."""
    root = match.group(1)
    numbers = [match.group(2)] + [part for part in match.group(3).split("/") if part]
    return " ".join(f"{root}-{number}" for number in numbers)


class SpecReviewContractTest(unittest.TestCase):
    def test_user_spec_directories_remain_markdown_sources_not_runtime_rules(self) -> None:
        for directory in ("backend", "frontend", "guides"):
            spec_dir = SPEC / directory
            self.assertTrue(spec_dir.is_dir(), spec_dir)
            markdown_files = sorted(path.name for path in spec_dir.glob("*.md"))
            self.assertIn("index.md", markdown_files)
            self.assertGreater(len(markdown_files), 1, markdown_files)

        self.assertFalse((SPEC / "runtime" / "rules.json").exists())
        self.assertFalse((SPEC / "schemas" / "rules.schema.json").exists())

    def test_spec_index_places_guides_in_planning_not_review_sources(self) -> None:
        index = (SPEC / "index.md").read_text(encoding="utf-8")

        required_markers = (
            "流程内核只负责",
            "`backend/`、`frontend/` 中的自然语言规范不注册为 runtime gate",
            "`task-review` skill 根据当前 diff 和任务范围读取并逐条审查",
            "`guides/` 属于前置澄清与计划参考",
            "`decision-anchor.md` 或任务计划",
        )
        forbidden_markers = (
            "`backend/`、`frontend/`、`guides/` 中的自然语言规范",
            "runtime/rules.json",
        )

        self.assertEqual([], [marker for marker in required_markers if marker not in index])
        self.assertEqual([], [marker for marker in forbidden_markers if marker in index])

    def test_runtime_index_no_longer_declares_rule_registry(self) -> None:
        runtime_index = (SPEC / "runtime" / "index.md").read_text(encoding="utf-8")
        schema_index = (SPEC / "schemas" / "index.md").read_text(encoding="utf-8")

        self.assertIn("contract-registry.json", runtime_index)
        self.assertIn("host-assets.json", runtime_index)
        self.assertIn("用户自然语言规范不在本目录注册", runtime_index)
        self.assertNotIn("rules.json", runtime_index)
        self.assertNotIn("rules.schema.json", schema_index)

    def test_host_assets_obsoletes_removed_gate_and_rule_assets(self) -> None:
        manifest = json.loads((SPEC / "runtime" / "host-assets.json").read_text(encoding="utf-8"))
        sync_policy = manifest["syncPolicy"]
        obsolete = set(sync_policy["obsoleteFiles"])
        safe_files = set(sync_policy["safeFiles"])

        self.assertNotIn(".cowork-flow/spec/runtime/rules.json", safe_files)
        # Retirement and preservation are mutually exclusive: a path claimed
        # by both sets would make the sync outcome undefined.
        self.assertEqual(set(), obsolete & safe_files)
        for path in (
            ".cowork-flow/spec/runtime/rules.json",
            ".cowork-flow/spec/schemas/rules.schema.json",
            ".cowork-flow/scripts/common/gates/gates.py",
            ".cowork-flow/scripts/common/gates/models.py",
            ".cowork-flow/scripts/common/gates/registry.py",
            ".cowork-flow/scripts/common/gates/validate_rules.py",
            ".cowork-flow/scripts/common/gates/validate_implementation.py",
            ".cowork-flow/scripts/common/gates/validate_coding_standards.py",
        ):
            self.assertIn(path, obsolete)

        # The spec-check mechanism is gone: its contract and its two modules
        # must be retired from installs rather than shipped, so a project that
        # upgrades gets them deleted instead of left behind.
        for path in (
            ".cowork-flow/spec/contracts/spec-checks.md",
            ".cowork-flow/scripts/services/spec_check.py",
            ".cowork-flow/scripts/adapters/cli/spec_check.py",
        ):
            self.assertIn(path, obsolete)
            self.assertNotIn(path, safe_files)

    def test_contract_registry_drops_the_spec_checks_contract(self) -> None:
        registry = json.loads(
            (SPEC / "runtime" / "contract-registry.json").read_text(encoding="utf-8")
        )
        ids = [contract["id"] for contract in registry["contracts"]]

        self.assertNotIn("SPEC_CHECKS_V1", ids)
        self.assertEqual(
            [],
            [
                contract["path"]
                for contract in registry["contracts"]
                if "spec-checks" in contract["path"]
            ],
        )
        # The remaining contracts still ship their entries.
        self.assertEqual(9, len(ids))
        for remaining in ("RUNTIME_CONTEXT_DISPATCH_V2", "PLAN_BINDING_LITE_V1"):
            self.assertIn(remaining, ids)

    def test_runtime_spec_documents_real_storage_layer_path(self) -> None:
        runtime_index = (SPEC / "runtime" / "index.md").read_text(encoding="utf-8")
        template_scripts = TEMPLATE / ".cowork-flow" / "scripts"

        self.assertTrue((template_scripts / "infra" / "storage").is_dir())
        self.assertEqual([], list((template_scripts / "kernel" / "storage").glob("*.py")))
        self.assertIn("scripts/infra/storage/", runtime_index)
        self.assertNotIn("scripts/kernel/storage/", runtime_index)
        self.assertNotIn("scripts/common/storage/", runtime_index)

    def test_task_review_skill_requires_per_requirement_user_spec_review(self) -> None:
        skill = (TEMPLATE / "skills" / "task-review" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        required_markers = (
            "Relevant `.cowork-flow/spec/backend/` and `.cowork-flow/spec/frontend/` files",
            "every applicable backend/frontend requirement",
            "pass",
            "finding",
            "not_applicable",
            "mandatory review input",
            "fix every violation before completion",
            "never accepted as-is or deferred to the user",
            "not eligible for acceptance",
            "user_spec_review",
            "lifecycle_check_review",
            "anti-self-proof",
            "anti-rationalization",
            "verification-before-completion",
            "machine-checkable",
            "name the command that decides it",
            "what that command reports when the clause is broken",
            "a machine-checkable clause left with no deciding command is itself a finding",
            "Review never rewrites the clause text",
            "clause → command",
        )
        forbidden_markers = (
            "guides",
            ".cowork-flow/spec/guides/",
            "backend/frontend/guides",
            "needs_user_judgment",
            "not dynamic hard validators",
            # The declaration mechanism and its edit-phase command were
            # removed; the duty is now to name the deciding command inline.
            "`checks:`",
            "spec-check",
        )

        self.assertEqual([], [marker for marker in required_markers if marker not in skill])
        self.assertEqual([], [marker for marker in forbidden_markers if marker in skill])

    def test_spec_sync_skill_declares_no_check_declaration_duty(self) -> None:
        """Sync still owns concrete spec updates, but the `checks:` frontmatter
        declaration went away with `spec-check`; re-teaching it would point
        agents at a mechanism that no longer runs."""
        skill = (TEMPLATE / "skills" / "spec-sync" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        required_markers = (
            "Show the contract or command shape.",
            "State tests or checks that protect the behavior.",
            "Check for duplicate guidance and remove stale wording before finishing.",
        )
        self.assertEqual([], [marker for marker in required_markers if marker not in skill])
        for stale_marker in ("`checks:`", "spec-check", "main session only"):
            self.assertNotIn(stale_marker, skill)

    def test_task_review_skill_uses_task_next_for_lifecycle_blockers(self) -> None:
        skill = (TEMPLATE / "skills" / "task-review" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        required_markers = (
            "task next --json",
            "task next <dir> --validate",
            "task next <dir> --run --intent review",
        )
        stale_markers = ("`task review`", "`task complete`")

        self.assertEqual(
            [],
            [marker for marker in required_markers if marker not in skill],
        )
        self.assertEqual(
            [],
            [marker for marker in stale_markers if marker in skill],
        )

    def test_lifecycle_reference_docs_use_task_next_entrypoint(self) -> None:
        docs = {
            "contracts/decision-anchor.md": (
                "task next <dir> --run",
                "task start",
            ),
            "references/definition-of-done.md": (
                "task next <dir> --run",
                "task start",
            ),
            "references/orchestration-patterns.md": (
                "task next --run --title",
                "/start",
            ),
        }

        for relative_path, (required, forbidden) in docs.items():
            with self.subTest(path=relative_path):
                text = (SPEC / relative_path).read_text(encoding="utf-8")
                self.assertEqual(
                    (True, False),
                    (required in text, forbidden in text),
                )

    def test_adversarial_review_skill_uses_severity_and_contract_first_review(self) -> None:
        skill = (TEMPLATE / "skills" / "adversarial-review" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        required_markers = (
            "precise context",
            "severity",
            "critical",
            "important",
            "minor",
            "verification-before-completion",
            "anti-rationalization",
            "Pass only ARTIFACT + CONTRACT",
        )
        missing = [marker for marker in required_markers if marker not in skill]
        self.assertEqual([], missing)

    def test_task_review_skill_avoids_review_evidence_artifact_pressure(self) -> None:
        skill = (TEMPLATE / "skills" / "task-review" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("check context index", skill)
        self.assertIn("do not write review conclusions", skill)
        self.assertIn("advisory helper output", skill)
        for forbidden in (
            "quality-review.jsonl",
            "review.jsonl",
            "coding-review.jsonl",
            "evidenceArtifact",
            "machine_gate_review",
        ):
            self.assertNotIn(forbidden, skill)

    def test_review_helper_contract_stays_advisory_not_gate(self) -> None:
        contract = (
            SPEC / "contracts" / "skill-owned-actions.md"
        ).read_text(encoding="utf-8")

        self.assertIn("advisory facts", contract)
        self.assertIn("read-only helpers", contract)
        self.assertIn("diagnosticsCommand", contract)
        self.assertIn("no task-local review evidence file", contract)
        self.assertIn("pass/fail completion verdict", contract)
        self.assertIn("natural-language spec hard gate", contract)

    def test_runtime_health_contract_distinguishes_template_source_from_optional_local_runtime(self) -> None:
        contract = (
            SPEC / "contracts" / "skill-owned-actions.md"
        ).read_text(encoding="utf-8")
        skill = (TEMPLATE / "skills" / "runtime-health" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        for marker in (
            "ignored local live runtime",
            "template distribution source",
            "must not force-track `.cowork-flow/` runtime files",
            "stale task hygiene",
        ):
            self.assertIn(marker, contract)
            self.assertIn(marker, skill)

    def test_removed_gate_modules_do_not_exist_in_template(self) -> None:
        gates_dir = TEMPLATE / ".cowork-flow" / "scripts" / "common" / "gates"

        gate_sources = []
        if gates_dir.exists():
            gate_sources = [
                path
                for path in gates_dir.rglob("*")
                if path.is_file() and path.suffix in {".py", ".json"}
            ]
        self.assertEqual([], gate_sources)
        self.assertTrue(
            (TEMPLATE / ".cowork-flow" / "scripts" / "services" / "lifecycle_checks.py").is_file()
        )
        self.assertTrue(
            (TEMPLATE / ".cowork-flow" / "scripts" / "adapters" / "review" / "test_intent.py").is_file()
        )

    def test_contract_index_lists_every_code_its_contracts_declare(self) -> None:
        """The index names the gate codes each contract declares — no silent gaps.

        A contract declares its codes in a table whose first column is the code.
        The index line for that contract must name every one of them: the second
        round of gate hardening shipped a stricter completion gate whose codes
        only ever existed in the contract, so the index still offered to tell a
        reader "001/002" and left the two codes that actually block completion
        unlisted. Under-declaring is what this locks; over-listing fails too, so
        the index cannot name a code the contract dropped.

        Driven from the contracts, not from the index: an index entry that is
        missing entirely, or whose list marker was changed, would otherwise be
        skipped without ever being looked at — which is the same silence this
        test exists to break. A code a contract mentions only in prose is
        outside the rule, because forcing every prose mention into the index
        would turn it into a second copy of the contract.

        Only the shipped tree is read here, so this also runs on a CI checkout
        that has no local `.cowork-flow` instance (it is gitignored). The
        instance copy carries the same content through
        `test_instance_contracts_mirror_the_template_byte_for_byte`.
        """
        listed: dict[str, set[str]] = {}
        for line in (SPEC / "contracts" / "index.md").read_text(encoding="utf-8").splitlines():
            entry = _INDEX_ENTRY.match(line.strip())
            if entry:
                listed[entry.group(1)] = set(
                    _CODE.findall(_CODE_RUN.sub(_expand_code_run, line))
                )
        for path in sorted((SPEC / "contracts").glob("*.md")):
            body = path.read_text(encoding="utf-8")
            declared = {
                match.group(1)
                for text in body.splitlines()
                if (match := _CODE_CELL.match(text))
            }
            if not declared:
                continue
            self.assertIn(path.name, listed, f"contracts/index.md has no entry for {path.name}")
            self.assertEqual(
                declared,
                listed[path.name],
                f"contracts/index.md mis-lists {path.name}",
            )

    def test_instance_contracts_mirror_the_template_byte_for_byte(self) -> None:
        """The instance this repo is gated by is the tree it ships.

        In the source checkout `.cowork-flow/spec/**` is *not* a protected
        prefix — `isSourceCheckoutProtected` drops it on purpose — so
        `dev refresh` does rewrite it, and `self-instance-drift` in
        `release:check` already refuses a divergence. That gate only runs where
        `release:check` runs, which is the ubuntu job; the Windows job runs
        `python -m pytest -q` and never calls it, so this assertion is what
        would catch a half-edited contract there, days before a release.

        Skipped, not failed, when the checkout has no local instance: a CI
        checkout has none (`.cowork-flow/` is gitignored), and "no instance" is
        not a defect. An instance that exists but lost its `spec/contracts`
        directory *is* one, so that state fails instead of skipping. The
        comparison is byte-exact, so it also fails when one tree gains CRLF
        endings while the other keeps LF — a real divergence, not noise.
        """
        if not (ROOT / ".cowork-flow").is_dir():
            self.skipTest("no local .cowork-flow instance in this checkout (it is gitignored)")
        self.assertTrue(
            (INSTANCE_SPEC / "contracts").is_dir(),
            "local instance has no spec/contracts directory",
        )
        template_files = {
            path.name: path
            for path in (TEMPLATE / ".cowork-flow" / "spec" / "contracts").glob("*.md")
        }
        instance_files = {
            path.name: path
            for path in (INSTANCE_SPEC / "contracts").glob("*.md")
        }
        self.assertEqual(sorted(template_files), sorted(instance_files))
        for name in sorted(template_files):
            self.assertEqual(
                template_files[name].read_bytes(),
                instance_files[name].read_bytes(),
                f"contracts/{name} differs between template and this instance",
            )


if __name__ == "__main__":
    unittest.main()
