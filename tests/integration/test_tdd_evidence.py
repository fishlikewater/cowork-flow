#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration tests for TDD evidence module (tdd.jsonl + quality.json fallback)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

for p in [
    str(ROOT / ".cowork-flow" / "scripts"),
    str(ROOT / "template" / ".cowork-flow" / "scripts"),
]:
    if p not in sys.path:
        sys.path.insert(0, p)

from common.tdd_evidence import (
    TddEvidence,
    TddRecord,
    load_tdd_evidence,
    write_tdd_record,
)


class TestTddJsonlFormat(unittest.TestCase):
    """Tests for tdd.jsonl reading and writing."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="tdd_test_"))
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_load_valid_jsonl(self):
        lines = [
            json.dumps({
                "acceptanceId": "AC-001",
                "testFile": "tests/test_foo.py",
                "testName": "test_bar",
                "redCommand": "pytest tests/test_foo.py::test_bar -q",
                "redExitCode": 1,
                "failureReason": "assertion failure",
                "whyThisTestMatters": "proves bar() works",
                "greenCommand": "pytest tests/test_foo.py::test_bar -q",
                "greenExitCode": 0,
            }),
        ]
        (self.tmp / "tdd.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        evidence = load_tdd_evidence(self.tmp)
        self.assertEqual(evidence.source, "tdd.jsonl")
        self.assertEqual(len(evidence.records), 1)
        self.assertTrue(evidence.has_red_evidence)
        self.assertTrue(evidence.has_green_evidence)
        self.assertTrue(evidence.is_complete)

    def test_load_quality_json_fallback(self):
        data = {
            "workType": "behavior_change",
            "testPlan": [
                {
                    "acceptancePoint": "Feature works",
                    "testCommand": "pytest tests/test_x.py::test_y -q",
                    "breaksWhen": "assertion failure",
                }
            ],
            "red": {"command": "pytest tests/test_x.py::test_y -q", "exitCode": 1},
            "green": {"command": "pytest tests/test_x.py::test_y -q", "exitCode": 0},
        }
        (self.tmp / "quality.json").write_text(json.dumps(data), encoding="utf-8")
        evidence = load_tdd_evidence(self.tmp)
        self.assertEqual(evidence.source, "quality.json")
        self.assertGreater(len(evidence.records), 0)

    def test_docs_chore_exempt(self):
        data = {
            "workType": "docs_chore",
            "testPlan": [],
            "red": {},
            "green": {},
        }
        (self.tmp / "quality.json").write_text(json.dumps(data), encoding="utf-8")
        evidence = load_tdd_evidence(self.tmp)
        self.assertTrue(all(r.exempt for r in evidence.records))

    def test_red_exit_code_zero_error(self):
        lines = [
            json.dumps({
                "acceptanceId": "AC-001",
                "testFile": "tests/test.py",
                "testName": "test_it",
                "redCommand": "pytest tests/test.py -q",
                "redExitCode": 0,
                "failureReason": "should fail but passed",
                "whyThisTestMatters": "test",
            }),
        ]
        (self.tmp / "tdd.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        evidence = load_tdd_evidence(self.tmp)
        self.assertTrue(len(evidence.errors) > 0)

    def test_green_exit_code_nonzero_error(self):
        lines = [
            json.dumps({
                "acceptanceId": "AC-001",
                "testFile": "tests/test.py",
                "testName": "test_it",
                "redCommand": "pytest tests/test.py -q",
                "redExitCode": 1,
                "failureReason": "assertion fails",
                "whyThisTestMatters": "proves behavior",
                "greenCommand": "pytest tests/test.py -q",
                "greenExitCode": 1,
            }),
        ]
        (self.tmp / "tdd.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        evidence = load_tdd_evidence(self.tmp)
        self.assertTrue(len(evidence.errors) > 0)

    def test_write_tdd_record(self):
        record = TddRecord(
            acceptance_id="AC-999",
            test_file="tests/test_z.py",
            test_name="test_new",
            red_command="pytest tests/test_z.py -q",
            red_exit_code=1,
            failure_reason="new feature not yet implemented",
            why_this_test_matters="proves new feature",
        )
        write_tdd_record(self.tmp, record)
        evidence = load_tdd_evidence(self.tmp)
        self.assertEqual(len(evidence.records), 1)
        self.assertEqual(evidence.records[0].acceptance_id, "AC-999")

    def test_exemption_record(self):
        lines = [
            json.dumps({
                "exempt": True,
                "acceptanceId": "N/A",
                "exemptReason": "docs_chore workType does not require TDD",
            }),
        ]
        (self.tmp / "tdd.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        evidence = load_tdd_evidence(self.tmp)
        self.assertEqual(len(evidence.records), 1)
        self.assertTrue(evidence.records[0].exempt)

    def test_missing_file_returns_empty(self):
        """No tdd.jsonl or quality.json → empty evidence."""
        evidence = load_tdd_evidence(self.tmp)
        self.assertEqual(evidence.records, [])
        self.assertEqual(evidence.source, "")


class TestTddRecordModel(unittest.TestCase):
    """Tests for TddRecord dataclass."""

    def test_create_minimal(self):
        r = TddRecord(acceptance_id="AC-001", test_file="", test_name="test_x")
        self.assertEqual(r.acceptance_id, "AC-001")
        self.assertFalse(r.exempt)

    def test_create_exempt(self):
        r = TddRecord(
            acceptance_id="N/A", test_file="", test_name="",
            exempt=True, exempt_reason="docs only",
        )
        self.assertTrue(r.exempt)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
