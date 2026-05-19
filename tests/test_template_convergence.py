from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"


class TemplateConvergenceTest(unittest.TestCase):
    def test_template_root_has_only_converged_collaboration_entries(self) -> None:
        entries = {path.name for path in TEMPLATE.iterdir()}

        self.assertEqual({"AGENTS.md", ".agent", ".cowork-flow", ".superpowers"}, entries)

    def test_superpowers_is_internal_cli_seed_material(self) -> None:
        self.assertTrue((TEMPLATE / ".superpowers" / "using-superpowers" / "SKILL.md").is_file())
        self.assertTrue((TEMPLATE / ".superpowers" / "test-driven-development" / "SKILL.md").is_file())

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

    def test_resume_script_exists(self) -> None:
        self.assertTrue((TEMPLATE / ".cowork-flow" / "scripts" / "resume.py").is_file())

    def test_required_placeholder_files_exist(self) -> None:
        expected = [
            TEMPLATE / ".cowork-flow" / "tasks" / ".gitkeep",
            TEMPLATE / ".cowork-flow" / "tasks" / "archive" / ".gitkeep",
            TEMPLATE / ".cowork-flow" / "plans" / ".gitkeep",
            TEMPLATE / ".cowork-flow" / "changes" / "archive" / ".gitkeep",
        ]

        missing = [
            str(path.relative_to(ROOT))
            for path in expected
            if not path.is_file()
        ]

        self.assertEqual([], missing)

    def test_template_documents_layered_resume_protocol(self) -> None:
        agents = (TEMPLATE / "AGENTS.md").read_text(encoding="utf-8")
        workflow = (TEMPLATE / ".cowork-flow" / "workflow.md").read_text(encoding="utf-8")
        start_skill = (
            TEMPLATE / ".agent" / "skills" / "start" / "SKILL.md"
        ).read_text(encoding="utf-8")

        self.assertIn("上下文压缩", agents)
        self.assertIn("resume.py", agents)
        self.assertIn("最小恢复层", workflow)
        self.assertIn("不要全量重读", workflow)
        self.assertIn("resume.py", workflow)
        self.assertIn("Resume / Context Compression", start_skill)
        self.assertIn("resume.py", start_skill)


if __name__ == "__main__":
    unittest.main()
