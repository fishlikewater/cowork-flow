from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from services import fact_view  # noqa: E402
from services.decision_anchor_schema import (  # noqa: E402
    ACCEPTANCE,
    ACCEPTANCE_RE,
    ASSUMPTIONS,
    GOAL,
    REJECTED,
    SCOPE,
    SPEC_CHECK_LABELS,
    VERIFICATION,
    acceptance_section_lines,
    canonical_section,
    heading_for,
    is_spec_check_line,
    is_spec_check_result_line,
    parse_decision_anchor,
    present_sections,
    section_headings,
    spec_check_example,
    spec_check_label,
    spec_check_placeholder,
    structural_lines,
    verification_section_lines,
)


ENGLISH_ANCHOR = "\n".join(
    [
        "# Decision Anchor",
        "",
        "## Goal",
        "Keep generated tasks readable.",
        "",
        "## Acceptance Criteria",
        "- [ ] AC-001: English headings parse",
        "- [x] AC-002: Mixed anchors parse",
        "",
        "## Rejected Options",
        "- **Option B**: rejected because it duplicates state",
        "",
        "## Key Assumptions",
        "- The project language is explicit.",
        "",
        "## Scope Boundary",
        "- In scope: parser and generator",
        "",
        "## Verification Commands",
        "- python -m pytest -q",
    ]
)

MIXED_ANCHOR = "\n".join(
    [
        "## Goal",
        "Mixed goal.",
        "",
        "## 验收标准",
        "- [ ] AC-001: Mixed acceptance row",
    ]
)


class DecisionAnchorSchemaTest(unittest.TestCase):
    def test_parse_decision_anchor_has_one_definition(self) -> None:
        self.assertIs(fact_view.parse_decision_anchor, parse_decision_anchor)

    def test_canonical_section_accepts_both_heading_sets(self) -> None:
        for heading, expected in (
            ("目标", GOAL),
            ("Goal", GOAL),
            ("验收标准", ACCEPTANCE),
            ("Acceptance Criteria", ACCEPTANCE),
            ("被拒方案", REJECTED),
            ("Rejected Options", REJECTED),
            ("关键假设", ASSUMPTIONS),
            ("Key Assumptions", ASSUMPTIONS),
            ("范围边界", SCOPE),
            ("Scope Boundary", SCOPE),
            ("验证命令", VERIFICATION),
            ("Verification Commands", VERIFICATION),
        ):
            with self.subTest(heading=heading):
                self.assertEqual(expected, canonical_section(heading))

    def test_unknown_heading_is_not_a_section(self) -> None:
        self.assertIsNone(canonical_section("概述"))
        self.assertIsNone(canonical_section("Overview"))

    def test_heading_for_uses_language_and_falls_back(self) -> None:
        self.assertEqual("目标", heading_for(GOAL, "zh-CN"))
        self.assertEqual("Goal", heading_for(GOAL, "en-US"))
        self.assertEqual("目标", heading_for(GOAL, "fr-FR"))
        self.assertEqual(
            ("目标", "Goal"),
            section_headings(GOAL),
        )
        self.assertEqual(
            ("验收标准", "Acceptance Criteria"),
            section_headings(ACCEPTANCE),
        )

    def test_present_sections_recognizes_english_and_mixed_anchors(self) -> None:
        self.assertEqual({GOAL, ACCEPTANCE}, present_sections(MIXED_ANCHOR))
        expected = {
            GOAL,
            ACCEPTANCE,
            REJECTED,
            ASSUMPTIONS,
            SCOPE,
            VERIFICATION,
        }
        self.assertEqual(expected, present_sections(ENGLISH_ANCHOR))

    def test_acceptance_lines_only_read_the_acceptance_section(self) -> None:
        lines = acceptance_section_lines(ENGLISH_ANCHOR)
        self.assertIn("- [ ] AC-001: English headings parse", lines)
        self.assertNotIn("- **Option B**: rejected because it duplicates state", lines)

    def test_parse_decision_anchor_reads_english_headings(self) -> None:
        parsed = parse_decision_anchor(ENGLISH_ANCHOR)
        self.assertEqual("Keep generated tasks readable.", parsed["goal"])
        self.assertEqual(2, len(parsed["acceptanceCriteria"]))
        self.assertEqual("AC-001", parsed["acceptanceCriteria"][0]["id"])
        self.assertTrue(parsed["acceptanceCriteria"][1]["checked"])
        self.assertEqual(["Option B"], parsed["rejectedOptions"])
        self.assertEqual(["python -m pytest -q"], parsed["validationCommands"])
        self.assertEqual("- In scope: parser and generator", parsed["scopeBoundary"])

    def test_parse_decision_anchor_reads_mixed_headings(self) -> None:
        parsed = parse_decision_anchor(MIXED_ANCHOR)
        self.assertEqual("Mixed goal.", parsed["goal"])
        self.assertEqual("AC-001", parsed["acceptanceCriteria"][0]["id"])

    def test_acceptance_regex_accepts_both_colons(self) -> None:
        self.assertIsNotNone(ACCEPTANCE_RE.match("- [ ] AC-001: ascii"))
        self.assertIsNotNone(ACCEPTANCE_RE.match("- [x] AC-002：full width"))

    def test_spec_check_labels_are_language_specific(self) -> None:
        self.assertEqual("规范核对：", spec_check_label("zh-CN"))
        self.assertEqual("Spec check:", spec_check_label("en-US"))
        self.assertEqual("规范核对：", spec_check_label("fr-FR"))
        self.assertEqual(
            {"zh-CN": "规范核对：", "en-US": "Spec check:"},
            SPEC_CHECK_LABELS,
        )

    def test_spec_check_result_accepts_filled_results(self) -> None:
        zh_line = (
            "- 规范核对：逐条核对 `.cowork-flow/spec/backend/` 适用规范 "
            "→ pass（理由：已核对）。"
        )
        en_line = (
            "- Spec check: clause-by-clause check against applicable "
            "`.cowork-flow/spec/backend/` rules -> not_applicable (reason: no rules)."
        )
        self.assertTrue(is_spec_check_line(zh_line, "zh-CN"))
        self.assertTrue(is_spec_check_result_line(zh_line, "zh-CN"))
        self.assertTrue(is_spec_check_result_line(en_line, "en-US"))
        self.assertFalse(is_spec_check_result_line(zh_line, "en-US"))

    def test_spec_check_placeholder_is_not_a_result(self) -> None:
        placeholder = spec_check_placeholder("zh-CN", "backend")
        self.assertTrue(is_spec_check_line(placeholder, "zh-CN"))
        self.assertFalse(is_spec_check_result_line(placeholder, "zh-CN"))
        self.assertFalse(
            is_spec_check_result_line(
                spec_check_placeholder("en-US", "backend"), "en-US"
            )
        )

    def test_spec_check_example_is_filled(self) -> None:
        example = spec_check_example("zh-CN", "backend")
        self.assertIn("backend", example)
        self.assertTrue(is_spec_check_result_line(example, "zh-CN"))
        self.assertTrue(
            is_spec_check_result_line(spec_check_example("en-US", "backend"), "en-US")
        )

    def test_spec_check_scope_matches_the_spec_dev_type_dispatch(self) -> None:
        for language in ("zh-CN", "en-US"):
            with self.subTest(language=language):
                for line in (
                    spec_check_placeholder(language, "spec"),
                    spec_check_example(language, "spec"),
                ):
                    self.assertIn("`.cowork-flow/spec/`", line)
                    self.assertNotIn("spec/spec/", line)

    def test_verification_section_lines_ignore_fenced_code(self) -> None:
        text = "\n".join(
            [
                "## 验证命令",
                "- `pytest -q` → pass",
                "```text",
                "- 规范核对：fenced result → pass",
                "```",
                "## 范围边界",
                "范围内。",
            ]
        )
        lines = verification_section_lines(text)
        self.assertIn("- `pytest -q` → pass", lines)
        self.assertNotIn("- 规范核对：fenced result → pass", lines)
        self.assertNotIn("范围内。", lines)

    def test_structural_lines_drops_fenced_content(self) -> None:
        text = "\n".join(
            [
                "# Title",
                "```markdown",
                "## 这不是实际标题",
                "```",
                "## 目标",
                "演示。",
            ]
        )
        self.assertEqual(
            ["# Title", "## 目标", "演示。"],
            structural_lines(text),
        )


if __name__ == "__main__":
    unittest.main()
