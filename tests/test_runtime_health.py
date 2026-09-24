from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
DOCTOR_PATH = TEMPLATE / "skills" / "runtime-health" / "scripts" / "doctor.py"


def _load_doctor():
    spec = importlib.util.spec_from_file_location("cowork_flow_runtime_health", DOCTOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Doctor: {DOCTOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DshPresetCheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doctor = _load_doctor()

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.dsh_home = root / "dsh-home"
        self.project = root / "project"
        (self.project / ".cowork-flow").mkdir(parents=True)
        (self.project / ".cowork-flow" / ".version").write_text(
            "1.5.0\n", encoding="utf-8"
        )
        self.preset_dir = self.dsh_home / ".agent-presets" / "cowork-flow"

    def _check(self) -> list[dict[str, str]]:
        with mock.patch.dict("os.environ", {"DSH_HOME": str(self.dsh_home)}):
            return self.doctor.check_dsh_preset(self.project)

    def test_absent_preset_is_silent(self) -> None:
        self.assertEqual([], self._check())

    def test_preset_without_marker_reports_unknown_version(self) -> None:
        self.preset_dir.mkdir(parents=True)
        issues = self._check()
        self.assertEqual(1, len(issues))
        self.assertEqual("PRESET-UNKNOWN-VERSION", issues[0]["code"])
        self.assertEqual("warning", issues[0]["severity"])
        self.assertIn("cwf host add dsh --component preset --force", issues[0]["commandHint"])

    def test_unreadable_marker_reports_unknown_version(self) -> None:
        self.preset_dir.mkdir(parents=True)
        (self.preset_dir / ".cowork-flow-preset.json").write_text(
            "not json", encoding="utf-8"
        )
        issues = self._check()
        self.assertEqual(1, len(issues))
        self.assertEqual("PRESET-UNKNOWN-VERSION", issues[0]["code"])

    def test_stale_marker_reports_with_update_hint(self) -> None:
        self.preset_dir.mkdir(parents=True)
        (self.preset_dir / ".cowork-flow-preset.json").write_text(
            '{"version": "0.0.1", "installedAt": "2020-01-01T00:00:00.000Z"}',
            encoding="utf-8",
        )
        issues = self._check()
        self.assertEqual(1, len(issues))
        self.assertEqual("PRESET-STALE", issues[0]["code"])
        self.assertIn("0.0.1", issues[0]["message"])
        self.assertIn("1.5.0", issues[0]["message"])
        self.assertIn("cwf host add dsh --component preset --force", issues[0]["commandHint"])

    def test_matching_version_is_silent(self) -> None:
        self.preset_dir.mkdir(parents=True)
        (self.preset_dir / ".cowork-flow-preset.json").write_text(
            '{"version": "1.5.0"}', encoding="utf-8"
        )
        self.assertEqual([], self._check())

    def test_preset_check_never_enters_doctor_errors(self) -> None:
        self.preset_dir.mkdir(parents=True)
        with mock.patch.dict("os.environ", {"DSH_HOME": str(self.dsh_home)}):
            result = self.doctor._all_check_result(self.project)
        self.assertEqual("warning", result["issues"]["dshPreset"][0]["severity"])
        for error in result["errors"]:
            self.assertNotIn("dshPreset", str(error))


class KimiHookCheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doctor = _load_doctor()

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.kimi_home = root / "kimi-home"
        self.project = root / "project"
        (self.project / ".cowork-flow").mkdir(parents=True)
        (self.project / ".cowork-flow" / ".version").write_text(
            "1.5.0\n", encoding="utf-8"
        )
        self.config = self.kimi_home / "config.toml"
        self.shim = self.kimi_home / "hooks" / "cowork-flow-inject.mjs"
        self.marker = self.kimi_home / "hooks" / ".cowork-flow-kimi-hook.json"

    def _check(self) -> list[dict[str, str]]:
        with mock.patch.dict(
            "os.environ", {"KIMI_CODE_HOME": str(self.kimi_home)}
        ):
            return self.doctor.check_kimi_hook(self.project)

    def _install_block(self, command: str = 'command = "node shim.mjs"') -> None:
        self.kimi_home.mkdir(parents=True, exist_ok=True)
        self.config.write_text(
            "[providers.moonshot]\n"
            'api_key = "sk-test"\n'
            "\n"
            f"{self.doctor._HOOK_START_MARK}\n"
            "[[hooks]]\n"
            'event = "UserPromptSubmit"\n'
            f"{command}\n"
            "timeout = 30\n"
            "# cowork-flow: kimi hook end.\n",
            encoding="utf-8",
        )

    def _install_shim(self) -> None:
        self.shim.parent.mkdir(parents=True, exist_ok=True)
        self.shim.write_text("#!/usr/bin/env node\n", encoding="utf-8")

    def _write_marker(self, payload: str) -> None:
        self.marker.parent.mkdir(parents=True, exist_ok=True)
        self.marker.write_text(payload, encoding="utf-8")

    def test_home_without_config_is_silent(self) -> None:
        self.assertEqual([], self._check())

    def test_config_without_hook_reports_not_installed(self) -> None:
        self.kimi_home.mkdir(parents=True)
        self.config.write_text(
            "[providers.moonshot]\n" 'api_key = "sk-test"\n', encoding="utf-8"
        )
        issues = self._check()
        self.assertEqual(1, len(issues))
        self.assertEqual("HOOK-NOT-INSTALLED", issues[0]["code"])
        self.assertEqual("warning", issues[0]["severity"])
        self.assertIn("cwf host add kimi-code", issues[0]["commandHint"])

    def test_registered_row_without_shim_reports_missing_shim(self) -> None:
        self._install_block()
        issues = self._check()
        self.assertEqual(1, len(issues))
        self.assertEqual("HOOK-SHIM-MISSING", issues[0]["code"])
        self.assertIn("cwf host add kimi-code", issues[0]["commandHint"])

    def test_installed_hook_without_marker_reports_unknown_version(self) -> None:
        self._install_block()
        self._install_shim()
        issues = self._check()
        self.assertEqual(1, len(issues))
        self.assertEqual("HOOK-UNKNOWN-VERSION", issues[0]["code"])
        self.assertEqual("warning", issues[0]["severity"])
        self.assertIn("cwf host add kimi-code", issues[0]["commandHint"])

    def test_unreadable_marker_reports_unknown_version(self) -> None:
        self._install_block()
        self._install_shim()
        self._write_marker("not json")
        issues = self._check()
        self.assertEqual(1, len(issues))
        self.assertEqual("HOOK-UNKNOWN-VERSION", issues[0]["code"])

    def test_stale_marker_reports_with_update_hint(self) -> None:
        self._install_block()
        self._install_shim()
        self._write_marker(
            '{"version": "0.0.1", "installedAt": "2020-01-01T00:00:00.000Z"}'
        )
        issues = self._check()
        self.assertEqual(1, len(issues))
        self.assertEqual("HOOK-STALE", issues[0]["code"])
        self.assertIn("0.0.1", issues[0]["message"])
        self.assertIn("1.5.0", issues[0]["message"])
        self.assertIn("cwf host add kimi-code", issues[0]["commandHint"])

    def test_matching_version_is_silent(self) -> None:
        self._install_block()
        self._install_shim()
        self._write_marker('{"version": "1.5.0"}')
        self.assertEqual([], self._check())

    def test_missing_project_version_is_silent(self) -> None:
        self._install_block()
        self._install_shim()
        self._write_marker('{"version": "0.0.1"}')
        (self.project / ".cowork-flow" / ".version").unlink()
        self.assertEqual([], self._check())

    def test_hook_check_never_enters_doctor_errors(self) -> None:
        self._install_block()
        with mock.patch.dict(
            "os.environ",
            {"KIMI_CODE_HOME": str(self.kimi_home), "DSH_HOME": str(self.kimi_home)},
        ):
            result = self.doctor._all_check_result(self.project)
        self.assertEqual("warning", result["issues"]["kimiHook"][0]["severity"])
        for error in result["errors"]:
            self.assertNotIn("kimiHook", str(error))
        # An installed-but-unknown-version hook must not become fatal either.
        self._install_shim()
        self._write_marker("not json")
        with mock.patch.dict(
            "os.environ",
            {"KIMI_CODE_HOME": str(self.kimi_home), "DSH_HOME": str(self.kimi_home)},
        ):
            result = self.doctor._all_check_result(self.project)
        self.assertEqual(
            "HOOK-UNKNOWN-VERSION", result["issues"]["kimiHook"][0]["code"]
        )
        for error in result["errors"]:
            self.assertNotIn("kimiHook", str(error))


class QoderPluginCheckTest(unittest.TestCase):
    """Qoder plugin diagnostics. The plugin is a machine-level asset, so the
    check must stay silent for projects that never selected the Qoder host and
    must never turn a lagging install into a hard error."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.doctor = _load_doctor()

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.qoder_home = root / "qoder-home"
        self.project = root / "project"
        (self.project / ".cowork-flow" / "adapters" / "qoder").mkdir(parents=True)
        (self.project / ".cowork-flow" / "adapters" / "qoder" / "adapter.yaml").write_text(
            "schemaVersion: 1\nhost: qoder\n", encoding="utf-8"
        )
        (self.project / ".cowork-flow" / ".version").write_text("1.5.0\n", encoding="utf-8")
        self.version = "1.5.0"
        self.install_path = (
            self.qoder_home
            / "plugins"
            / "cache"
            / "cowork-flow-local"
            / "cowork-flow"
            / self.version
        )

    def _check(self) -> list[dict[str, str]]:
        with mock.patch.dict("os.environ", {"QODER_CONFIG_DIR": str(self.qoder_home)}):
            return self.doctor.check_qoder_plugin(self.project)

    def _write_payload(
        self, *, shim: bool = True, hooks_config: bool = True, manifest: str = "plugin.json"
    ) -> None:
        (self.install_path / ".qoder-plugin").mkdir(parents=True, exist_ok=True)
        (self.install_path / ".qoder-plugin" / manifest).write_text(
            json.dumps({"name": "cowork-flow", "version": self.version}), encoding="utf-8"
        )
        (self.install_path / "hooks").mkdir(parents=True, exist_ok=True)
        if hooks_config:
            (self.install_path / "hooks" / "hooks.json").write_text(
                json.dumps({"hooks": {}}), encoding="utf-8"
            )
        if shim:
            (self.install_path / "hooks" / "inject-context.py").write_text(
                "# shim\n", encoding="utf-8"
            )

    def _write_registry(self, install_path: Path | None = None) -> None:
        registry = self.qoder_home / "plugins" / "installed_plugins_v2.json"
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(
            json.dumps(
                {
                    "version": 2,
                    "plugins": {
                        "cowork-flow@cowork-flow-local": [
                            {"scope": "user", "installPath": str(install_path or self.install_path),
                             "version": self.version}
                        ]
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _write_settings(self, enabled: bool | None) -> None:
        plugins = {"someone-else@their-market": True}
        if enabled is not None:
            plugins["cowork-flow@cowork-flow-local"] = enabled
        (self.qoder_home / "settings.json").write_text(
            json.dumps({"enabledPlugins": plugins, "mcpServers": {"docs": {}}}, indent=2),
            encoding="utf-8",
        )

    def _install(self, *, version: str | None = None, enabled: bool | None = True) -> None:
        self._write_payload()
        self._write_registry()
        self._write_settings(enabled)
        if version is not None:
            registry = self.qoder_home / "plugins" / "installed_plugins_v2.json"
            data = json.loads(registry.read_text(encoding="utf-8"))
            data["plugins"]["cowork-flow@cowork-flow-local"][0]["version"] = version
            registry.write_text(json.dumps(data), encoding="utf-8")

    def test_project_without_qoder_adapter_is_silent(self) -> None:
        (self.project / ".cowork-flow" / "adapters" / "qoder" / "adapter.yaml").unlink()
        self.assertEqual([], self._check())

    def test_declared_host_without_registry_reports_not_installed(self) -> None:
        issues = self._check()
        self.assertEqual(1, len(issues))
        self.assertEqual("PLUGIN-NOT-INSTALLED", issues[0]["code"])
        self.assertEqual("warning", issues[0]["severity"])
        self.assertIn("cwf host add qoder", issues[0]["commandHint"])

    def test_registry_pointing_at_missing_payload_reports_payload_missing(self) -> None:
        self._write_registry()
        issues = self._check()
        self.assertEqual(["PLUGIN-PAYLOAD-MISSING"], [issue["code"] for issue in issues])

    def _write_host_manifest(self, manifest_relative: str) -> None:
        """Deliver the host asset manifest with qoder's declared payload manifest
        renamed, so the check can be observed following the declaration."""
        data = json.loads(
            (
                TEMPLATE / ".cowork-flow" / "spec" / "runtime" / "host-assets.json"
            ).read_text(encoding="utf-8")
        )
        qoder = next(item for item in data["platforms"] if item["id"] == "qoder")
        qoder["payload"]["manifest"] = manifest_relative
        target = (
            self.project / ".cowork-flow" / "spec" / "runtime" / "host-assets.json"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def test_payload_manifest_path_follows_the_declaration(self) -> None:
        # The declaration is the only place naming the payload manifest: a
        # payload carrying exactly the declared name is healthy, and the same
        # payload is reported missing once the declaration points elsewhere.
        self._write_host_manifest(".qoder-plugin/plugin-alt.json")
        self._write_payload(manifest="plugin-alt.json")
        self._write_registry()
        self._write_settings(True)
        self.assertEqual([], self._check())

        self._write_host_manifest(".qoder-plugin/plugin.json")
        issues = self._check()
        self.assertEqual(["PLUGIN-PAYLOAD-MISSING"], [issue["code"] for issue in issues])
        self.assertTrue(
            str(issues[0]["path"]).endswith("plugin.json"),
            issues[0]["path"],
        )

    def test_payload_without_hook_shim_reports_incomplete(self) -> None:
        self._write_payload(shim=False)
        self._write_registry()
        self._write_settings(True)
        issues = self._check()
        self.assertEqual(["PLUGIN-PAYLOAD-INCOMPLETE"], [issue["code"] for issue in issues])

    def test_installed_but_disabled_reports_disabled_and_keeps_other_plugins(self) -> None:
        self._write_payload()
        self._write_registry()
        self._write_settings(False)
        issues = self._check()
        self.assertEqual(["PLUGIN-DISABLED"], [issue["code"] for issue in issues])

    def test_healthy_install_reports_nothing(self) -> None:
        self._install()
        self.assertEqual([], self._check())

    def test_stale_plugin_version_reports_stale(self) -> None:
        self._install(version="1.4.0")
        issues = self._check()
        self.assertEqual(["PLUGIN-STALE"], [issue["code"] for issue in issues])
        self.assertIn("1.4.0", issues[0]["message"])

    def test_unreadable_registry_is_reported_as_not_installed(self) -> None:
        registry = self.qoder_home / "plugins" / "installed_plugins_v2.json"
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text("{ broken", encoding="utf-8")
        issues = self._check()
        self.assertEqual(["PLUGIN-NOT-INSTALLED"], [issue["code"] for issue in issues])

    def test_plugin_check_never_enters_doctor_errors(self) -> None:
        with mock.patch.dict("os.environ", {"QODER_CONFIG_DIR": str(self.qoder_home)}):
            result = self.doctor._all_check_result(self.project)
        self.assertEqual("PLUGIN-NOT-INSTALLED", result["issues"]["qoderPlugin"][0]["code"])
        for error in result["errors"]:
            self.assertNotIn("qoder-plugin", str(error))


class CodexPluginCheckTest(unittest.TestCase):
    """Codex plugin diagnostics. The plugin is a machine-level asset registered in
    `~/.codex/config.toml`, so the check must stay silent for projects that never
    selected the Codex host and must never turn a lagging install into a hard
    error."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.doctor = _load_doctor()

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.codex_home = root / "codex-home"
        self.project = root / "project"
        (self.project / ".cowork-flow" / "adapters" / "codex").mkdir(parents=True)
        (self.project / ".cowork-flow" / "adapters" / "codex" / "adapter.yaml").write_text(
            "schemaVersion: 1\nhost: codex\n", encoding="utf-8"
        )
        (self.project / ".cowork-flow" / ".version").write_text("1.6.0\n", encoding="utf-8")
        self.source = self.codex_home / "plugins" / "marketplaces" / "cowork-flow-local"
        self.config = self.codex_home / "config.toml"

    def _check(self) -> list[dict[str, str]]:
        with mock.patch.dict("os.environ", {"CODEX_HOME": str(self.codex_home)}):
            return self.doctor.check_codex_plugin(self.project)

    def _write_config(self, *, source: str | None = None, enabled: bool | None = True) -> None:
        lines = [
            'model = "gpt-5"',
            "",
            "[features]",
            "plugins = true",
            "",
            '[plugins."someone-else@their-market"]',
            "enabled = false",
        ]
        if source is not None:
            lines += [
                "",
                "[marketplaces.cowork-flow-local]",
                'source_type = "local"',
                f"source = '{source}'",
            ]
        if enabled is not None:
            lines += [
                "",
                '[plugins."cowork-flow@cowork-flow-local"]',
                f"enabled = {str(enabled).lower()}",
            ]
        self.config.parent.mkdir(parents=True, exist_ok=True)
        self.config.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_payload(self, manifest: str = ".codex-plugin/plugin.json") -> None:
        path = self.source / "plugins" / "cowork-flow" / Path(manifest)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"name": "cowork-flow", "version": "1.6.0"}), encoding="utf-8"
        )

    def _install(self, *, enabled: bool | None = True) -> None:
        self._write_payload()
        self._write_config(source=str(self.source), enabled=enabled)

    def test_project_without_codex_adapter_is_silent(self) -> None:
        (self.project / ".cowork-flow" / "adapters" / "codex" / "adapter.yaml").unlink()
        self.assertEqual([], self._check())

    def test_declared_host_without_marketplace_reports_not_installed(self) -> None:
        issues = self._check()
        self.assertEqual(["PLUGIN-NOT-INSTALLED"], [issue["code"] for issue in issues])
        self.assertEqual("warning", issues[0]["severity"])
        self.assertEqual("cwf host add codex", issues[0]["commandHint"])

    def _write_host_manifest(self, manifest_relative: str) -> None:
        """Deliver the host asset manifest with codex's declared payload manifest
        renamed, so the check can be observed following the declaration."""
        data = json.loads(
            (
                TEMPLATE / ".cowork-flow" / "spec" / "runtime" / "host-assets.json"
            ).read_text(encoding="utf-8")
        )
        codex = next(item for item in data["platforms"] if item["id"] == "codex")
        codex["payload"]["manifest"] = manifest_relative
        target = (
            self.project / ".cowork-flow" / "spec" / "runtime" / "host-assets.json"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def test_payload_manifest_path_follows_the_declaration(self) -> None:
        # A payload carrying exactly the declared manifest name is healthy; the
        # same payload is reported missing once the declaration points elsewhere.
        self._write_host_manifest(".codex-plugin/plugin-alt.json")
        self._write_payload(".codex-plugin/plugin-alt.json")
        self._write_config(source=str(self.source))
        self.assertEqual([], self._check())

        self._write_host_manifest(".codex-plugin/plugin.json")
        issues = self._check()
        self.assertEqual(["PLUGIN-PAYLOAD-MISSING"], [issue["code"] for issue in issues])
        # codex reports the payload directory, not the manifest path.
        self.assertTrue(
            str(issues[0]["path"]).endswith("cowork-flow"),
            issues[0]["path"],
        )

    def test_registered_marketplace_without_payload_reports_payload_missing(self) -> None:
        self._write_config(source=str(self.source))
        issues = self._check()
        self.assertEqual(["PLUGIN-PAYLOAD-MISSING"], [issue["code"] for issue in issues])

    def test_installed_but_disabled_reports_disabled(self) -> None:
        self._install(enabled=False)
        issues = self._check()
        self.assertEqual(["PLUGIN-DISABLED"], [issue["code"] for issue in issues])

    def test_installed_without_an_enable_entry_reports_disabled(self) -> None:
        self._install(enabled=None)
        issues = self._check()
        self.assertEqual(["PLUGIN-DISABLED"], [issue["code"] for issue in issues])

    def test_healthy_install_reports_nothing(self) -> None:
        self._install()
        self.assertEqual([], self._check())

    def test_unreadable_config_is_reported_as_not_installed(self) -> None:
        self.config.parent.mkdir(parents=True, exist_ok=True)
        self.config.write_text("{ broken", encoding="utf-8")
        issues = self._check()
        self.assertEqual(["PLUGIN-NOT-INSTALLED"], [issue["code"] for issue in issues])

    def test_quoted_marketplace_section_is_read(self) -> None:
        # Codex quotes a marketplace name only when it needs to; both forms must
        # resolve to the same section.
        self._write_payload()
        self._write_config()
        self.config.write_text(
            self.config.read_text(encoding="utf-8").replace(
                "[marketplaces.cowork-flow-local]",
                '[marketplaces."cowork-flow-local"]',
            )
            + f"\n[marketplaces.cowork-flow-local]\nsource = '{self.source}'\n",
            encoding="utf-8",
        )
        self.assertEqual([], self._check())

    def test_plugin_check_never_enters_doctor_errors(self) -> None:
        with mock.patch.dict("os.environ", {"CODEX_HOME": str(self.codex_home)}):
            result = self.doctor._all_check_result(self.project)
        self.assertEqual("PLUGIN-NOT-INSTALLED", result["issues"]["codexPlugin"][0]["code"])
        for error in result["errors"]:
            self.assertNotIn("codex-plugin", str(error))


class ClaudeCodePluginCheckTest(unittest.TestCase):
    """Claude Code plugin diagnostics. The plugin is a skills-directory folder in
    the user's Claude home, so the check must stay silent for projects that never
    selected the Claude Code host and must never turn a lagging install into a
    hard error."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.doctor = _load_doctor()

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.claude_home = root / "claude-home"
        self.project = root / "project"
        adapter_dir = self.project / ".cowork-flow" / "adapters" / "claude-code"
        adapter_dir.mkdir(parents=True)
        (adapter_dir / "adapter.yaml").write_text(
            "schemaVersion: 1\nhost: claude-code\n", encoding="utf-8"
        )
        (self.project / ".cowork-flow" / ".version").write_text(
            "1.6.0\n", encoding="utf-8"
        )
        self.version = "1.6.0"
        self.install_path = self.claude_home / "skills" / "cowork-flow"

    def _check(self) -> list[dict[str, str]]:
        with mock.patch.dict(
            "os.environ", {"CLAUDE_CONFIG_DIR": str(self.claude_home)}
        ):
            return self.doctor.check_claude_code_plugin(self.project)

    def _write_payload(
        self,
        *,
        version: str | None = None,
        skill: bool = True,
        name: str = "cowork-flow",
        manifest: str = "plugin.json",
    ) -> None:
        (self.install_path / ".claude-plugin").mkdir(parents=True, exist_ok=True)
        (self.install_path / ".claude-plugin" / manifest).write_text(
            json.dumps({"name": name, "version": version or self.version}),
            encoding="utf-8",
        )
        if skill:
            target = self.install_path / "skills" / "cowork-flow-bootstrap"
            target.mkdir(parents=True, exist_ok=True)
            (target / "SKILL.md").write_text("# bootstrap\n", encoding="utf-8")

    def test_project_without_claude_code_adapter_is_silent(self) -> None:
        (
            self.project / ".cowork-flow" / "adapters" / "claude-code" / "adapter.yaml"
        ).unlink()
        self.assertEqual([], self._check())

    def test_declared_host_without_install_reports_not_installed(self) -> None:
        issues = self._check()
        self.assertEqual(["PLUGIN-NOT-INSTALLED"], [issue["code"] for issue in issues])
        self.assertEqual("warning", issues[0]["severity"])
        self.assertIn("cwf host add claude-code", issues[0]["commandHint"])

    def test_healthy_install_reports_nothing(self) -> None:
        self._write_payload()
        self.assertEqual([], self._check())

    def test_payload_without_bootstrap_skill_reports_incomplete(self) -> None:
        self._write_payload(skill=False)
        issues = self._check()
        self.assertEqual(
            ["PLUGIN-PAYLOAD-INCOMPLETE"], [issue["code"] for issue in issues]
        )

    def test_stale_plugin_version_reports_stale(self) -> None:
        self._write_payload(version="1.5.0")
        issues = self._check()
        self.assertEqual(["PLUGIN-STALE"], [issue["code"] for issue in issues])
        self.assertIn("1.5.0", issues[0]["message"])

    def test_foreign_skills_directory_is_silent(self) -> None:
        # A hand-made folder at the same path is not cowork-flow's to report on.
        # It is deliberately stale, so only the name guard can explain silence.
        self._write_payload(name="someone-else", version="1.5.0")
        self.assertEqual([], self._check())

    def test_missing_project_version_is_silent(self) -> None:
        self._write_payload(version="0.0.1")
        (self.project / ".cowork-flow" / ".version").unlink()
        self.assertEqual([], self._check())

    def _write_host_manifest(self, manifest_relative: str) -> None:
        """Deliver the host asset manifest with claude-code's declared payload
        manifest renamed, so the check can be observed following the
        declaration."""
        data = json.loads(
            (
                TEMPLATE / ".cowork-flow" / "spec" / "runtime" / "host-assets.json"
            ).read_text(encoding="utf-8")
        )
        platform = next(
            item for item in data["platforms"] if item["id"] == "claude-code"
        )
        platform["payload"]["manifest"] = manifest_relative
        target = (
            self.project / ".cowork-flow" / "spec" / "runtime" / "host-assets.json"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def test_payload_manifest_path_follows_the_declaration(self) -> None:
        # The declaration is the only place naming the payload manifest: a
        # payload carrying exactly the declared name is healthy, and the same
        # payload is reported missing once the declaration points elsewhere.
        self._write_host_manifest(".claude-plugin/plugin-alt.json")
        self._write_payload(manifest="plugin-alt.json")
        self.assertEqual([], self._check())

        self._write_host_manifest(".claude-plugin/plugin.json")
        issues = self._check()
        self.assertEqual(["PLUGIN-NOT-INSTALLED"], [issue["code"] for issue in issues])
        self.assertTrue(str(issues[0]["path"]).endswith("cowork-flow"), issues[0]["path"])

    def test_plugin_check_never_enters_doctor_errors(self) -> None:
        with mock.patch.dict(
            "os.environ", {"CLAUDE_CONFIG_DIR": str(self.claude_home)}
        ):
            result = self.doctor._all_check_result(self.project)
        self.assertEqual(
            "PLUGIN-NOT-INSTALLED", result["issues"]["claudeCodePlugin"][0]["code"]
        )
        for error in result["errors"]:
            self.assertNotIn("claudeCodePlugin", str(error))


class SkillDeliveryCheckTest(unittest.TestCase):
    """Skill delivery diagnostics: a declared read root that is not on disk, a
    machine-level plugin payload that still carries a copy of a project Skill,
    and discovery channels that stay gated. All three are advisory, so none may
    fail doctor."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.doctor = _load_doctor()

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.qoder_home = self.root / "qoder-home"
        self.zcode_home = self.root / "zcode-home"
        self.codex_home = self.root / "codex-home"
        patcher = mock.patch.dict(
            "os.environ",
            {
                "QODER_CONFIG_DIR": str(self.qoder_home),
                "ZCODE_HOME": str(self.zcode_home),
                "CODEX_HOME": str(self.codex_home),
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _project(self, platform: str | None, version: str = "1.6.0") -> Path:
        root = self.root / f"project-{platform or 'bare'}"
        manifest = root / ".cowork-flow" / "spec" / "runtime" / "host-assets.json"
        manifest.parent.mkdir(parents=True)
        shutil.copy2(
            TEMPLATE / ".cowork-flow" / "spec" / "runtime" / "host-assets.json", manifest
        )
        (root / ".cowork-flow" / ".version").write_text(version + "\n", encoding="utf-8")
        if platform is not None:
            adapter = root / ".cowork-flow" / "adapters" / platform
            adapter.mkdir(parents=True)
            (adapter / "adapter.yaml").write_text(
                f"schemaVersion: 1\nhost: {platform}\n", encoding="utf-8"
            )
        return root

    def _project_skills(self, project: Path, *names: str) -> None:
        """Deliver project Skill copies under the host's read root."""
        for name in names:
            skill_dir = project / ".agents" / "skills" / name
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text("---\n---\n", encoding="utf-8")

    def _install_qoder_plugin(
        self, version: str, *, skill_names: tuple[str, ...] = ("task-review",)
    ) -> None:
        payload = (
            self.qoder_home / "plugins" / "cache" / "cowork-flow-local"
            / "cowork-flow" / version
        )
        (payload / ".qoder-plugin").mkdir(parents=True)
        (payload / ".qoder-plugin" / "plugin.json").write_text(
            json.dumps({"name": "cowork-flow", "version": version}), encoding="utf-8"
        )
        (payload / "hooks").mkdir()
        for relative in ("hooks/hooks.json", "hooks/inject-context.py"):
            (payload / relative).write_text("{}", encoding="utf-8")
        for name in skill_names:
            skill_dir = payload / "skills" / name
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("---\n---\n", encoding="utf-8")
        registry = self.qoder_home / "plugins" / "installed_plugins_v2.json"
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(
            json.dumps(
                {
                    "version": 2,
                    "plugins": {
                        "cowork-flow@cowork-flow-local": [
                            {"scope": "user", "installPath": str(payload), "version": version}
                        ]
                    },
                }
            ),
            encoding="utf-8",
        )
        (self.qoder_home / "settings.json").write_text(
            json.dumps({"enabledPlugins": {"cowork-flow@cowork-flow-local": True}}),
            encoding="utf-8",
        )

    def _install_zcode_plugin(
        self,
        version: str,
        *,
        skills: bool = True,
        skill_names: tuple[str, ...] = ("task-review",),
    ) -> None:
        payload = (
            self.zcode_home / "cli" / "plugins" / "cache" / "cowork-flow-local"
            / "cowork-flow" / version
        )
        payload.mkdir(parents=True)
        if skills:
            for name in skill_names:
                skill_dir = payload / "skills" / name
                skill_dir.mkdir(parents=True)
                (skill_dir / "SKILL.md").write_text("---\n---\n", encoding="utf-8")
        marketplace = (
            self.zcode_home / "cli" / "plugins" / "marketplaces" / "cowork-flow-local"
            / "marketplace.json"
        )
        marketplace.parent.mkdir(parents=True)
        marketplace.write_text(
            json.dumps(
                {
                    "name": "cowork-flow-local",
                    "plugins": [
                        {
                            "name": "cowork-flow",
                            "version": version,
                            "source": {"source": "directory", "path": str(payload)},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    def _install_codex_plugin(
        self, version: str, *, skill_names: tuple[str, ...] = ("task-review",)
    ) -> None:
        source = self.codex_home / "plugins" / "marketplaces" / "cowork-flow-local"
        payload = source / "plugins" / "cowork-flow"
        (payload / ".codex-plugin").mkdir(parents=True)
        (payload / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({"name": "cowork-flow", "version": version}), encoding="utf-8"
        )
        for name in skill_names:
            skill_dir = payload / "skills" / name
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("---\n---\n", encoding="utf-8")
        (self.codex_home / "config.toml").write_text(
            "\n".join(
                [
                    "[marketplaces.cowork-flow-local]",
                    'source_type = "local"',
                    f"source = '{source}'",
                    "",
                    '[plugins."cowork-flow@cowork-flow-local"]',
                    "enabled = true",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def test_project_without_a_selected_host_is_silent(self) -> None:
        self.assertEqual([], self.doctor.check_skill_delivery(self._project(None)))

    def test_missing_read_root_is_reported_with_the_sync_hint(self) -> None:
        issues = self.doctor.check_skill_delivery(self._project("qoder"))
        self.assertEqual(["SKILL-READROOT-MISSING"], [issue["code"] for issue in issues])
        self.assertEqual("warning", issues[0]["severity"])
        self.assertEqual(".agents/skills", issues[0]["path"])
        self.assertEqual("cwf project sync", issues[0]["commandHint"])

    def test_delivered_skills_report_the_gated_discovery_reminder(self) -> None:
        project = self._project("qoder")
        (project / ".agents" / "skills").mkdir(parents=True)
        issues = self.doctor.check_skill_delivery(project)
        self.assertEqual(["SKILL-DISCOVERY-GATED"], [issue["code"] for issue in issues])
        self.assertIn("trusted-folder", issues[0]["message"])
        self.assertIn("restart", issues[0]["message"])
        # Nothing to run: doctor cannot read host trust state, so this is a
        # reminder about a host-side gate rather than a defect to repair.
        self.assertEqual("", issues[0]["commandHint"])

    def test_plugin_payload_still_carrying_skills_is_reported_as_legacy(self) -> None:
        project = self._project("zcode")
        self._project_skills(project, "task-review")
        self._install_zcode_plugin("1.5.0")
        issues = self.doctor.check_skill_delivery(project)
        self.assertEqual(["PLUGIN-SKILLS-LEGACY"], [issue["code"] for issue in issues])
        self.assertIn("1.5.0", issues[0]["message"])
        self.assertEqual("cwf host add zcode --force", issues[0]["commandHint"])

    def test_a_payload_copy_is_reported_even_at_the_project_version(self) -> None:
        project = self._project("zcode")
        self._project_skills(project, "task-review")
        self._install_zcode_plugin("1.6.0")
        issues = self.doctor.check_skill_delivery(project)
        self.assertEqual(["PLUGIN-SKILLS-LEGACY"], [issue["code"] for issue in issues])

    def test_plugin_without_a_skills_copy_is_silent(self) -> None:
        project = self._project("zcode")
        (project / ".agents" / "skills").mkdir(parents=True)
        self._install_zcode_plugin("1.5.0", skills=False)
        self.assertEqual([], self.doctor.check_skill_delivery(project))

    def test_payload_bootstrap_skill_is_not_reported_as_legacy(self) -> None:
        # The payload's bootstrap guide has no project counterpart, so it is an
        # expected payload Skill rather than a leftover copy.
        project = self._project("zcode")
        self._project_skills(project, "task-review")
        self._install_zcode_plugin("1.6.0", skill_names=("cowork-flow-bootstrap",))
        self.assertEqual([], self.doctor.check_skill_delivery(project))

    def test_codex_payload_still_carrying_skills_is_reported_as_legacy(self) -> None:
        project = self._project("codex")
        (project / ".codex").mkdir()
        self._project_skills(project, "task-review")
        self._install_codex_plugin("1.5.0")
        issues = self.doctor.check_skill_delivery(project)
        self.assertEqual(["PLUGIN-SKILLS-LEGACY"], [issue["code"] for issue in issues])
        self.assertEqual("cwf host add codex --force", issues[0]["commandHint"])

    def test_codex_payload_bootstrap_skill_is_not_reported_as_legacy(self) -> None:
        project = self._project("codex")
        (project / ".codex").mkdir()
        self._project_skills(project, "task-review")
        self._install_codex_plugin("1.6.0", skill_names=("cowork-flow-bootstrap",))
        self.assertEqual([], self.doctor.check_skill_delivery(project))

    def test_qoder_plugin_skew_stays_with_the_host_plugin_check(self) -> None:
        project = self._project("qoder")
        self._project_skills(project, "task-review")
        self._install_qoder_plugin("1.5.0")
        self.assertEqual(
            ["PLUGIN-STALE"],
            [issue["code"] for issue in self.doctor.check_qoder_plugin(project)],
        )
        # The plugin version skew stays with the plugin check; what the delivery
        # check reports is the payload's leftover copy of a project Skill.
        self.assertEqual(
            ["SKILL-DISCOVERY-GATED", "PLUGIN-SKILLS-LEGACY"],
            [issue["code"] for issue in self.doctor.check_skill_delivery(project)],
        )

    def test_skill_delivery_warnings_never_enter_doctor_errors(self) -> None:
        project = self._project("zcode")
        self._project_skills(project, "task-review")
        self._install_zcode_plugin("1.5.0")
        result = self.doctor._all_check_result(project)
        self.assertEqual(
            ["PLUGIN-SKILLS-LEGACY"],
            [issue["code"] for issue in result["issues"]["skillDelivery"]],
        )
        self.assertEqual(
            ["warning"], [issue["severity"] for issue in result["issues"]["skillDelivery"]]
        )
        for error in result["errors"]:
            self.assertNotIn("skill-delivery", str(error))

    def test_text_output_prints_the_skill_delivery_section(self) -> None:
        project = self._project("zcode")
        self._project_skills(project, "task-review")
        self._install_zcode_plugin("1.5.0")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
            self.doctor._run_checks(project)
        lines = stdout.getvalue().splitlines()
        self.assertEqual(
            [
                "Skill delivery (PLUGIN-SKILLS-LEGACY): the zcode plugin payload "
                "still carries project Skill copies (task-review) from 1.5.0; "
                "project Skills ship with the project only, so the payload copy "
                "is redundant and may come from another release",
                "  fix: cwf host add zcode --force",
            ],
            [line for line in lines if "Skill delivery" in line or "fix: cwf host add zcode" in line],
        )


class RuntimeHealthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doctor = _load_doctor()

    def _install_codex_project(self, root: Path) -> None:
        shutil.copytree(TEMPLATE / ".cowork-flow", root / ".cowork-flow")
        shutil.copytree(TEMPLATE / ".codex", root / ".codex")
        shutil.copytree(TEMPLATE / "skills", root / ".agents" / "skills")
        shutil.copy2(TEMPLATE / "AGENTS.md", root / "AGENTS.md")

    def _run_doctor(self, root: Path) -> tuple[int, str]:
        stderr = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            result = self.doctor._run_checks(root)
        return result, stderr.getvalue()

    def _distribution_fixture(self, root: Path) -> None:
        for relative in (
            ".cowork-flow/spec/runtime/host-assets.json",
            ".cowork-flow/scripts/run.py",
            ".cowork-flow/scripts/kernel/workflow_route.py",
            ".cowork-flow/scripts/services/task_routing.py",
            ".cowork-flow/scripts/services/task_context.py",
            ".cowork-flow/scripts/infra/skill_manifest.py",
            ".cowork-flow/scripts/adapters/cli/task_navigation.py",
        ):
            source = TEMPLATE / relative
            for target_root in (root / "template", root):
                target = target_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        for skill in (
            "brainstorming",
            "task-planning",
            "cowork-flow",
            "task-review",
            "batch-execution",
            "runtime-health",
        ):
            skill_source = TEMPLATE / "skills" / skill
            for source in skill_source.rglob("*"):
                if not source.is_file() or "__pycache__" in source.parts:
                    continue
                relative = source.relative_to(skill_source)
                for target in (
                    root / "template" / "skills" / skill / relative,
                    root / ".agents" / "skills" / skill / relative,
                    root / ".claude" / "skills" / skill / relative,
                ):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)

    def _source_checkout_fixture(self, root: Path) -> None:
        shutil.copytree(TEMPLATE / ".cowork-flow" / "scripts", root / "template" / ".cowork-flow" / "scripts")
        shutil.copytree(TEMPLATE / "skills", root / "template" / "skills")
        for relative in (
            ".cowork-flow/spec/runtime/host-assets.json",
            ".cowork-flow/spec/runtime/contract-registry.json",
        ):
            source_contract = TEMPLATE / relative
            target_contract = root / "template" / relative
            target_contract.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_contract, target_contract)

    def test_installed_codex_project_does_not_require_source_template(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._install_codex_project(root)
            result, stderr = self._run_doctor(root)

        self.assertEqual(0, result)
        self.assertEqual("", stderr)

    def test_installed_project_reports_corrupt_skill_manifest_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._install_codex_project(root)
            manifest = root / ".agents" / "skills" / "runtime-health" / "manifest.json"
            manifest.write_text("{not-json}\n", encoding="utf-8")

            result, stderr = self._run_doctor(root)

        self.assertEqual(1, result)
        self.assertIn("Skill manifest error", stderr)
        self.assertIn("invalid Skill manifest", stderr)
        self.assertIn("runtime-health/manifest.json", stderr.replace("\\", "/"))

    def test_installed_project_reports_missing_skill_command_script_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._install_codex_project(root)
            script = root / ".agents" / "skills" / "runtime-health" / "scripts" / "doctor.py"
            script.unlink()

            result, stderr = self._run_doctor(root)

        self.assertEqual(1, result)
        self.assertIn("Skill manifest error", stderr)
        self.assertIn("manifest command script is missing", stderr)
        self.assertIn("runtime-health/scripts/doctor.py", stderr.replace("\\", "/"))

    def test_installed_project_reports_skill_command_conflict_owner_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._install_codex_project(root)
            skill_dir = root / ".agents" / "skills" / "demo-conflict"
            skill_dir.mkdir(parents=True)
            script = skill_dir / "scripts" / "doctor_conflict.py"
            script.parent.mkdir()
            script.write_text("print('conflict')\n", encoding="utf-8")
            manifest = skill_dir / "manifest.json"
            data = {
                "schemaVersion": 1,
                "skill": "demo-conflict",
                "commands": [
                    {
                        "name": "doctor",
                        "aliases": [],
                        "script": "scripts/doctor_conflict.py",
                    }
                ],
            }
            manifest.write_text(json.dumps(data), encoding="utf-8")

            result, stderr = self._run_doctor(root)

        self.assertEqual(1, result)
        self.assertIn("Skill command has multiple owners: doctor", stderr)
        self.assertIn("demo-conflict", stderr)
        self.assertIn("runtime-health", stderr)

    def test_installed_project_reports_host_asset_validation_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._install_codex_project(root)
            target = root / ".codex" / "hooks" / "inject-workflow-state.py"
            target.unlink()

            result, stderr = self._run_doctor(root)

        self.assertEqual(1, result)
        self.assertIn("missing command target", stderr)
        self.assertIn(".codex/hooks/inject-workflow-state.py", stderr.replace("\\", "/"))

    def test_all_json_reports_stable_payload_without_text_noise(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._install_codex_project(root)
            stdout = io.StringIO()
            stderr = io.StringIO()

            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = self.doctor._run_checks(root, structured=True)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(0, result)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(True, payload["ok"])
        self.assertEqual([], payload["errors"])
        self.assertEqual([], payload["issues"]["hostAdapters"])
        self.assertEqual([], payload["issues"]["taskHygiene"])

    def test_host_adapter_json_reports_stable_issue_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._install_codex_project(root)
            target = root / ".codex" / "hooks" / "inject-workflow-state.py"
            target.unlink()
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                result = self.doctor._run_host_checks(
                    root,
                    structured=True,
                )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(1, result)
        self.assertEqual(1, len(payload["issues"]))
        issue = payload["issues"][0]
        self.assertEqual(
            {
                "code": "HOST-ASSET-MISSING-COMMAND-TARGET",
                "severity": "error",
                "path": ".codex/hooks/inject-workflow-state.py",
                "commandHint": "",
                "contract": "runtime-health:host-adapters",
            },
            {key: issue[key] for key in (
                "code",
                "severity",
                "path",
                "commandHint",
                "contract",
            )},
        )
        self.assertIn("missing command target", issue["message"])

    def test_source_checkout_does_not_require_full_ignored_live_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._source_checkout_fixture(root)

            errors = self.doctor.check_distribution(root)

        self.assertEqual([], errors)

    def test_source_checkout_detects_present_runtime_contract_registry_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._source_checkout_fixture(root)
            source = (
                root
                / "template"
                / ".cowork-flow"
                / "spec"
                / "runtime"
                / "contract-registry.json"
            )
            live = (
                root
                / ".cowork-flow"
                / "spec"
                / "runtime"
                / "contract-registry.json"
            )
            live.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, live)
            payload = json.loads(live.read_text(encoding="utf-8"))
            payload["schemaVersion"] = payload.get("schemaVersion", 1) + 1
            live.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            self.assertNotEqual(source.read_bytes(), live.read_bytes())

            errors = self.doctor.check_distribution(root)

        self.assertTrue(
            any(
                "local live runtime drift" in error
                and "contract-registry.json" in error.replace("\\", "/")
                for error in errors
            ),
            errors,
        )

    def test_source_checkout_detects_present_navigation_runtime_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._source_checkout_fixture(root)
            source = root / "template" / ".cowork-flow" / "scripts" / "adapters" / "cli" / "task_navigation.py"
            bootstrap = root / ".cowork-flow" / "scripts" / "adapters" / "cli" / "task_navigation.py"
            bootstrap.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, bootstrap)
            bootstrap.write_text(
                bootstrap.read_text(encoding="utf-8") + "\n# local drift\n",
                encoding="utf-8",
            )

            errors = self.doctor.check_distribution(root)

        self.assertTrue(any("local live runtime drift" in error for error in errors), errors)

    def test_source_checkout_detects_present_local_live_runtime_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._source_checkout_fixture(root)
            source = root / "template" / ".cowork-flow" / "scripts" / "runtime" / "session_state.py"
            live = root / ".cowork-flow" / "scripts" / "runtime" / "session_state.py"
            live.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, live)
            live.write_text(
                live.read_text(encoding="utf-8") + "\n# local drift\n",
                encoding="utf-8",
            )

            errors = self.doctor.check_distribution(root)

        self.assertTrue(any("local live runtime drift" in error for error in errors), errors)

    def test_distribution_detects_claude_skill_replica_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._distribution_fixture(root)
            replica = root / ".claude" / "skills" / "cowork-flow" / "manifest.json"
            replica.write_text(
                replica.read_text(encoding="utf-8").replace("start task", "start drifted task"),
                encoding="utf-8",
            )

            errors = self.doctor.check_distribution(root)

        self.assertTrue(any(".claude" in error for error in errors), errors)

    def test_distribution_detects_non_core_skill_replica_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._distribution_fixture(root)
            replica = root / ".claude" / "skills" / "runtime-health" / "SKILL.md"
            replica.write_text(
                replica.read_text(encoding="utf-8") + "\nDrifted guidance.\n",
                encoding="utf-8",
            )

            errors = self.doctor.check_distribution(root)

        self.assertTrue(any("runtime-health" in error for error in errors), errors)

    def test_distribution_detects_non_core_runtime_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._distribution_fixture(root)
            runtime = root / ".cowork-flow" / "scripts" / "run.py"
            runtime.write_text(
                runtime.read_text(encoding="utf-8") + "\n# drift\n",
                encoding="utf-8",
            )

            errors = self.doctor.check_distribution(root)

        self.assertTrue(
            any("scripts/run.py" in error.replace("\\", "/") for error in errors),
            errors,
        )

    def test_task_hygiene_reports_stale_tasks_without_failing_health(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tasks = root / ".cowork-flow" / "tasks"
            completed = tasks / "05-19-completed"
            in_progress = tasks / "05-20-in-progress"
            missing_context = tasks / "05-21-missing-context"
            for task_dir, status in (
                (completed, "completed"),
                (in_progress, "in_progress"),
                (missing_context, "planning"),
            ):
                task_dir.mkdir(parents=True)
                (task_dir / "task.json").write_text(
                    f'{{"status": "{status}", "assignee": "codex"}}\n',
                    encoding="utf-8",
                )
            (missing_context / "implement.jsonl").write_text('{"file": "README.md"}\n', encoding="utf-8")

            issues = self.doctor.check_task_hygiene(root)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                io.StringIO()
            ):
                result = self.doctor._run_task_hygiene_checks(root)
            with contextlib.redirect_stdout(stdout):
                structured_result = self.doctor._run_task_hygiene_checks(
                    root,
                    structured=True,
                )

        kinds = {issue["kind"] for issue in issues}
        payload = json.loads(stdout.getvalue())
        structured_issues = payload["issues"]
        envelope_keys = {
            "code",
            "severity",
            "path",
            "message",
            "commandHint",
            "contract",
        }
        self.assertEqual(0, result)
        self.assertEqual(0, structured_result)
        self.assertIn("completed_unarchived", kinds)
        self.assertIn("in_progress_unbound", kinds)
        self.assertIn("missing_task_context", kinds)
        self.assertEqual(
            [],
            [issue for issue in issues if not envelope_keys <= set(issue)],
        )
        self.assertEqual(
            [],
            [
                issue
                for issue in structured_issues
                if issue["commandHint"] != issue["hint"]
            ],
        )
        self.assertEqual(
            [],
            [
                issue
                for issue in structured_issues
                if issue["severity"] != "warning"
                or issue["contract"] != "runtime-health:task-hygiene"
            ],
        )
        self.assertEqual(
            {
                "TASK-HYGIENE-COMPLETED-UNARCHIVED",
                "TASK-HYGIENE-IN-PROGRESS-UNBOUND",
                "TASK-HYGIENE-MISSING-TASK-CONTEXT",
            },
            {issue["code"] for issue in structured_issues},
        )
        self.assertEqual(
            [],
            [issue for issue in structured_issues if issue["severity"] == "error"],
        )
        self.assertEqual(
            [],
            [
                issue
                for issue in issues
                if not issue["hint"].startswith("./.cowork-flow/run ")
            ],
        )

    def test_session_hygiene_reports_stale_sessions_without_failing_health(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sessions = root / ".cowork-flow" / ".runtime" / "sessions"
            sessions.mkdir(parents=True)
            (sessions / "zcode_dead-task.json").write_text(
                json.dumps(
                    {
                        "active_task_path": ".cowork-flow/tasks/06-21-gone",
                        "scope": "main",
                        "platform": "zcode",
                        "last_seen_at": "2026-01-01T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            (sessions / "zcode_aged.json").write_text(
                json.dumps(
                    {
                        "scope": "main",
                        "platform": "zcode",
                        "last_seen_at": "2020-01-01T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            (sessions / "zcode_broken.json").write_text("{not json", encoding="utf-8")
            (sessions / "zcode_naive.json").write_text(
                json.dumps(
                    {
                        "scope": "main",
                        "platform": "zcode",
                        "last_seen_at": "2099-01-01T00:00:00",
                    }
                ),
                encoding="utf-8",
            )
            (sessions / "claude_fresh.json").write_text(
                json.dumps(
                    {
                        "active_task_path": ".cowork-flow/tasks/07-02-live",
                        "scope": "main",
                        "platform": "claude",
                        "last_seen_at": "2099-01-01T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            live_task = root / ".cowork-flow" / "tasks" / "07-02-live"
            live_task.mkdir(parents=True)
            (live_task / "task.json").write_text('{"status": "in_progress"}\n', encoding="utf-8")

            issues = self.doctor.check_session_hygiene(root)
            result = self.doctor._all_check_result(root)
            structured_issues = result["issues"]["sessionHygiene"]

        codes = {issue["code"] for issue in issues}
        self.assertIn("SESSION-HYGIENE-DEAD-TASK", codes)
        self.assertIn("SESSION-HYGIENE-AGED", codes)
        self.assertIn("SESSION-HYGIENE-UNREADABLE-SESSION", codes)
        self.assertEqual(
            {
                "SESSION-HYGIENE-DEAD-TASK",
                "SESSION-HYGIENE-AGED",
                "SESSION-HYGIENE-UNREADABLE-SESSION",
            },
            {issue["code"] for issue in structured_issues},
        )
        self.assertEqual([], [issue for issue in issues if "claude_fresh" in issue["path"]])
        envelope_keys = {"code", "severity", "path", "message", "commandHint", "contract"}
        self.assertEqual(
            [],
            [issue for issue in structured_issues if not envelope_keys <= set(issue)],
        )
        self.assertEqual(
            [],
            [
                issue
                for issue in structured_issues
                if issue["severity"] != "warning"
                or issue["contract"] != "runtime-health:session-hygiene"
            ],
        )
        self.assertEqual(
            [],
            [error for error in result["errors"] if "SESSION-HYGIENE" in json.dumps(error)],
        )

    def test_state_recovery_reports_locks_and_pending_operations_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = root / ".cowork-flow" / ".runtime"
            target = runtime / "sessions" / "main.json"
            lock_path = target.with_name(f"{target.name}.lock")
            lock_path.parent.mkdir(parents=True)
            operation_path = runtime / "operations" / "op-demo.json"
            operation_path.parent.mkdir(parents=True)
            operation_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "operation_id": "op-demo",
                        "kind": "runtime-context-bind",
                        "phase": "prepared",
                        "participants": [{"path": str(target)}],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            conflict_path = runtime / "operations" / "op-conflict.json"
            conflict_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "operation_id": "op-conflict",
                        "kind": "task-lifecycle-start",
                        "phase": "conflicted",
                        "participants": [{"path": str(target)}],
                        "error": {
                            "code": "STATE-CONFLICT-001",
                            "path": str(target),
                            "detail": "expected revision 1, found 2",
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            self.doctor.StateStore._write_lock_file(
                lock_path,
                target,
                pid=424242,
                created_at="2000-01-01T00:00:00Z",
            )

            with mock.patch.object(
                self.doctor.StateStore,
                "_pid_exists",
                return_value=False,
            ):
                issues = self.doctor.check_state_recovery(root)

            lock_issues = [issue for issue in issues if issue["kind"] == "state_lock"]
            operation_issues = [
                issue for issue in issues if issue["kind"] == "pending_operation"
            ]
            self.assertEqual(1, len(lock_issues), issues)
            self.assertEqual(2, len(operation_issues), issues)
            lock_issue = lock_issues[0]
            self.assertEqual("STATE-RECOVERY-LOCK-RECOVERABLE", lock_issue["code"])
            self.assertEqual("recoverable", lock_issue["status"])
            self.assertEqual("missing", lock_issue["ownerAvailability"])
            self.assertEqual(str(target), lock_issue["target"])
            self.assertIn("ageSeconds", lock_issue)
            self.assertIn("remove_stale_lock", lock_issue["commandHint"])
            self.assertTrue(lock_path.exists())
            operation_issue = next(
                issue
                for issue in operation_issues
                if issue["operationId"] == "op-demo"
            )
            self.assertEqual("STATE-RECOVERY-PENDING-OPERATION", operation_issue["code"])
            self.assertEqual("prepared", operation_issue["phase"])
            self.assertIn("UnitOfWork.recover_all", operation_issue["commandHint"])
            conflict_issue = next(
                issue
                for issue in operation_issues
                if issue["operationId"] == "op-conflict"
            )
            self.assertEqual(
                "STATE-RECOVERY-CONFLICTED-OPERATION",
                conflict_issue["code"],
            )
            self.assertEqual("conflicted", conflict_issue["phase"])
            self.assertIn("STATE-CONFLICT-001", conflict_issue["message"])
            self.assertNotIn("UnitOfWork.recover_all", conflict_issue["commandHint"])

    def test_spec_checks_health_reports_broken_declarations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            spec_dir = root / ".cowork-flow" / "spec" / "backend"
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "bad-glob.md").write_text(
                "---\n"
                "checks:\n"
                "  - cmd: echo hi\n"
                "    files: src/**/*.ts\n"
                "---\n",
                encoding="utf-8",
            )
            (spec_dir / "missing-entry.md").write_text(
                "---\n"
                "checks:\n"
                "  - cmd: definitely-not-a-real-command-xyz\n"
                "---\n",
                encoding="utf-8",
            )

            issues = self.doctor.check_spec_checks(root)

            specs = {issue["spec"]: issue["message"] for issue in issues}
            self.assertIn("backend/bad-glob.md", specs)
            self.assertIn("unsupported files form", specs["backend/bad-glob.md"])
            self.assertIn("backend/missing-entry.md", specs)
            self.assertIn("command entry not found", specs["backend/missing-entry.md"])

    def test_spec_checks_health_passes_clean_declarations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            spec_dir = root / ".cowork-flow" / "spec" / "backend"
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "clean.md").write_text(
                "---\n"
                "checks:\n"
                "  - cmd: echo ok\n"
                "    files: src/\n"
                "---\n",
                encoding="utf-8",
            )

            self.assertEqual([], self.doctor.check_spec_checks(root))

    def test_mcp_registration_reports_project_level_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".mcp.json").write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "cowork-flow": {
                                "command": "cowork-flow",
                                "args": ["mcp-state"],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch.object(
                self.doctor, "_global_mcp_registered", return_value=False
            ):
                issues = self.doctor.check_mcp_registration(root)

        statuses = {issue["status"] for issue in issues}
        self.assertIn("project", statuses)
        self.assertNotIn("absent", statuses)
        self.assertNotIn("duplicate", statuses)

    def test_mcp_registration_reports_duplicate_global_and_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".mcp.json").write_text(
                json.dumps({"mcpServers": {"cowork-flow": {}}}),
                encoding="utf-8",
            )

            with mock.patch.object(
                self.doctor, "_global_mcp_registered", return_value=True
            ):
                issues = self.doctor.check_mcp_registration(root)

        statuses = {issue["status"] for issue in issues}
        self.assertIn("duplicate", statuses)

    def test_mcp_registration_absent_is_advisory_not_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir(parents=True)

            with mock.patch.object(
                self.doctor, "_global_mcp_registered", return_value=False
            ):
                issues = self.doctor.check_mcp_registration(root)
                result = self.doctor._all_check_result(root)

        statuses = {issue["status"] for issue in issues}
        self.assertIn("absent", statuses)
        # Advisory only: MCP registration issues never appear in the fatal
        # error list, whatever else the doctor reports about the fixture.
        self.assertFalse(
            [
                error
                for error in result["errors"]
                if error.get("kind") == "mcp"
            ]
        )


if __name__ == "__main__":
    unittest.main()
