"""Tests for the quality gate kernel (Phase 1).

Covers:
- GateResult construction
- load_quality_evidence (valid, missing, invalid)
- validate_tdd_evidence (every work_type path)
- validate_completion_evidence (green, standards, check)
- command family helpers
"""

from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"


class QualityGateTest(unittest.TestCase):
    """Tests that only need the quality_gate module (no flow store)."""

    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPTS))
        cls.qg = importlib.import_module("common.quality_gate")

    @classmethod
    def tearDownClass(cls) -> None:
        sys.path.remove(str(SCRIPTS))
        for name in ("common.quality_gate", "common"):
            sys.modules.pop(name, None)

    # -- helpers ----------------------------------------------------------

    def _write_quality(self, task_dir: Path, data: dict) -> None:
        path = task_dir / "quality.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def _make_task_dir(self) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="qg_test_"))
        self.addCleanup(self._rmtree, tmp)
        return tmp

    @staticmethod
    def _rmtree(path: Path) -> None:
        import shutil

        shutil.rmtree(path, ignore_errors=True)

    # -- GateResult -------------------------------------------------------

    def test_gate_result_ok_with_empty_lists(self) -> None:
        r = self.qg.GateResult(ok=True)
        self.assertTrue(r.ok)
        self.assertEqual([], r.errors)
        self.assertEqual([], r.warnings)

    def test_gate_result_not_ok_with_errors(self) -> None:
        r = self.qg.GateResult(ok=False, errors=["missing red"], warnings=["tip"])
        self.assertFalse(r.ok)
        self.assertEqual(["missing red"], r.errors)
        self.assertEqual(["tip"], r.warnings)

    # -- load_quality_evidence --------------------------------------------

    def test_load_returns_empty_when_file_missing(self) -> None:
        d = self._make_task_dir()
        self.assertEqual({}, self.qg.load_quality_evidence(d))

    def test_load_returns_parsed_json(self) -> None:
        d = self._make_task_dir()
        self._write_quality(d, {"workType": "bugfix"})
        self.assertEqual({"workType": "bugfix"}, self.qg.load_quality_evidence(d))

    def test_load_returns_empty_on_invalid_json(self) -> None:
        d = self._make_task_dir()
        (d / "quality.json").write_text("{not valid", encoding="utf-8")
        self.assertEqual({}, self.qg.load_quality_evidence(d))

    # -- validate_tdd_evidence: behavior_change ---------------------------

    def test_behavior_change_fails_without_test_plan(self) -> None:
        d = self._make_task_dir()
        self._write_quality(d, {"workType": "behavior_change"})
        result = self.qg.validate_tdd_evidence(d)
        self.assertFalse(result.ok)
        self.assertTrue(any("testPlan" in e for e in result.errors))

    def test_behavior_change_fails_with_empty_test_plan(self) -> None:
        d = self._make_task_dir()
        self._write_quality(d, {"workType": "behavior_change", "testPlan": []})
        result = self.qg.validate_tdd_evidence(d)
        self.assertFalse(result.ok)
        self.assertTrue(any("testPlan" in e for e in result.errors))

    def test_behavior_change_fails_without_red_evidence(self) -> None:
        d = self._make_task_dir()
        self._write_quality(
            d,
            {
                "workType": "behavior_change",
                "testPlan": [
                    {
                        "acceptancePoint": "x",
                        "testCommand": "pytest",
                        "breaksWhen": "assertion fails",
                    }
                ],
            },
        )
        result = self.qg.validate_tdd_evidence(d)
        self.assertFalse(result.ok)
        self.assertTrue(any("red" in e for e in result.errors))

    def test_behavior_change_fails_when_red_exit_code_zero(self) -> None:
        d = self._make_task_dir()
        self._write_quality(
            d,
            {
                "workType": "behavior_change",
                "testPlan": [
                    {
                        "acceptancePoint": "x",
                        "testCommand": "pytest",
                        "breaksWhen": "assertion fails",
                    }
                ],
                "red": {"command": "pytest -q", "exitCode": 0},
            },
        )
        result = self.qg.validate_tdd_evidence(d)
        self.assertFalse(result.ok)
        self.assertTrue(any("exitCode is 0" in e for e in result.errors))

    def test_behavior_change_passes_with_valid_red_evidence(self) -> None:
        d = self._make_task_dir()
        self._write_quality(
            d,
            {
                "workType": "behavior_change",
                "testPlan": [
                    {
                        "acceptancePoint": "create returns valid ID",
                        "testCommand": "pytest tests/test_task.py::test_create",
                        "breaksWhen": "returns None or empty string",
                    }
                ],
                "red": {
                    "command": "pytest tests/test_task.py::test_create -q",
                    "exitCode": 1,
                    "failingTests": ["test_create"],
                    "outputExcerpt": "FAILED test_create",
                },
            },
        )
        result = self.qg.validate_tdd_evidence(d)
        self.assertTrue(result.ok, f"expected ok, got errors: {result.errors}")

    def test_missing_work_type_defaults_to_behavior_change(self) -> None:
        d = self._make_task_dir()
        self._write_quality(d, {})
        result = self.qg.validate_tdd_evidence(d)
        self.assertFalse(result.ok)
        self.assertTrue(any("testPlan" in e for e in result.errors))

    # -- validate_tdd_evidence: bugfix ------------------------------------

    def test_bugfix_fails_without_red_evidence(self) -> None:
        d = self._make_task_dir()
        self._write_quality(
            d,
            {
                "workType": "bugfix",
                "testPlan": [
                    {
                        "acceptancePoint": "null pointer fixed",
                        "testCommand": "pytest tests/::test_null",
                        "breaksWhen": "NullPointerError",
                    }
                ],
            },
        )
        result = self.qg.validate_tdd_evidence(d)
        self.assertFalse(result.ok)
        self.assertTrue(any("red" in e for e in result.errors))

    # -- validate_tdd_evidence: refactor ----------------------------------

    def test_refactor_fails_without_test_plan(self) -> None:
        d = self._make_task_dir()
        self._write_quality(d, {"workType": "refactor_no_behavior_change"})
        result = self.qg.validate_tdd_evidence(d)
        self.assertFalse(result.ok)
        self.assertTrue(any("testPlan" in e for e in result.errors))

    def test_refactor_passes_with_test_plan(self) -> None:
        d = self._make_task_dir()
        self._write_quality(
            d,
            {
                "workType": "refactor_no_behavior_change",
                "testPlan": [
                    {
                        "acceptancePoint": "existing behavior preserved",
                        "testCommand": "pytest tests/test_legacy.py",
                        "breaksWhen": "existing tests regress",
                    }
                ],
            },
        )
        result = self.qg.validate_tdd_evidence(d)
        self.assertTrue(result.ok, f"expected ok, got errors: {result.errors}")

    # -- validate_tdd_evidence: docs_chore ---------------------------------

    def test_docs_chore_passes_without_tdd(self) -> None:
        d = self._make_task_dir()
        self._write_quality(d, {"workType": "docs_chore"})
        result = self.qg.validate_tdd_evidence(d)
        self.assertTrue(result.ok)

    def test_docs_chore_warns_when_check_evidence_missing(self) -> None:
        d = self._make_task_dir()
        self._write_quality(d, {"workType": "docs_chore"})
        result = self.qg.validate_tdd_evidence(d)
        self.assertTrue(result.ok)
        self.assertTrue(any("check" in w for w in result.warnings))

    # -- validate_tdd_evidence: unknown work_type -------------------------

    def test_unknown_work_type_returns_error(self) -> None:
        d = self._make_task_dir()
        self._write_quality(d, {"workType": "garbage"})
        result = self.qg.validate_tdd_evidence(d)
        self.assertFalse(result.ok)
        self.assertTrue(any("Unknown workType" in e for e in result.errors))

    # -- validate_completion_evidence: green ------------------------------

    def test_completion_fails_missing_green_for_behavior_change(self) -> None:
        d = self._make_task_dir()
        self._write_quality(
            d,
            {
                "workType": "behavior_change",
                "testPlan": [
                    {
                        "acceptancePoint": "x",
                        "testCommand": "pytest",
                        "breaksWhen": "fails",
                    }
                ],
                "red": {"command": "pytest -q", "exitCode": 1},
                "standards": {
                    "encodingScan": {"ok": True},
                    "bomScan": {"ok": True},
                    "whitespaceCheck": {"ok": True},
                    "shallowTestScan": {"ok": True},
                },
                "check": {"reviewerMode": "code-review", "commands": [], "specSync": "no-changes", "scopeReview": "matched"},
            },
        )
        result = self.qg.validate_completion_evidence(d)
        self.assertFalse(result.ok)
        self.assertTrue(any("green" in e for e in result.errors))

    def test_completion_fails_green_exit_not_zero(self) -> None:
        d = self._make_task_dir()
        self._write_quality(
            d,
            {
                "workType": "behavior_change",
                "testPlan": [
                    {
                        "acceptancePoint": "x",
                        "testCommand": "pytest",
                        "breaksWhen": "fails",
                    }
                ],
                "red": {"command": "pytest -q", "exitCode": 1},
                "green": {"command": "pytest -q", "exitCode": 1},
                "standards": {
                    "encodingScan": {"ok": True},
                    "bomScan": {"ok": True},
                    "whitespaceCheck": {"ok": True},
                    "shallowTestScan": {"ok": True},
                },
                "check": {"reviewerMode": "code-review", "commands": [], "specSync": "no-changes", "scopeReview": "matched"},
            },
        )
        result = self.qg.validate_completion_evidence(d)
        self.assertFalse(result.ok)
        self.assertTrue(any("exitCode" in e for e in result.errors))

    def test_completion_fails_green_command_mismatch(self) -> None:
        d = self._make_task_dir()
        self._write_quality(
            d,
            {
                "workType": "behavior_change",
                "testPlan": [
                    {
                        "acceptancePoint": "x",
                        "testCommand": "pytest",
                        "breaksWhen": "fails",
                    }
                ],
                "red": {"command": "pytest tests/test_a.py -q", "exitCode": 1},
                "green": {"command": "pytest tests/test_b.py -q", "exitCode": 0},
                "standards": {
                    "encodingScan": {"ok": True},
                    "bomScan": {"ok": True},
                    "whitespaceCheck": {"ok": True},
                    "shallowTestScan": {"ok": True},
                },
                "check": {"reviewerMode": "code-review", "commands": [], "specSync": "no-changes", "scopeReview": "matched"},
            },
        )
        result = self.qg.validate_completion_evidence(d)
        self.assertFalse(result.ok)
        self.assertTrue(any("command family" in e for e in result.errors))

    def test_completion_passes_with_matching_red_green(self) -> None:
        d = self._make_task_dir()
        self._write_quality(
            d,
            {
                "workType": "behavior_change",
                "testPlan": [
                    {
                        "acceptancePoint": "x",
                        "testCommand": "pytest tests/test_x.py",
                        "breaksWhen": "fails",
                    }
                ],
                "red": {"command": "pytest tests/test_x.py -q", "exitCode": 1},
                "green": {"command": "pytest tests/test_x.py -v", "exitCode": 0},
                "standards": {
                    "encodingScan": {"ok": True},
                    "bomScan": {"ok": True},
                    "whitespaceCheck": {"ok": True},
                    "shallowTestScan": {"ok": True},
                },
                "check": {"reviewerMode": "code-review", "commands": [], "specSync": "no-changes", "scopeReview": "matched"},
            },
        )
        result = self.qg.validate_completion_evidence(d)
        self.assertTrue(result.ok, f"expected ok, got errors: {result.errors}")

    # -- validate_completion_evidence: standards (real scanner) -----------

    def test_completion_passes_empty_task_dir_standards(self) -> None:
        """Empty task dir scans clean — gate passes with auto-scan."""
        d = self._make_task_dir()
        self._write_quality(
            d,
            {
                "workType": "docs_chore",
                "check": {"reviewerMode": "code-review", "commands": [], "specSync": "no-changes", "scopeReview": "matched"},
            },
        )
        result = self.qg.validate_completion_evidence(d)
        self.assertTrue(result.ok, f"expected ok, got errors: {result.errors}")

    def test_completion_fails_real_bom_file(self) -> None:
        """Task dir with a BOM file → completion fails."""
        d = self._make_task_dir()
        (d / "bad.py").write_bytes(b"\xef\xbb\xbf# coding: utf-8\nx=1\n")
        self._write_quality(
            d,
            {
                "workType": "docs_chore",
                "check": {"reviewerMode": "code-review", "commands": [], "specSync": "no-changes", "scopeReview": "matched"},
            },
        )
        result = self.qg.validate_completion_evidence(d)
        self.assertFalse(result.ok)
        self.assertTrue(any("bomScan" in e for e in result.errors))

    def test_completion_fails_real_encoding_violation(self) -> None:
        """Task dir with missing encoding → completion fails."""
        d = self._make_task_dir()
        (d / "reader.py").write_text(
            "from pathlib import Path\ndef read():\n    return Path('x.txt').read_text()\n",
            encoding="utf-8")
        self._write_quality(
            d,
            {
                "workType": "docs_chore",
                "check": {"reviewerMode": "code-review", "commands": [], "specSync": "no-changes", "scopeReview": "matched"},
            },
        )
        result = self.qg.validate_completion_evidence(d)
        self.assertFalse(result.ok)
        self.assertTrue(any("encodingScan" in e for e in result.errors))

    def test_completion_fails_claimed_vs_real_mismatch(self) -> None:
        """When quality.json claims ok=false but real scan passes → mismatch error."""
        d = self._make_task_dir()
        self._write_quality(
            d,
            {
                "workType": "docs_chore",
                "standards": {
                    "encodingScan": {"ok": True},
                    "bomScan": {"ok": False, "violations": ["claimed BOM"]},
                    "whitespaceCheck": {"ok": True},
                    "shallowTestScan": {"ok": True},
                },
                "check": {"reviewerMode": "code-review", "commands": [], "specSync": "no-changes", "scopeReview": "matched"},
            },
        )
        result = self.qg.validate_completion_evidence(d)
        self.assertFalse(result.ok)
        self.assertTrue(any("claimed" in e for e in result.errors))

    # -- validate_completion_evidence: failed scan (old test repurposed) ---

    def test_completion_fails_failed_standards_scan(self) -> None:
        d = self._make_task_dir()
        (d / "bad.md").write_bytes(b"\xef\xbb\xbf# Title\n")
        self._write_quality(
            d,
            {
                "workType": "docs_chore",
                "standards": {
                    "encodingScan": {"ok": True},
                    "bomScan": {"ok": False, "violations": ["file.py has BOM"]},
                    "whitespaceCheck": {"ok": True},
                    "shallowTestScan": {"ok": True},
                },
                "check": {"reviewerMode": "code-review", "commands": [], "specSync": "no-changes", "scopeReview": "matched"},
            },
        )
        result = self.qg.validate_completion_evidence(d)
        self.assertFalse(result.ok)
        self.assertTrue(any("bomScan" in e for e in result.errors))

    # -- validate_completion_evidence: refactor ---------------------------

    def test_completion_passes_refactor_with_valid_evidence(self) -> None:
        """refactor_no_behavior_change completion passes with green + standards + check."""
        d = self._make_task_dir()
        self._write_quality(
            d,
            {
                "workType": "refactor_no_behavior_change",
                "testPlan": [
                    {
                        "acceptancePoint": "behavior unchanged",
                        "testCommand": "pytest tests/test_x.py",
                        "breaksWhen": "existing test fails",
                    }
                ],
                "green": {"command": "pytest tests/test_x.py -q", "exitCode": 0},
                "standards": {
                    "encodingScan": {"ok": True},
                    "bomScan": {"ok": True},
                    "whitespaceCheck": {"ok": True},
                    "shallowTestScan": {"ok": True},
                },
                "check": {"reviewerMode": "code-review", "commands": [], "specSync": "no-changes", "scopeReview": "matched"},
            },
        )
        result = self.qg.validate_completion_evidence(d)
        self.assertTrue(result.ok, f"expected ok, got errors: {result.errors}")

    def test_completion_fails_refactor_without_green(self) -> None:
        """refactor_no_behavior_change completion fails without green evidence."""
        d = self._make_task_dir()
        self._write_quality(
            d,
            {
                "workType": "refactor_no_behavior_change",
                "testPlan": [
                    {
                        "acceptancePoint": "x",
                        "testCommand": "pytest",
                        "breaksWhen": "fails",
                    }
                ],
                "standards": {
                    "encodingScan": {"ok": True},
                    "bomScan": {"ok": True},
                    "whitespaceCheck": {"ok": True},
                    "shallowTestScan": {"ok": True},
                },
                "check": {"reviewerMode": "code-review", "commands": [], "specSync": "no-changes", "scopeReview": "matched"},
            },
        )
        result = self.qg.validate_completion_evidence(d)
        self.assertFalse(result.ok)
        self.assertTrue(any("green" in e for e in result.errors))

    # -- validate_completion_evidence: bugfix -----------------------------

    def test_completion_passes_bugfix_with_valid_evidence(self) -> None:
        """bugfix completion passes with green + standards + check + red command match."""
        d = self._make_task_dir()
        self._write_quality(
            d,
            {
                "workType": "bugfix",
                "testPlan": [
                    {
                        "acceptancePoint": "null pointer fixed",
                        "testCommand": "pytest tests/test_fix.py -q",
                        "breaksWhen": "NullPointerError",
                    }
                ],
                "red": {"command": "pytest tests/test_fix.py -q", "exitCode": 1},
                "green": {"command": "pytest tests/test_fix.py -q", "exitCode": 0},
                "standards": {
                    "encodingScan": {"ok": True},
                    "bomScan": {"ok": True},
                    "whitespaceCheck": {"ok": True},
                    "shallowTestScan": {"ok": True},
                },
                "check": {"reviewerMode": "code-review", "commands": [], "specSync": "no-changes", "scopeReview": "matched"},
            },
        )
        result = self.qg.validate_completion_evidence(d)
        self.assertTrue(result.ok, f"expected ok, got errors: {result.errors}")

    def test_completion_fails_bugfix_without_green(self) -> None:
        """bugfix completion fails without green evidence."""
        d = self._make_task_dir()
        self._write_quality(
            d,
            {
                "workType": "bugfix",
                "testPlan": [
                    {
                        "acceptancePoint": "x",
                        "testCommand": "pytest",
                        "breaksWhen": "fails",
                    }
                ],
                "red": {"command": "pytest -q", "exitCode": 1},
                "standards": {
                    "encodingScan": {"ok": True},
                    "bomScan": {"ok": True},
                    "whitespaceCheck": {"ok": True},
                    "shallowTestScan": {"ok": True},
                },
                "check": {"reviewerMode": "code-review", "commands": [], "specSync": "no-changes", "scopeReview": "matched"},
            },
        )
        result = self.qg.validate_completion_evidence(d)
        self.assertFalse(result.ok)
        self.assertTrue(any("green" in e for e in result.errors))

    def test_completion_fails_missing_check_evidence(self) -> None:
        d = self._make_task_dir()
        self._write_quality(
            d,
            {
                "workType": "docs_chore",
                "standards": {
                    "encodingScan": {"ok": True},
                    "bomScan": {"ok": True},
                    "whitespaceCheck": {"ok": True},
                    "shallowTestScan": {"ok": True},
                },
            },
        )
        result = self.qg.validate_completion_evidence(d)
        self.assertFalse(result.ok)
        self.assertTrue(any("check" in e for e in result.errors))

    # -- command family helpers ------------------------------------------

    def test_same_family_ignores_verbosity_flags(self) -> None:
        self.assertTrue(
            self.qg._same_command_family(
                "pytest tests/test_x.py -q",
                "pytest tests/test_x.py -v",
            )
        )

    def test_same_family_ignores_tb_flags(self) -> None:
        self.assertTrue(
            self.qg._same_command_family(
                "pytest tests/test_x.py --tb=short",
                "pytest tests/test_x.py --tb=long",
            )
        )

    def test_same_family_different_targets_not_equal(self) -> None:
        self.assertFalse(
            self.qg._same_command_family(
                "pytest tests/test_a.py",
                "pytest tests/test_b.py",
            )
        )

    def test_command_base_strips_verbosity_flags(self) -> None:
        base = self.qg._command_base("pytest tests/test_x.py -q -x --tb=short -vv")
        self.assertEqual("pytest tests/test_x.py", base)

    def test_command_base_keeps_target_files(self) -> None:
        base = self.qg._command_base(
            "pytest tests/test_a.py tests/test_b.py -q --color=no"
        )
        self.assertEqual("pytest tests/test_a.py tests/test_b.py", base)

    # -- testPlan entry validation ---------------------------------------

    def test_test_plan_entry_missing_field_rejected(self) -> None:
        d = self._make_task_dir()
        self._write_quality(
            d,
            {
                "workType": "behavior_change",
                "testPlan": [
                    {"acceptancePoint": "x", "testCommand": "pytest"}
                    # missing breaksWhen
                ],
            },
        )
        result = self.qg.validate_tdd_evidence(d)
        self.assertFalse(result.ok)
        self.assertTrue(any("breaksWhen" in e for e in result.errors))

    def test_test_plan_non_dict_entry_rejected(self) -> None:
        d = self._make_task_dir()
        self._write_quality(
            d,
            {
                "workType": "behavior_change",
                "testPlan": ["not an object"],
            },
        )
        result = self.qg.validate_tdd_evidence(d)
        self.assertFalse(result.ok)
        self.assertTrue(any("testPlan[0]" in e for e in result.errors))

    # -- red evidence missing fields --------------------------------------

    def test_red_evidence_missing_command_rejected(self) -> None:
        d = self._make_task_dir()
        self._write_quality(
            d,
            {
                "workType": "behavior_change",
                "testPlan": [
                    {
                        "acceptancePoint": "x",
                        "testCommand": "pytest",
                        "breaksWhen": "fails",
                    }
                ],
                "red": {"exitCode": 1},
            },
        )
        result = self.qg.validate_tdd_evidence(d)
        self.assertFalse(result.ok)
        self.assertTrue(any("command" in e for e in result.errors))

    def test_red_evidence_not_dict_rejected(self) -> None:
        d = self._make_task_dir()
        self._write_quality(
            d,
            {
                "workType": "behavior_change",
                "testPlan": [
                    {
                        "acceptancePoint": "x",
                        "testCommand": "pytest",
                        "breaksWhen": "fails",
                    }
                ],
                "red": "not an object",
            },
        )
        result = self.qg.validate_tdd_evidence(d)
        self.assertFalse(result.ok)
        self.assertTrue(any("red" in e for e in result.errors))


if __name__ == "__main__":
    unittest.main()
