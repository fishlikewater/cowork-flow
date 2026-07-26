#!/usr/bin/env python3
"""Behavior coverage for Party facade and domain guide routing."""

from __future__ import annotations

import importlib
import json
import tempfile
from pathlib import Path

from tests.flow_test_support import FlowScriptTestCase


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"


class DomainSkillRoutingTest(FlowScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.context_module = importlib.import_module(
            "application.task_context"
        )

    def test_party_has_one_public_facade_and_defaults_to_v2(self) -> None:
        party_skill = TEMPLATE / "skills/party-mode/SKILL.md"
        party_manifest = json.loads(
            (TEMPLATE / "skills/party-mode/manifest.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertTrue(party_skill.is_file())
        self.assertEqual("party-mode", party_manifest["skill"])
        self.assertEqual("party-v2", party_manifest["commands"][0]["name"])

        facade = party_skill.read_text(encoding="utf-8")
        self.assertIn(".cowork-flow/run party-v2 init", facade)
        self.assertIn("single public Party Mode entrypoint", facade)
        self.assertNotIn("manual fallback", facade.lower())

    def test_static_domain_guides_route_by_dev_type_and_path(self) -> None:
        context = self.context_module

        self.assertEqual(
            [".agents/skills/python-runtime-design/SKILL.md"],
            [
                entry["file"]
                for entry in context.get_domain_skill_context(
                    ROOT,
                    dev_type="backend",
                    paths=(),
                )
            ],
        )
        self.assertEqual(
            [".agents/skills/game-design/SKILL.md"],
            [
                entry["file"]
                for entry in context.get_domain_skill_context(
                    ROOT,
                    paths=("games/demo/scene.tscn",),
                )
            ],
        )
        self.assertEqual(
            [".agents/skills/cowork-flow-maintenance/SKILL.md"],
            [
                entry["file"]
                for entry in context.get_domain_skill_context(
                    ROOT,
                    paths=(".cowork-flow/spec/runtime/rules.json",),
                )
            ],
        )
        self.assertEqual(
            [],
            context.get_domain_skill_context(
                ROOT,
                dev_type="frontend",
                paths=("src/components/button.tsx",),
            ),
        )

    def test_task_context_injects_unique_domain_guides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "src").mkdir()
            (root / "src/example.py").write_text(
                "value = 1\n",
                encoding="utf-8",
            )
            (root / ".cowork-flow").mkdir()
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
                files.count(".agents/skills/python-runtime-design/SKILL.md"),
            )
            self.assertEqual(
                1,
                files.count(".agents/skills/cowork-flow-maintenance/SKILL.md"),
            )


if __name__ == "__main__":
    import unittest

    unittest.main()
