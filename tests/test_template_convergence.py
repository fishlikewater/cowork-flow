from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"


class TemplateConvergenceTest(unittest.TestCase):
    def test_template_root_has_only_converged_collaboration_entries(self) -> None:
        entries = {path.name for path in TEMPLATE.iterdir()}

        self.assertIn("AGENTS.md", entries)
        self.assertIn(".agent", entries)
        self.assertIn(".cowork-flow", entries)

        self.assertNotIn(".agents", entries)
        self.assertNotIn(".trellis", entries)
        self.assertNotIn("docs", entries)
        self.assertNotIn("openspec", entries)

    def test_template_does_not_ship_macos_metadata(self) -> None:
        ds_store_files = sorted(
            str(path.relative_to(ROOT))
            for path in TEMPLATE.rglob(".DS_Store")
        )

        self.assertEqual([], ds_store_files)

    def test_required_flow_subdirectories_exist(self) -> None:
        expected = {
            "changes",
            "config.yaml",
            "plans",
            "scripts",
            "spec",
            "tasks",
            "workflow.md",
            "workspace",
        }
        actual = {path.name for path in (TEMPLATE / ".cowork-flow").iterdir()}

        self.assertTrue(expected.issubset(actual))


if __name__ == "__main__":
    unittest.main()
