from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests.flow_test_support import ROOT


TEMPLATE = ROOT / "template"
SPEC = TEMPLATE / ".cowork-flow" / "spec"


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

    def test_spec_index_says_review_skill_reads_user_specs(self) -> None:
        index = (SPEC / "index.md").read_text(encoding="utf-8")

        self.assertIn("流程内核只负责", index)
        self.assertIn("task-review", index)
        self.assertIn("不注册为 runtime gate", index)
        self.assertNotIn("runtime/rules.json", index)

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

    def test_task_review_skill_requires_per_requirement_user_spec_review(self) -> None:
        skill = (TEMPLATE / "skills" / "task-review" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        required_markers = (
            "Relevant `.cowork-flow/spec/backend/`, `.cowork-flow/spec/frontend/`, and `.cowork-flow/spec/guides/` files",
            "every applicable backend/frontend/guides requirement",
            "pass",
            "finding",
            "not_applicable",
            "needs_user_judgment",
            "user_spec_review",
            "lifecycle_check_review",
            "anti-self-proof",
            "anti-rationalization",
            "verification-before-completion",
        )
        missing = [marker for marker in required_markers if marker not in skill]
        self.assertEqual([], missing)

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


if __name__ == "__main__":
    unittest.main()
