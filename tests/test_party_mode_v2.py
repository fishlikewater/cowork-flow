from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
from tests.party_mode_test_support import PARTY_MODE_SCRIPT, PartyModeTestCase, ROOT, TEMPLATE_SCRIPTS


class PartyModeV2IntegrationTest(PartyModeTestCase):
    def test_party_mode_v2_config_defaults_and_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(
                Path(temp_name),
                """
party_mode_v2:
  min_agents: 4
  max_agents: 6
  max_rounds: 7
  max_rebuttal_targets_per_agent: 3
  max_drift_warnings: 1
  fresh_context_per_round: "false"
  require_current_round_only: "true"
""",
            )

            config = self.config.get_party_mode_v2_config(root)

            self.assertEqual(4, config["min_agents"])
            self.assertEqual(6, config["max_agents"])
            self.assertEqual(7, config["max_rounds"])
            self.assertEqual(3, config["max_rebuttal_targets_per_agent"])
            self.assertEqual(1, config["max_drift_warnings"])
            self.assertIs(config["fresh_context_per_round"], False)
            self.assertIs(config["require_current_round_only"], True)

    def test_party_mode_v2_config_falls_back_for_invalid_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(
                Path(temp_name),
                """
party_mode_v2:
  min_agents: 2
  max_agents: nope
  max_rounds: 0
  fresh_context_per_round: maybe
""",
            )

            config = self.config.get_party_mode_v2_config(root)

            self.assertEqual(3, config["min_agents"])
            self.assertEqual(5, config["max_agents"])
            self.assertEqual(5, config["max_rounds"])
            self.assertIs(config["fresh_context_per_round"], True)

    def test_template_runtime_assets_are_valid(self) -> None:
        # Verify template scripts exist and are valid
        self.assertTrue(PARTY_MODE_SCRIPT.is_file())
        self.assertTrue((TEMPLATE_SCRIPTS / "run.py").is_file())
        self.assertTrue((TEMPLATE_SCRIPTS / "kernel" / "config.py").is_file())

    def test_party_v2_command_is_registered(self) -> None:
        manifest = json.loads(
            (ROOT / "template" / "skills" / "party-mode" / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertNotIn("actions", manifest)
        command = manifest["commands"][0]
        self.assertEqual("party-v2", command["name"])
        self.assertIn("party_v2", command["aliases"])
        self.assertEqual("scripts/party_mode_v2.py", command["script"])
        runner = (TEMPLATE_SCRIPTS / "run.py").read_text(encoding="utf-8")
        self.assertIn("skill_command_scripts", runner)
        self.assertNotIn("SKILL_COMMAND_SCRIPTS", runner)

    def test_runner_dispatches_party_v2_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(Path(temp_name))
            result = subprocess.run(
                [
                    sys.executable,
                    str(TEMPLATE_SCRIPTS / "run.py"),
                    "party-v2",
                    "--repo-root",
                    str(root),
                    "init",
                    "--discussion-id",
                    "demo",
                    "--topic",
                    "Runtime board",
                    "--agent",
                    "arch:architecture",
                    "--agent",
                    "runtime:runtime-control",
                    "--agent",
                    "test:testing",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(0, result.returncode, result.stderr)
            output = json.loads(result.stdout)
            self.assertEqual("demo", output["discussion_id"])
            self.assertTrue(
                (
                    root
                    / ".cowork-flow"
                    / ".runtime"
                    / "party-mode-v2"
                    / "demo"
                    / "board.json"
                ).is_file()
            )

    def test_config_templates_document_party_mode_v2(self) -> None:
        for path in (
            ROOT / "template" / ".cowork-flow" / "config.yaml",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("party_mode_v2:", text)
            self.assertIn("min_agents: 3", text)
            self.assertIn("max_rounds: 5", text)


if __name__ == "__main__":
    unittest.main()
