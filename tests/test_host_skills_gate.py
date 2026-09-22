from __future__ import annotations

import importlib
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
TEMPLATE = ROOT / "template"

# Fixed-subagent bodies per platform, and where they live. Platforms whose
# declaration is machine-scope (their host discovers skills inside a plugin
# payload) are listed here with the payload-relative prefix they may reference.
PLATFORM_AGENT_SOURCES = {
    "codex": (TEMPLATE / ".codex" / "agents", "*.toml"),
    "opencode": (TEMPLATE / ".opencode" / "agents", "*.md"),
    "claude-code": (TEMPLATE / ".claude" / "agents", "*.md"),
    "kimi-code": (TEMPLATE / ".kimi-code" / "agents", "*.md"),
    "qoder": (ROOT / "presets" / "qoder" / "agents", "*.md"),
    "zcode": (ROOT / "presets" / "zcode" / "agents", "*.md"),
}
MACHINE_SCOPE_PREFIXES = {
    # zcode resolves `skills/` inside the plugin payload it was installed into.
    "zcode": ("skills/",),
}
# Declarations that are still carried by convention rather than by a local
# probe. Adding a new unverified declaration must show up here on purpose.
ASSUMED_DISCOVERY = {
    "codex": ".agents/skills",
    "opencode": ".agents/skills",
    "claude-code": ".claude/skills",
    "dsh": ".agents/skills",
    "kimi-code": ".agents/skills",
}
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

            project_scope = [
                discovery
                for discovery in platform.skill_discovery
                if discovery.scope == "project"
            ]
            if project_scope:
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
                continue

            prefixes = MACHINE_SCOPE_PREFIXES.get(platform_id)
            self.assertIsNotNone(
                prefixes,
                f"{platform_id} is machine-scope; register its payload prefix",
            )
            self.assertEqual(
                [],
                [
                    f"{path.name} references {reference}, which is outside {prefixes}"
                    for path, reference in references
                    if not any(reference.startswith(prefix) for prefix in prefixes)
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


if __name__ == "__main__":
    unittest.main()
