from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from services.plan_schema import plan_template_blockers  # noqa: E402


def zh_plan(**overrides: str) -> str:
    sections = {
        "title": "# 演示实施计划",
        "goal": "## 目标\n\n演示。",
        "acceptance": "## 验收标准\n\n- AC-001: 演示。",
        "constraints": "## 全局约束\n\n- 不扩大范围。",
        "files": "## 文件边界\n\n- `src/demo.py`",
        "tasks": "## 任务\n\n### 任务 1：演示",
        "verification": (
            "## 最终验证\n\n"
            "规范核对：逐条核对 `.cowork-flow/spec/backend/` 适用规范 "
            "→ pass（理由：已核对）。"
        ),
    }
    sections.update(overrides)
    return "\n\n".join(sections.values()) + "\n"


def en_plan(**overrides: str) -> str:
    sections = {
        "title": "# Demo Implementation Plan",
        "goal": "## Goal\n\nDemo.",
        "acceptance": "## Acceptance Criteria\n\n- AC-001: Demo.",
        "constraints": "## Global Constraints\n\n- Do not expand scope.",
        "files": "## File Boundaries\n\n- `src/demo.py`",
        "tasks": "## Tasks\n\n### Task 1: Demo",
        "verification": (
            "## Final Verification\n\n"
            "Spec check: clause-by-clause check against applicable "
            "`.cowork-flow/spec/backend/` rules -> pass (reason: checked)."
        ),
    }
    sections.update(overrides)
    return "\n\n".join(sections.values()) + "\n"


class PlanTemplateBlockersTest(unittest.TestCase):
    def test_valid_chinese_plan_passes(self) -> None:
        self.assertEqual([], plan_template_blockers(zh_plan(), "zh-CN"))

    def test_valid_english_plan_passes(self) -> None:
        self.assertEqual([], plan_template_blockers(en_plan(), "en-US"))

    def test_english_template_in_chinese_project_blocks(self) -> None:
        blockers = plan_template_blockers(en_plan(), "zh-CN")
        self.assertTrue(
            any("en-US" in blocker and "## Goal" in blocker for blocker in blockers),
            blockers,
        )
        self.assertTrue(any("## 目标" in blocker for blocker in blockers), blockers)

    def test_chinese_template_in_english_project_blocks(self) -> None:
        blockers = plan_template_blockers(zh_plan(), "en-US")
        self.assertTrue(
            any("zh-CN" in blocker and "## 目标" in blocker for blocker in blockers),
            blockers,
        )

    def test_missing_title_marker_blocks(self) -> None:
        blockers = plan_template_blockers(
            zh_plan(title="# 演示计划"), "zh-CN"
        )
        self.assertTrue(any("实施计划" in blocker for blocker in blockers), blockers)

    def test_missing_section_blocks(self) -> None:
        text = zh_plan(tasks="## 任务清单\n\n### 任务 1：演示")
        blockers = plan_template_blockers(text, "zh-CN")
        self.assertTrue(any("## 任务" in blocker for blocker in blockers), blockers)

    def test_out_of_order_sections_block(self) -> None:
        text = zh_plan(
            constraints="## 全局约束\n\n- 不扩大范围。",
            files="## 文件边界\n\n- `src/demo.py`",
        ).replace(
            "## 全局约束\n\n- 不扩大范围。\n\n## 文件边界\n\n- `src/demo.py`",
            "## 文件边界\n\n- `src/demo.py`\n\n## 全局约束\n\n- 不扩大范围。",
        )
        blockers = plan_template_blockers(text, "zh-CN")
        self.assertTrue(any("order" in blocker.lower() for blocker in blockers), blockers)

    def test_task_prefix_mismatch_blocks(self) -> None:
        blockers = plan_template_blockers(
            zh_plan(tasks="## 任务\n\n### Task 1: Demo"), "zh-CN"
        )
        self.assertTrue(any("### 任务" in blocker for blocker in blockers), blockers)

    def test_english_task_prefix_in_english_plan_passes(self) -> None:
        self.assertEqual([], plan_template_blockers(en_plan(), "en-US"))

    def test_placeholder_result_blocks(self) -> None:
        placeholders = (
            "## 最终验证\n\n"
            "规范核对：逐条核对 `.cowork-flow/spec/backend/` 适用规范 "
            "→ <pass / not_applicable + 理由>。"
        )
        blockers = plan_template_blockers(
            zh_plan(verification=placeholders), "zh-CN"
        )
        self.assertTrue(
            any("spec-check" in blocker or "规范核对" in blocker for blocker in blockers),
            blockers,
        )

    def test_not_applicable_result_passes(self) -> None:
        verification = (
            "## 最终验证\n\n"
            "规范核对：逐条核对 `.cowork-flow/spec/backend/` 适用规范 "
            "→ not_applicable（理由：无适用规范）。"
        )
        self.assertEqual(
            [],
            plan_template_blockers(zh_plan(verification=verification), "zh-CN"),
        )

    def test_result_inside_code_fence_does_not_satisfy_gate(self) -> None:
        verification = (
            "## 最终验证\n\n"
            "```text\n"
            "规范核对：逐条核对 `.cowork-flow/spec/backend/` 适用规范 → pass\n"
            "```"
        )
        blockers = plan_template_blockers(
            zh_plan(verification=verification), "zh-CN"
        )
        self.assertTrue(any("spec-check" in blocker for blocker in blockers), blockers)

    def test_fenced_example_with_other_language_is_ignored(self) -> None:
        text = zh_plan().replace(
            "## 任务\n\n### 任务 1：演示",
            "```markdown\n## Goal\n## Tasks\n### Task 1: Demo\n```\n\n"
            "## 任务\n\n### 任务 1：演示",
        )
        self.assertEqual([], plan_template_blockers(text, "zh-CN"))

    def test_extra_sections_are_allowed(self) -> None:
        text = zh_plan().replace(
            "## 文件边界\n\n- `src/demo.py`",
            "## 文件边界\n\n- `src/demo.py`\n\n## 补充说明\n\n额外内容。",
        )
        self.assertEqual([], plan_template_blockers(text, "zh-CN"))

    def test_empty_plan_blocks(self) -> None:
        self.assertTrue(plan_template_blockers("", "zh-CN"))


if __name__ == "__main__":
    unittest.main()
