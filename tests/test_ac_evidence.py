from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = (
    Path(__file__).resolve().parents[1]
    / "template"
    / ".cowork-flow"
    / "scripts"
)
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


ANCHOR_WITH_ACS = """# Decision Anchor

## 目标
消除静默失效面。

## 验收标准
- [ ] AC-001: 解析器捕获勾选状态
- [x] AC-002: 证据可追加读取
- [X] AC-003: 大写勾选同样识别

## 被拒方案
- **方案B**: 不做解析 — 拒绝原因: 机器无从校验

## 验证命令
- `python3 -m pytest -q` → exit 0
"""

ANCHOR_WITHOUT_ACS = """# Decision Anchor

## 目标
没有验收标准章节的锚点。
"""


def ac_evidence():
    return importlib.import_module("services.ac_evidence")


class AcceptanceParsingTest(unittest.TestCase):
    """The anchor parser is the single AC source; it must expose check state."""

    def test_parse_captures_checked_state(self) -> None:
        fact_view = importlib.import_module("services.fact_view")
        parsed = fact_view.parse_decision_anchor(ANCHOR_WITH_ACS)
        criteria = parsed["acceptanceCriteria"]
        self.assertEqual(
            ["AC-001", "AC-002", "AC-003"],
            [item["id"] for item in criteria],
        )
        self.assertEqual(
            [False, True, True],
            [item["checked"] for item in criteria],
        )
        # id/text remain the contract keys for existing consumers
        self.assertEqual("AC-001", criteria[0]["id"])
        self.assertIn("勾选状态", criteria[0]["text"])

    def test_parse_row_without_checkbox_is_unchecked(self) -> None:
        fact_view = importlib.import_module("services.fact_view")
        parsed = fact_view.parse_decision_anchor(
            "## 验收标准\n- AC-009: 无勾选框的旧格式行\n"
        )
        criteria = parsed["acceptanceCriteria"]
        self.assertEqual(1, len(criteria))
        self.assertEqual("AC-009", criteria[0]["id"])
        self.assertFalse(criteria[0]["checked"])

    def test_parse_section_without_rows_yields_empty(self) -> None:
        fact_view = importlib.import_module("services.fact_view")
        parsed = fact_view.parse_decision_anchor(ANCHOR_WITHOUT_ACS)
        self.assertEqual([], parsed["acceptanceCriteria"])


class EvidenceReadingTest(unittest.TestCase):
    def test_read_evidence_missing_file_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual([], ac_evidence().read_evidence(Path(tmp)))

    def test_read_evidence_skips_bad_lines_and_malformed_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            (task_dir / "evidence.jsonl").write_text(
                "\n"
                "not json at all\n"
                + json.dumps({"ac": "AC-001"}) + "\n"  # no ref/kind
                + json.dumps({"ac": "AC-001", "ref": "x", "kind": "vibes"}) + "\n"  # bad kind
                + json.dumps(
                    {
                        "ac": "AC-001",
                        "kind": "test",
                        "ref": "tests/test_x.py::test_y",
                        "note": "核心断言一句话",
                        "recordedAt": "2026-10-06",
                        "by": "cwf-cli-1004",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            records = ac_evidence().read_evidence(task_dir)
        self.assertEqual(1, len(records))
        self.assertEqual("AC-001", records[0]["ac"])
        self.assertEqual("test", records[0]["kind"])

    def test_read_evidence_tolerates_invalid_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            (task_dir / "evidence.jsonl").write_bytes(b"\xff\xfe\x00bad")
            self.assertEqual([], ac_evidence().read_evidence(task_dir))


class EvidenceCoverageTest(unittest.TestCase):
    def test_coverage_counts_and_lists_missing(self) -> None:
        module = ac_evidence()
        acceptance = [
            {"id": "AC-001", "text": "a", "checked": True},
            {"id": "AC-002", "text": "b", "checked": True},
            {"id": "AC-003", "text": "c", "checked": False},
        ]
        evidence = [
            {"ac": "AC-001", "kind": "test", "ref": "t::x"},
            {"ac": "AC-999", "kind": "manual", "ref": "n/a"},
        ]
        coverage = module.evidence_coverage(acceptance, evidence)
        self.assertEqual(3, coverage["total"])
        self.assertEqual(1, coverage["withEvidence"])
        self.assertEqual(["AC-002", "AC-003"], coverage["missing"])

    def test_coverage_summary_none_without_acceptance_criteria(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            (task_dir / "decision-anchor.md").write_text(
                ANCHOR_WITHOUT_ACS, encoding="utf-8"
            )
            self.assertIsNone(ac_evidence().coverage_summary(task_dir))

    def test_coverage_summary_none_without_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(ac_evidence().coverage_summary(Path(tmp)))

    def test_coverage_summary_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            (task_dir / "decision-anchor.md").write_text(
                ANCHOR_WITH_ACS, encoding="utf-8"
            )
            (task_dir / "evidence.jsonl").write_text(
                json.dumps({"ac": "AC-002", "kind": "test", "ref": "t::y"}) + "\n",
                encoding="utf-8",
            )
            coverage = ac_evidence().coverage_summary(task_dir)
        self.assertEqual(
            {"total": 3, "withEvidence": 1, "missing": ["AC-001", "AC-003"]},
            coverage,
        )


if __name__ == "__main__":
    unittest.main()
