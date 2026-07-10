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
        self.assertNotIn("batch-mode", registry.public_skill_ids)
        before_dev = registry.entry("before-dev")
        self.assertEqual("mandatory", before_dev.enforcement)
        self.assertEqual("runtime", registry.entry(before_dev.runtime_gate).kind)

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
            before_dev = next(
                entry for entry in raw["entries"] if entry["id"] == "before-dev"
            )
            before_dev["runtimeGate"] = None
            registry_path.write_text(
                json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            errors = []
            doctor._check_skill_registry(repo_root, errors)

        self.assertTrue(
            any(
                "mandatory entry before-dev requires runtimeGate" in error
                for error in errors
            ),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
