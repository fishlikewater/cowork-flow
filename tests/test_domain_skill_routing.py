#!/usr/bin/env python3
"""Behavior coverage for Party facade and domain guide routing."""

from __future__ import annotations

import importlib
import shutil
import tempfile
from pathlib import Path

from tests.flow_test_support import FlowScriptTestCase


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"


class DomainSkillRoutingTest(FlowScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.registry_module = importlib.import_module(
            "common.core.skill_registry"
        )
        self.context_module = importlib.import_module(
            "application.task_context"
        )

    def test_party_has_one_public_facade_and_defaults_to_v2(self) -> None:
        registry = self.registry_module.load_skill_registry(TEMPLATE)
        public_party_ids = [
            entry.id
            for entry in registry.public_entries
            if entry.id.startswith("party-mode")
        ]

        self.assertEqual(["party-mode"], public_party_ids)
        self.assertEqual(
            "party-v2 init",
            registry.entry("party-mode").runtime_command,
        )

        facade = (TEMPLATE / "skills/party-mode/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(".cowork-flow/run party-v2 init", facade)
        self.assertIn("single public Party Mode entrypoint", facade)
        self.assertNotIn("manual fallback", facade.lower())

    def test_registry_routes_domain_guides_by_dev_type_and_path(self) -> None:
        registry = self.registry_module.load_skill_registry(TEMPLATE)

        self.assertEqual(
            ("python-design",),
            tuple(
                entry.id
                for entry in registry.domain_entries_for(
                    dev_type="backend",
                    paths=(),
                )
            ),
        )
        self.assertEqual(
            ("game-design",),
            tuple(
                entry.id
                for entry in registry.domain_entries_for(
                    dev_type=None,
                    paths=("games/demo/scene.tscn",),
                )
            ),
        )
        self.assertEqual(
            ("meta",),
            tuple(
                entry.id
                for entry in registry.domain_entries_for(
                    dev_type=None,
                    paths=(".cowork-flow/spec/runtime/rules.json",),
                )
            ),
        )
        self.assertEqual(
            (),
            registry.domain_entries_for(
                dev_type="frontend",
                paths=("src/components/button.tsx",),
            ),
        )

    def test_task_context_injects_unique_domain_guides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            registry_dir = root / ".cowork-flow/spec/runtime"
            registry_dir.mkdir(parents=True)
            shutil.copyfile(
                TEMPLATE / ".cowork-flow/spec/runtime/skill-registry.json",
                registry_dir / "skill-registry.json",
            )
            (root / "src").mkdir()
            (root / "src/example.py").write_text(
                "value = 1\n",
                encoding="utf-8",
            )
            (root / ".cowork-flow/config.yaml").write_text(
                "version: 1\n",
                encoding="utf-8",
            )
            task_dir = root / ".cowork-flow/tasks/example"
            task_dir.mkdir(parents=True)

            service = self.context_module.TaskContextService(root)
            service.initialize(task_dir, "backend")
            service.add(
                task_dir,
                "implement",
                "src/example.py",
                "Python implementation target",
            )
            service.add(
                task_dir,
                "implement",
                ".cowork-flow/config.yaml",
                "Workflow metadata target",
            )

            files = [
                entry["file"]
                for entry in service.entries(task_dir, "implement")
            ]
            self.assertEqual(
                1,
                files.count(".agents/skills/python-design/SKILL.md"),
            )
            self.assertEqual(
                1,
                files.count(".agents/skills/meta/SKILL.md"),
            )


if __name__ == "__main__":
    import unittest

    unittest.main()
