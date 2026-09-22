from __future__ import annotations

import importlib
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
TEMPLATE = ROOT / "template"
MANIFEST = ".cowork-flow/spec/runtime/host-assets.json"


class HostSkillPathTest(unittest.TestCase):
    """Skill path rendering follows the manifest's per-host skillReadRoot."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.added_scripts_path = str(SCRIPTS) not in sys.path
        if cls.added_scripts_path:
            sys.path.insert(0, str(SCRIPTS))
        cls.skill_manifest = importlib.import_module("infra.skill_manifest")
        cls.context_discovery = importlib.import_module("services.context_discovery")
        cls.host_manifest = importlib.import_module("adapters.host.host_manifest")

    @classmethod
    def tearDownClass(cls) -> None:
        for name in (
            "infra.skill_manifest",
            "services.context_discovery",
            "adapters.host.host_manifest",
        ):
            sys.modules.pop(name, None)
        if cls.added_scripts_path and str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))

    def _project(self, temp_dir: str, *, dirs: tuple[str, ...], with_manifest: bool = True) -> Path:
        root = Path(temp_dir)
        for relative in dirs:
            (root / relative).mkdir(parents=True, exist_ok=True)
        if with_manifest:
            (root / ".cowork-flow" / "spec" / "runtime").mkdir(parents=True, exist_ok=True)
            shutil.copy(TEMPLATE / MANIFEST, root / MANIFEST)
        return root

    def test_active_host_decides_the_read_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._project(
                temp_dir, dirs=(".agents/skills", ".claude/skills")
            )

            self.assertEqual(
                ".agents/skills/task-review/SKILL.md",
                self.skill_manifest._skill_path(root, "task-review", host="qoder"),
            )
            self.assertEqual(
                ".claude/skills/task-review/SKILL.md",
                self.skill_manifest._skill_path(
                    root, "task-review", host="claude-code"
                ),
            )

    def test_first_present_read_root_wins_without_a_host(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._project(temp_dir, dirs=(".claude/skills",))

            self.assertEqual(
                ".claude/skills/task-review/SKILL.md",
                self.skill_manifest._skill_path(root, "task-review"),
            )

    def test_zcode_project_renders_the_kernel_replica(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._project(temp_dir, dirs=(".cowork-flow/skills",))

            self.assertEqual(
                ".cowork-flow/skills/task-review/SKILL.md",
                self.skill_manifest._skill_path(root, "task-review", host="zcode"),
            )

    def test_project_without_a_local_manifest_uses_the_installed_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._project(temp_dir, dirs=(".agents/skills",), with_manifest=False)

            self.assertEqual(
                ".agents/skills/task-review/SKILL.md",
                self.skill_manifest._skill_path(root, "task-review"),
            )

    def test_session_env_selects_the_host(self) -> None:
        with patch.dict(os.environ, {"COWORK_FLOW_HOST": "claude-code"}, clear=True):
            self.assertEqual("claude-code", self.context_discovery.active_host())
        with patch.dict(os.environ, {"QODER_SESSION_ID": "q1"}, clear=True):
            self.assertEqual("qoder", self.context_discovery.active_host())
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(self.context_discovery.active_host())

    def test_declared_host_overrides_a_detected_one(self) -> None:
        with patch.dict(
            os.environ,
            {"COWORK_FLOW_HOST": "qoder", "CLAUDE_SESSION_ID": "c1"},
            clear=True,
        ):
            self.assertEqual("qoder", self.context_discovery.active_host())

    def test_infra_read_roots_match_the_manifest_loader(self) -> None:
        roots = dict(self.skill_manifest._skill_read_roots(TEMPLATE))
        manifest = self.host_manifest.load_host_manifest(TEMPLATE)

        self.assertEqual(
            {
                platform.id: platform.skill_read_root
                for platform in manifest.platforms
            },
            roots,
        )
        self.assertEqual(
            ("codex", "opencode", "claude-code", "dsh", "zcode", "kimi-code", "qoder"),
            tuple(roots),
        )


if __name__ == "__main__":
    unittest.main()
