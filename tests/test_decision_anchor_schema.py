from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from services.decision_anchor_schema import (  # noqa: E402
    ACCEPTANCE,
    ACCEPTANCE_RE,
    ASSUMPTIONS,
    GOAL,
    REJECTED,
    SCOPE,
    VERIFICATION,
    acceptance_section_lines,
    canonical_section,
    heading_for,
    present_sections,
    section_headings,
)
from services.fact_view import parse_decision_anchor  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
