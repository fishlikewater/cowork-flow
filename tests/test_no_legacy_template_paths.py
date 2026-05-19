from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
FORBIDDEN_PATTERNS = (
    "OpenSpec",
    "Trellis",
    "trellis",
    ".trellis",
    ".agents",
    "docs/superpowers",
    "openspec new",
    "openspec validate",
    "openspec archive",
    "openspec/changes",
    "openspec/config.yaml",
)


class NoLegacyTemplatePathsTest(unittest.TestCase):
    def test_template_text_files_do_not_reference_legacy_paths(self) -> None:
        offenders: list[str] = []
        text_files = [
            path
            for path in TEMPLATE.rglob("*")
            if path.is_file()
            and path.suffix in {".md", ".py", ".yaml", ".gitignore"}
            and ".superpowers" not in path.parts
        ]

        for path in text_files:
            content = path.read_text(encoding="utf-8")
            for pattern in FORBIDDEN_PATTERNS:
                if pattern in content:
                    offenders.append(f"{path.relative_to(ROOT)} contains {pattern}")

        self.assertEqual([], offenders)

    def test_superpowers_seed_uses_cowork_flow_paths(self) -> None:
        forbidden_patterns = (
            "docs/superpowers",
            "OpenSpec",
            "openspec new",
            "openspec validate",
            "openspec archive",
            "openspec/changes",
            "openspec/config.yaml",
            ".trellis",
        )
        offenders: list[str] = []
        text_files = [
            path
            for path in (TEMPLATE / ".superpowers").rglob("*")
            if path.is_file()
            and path.suffix in {".md", ".js", ".cjs", ".sh", ".html", ".dot", ".ts"}
        ]

        for path in text_files:
            content = path.read_text(encoding="utf-8")
            for pattern in forbidden_patterns:
                if pattern in content:
                    offenders.append(f"{path.relative_to(ROOT)} contains {pattern}")

        self.assertEqual([], offenders)

    def test_change_directories_do_not_define_tasks_md(self) -> None:
        tasks_files = sorted(
            str(path.relative_to(ROOT))
            for path in (TEMPLATE / ".cowork-flow" / "changes").rglob("tasks.md")
        )

        self.assertEqual([], tasks_files)

    def test_readme_documents_converged_template_structure(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("AGENTS.md", readme)
        self.assertIn(".agent/", readme)
        self.assertIn(".cowork-flow/", readme)
        self.assertIn("python3 ./.cowork-flow/scripts/change.py create <slug>", readme)

        self.assertNotIn(".trellis/", readme)
        self.assertNotIn(".agents/", readme)
        self.assertNotIn("docs/superpowers/", readme)
        self.assertNotIn("openspec/", readme)
        self.assertNotIn("openspec new", readme)


if __name__ == "__main__":
    unittest.main()
