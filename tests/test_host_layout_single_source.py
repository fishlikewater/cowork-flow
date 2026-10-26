from __future__ import annotations

import ast
import io
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
DOCTOR_PATH = TEMPLATE / "skills" / "runtime-health" / "scripts" / "doctor.py"

# Every Python tree that ships into a project or a host payload. Machine-level
# install layouts belong to the Node installers, never to these scripts.
SOURCE_ROOTS = (
    TEMPLATE / ".cowork-flow" / "scripts",
    TEMPLATE / "skills",
    ROOT / "presets",
)

# Host install-state checks that must read the CLI-owned inspect rows. Adding a
# host here is the point: its layout stays in the Node installer, not in doctor.
HOST_STATE_CHECKS = (
    "check_qoder_plugin",
    "check_zcode_plugin",
    "check_claude_code_plugin",
    "check_opencode_plugin",
    "check_kimi_code_plugin",
    "check_kimi_hook",
    "check_dsh_preset",
    "check_codex_plugin",
    "_legacy_machine_skills_issues",
)

# Layout knowledge that belongs to the installers. Messages may name a file,
# but a check body must not resolve or parse one of these itself.
FORBIDDEN_IN_CHECK_BODY = (
    "installed_plugins_v2.json",
    "installed.json",
    "settings.json",
    "marketplace.json",
    "cordis.patch.yml",
    ".agent-presets",
    "QODER_CONFIG_DIR",
    "ZCODE_HOME",
    "CLAUDE_CONFIG_DIR",
    "CODEX_HOME",
    "DSH_HOME",
    "KIMI_CODE_HOME",
    "XDG_CONFIG_HOME",
    "Path.home(",
    "expanduser",
)

# Host registries, enable files and machine-level asset roots. None of these
# may be opened by shipped Python, at any scope (module constants included).
FORBIDDEN_LAYOUT_TOKENS = (
    "installed_plugins_v2.json",
    "installed.json",
    "settings.json",
    "marketplace.json",
    "cordis.patch.yml",
    ".agent-presets",
    ".cowork-flow-preset.json",
    ".cowork-flow-kimi-hook.json",
    "QODER_CONFIG_DIR",
    "ZCODE_HOME",
    "CLAUDE_CONFIG_DIR",
    "CODEX_HOME",
    "DSH_HOME",
    "KIMI_CODE_HOME",
    "XDG_CONFIG_HOME",
)

# Resolving a user's home directory is how a machine-level layout read starts.
# The one legitimate exception is the MCP-registration probe, which reports
# whether a client config mentions cowork-flow rather than reading host install
# state; it is exempted by function name below.
FORBIDDEN_HOME_TOKENS = (
    "Path.home(",
    "expanduser",
    "homedir",
    '"HOME"',
    "'HOME'",
    "$HOME",
    '"USERPROFILE"',
    "'USERPROFILE'",
    "%USERPROFILE%",
)

EXEMPT_FUNCTIONS = {"_global_mcp_registered"}

# Python helpers deleted once the CLI owned install state. Their return would
# mean a second layout reader grew back.
REMOVED_HELPERS = (
    "_machine_plugin_payload",
    "_payload_manifest",
    "_qoder_home",
    "_qoder_registry_entry",
    "_zcode_marketplace_path",
    "_codex_home",
    "_codex_config_sections",
    "_codex_marketplace_source",
    "_kimi_home",
    "_kimi_plugin_record",
    "_marker_version",
    "_dsh_preset_dir",
)


def _strip_exempt_functions(text: str, tree: ast.AST) -> str:
    """Remove the source ranges of explicitly justified home probes."""
    lines = text.splitlines(keepends=True)
    spans = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef)
            and node.name in EXEMPT_FUNCTIONS
            and node.end_lineno is not None
        ):
            spans.append((node.lineno, node.end_lineno))
    for start, end in sorted(spans, reverse=True):
        del lines[start - 1:end]
    return "".join(lines)


def layout_violations(text: str, name: str) -> list[tuple[str, str]]:
    """Machine-layout reads in one source file, with the exempt probe removed."""
    tree = ast.parse(text)
    stripped = _strip_exempt_functions(text, tree)
    violations = []
    for token in FORBIDDEN_LAYOUT_TOKENS + FORBIDDEN_HOME_TOKENS:
        if token in stripped:
            violations.append((name, token))
    return violations


def _iter_sources():
    for root in SOURCE_ROOTS:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            yield path, io.open(path, encoding="utf-8").read()


def _load_doctor() -> tuple[str, dict[str, ast.FunctionDef]]:
    text = io.open(DOCTOR_PATH, encoding="utf-8").read()
    tree = ast.parse(text)
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    return text, functions


class HostLayoutSingleSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text, cls.functions = _load_doctor()

    def test_shipped_python_does_not_read_host_layouts(self) -> None:
        violations = []
        for path, text in _iter_sources():
            violations.extend(layout_violations(text, str(path.relative_to(ROOT))))
        self.assertEqual(
            [],
            violations,
            "machine-level host layouts belong to the Node installers; "
            "shipped Python must consume cwf host inspect instead",
        )

    def test_the_guard_catches_a_renamed_home_layout_helper(self) -> None:
        sample = (
            "from pathlib import Path\n"
            "def _codex_layout():\n"
            '    return Path.home() / ".codex"\n'
        )
        self.assertEqual(
            [("sample.py", "Path.home(")],
            layout_violations(sample, "sample.py"),
        )

    def test_project_relative_host_directories_are_not_install_layouts(self) -> None:
        sample = (
            "from pathlib import Path\n"
            "def project_codex(root: Path) -> Path:\n"
            '    return root / ".codex"\n'
        )
        self.assertEqual([], layout_violations(sample, "sample.py"))

    def test_the_mcp_registration_probe_is_explicitly_exempt(self) -> None:
        sample = (
            "import os\nfrom pathlib import Path\n"
            "def _global_mcp_registered():\n"
            '    home = Path(os.path.expanduser("~"))\n'
            '    return (home / ".codex" / "config.toml").is_file()\n'
        )
        self.assertEqual([], layout_violations(sample, "sample.py"))

    def test_every_host_check_consumes_inspect_rows(self) -> None:
        missing = []
        for name in HOST_STATE_CHECKS:
            if name not in self.functions:
                missing.append(f"{name}: missing function")
                continue
            source = ast.get_source_segment(self.text, self.functions[name]) or ""
            reader = (
                "_inspect_row"
                if name == "_legacy_machine_skills_issues"
                else "_inspect_component_row"
            )
            if reader not in source:
                missing.append(f"{name}: {reader}")
            if name == "_legacy_machine_skills_issues" and "facts" not in source:
                missing.append(f"{name}: facts")
        self.assertEqual(
            [],
            missing,
            "host checks must consume the CLI-owned inspect rows",
        )

    def test_host_checks_do_not_parse_install_layouts(self) -> None:
        violations = []
        for name in HOST_STATE_CHECKS:
            source = ast.get_source_segment(self.text, self.functions[name]) or ""
            violations.extend(
                (name, token)
                for token in FORBIDDEN_IN_CHECK_BODY
                if token in source
            )
        self.assertEqual(
            [],
            violations,
            "host checks must not resolve or parse install layouts",
        )

    def test_removed_python_layout_helpers_stay_removed(self) -> None:
        present = [
            name
            for name in REMOVED_HELPERS
            if name in self.functions or name in self.text
        ]
        self.assertEqual(
            [],
            present,
            "deleted layout helpers must not grow back",
        )


if __name__ == "__main__":
    unittest.main()
