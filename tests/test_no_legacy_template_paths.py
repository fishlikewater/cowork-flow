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
    "python3 ./.cowork-flow/scripts",
    "agent-team",
    "agent_team",
    "agent-team-execution",
    "dispatching-parallel-agents",
    "subagent-driven-development",
    "requesting-code-review",
    "using-superpowers",
    "worker-report",
    ".current-task",
    "agent run",
    "codex exec",
)


class NoLegacyTemplatePathsTest(unittest.TestCase):
    def test_template_text_files_do_not_reference_legacy_paths(self) -> None:
        offenders: list[str] = []
        text_files = [
            path
            for path in TEMPLATE.rglob("*")
            if path.is_file()
            and path.suffix in {".md", ".py", ".yaml", ".gitignore"}
        ]

        for path in text_files:
            content = path.read_text(encoding="utf-8")
            for pattern in FORBIDDEN_PATTERNS:
                if pattern in content:
                    offenders.append(f"{path.relative_to(ROOT)} contains {pattern}")

        self.assertEqual([], offenders)

    def test_template_does_not_ship_superpowers_seed(self) -> None:
        self.assertFalse((TEMPLATE / ".superpowers").exists())

    def test_change_directories_do_not_define_tasks_md(self) -> None:
        tasks_files = sorted(
            str(path.relative_to(ROOT))
            for path in (TEMPLATE / ".cowork-flow" / "changes").rglob("tasks.md")
        )

        self.assertEqual([], tasks_files)

    def test_legacy_team_runtime_removed(self) -> None:
        legacy_script = "agent" + "_team.py"
        removed = [
            ROOT / ".cowork-flow" / "scripts" / legacy_script,
            ROOT / ".cowork-flow" / "scripts" / "common" / legacy_script,
            ROOT / "template" / ".cowork-flow" / "scripts" / legacy_script,
            ROOT / "template" / ".cowork-flow" / "scripts" / "common" / legacy_script,
        ]

        for path in removed:
            self.assertFalse(path.exists(), str(path))

    def test_readme_documents_converged_template_structure(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("AGENTS.md", readme)
        self.assertIn(".agent/", readme)
        self.assertIn(".cowork-flow/", readme)
        self.assertIn("./.cowork-flow/run change create <slug>", readme)

        self.assertNotIn("python3 ./.cowork-flow/scripts", readme)
        self.assertNotIn(".trellis/", readme)
        self.assertNotIn(".agents/", readme)
        self.assertNotIn(".superpowers/", readme)
        self.assertNotIn("Superpowers", readme)
        self.assertNotIn("docs/superpowers/", readme)
        self.assertNotIn("openspec/", readme)
        self.assertNotIn("openspec new", readme)
        self.assertNotIn("agent-team", readme)
        self.assertNotIn("agent_team", readme)


if __name__ == "__main__":
    unittest.main()
