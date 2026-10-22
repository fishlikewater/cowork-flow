from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_TEMPLATE = (
    ROOT / "template" / ".cowork-flow" / "templates" / "plan-template.md"
)
EN_TEMPLATE = (
    ROOT
    / "template"
    / "locales"
    / "en-US"
    / ".cowork-flow"
    / "templates"
    / "plan-template.md"
)
CJK_RE = re.compile(r"[\u4e00-\u9fff]")

SECTION_MARKERS = {
    "goal": ("## 目标", "## Goal"),
    "acceptance": ("## 验收标准", "## Acceptance Criteria"),
    "constraints": ("## 全局约束", "## Global Constraints"),
    "files": ("## 文件边界", "## File Boundaries"),
    "tasks": ("## 任务", "## Tasks"),
    "verification": ("## 最终验证", "## Final Verification"),
}

HEADER_MARKERS = {
    "task_type": ("**任务类型**", "**Task Type**"),
    "strategy": ("**执行策略**", "**Strategy**"),
    "success": ("**成功标准**", "**Success Criteria**"),
    "final_verification": ("**最终验证**", "**Final Verification**"),
    "risk": ("**主要风险**", "**Primary Risk**"),
}

BRIEF_MARKERS = {
    "purpose": ("**目的**", "**Purpose**"),
    "sources": ("**代码事实来源**", "**Code Fact Sources**"),
    "files": ("**文件边界**", "**File Boundaries**"),
    "symbols": ("**关键符号**", "**Key Symbols**"),
    "notes": ("**实现说明**", "**Implementation Notes**"),
    "proof": ("**测试证明**", "**Test Proof**"),
    "verify": ("**验证命令**", "**Verification Command**"),
    "completion": ("**完成条件**", "**Completion Conditions**"),
    "drift": ("**禁止漂移**", "**Prohibited Drift**"),
    "deviation": ("**偏差条件**", "**Deviation Conditions**"),
}

GOAL_LINE_RE = re.compile(r"(?m)^\*\*(?:Goal|目标):\*\*\s+\S")


def _assert_ordered(case: unittest.TestCase, text: str, markers: tuple[str, ...]) -> None:
    positions = [text.index(marker) for marker in markers]
    case.assertEqual(positions, sorted(positions), f"out of order: {markers}")


class PlanTemplateTest(unittest.TestCase):
    def test_both_language_variants_exist(self) -> None:
        self.assertTrue(BASE_TEMPLATE.is_file())
        self.assertTrue(EN_TEMPLATE.is_file())

    def test_sections_keep_the_same_order_in_both_languages(self) -> None:
        base = BASE_TEMPLATE.read_text(encoding="utf-8")
        english = EN_TEMPLATE.read_text(encoding="utf-8")
        for markers in (SECTION_MARKERS, HEADER_MARKERS, BRIEF_MARKERS):
            _assert_ordered(
                self, base, tuple(pair[0] for pair in markers.values())
            )
            _assert_ordered(
                self, english, tuple(pair[1] for pair in markers.values())
            )

    def test_every_variant_carries_the_machine_readable_goal_line(self) -> None:
        for path in (BASE_TEMPLATE, EN_TEMPLATE):
            text = path.read_text(encoding="utf-8")
            self.assertRegex(text, GOAL_LINE_RE, str(path))

    def test_variants_use_the_configured_language_only(self) -> None:
        base = BASE_TEMPLATE.read_text(encoding="utf-8")
        english = EN_TEMPLATE.read_text(encoding="utf-8")
        self.assertTrue(CJK_RE.search(base))
        self.assertIsNone(CJK_RE.search(english))

    def test_both_variants_keep_the_execution_rules(self) -> None:
        for path in (BASE_TEMPLATE, EN_TEMPLATE):
            text = path.read_text(encoding="utf-8")
            self.assertIn(".cowork-flow/run subagent init", text)
            self.assertIn("cowork_runtime_context_id", text)
            self.assertIn("cowork-implement", text)
            self.assertIn("cowork-check", text)


if __name__ == "__main__":
    unittest.main()
