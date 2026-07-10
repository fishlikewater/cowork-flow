from __future__ import annotations

import importlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
TEMPLATE = ROOT / "template"


class HostAssetManifestTest(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        self.host_manifest = importlib.import_module(
            "common.core.host_manifest"
        )

    def _cleanup_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in (
            "common.core.host_manifest",
            "common.core",
            "common",
        ):
            sys.modules.pop(module_name, None)

    def test_manifest_declares_platform_assets_and_policies(self) -> None:
        manifest = self.host_manifest.load_host_manifest(TEMPLATE)

        self.assertEqual(1, manifest.schema_version)
        self.assertEqual(
            ("codex", "opencode", "claude-code"),
            manifest.platform_ids,
        )
        self.assertEqual("claude-code", manifest.resolve_alias("claude"))
        self.assertEqual(".agents/skills", manifest.platform("codex").skill_target)
        self.assertEqual(
            ".claude/skills",
            manifest.platform("claude-code").skill_target,
        )
        self.assertIn(
            ".cowork-flow/scripts/task.py",
            manifest.sync_policy.obsolete_files,
        )

    def test_semantic_validation_accepts_repository_assets(self) -> None:
        errors = self.host_manifest.validate_host_assets(TEMPLATE)

        self.assertEqual([], errors)

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


if __name__ == "__main__":
    unittest.main()
