from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
FORBIDDEN_PATTERNS = (
    "OpenSpec",
    "." + "tre" + "llis",
    "." + "agent/",
    "." + "agent skills",
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
    "/current_task",
    "\\current_task",
    "agent run ",
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

    def test_formal_prompt_surfaces_do_not_use_prd_terminology(self) -> None:
        forbidden = (
            " PRD",
            "Read task PRD",
            "Read active task PRD",
            "Active task PRD missing",
            "PRD acceptance",
            "PRD 特有",
            "PRD 验收",
            "before PRD, planning",
            "Do not write PRD, planning",
            "PRD 和 implement.jsonl",
            "PRD、计划或固定代理派发",
            "required by the PRD",
            "Deprecated aliases may redirect here",
        )
        scanned_roots = (
            ROOT / "AGENTS.md",
            TEMPLATE / "AGENTS.md",
            TEMPLATE / "skills",
            TEMPLATE / ".codex" / "agents",
            TEMPLATE / ".claude" / "agents",
            TEMPLATE / ".opencode" / "agents",
            TEMPLATE / ".cowork-flow" / "scripts",
            TEMPLATE / ".cowork-flow" / "spec" / "contracts" / "workflow-state-templates.md",
            TEMPLATE / ".cowork-flow" / "spec" / "references" / "definition-of-done.md",
            TEMPLATE / ".zcode" / "scaffold" / "AGENTS.md",
        )
        suffixes = {".md", ".py", ".toml"}
        offenders: list[str] = []

        for root in scanned_roots:
            paths = [root] if root.is_file() else [path for path in root.rglob("*") if path.is_file()]
            for path in paths:
                if path.suffix not in suffixes:
                    continue
                text = path.read_text(encoding="utf-8")
                for pattern in forbidden:
                    if pattern in text:
                        offenders.append(f"{path.relative_to(ROOT)} contains {pattern}")

        self.assertEqual([], offenders)

    def test_git_context_uses_decision_anchor_internal_names(self) -> None:
        path = TEMPLATE / ".cowork-flow" / "scripts" / "adapters" / "git" / "git_context.py"
        text = path.read_text(encoding="utf-8")

        self.assertIn("has_decision_anchor", text)
        self.assertIn("decision_anchor_path", text)
        self.assertIn("include_decision_anchor_hint", text)
        self.assertNotIn("has_prd", text)
        self.assertNotIn("prd_path", text)
        self.assertNotIn("include_prd_hint", text)

    def test_template_does_not_ship_superpowers_seed(self) -> None:
        self.assertFalse((TEMPLATE / ".superpowers").exists())

    def test_internal_protocol_files_are_not_shipped(self) -> None:
        for name in ("review.md", "decision-review.md", "spec-maintenance.md"):
            self.assertFalse(
                (TEMPLATE / ".cowork-flow" / "spec" / "protocols" / name).exists(),
                name,
            )

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

    def test_config_template_only_documents_effective_settings(self) -> None:
        for path in (
            ROOT / "template" / ".cowork-flow" / "config.yaml",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("injected workflow dispatch hint", text)
            self.assertIn("does not force dispatch", text)
            self.assertIn("simple executable plus arguments", text)
            self.assertIn("No shell pipes, redirects, or command chaining", text)
            self.assertNotIn("verification:", text)
            self.assertNotIn("Project-specific commands", text)

    def test_workspace_index_does_not_claim_live_developer_state(self) -> None:
        for path in (
            ROOT / "template" / ".cowork-flow" / "workspace" / "index.md",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("状态来源", text)
            self.assertIn("不维护开发者状态", text)
            self.assertIn("./.cowork-flow/run resume", text)
            self.assertIn("workspace 仅用于记录会话 journal", text)
            self.assertNotIn("(none yet)", text)
            self.assertNotIn("| 开发者 | 最近活跃 | 会话数 | 当前文件 |", text)

    def test_spec_files_ship_generic_defaults_without_fill_in_placeholders(self) -> None:
        forbidden = (
            "<按项目",
            "按项目填写",
            "项目定制位",
            "可保留占位",
            "请替换为项目",
            "TODO",
            "TBD",
        )
        offenders: list[str] = []

        for spec_root in (
            ROOT / ".cowork-flow" / "spec",
            TEMPLATE / ".cowork-flow" / "spec",
        ):
            for path in spec_root.rglob("*.md"):
                text = path.read_text(encoding="utf-8")
                for pattern in forbidden:
                    if pattern in text:
                        offenders.append(f"{path.relative_to(ROOT)} contains {pattern}")

        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
