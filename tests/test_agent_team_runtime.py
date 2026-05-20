from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"


class AgentTeamRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        shutil.copytree(TEMPLATE, self.repo)
        self.script = self.repo / ".cowork-flow" / "scripts" / "agent_team.py"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_agent_team(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self.script), *args],
            cwd=self.repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_init_creates_project_config_when_missing(self) -> None:
        shutil.rmtree(self.repo / ".cowork-flow" / "agent-team")

        result = self.run_agent_team("init")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((self.repo / ".cowork-flow" / "agent-team" / "agents.yaml").is_file())
        self.assertTrue((self.repo / ".cowork-flow" / "agent-team" / "adapters.yaml").is_file())
        self.assertTrue((self.repo / ".cowork-flow" / "agent-team" / "policy.yaml").is_file())
        self.assertIn("initialized", result.stdout)

    def test_init_preserves_existing_project_config(self) -> None:
        agents = self.repo / ".cowork-flow" / "agent-team" / "agents.yaml"
        agents.write_text("custom: true\n", encoding="utf-8")

        result = self.run_agent_team("init")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("custom: true\n", agents.read_text(encoding="utf-8"))
        self.assertIn("preserved", result.stdout)


if __name__ == "__main__":
    unittest.main()
