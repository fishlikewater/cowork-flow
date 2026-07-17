from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
SCRIPTS = TEMPLATE / ".cowork-flow" / "scripts"
MODULE_PATH = SCRIPTS / "common" / "core" / "skill_registry.py"
REGISTRY_PATH = (
    TEMPLATE / ".cowork-flow" / "spec" / "runtime" / "skill-registry.json"
)
SCHEMA_PATH = (
    TEMPLATE / ".cowork-flow" / "spec" / "schemas" / "skill-registry.schema.json"
)


def registry_fixture() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "entries": [
            {
                "id": "workflow-readiness",
                "displayName": "Workflow Readiness",
                "aliases": [],
                "kind": "runtime",
                "visibility": "internal",
                "status": "active",
                "statuses": [],
                "intents": [],
                "enforcement": "runtime",
                "runtimeGate": None,
                "runtimeCommand": "task next",
                "evidenceArtifact": None,
                "source": ".cowork-flow/scripts/common/task/readiness.py",
                "managedPaths": [],
            },
            {
                "id": "example",
                "displayName": "Example",
                "aliases": [],
                "kind": "phase",
                "visibility": "public",
                "status": "active",
                "statuses": ["planning"],
                "intents": ["example_intent"],
                "enforcement": "advisory",
                "runtimeGate": None,
                "runtimeCommand": None,
                "evidenceArtifact": None,
                "source": "skills/brainstorming/SKILL.md",
                "managedPaths": [
                    ".agents/skills/example/",
                    ".claude/skills/example/",
                ],
            },
        ],
    }


NODE_REJECTION_SCRIPT = """
import { createSkillRegistry } from './src/lib/skill-registry.js';
let input = '';
process.stdin.setEncoding('utf8');
for await (const chunk of process.stdin) input += chunk;
try {
  createSkillRegistry(JSON.parse(input));
  process.stdout.write('OK');
} catch (error) {
  process.stdout.write(error.message);
  process.exitCode = 42;
}
"""


def registry_rejection_cases() -> list[tuple[dict[str, object], str]]:
    deprecated = registry_fixture()
    deprecated["entries"][1]["status"] = "deprecated"

    replacement = registry_fixture()
    replacement["entries"][1]["replacement"] = "workflow-readiness"

    overlap = registry_fixture()
    nested = deepcopy(overlap["entries"][1])
    nested.update(
        {
            "id": "nested",
            "intents": ["nested_intent"],
            "managedPaths": [".agents/skills/example/nested/"],
        }
    )
    overlap["entries"].append(nested)

    return [
        (deprecated, "invalid status for example: deprecated"),
        (replacement, "unexpected field for example: replacement"),
        (overlap, "managed path overlap"),
    ]


class SkillRegistryTest(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)

    def _cleanup_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in (
            "commands.doctor",
            "commands",
            "common.core.skill_registry",
            "common.core",
            "common",
        ):
            sys.modules.pop(module_name, None)

    def _module(self):
        self.assertTrue(
            MODULE_PATH.is_file(),
            "AC-002 requires the Python Skill Registry loader",
        )
        return importlib.import_module("common.core.skill_registry")

    def test_canonical_registry_and_schema_load(self) -> None:
        self.assertTrue(REGISTRY_PATH.is_file(), "AC-002 requires Registry JSON")
        self.assertTrue(SCHEMA_PATH.is_file(), "AC-002 requires Registry schema")
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            "https://json-schema.org/draft/2020-12/schema",
            schema["$schema"],
        )
        self.assertFalse(schema["additionalProperties"])

        registry = self._module().load_skill_registry(TEMPLATE)

        self.assertEqual(1, registry.schema_version)
        self.assertEqual(
            tuple(sorted(registry.public_skill_ids)),
            registry.public_skill_ids,
        )
        self.assertIn("batch-mode", registry.public_skill_ids)
        for removed_skill_id in (
            "before-dev",
            "start",
            "continue",
            "finish-work",
            "using-cowork-flow",
        ):
            with self.assertRaisesRegex(
                self._module().SkillRegistryError,
                f"unknown Skill Registry entry: {removed_skill_id}",
            ):
                registry.entry(removed_skill_id)

    def test_duplicate_id_or_alias_is_rejected(self) -> None:
        module = self._module()
        raw = registry_fixture()
        duplicate = deepcopy(raw["entries"][1])
        duplicate.update(
            {
                "id": "other",
                "aliases": ["example"],
                "intents": ["other_intent"],
                "managedPaths": [
                    ".agents/skills/other/",
                    ".claude/skills/other/",
                ],
            }
        )
        raw["entries"].append(duplicate)

        with self.assertRaisesRegex(
            module.SkillRegistryError,
            "duplicate skill id or alias: example",
        ):
            module.create_skill_registry(raw, TEMPLATE)

    def test_invalid_enum_is_rejected(self) -> None:
        module = self._module()
        raw = registry_fixture()
        raw["entries"][1]["kind"] = "unknown"

        with self.assertRaisesRegex(
            module.SkillRegistryError,
            "invalid kind for example: unknown",
        ):
            module.create_skill_registry(raw, TEMPLATE)

    def test_removed_lifecycle_fields_are_rejected(self) -> None:
        module = self._module()
        deprecated = registry_fixture()
        deprecated["entries"][1]["status"] = "deprecated"

        with self.assertRaisesRegex(
            module.SkillRegistryError,
            "invalid status for example: deprecated",
        ):
            module.create_skill_registry(deprecated, TEMPLATE)

        replacement = registry_fixture()
        replacement["entries"][1]["replacement"] = "workflow-readiness"
        with self.assertRaisesRegex(
            module.SkillRegistryError,
            "unexpected field for example: replacement",
        ):
            module.create_skill_registry(replacement, TEMPLATE)

    def test_mandatory_entry_requires_runtime_gate(self) -> None:
        module = self._module()
        raw = registry_fixture()
        raw["entries"][1]["enforcement"] = "mandatory"

        with self.assertRaisesRegex(
            module.SkillRegistryError,
            "mandatory entry example requires runtimeGate",
        ):
            module.create_skill_registry(raw, TEMPLATE)

    def test_runtime_gate_must_reference_runtime_entry(self) -> None:
        module = self._module()
        raw = registry_fixture()
        raw["entries"][1]["enforcement"] = "mandatory"
        raw["entries"][1]["runtimeGate"] = "example"

        with self.assertRaisesRegex(
            module.SkillRegistryError,
            "runtimeGate example must reference a runtime entry",
        ):
            module.create_skill_registry(raw, TEMPLATE)

    def test_missing_source_is_rejected(self) -> None:
        module = self._module()
        raw = registry_fixture()
        raw["entries"][1]["source"] = "skills/missing/SKILL.md"

        with self.assertRaisesRegex(
            module.SkillRegistryError,
            "source does not exist for example: skills/missing/SKILL.md",
        ):
            module.create_skill_registry(raw, TEMPLATE)

    def test_runtime_load_can_skip_template_source_existence(self) -> None:
        module = self._module()
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir)
            registry_path = (
                runtime_root
                / ".cowork-flow"
                / "spec"
                / "runtime"
                / "skill-registry.json"
            )
            registry_path.parent.mkdir(parents=True)
            registry_path.write_text(
                json.dumps(registry_fixture(), ensure_ascii=False, indent=2)
                + "\n",
                encoding="utf-8",
            )

            registry = module.load_skill_registry(
                runtime_root,
                validate_sources=False,
            )

        self.assertEqual(("example",), registry.public_skill_ids)

    def test_overlapping_managed_paths_are_rejected(self) -> None:
        module = self._module()
        raw = registry_fixture()
        nested = deepcopy(raw["entries"][1])
        nested.update(
            {
                "id": "nested",
                "intents": ["nested_intent"],
                "managedPaths": [".agents/skills/example/nested/"],
            }
        )
        raw["entries"].append(nested)

        with self.assertRaisesRegex(
            module.SkillRegistryError,
            "managed path overlap",
        ):
            module.create_skill_registry(raw, TEMPLATE)

    def test_node_and_python_normalization_match(self) -> None:
        registry = self._module().load_skill_registry(TEMPLATE)
        script = (
            "import { loadSkillRegistry } from './src/lib/skill-registry.js';"
            "process.stdout.write(JSON.stringify(loadSkillRegistry().normalized));"
        )
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            cwd=ROOT,
            check=True,
            capture_output=True,
            encoding="utf-8",
        )

        self.assertEqual(registry.to_dict(), json.loads(completed.stdout))

    def test_node_and_python_reject_same_registry_drift_cases(self) -> None:
        module = self._module()

        for raw, expected in registry_rejection_cases():
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(module.SkillRegistryError, expected):
                    module.create_skill_registry(deepcopy(raw), TEMPLATE)

                completed = subprocess.run(
                    ["node", "--input-type=module", "-e", NODE_REJECTION_SCRIPT],
                    cwd=ROOT,
                    input=json.dumps(raw),
                    capture_output=True,
                    encoding="utf-8",
                    check=False,
                )

                self.assertEqual(42, completed.returncode, completed.stdout)
                self.assertIn(expected, completed.stdout)

    def test_internal_protocols_use_spec_sources_and_are_not_distributed(self) -> None:
        registry = self._module().load_skill_registry(TEMPLATE)
        expected = {
            "tdd-protocol": (
                ".cowork-flow/spec/protocols/tdd.md",
                "mandatory",
                "tdd-evidence",
                "check.jsonl",
            ),
            "review-protocol": (
                ".cowork-flow/spec/protocols/review.md",
                "mandatory",
                "review-gates",
                "check.jsonl",
            ),
            "decision-review": (
                ".cowork-flow/spec/protocols/decision-review.md",
                "mandatory",
                "workflow-readiness",
                "decision-review.jsonl",
            ),
            "spec-maintenance": (
                ".cowork-flow/spec/protocols/spec-maintenance.md",
                "advisory",
                None,
                ".cowork-flow/spec/",
            ),
        }
        entries = {entry.id: entry for entry in registry.entries}

        for protocol_id, contract in expected.items():
            source, enforcement, runtime_gate, evidence_artifact = contract
            entry = entries[protocol_id]
            self.assertEqual("protocol", entry.kind)
            self.assertEqual("internal", entry.visibility)
            self.assertEqual(source, entry.source)
            self.assertEqual(enforcement, entry.enforcement)
            self.assertEqual(runtime_gate, entry.runtime_gate)
            self.assertEqual(evidence_artifact, entry.evidence_artifact)
            self.assertEqual((), entry.managed_paths)
            self.assertNotIn(protocol_id, registry.public_skill_ids)

        for legacy_id in ("check", "update-spec"):
            self.assertNotIn(legacy_id, entries)
            self.assertFalse(
                (TEMPLATE / "skills" / legacy_id / "SKILL.md").exists(),
                legacy_id,
            )


    def test_tdd_is_public_advisory_practice_skill(self) -> None:
        registry = self._module().load_skill_registry(TEMPLATE)
        entry = registry.entry("tdd")

        self.assertEqual("protocol", entry.kind)
        self.assertEqual("public", entry.visibility)
        self.assertEqual("advisory", entry.enforcement)
        self.assertEqual("check.jsonl", entry.evidence_artifact)
        self.assertEqual("skills/tdd/SKILL.md", entry.source)
        self.assertIn("tdd", registry.public_skill_ids)
        self.assertTrue((TEMPLATE / "skills" / "tdd" / "SKILL.md").exists())
    def test_doubt_review_is_public_advisory_protocol(self) -> None:
        registry = self._module().load_skill_registry(TEMPLATE)
        entry = registry.entry("doubt-review")

        self.assertEqual("protocol", entry.kind)
        self.assertEqual("public", entry.visibility)
        self.assertEqual("advisory", entry.enforcement)
        self.assertEqual("skills/doubt-review/SKILL.md", entry.source)
        self.assertTrue(
            (TEMPLATE / "skills" / "doubt-review" / "SKILL.md").exists()
        )
        self.assertEqual(
            True,
            "doubt-review" in registry.public_skill_ids,
        )

    def test_doubt_review_preserves_public_guardrails(self) -> None:
        text = (
            TEMPLATE / "skills" / "doubt-review" / "SKILL.md"
        ).read_text(encoding="utf-8")
        required_markers = (
            "Common Rationalizations",
            "Spawning a reviewer is expensive",
            "cannot spawn a fresh-context reviewer from within a subagent context",
            "surface back to the main session",
            "Verification",
            "Every non-trivial decision has a CLAIM record",
            "Reviewer receives ARTIFACT + CONTRACT (not CLAIM)",
            "decision-review",
            "review-protocol",
        )

        self.assertEqual(
            [],
            [marker for marker in required_markers if marker not in text],
        )

    def test_doctor_loads_registry_and_rejects_invalid_contract(self) -> None:
        doctor = importlib.import_module("commands.doctor")
        errors: list[str] = []
        doctor._check_skill_registry(ROOT, errors)
        self.assertEqual([], errors)

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            shutil.copytree(TEMPLATE, repo_root / "template")
            registry_path = (
                repo_root
                / "template"
                / ".cowork-flow"
                / "spec"
                / "runtime"
                / "skill-registry.json"
            )
            raw = json.loads(registry_path.read_text(encoding="utf-8"))
            brainstorming = next(
                entry for entry in raw["entries"] if entry["id"] == "brainstorming"
            )
            brainstorming["status"] = "deprecated"
            registry_path.write_text(
                json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            errors = []
            doctor._check_skill_registry(repo_root, errors)

        self.assertTrue(
            any(
                "invalid status for brainstorming: deprecated" in error
                for error in errors
            ),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
