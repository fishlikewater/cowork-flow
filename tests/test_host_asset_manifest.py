from __future__ import annotations

import importlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
TEMPLATE = ROOT / "template"

FIXTURES = ROOT / "tests" / "fixtures" / "host-manifest"
VALID_MANIFEST_FIXTURES = ("valid-minimal.json", "valid-extra-platform.json")
INVALID_MANIFEST_FIXTURES = {
    "invalid-duplicate-alias.json": r"duplicate platform alias",
    "invalid-capability-status.json": r"illegal host-neutral capability",
    "invalid-capability-value.json": r"capabilityValues",
    "invalid-unsupported-without-fallback.json": r"unsupported capability requires fallback",
    "invalid-unknown-field.json": r"unknown field",
}
ALL_MANIFEST_FIXTURES = tuple(sorted((*VALID_MANIFEST_FIXTURES, *INVALID_MANIFEST_FIXTURES)))
REQUIRED_HOST_NEUTRAL_CAPABILITIES = (
    "task_action",
    "subagent_dispatch",
    "file_write",
    "party_board_action",
)



class HostAssetManifestTest(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        self.host_manifest = importlib.import_module(
            "adapters.host.host_manifest"
        )

    def _cleanup_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in (
            "adapters.host.host_manifest",
            "kernel",
            "adapters.host",
        ):
            sys.modules.pop(module_name, None)


    def _fixture_template(self, fixture_name: str, temp_dir: str) -> Path:
        template = Path(temp_dir) / "template"
        manifest_path = template / self.host_manifest.MANIFEST_PATH
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_bytes((FIXTURES / fixture_name).read_bytes())
        return template

    def _load_fixture_manifest(self, fixture_name: str):
        with tempfile.TemporaryDirectory() as temp_dir:
            return self.host_manifest.load_host_manifest(
                self._fixture_template(fixture_name, temp_dir)
            )

    def _manifest_summary(self, manifest) -> dict[str, object]:
        return {
            "schemaVersion": manifest.schema_version,
            "platformIds": list(manifest.platform_ids),
            "aliasOwners": {
                alias: platform.id
                for platform in manifest.platforms
                for alias in platform.aliases
            },
            "assets": {
                platform.id: {
                    "assetPrefixes": list(platform.asset_prefixes),
                    "assetFiles": list(platform.asset_files),
                    "skillTarget": platform.skill_target,
                    "commandTargets": [
                        {
                            "config": target.config,
                            "format": target.format,
                            "target": target.target,
                        }
                        for target in platform.command_targets
                    ],
                }
                for platform in manifest.platforms
            },
            "syncPolicy": {
                "protectedFiles": list(manifest.sync_policy.protected_files),
                "protectedPrefixes": list(manifest.sync_policy.protected_prefixes),
                "safeFiles": list(manifest.sync_policy.safe_files),
                "safePrefixes": list(manifest.sync_policy.safe_prefixes),
                "managedBlockFiles": list(manifest.sync_policy.managed_block_files),
                "obsoleteFiles": list(manifest.sync_policy.obsolete_files),
            },
            "capabilitySummary": {
                host_id: {
                    capability: {
                        "status": manifest.capability_matrix[host_id][capability].status,
                        **(
                            {"fallback": manifest.capability_matrix[host_id][capability].fallback}
                            if manifest.capability_matrix[host_id][capability].fallback
                            else {}
                        ),
                    }
                    for capability in REQUIRED_HOST_NEUTRAL_CAPABILITIES
                }
                for host_id in sorted(manifest.capability_matrix)
            },
        }

    def test_host_manifest_fixtures_are_shared_and_classified_by_category(self) -> None:
        self.assertEqual(
            ALL_MANIFEST_FIXTURES,
            tuple(sorted(path.name for path in FIXTURES.glob("*.json"))),
        )
        for fixture_name in VALID_MANIFEST_FIXTURES:
            with self.subTest(fixture=fixture_name):
                self._load_fixture_manifest(fixture_name)
        for fixture_name, category in INVALID_MANIFEST_FIXTURES.items():
            with self.subTest(fixture=fixture_name):
                with self.assertRaisesRegex(self.host_manifest.HostManifestError, category):
                    self._load_fixture_manifest(fixture_name)

    def test_valid_host_manifest_fixtures_expose_normalized_summaries(self) -> None:
        minimal = self._manifest_summary(self._load_fixture_manifest("valid-minimal.json"))
        self.assertEqual(["codex"], minimal["platformIds"])
        self.assertEqual({"codex": "codex"}, minimal["aliasOwners"])
        self.assertEqual([".codex/"], minimal["assets"]["codex"]["assetPrefixes"])
        self.assertEqual(
            {
                "config": ".codex/config.toml",
                "format": "toml",
                "target": ".codex/agents/cowork-implement.toml",
            },
            minimal["assets"]["codex"]["commandTargets"][0],
        )
        self.assertEqual(["AGENTS.md"], minimal["syncPolicy"]["managedBlockFiles"])
        self.assertEqual(
            {"status": "unsupported", "fallback": "project_root_init_or_sync"},
            minimal["capabilitySummary"]["zcode"]["file_write"],
        )

        extra = self._manifest_summary(self._load_fixture_manifest("valid-extra-platform.json"))
        self.assertEqual(["codex", "demo-host"], extra["platformIds"])
        self.assertEqual("demo-host", extra["aliasOwners"]["demo"])
        self.assertEqual(["AGENTS.md"], extra["assets"]["demo-host"]["assetFiles"])
        self.assertEqual(".demo-host/skills", extra["assets"]["demo-host"]["skillTarget"])
        self.assertEqual(
            {
                "config": ".demo-host/config.json",
                "format": "json",
                "target": ".demo-host/agents/cowork-implement.md",
            },
            extra["assets"]["demo-host"]["commandTargets"][0],
        )
        self.assertEqual(
            {"status": "unsupported", "fallback": "inline_or_manual"},
            extra["capabilitySummary"]["demo-host"]["subagent_dispatch"],
        )

    def test_manifest_declares_platform_assets_and_policies(self) -> None:
        manifest = self.host_manifest.load_host_manifest(TEMPLATE)

        self.assertEqual(1, manifest.schema_version)
        self.assertEqual(
            ("codex", "opencode", "claude-code", "dsh", "zcode"),
            manifest.platform_ids,
        )
        self.assertEqual(
            ("task_action", "subagent_dispatch", "file_write", "party_board_action"),
            manifest.required_host_capabilities,
        )
        self.assertEqual(
            ("claude-code", "codex", "dsh", "opencode", "zcode"),
            tuple(sorted(manifest.capability_matrix)),
        )
        self.assertEqual("claude-code", manifest.resolve_alias("claude"))
        self.assertEqual("zcode", manifest.resolve_alias("zcode"))
        self.assertEqual(".agents/skills", manifest.platform("codex").skill_target)
        self.assertEqual(".agents/skills", manifest.platform("dsh").skill_target)
        self.assertEqual(
            ".cowork-flow/skills",
            manifest.platform("zcode").skill_target,
        )
        self.assertEqual(
            ".claude/skills",
            manifest.platform("claude-code").skill_target,
        )
        self.assertEqual(
            "unsupported",
            manifest.host_capability("zcode", "file_write").status,
        )
        self.assertEqual(
            "project_root_init_or_sync",
            manifest.host_capability("zcode", "file_write").fallback,
        )
        self.assertIn(
            ".cowork-flow/scripts/task.py",
            manifest.sync_policy.obsolete_files,
        )

    def test_semantic_validation_accepts_repository_assets(self) -> None:
        errors = self.host_manifest.validate_host_assets(TEMPLATE)

        self.assertEqual([], errors)

    def test_semantic_validation_can_limit_checks_to_installed_platforms(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            installed = Path(temp_dir) / "installed"
            shutil.copytree(TEMPLATE, installed)
            shutil.rmtree(installed / ".claude")
            shutil.rmtree(installed / ".opencode")
            shutil.rmtree(installed / ".cowork-flow" / "adapters" / "claude-code")
            shutil.rmtree(installed / ".cowork-flow" / "adapters" / "opencode")

            errors = self.host_manifest.validate_host_assets(
                installed,
                platform_ids=("codex",),
            )

        self.assertEqual([], errors)

    def test_sync_policy_obsoletes_removed_skill_registry_contracts(self) -> None:
        manifest = self.host_manifest.load_host_manifest(TEMPLATE)

        self.assertNotIn(
            ".cowork-flow/spec/runtime/skill-registry.json",
            manifest.sync_policy.safe_files,
        )
        self.assertNotIn(
            ".cowork-flow/spec/schemas/skill-registry.schema.json",
            manifest.sync_policy.safe_files,
        )
        self.assertIn(
            ".cowork-flow/spec/runtime/skill-registry.json",
            manifest.sync_policy.obsolete_files,
        )
        self.assertIn(
            ".agents/skills/decision-review",
            manifest.sync_policy.obsolete_files,
        )

    def test_semantic_validation_rejects_missing_command_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            template = Path(temp_dir) / "template"
            shutil.copytree(TEMPLATE, template)
            target = (
                template
                / ".codex"
                / "hooks"
                / "inject-workflow-state.py"
            )
            target.unlink()

            errors = self.host_manifest.validate_host_assets(template)

        self.assertTrue(
            any("missing command target" in error for error in errors),
            errors,
        )

    def test_semantic_validation_rejects_illegal_capability(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            template = Path(temp_dir) / "template"
            shutil.copytree(TEMPLATE, template)
            adapter = (
                template
                / ".cowork-flow"
                / "adapters"
                / "codex"
                / "adapter.yaml"
            )
            text = adapter.read_text(encoding="utf-8")
            adapter.write_text(
                text.replace(
                    "dispatchSubagent: native",
                    "dispatchSubagent: impossible",
                ),
                encoding="utf-8",
            )

            errors = self.host_manifest.validate_host_assets(template)

        self.assertTrue(
            any("illegal capability" in error for error in errors),
            errors,
        )

    def test_semantic_validation_rejects_missing_host_neutral_capability(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            template = Path(temp_dir) / "template"
            shutil.copytree(TEMPLATE, template)
            manifest_path = (
                template
                / ".cowork-flow"
                / "spec"
                / "runtime"
                / "host-assets.json"
            )
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            del data["capabilityMatrix"]["hosts"]["codex"]["task_action"]
            manifest_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            errors = self.host_manifest.validate_host_assets(template)

        self.assertTrue(
            any(
                "missing host-neutral capability codex:task_action" in error
                for error in errors
            ),
            errors,
        )

    def test_semantic_validation_rejects_unsupported_capability_without_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            template = Path(temp_dir) / "template"
            shutil.copytree(TEMPLATE, template)
            manifest_path = (
                template
                / ".cowork-flow"
                / "spec"
                / "runtime"
                / "host-assets.json"
            )
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            del data["capabilityMatrix"]["hosts"]["zcode"]["file_write"]["fallback"]
            manifest_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            errors = self.host_manifest.validate_host_assets(template)

        self.assertTrue(
            any(
                "unsupported capability requires fallback: zcode:file_write" in error
                for error in errors
            ),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
