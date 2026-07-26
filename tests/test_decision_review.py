#!/usr/bin/env python3
"""Regression coverage for structured L2 decision review evidence."""

from __future__ import annotations

import importlib
import json
import tempfile
from pathlib import Path

from tests.flow_test_support import FlowScriptTestCase


ROOT = Path(__file__).resolve().parents[1]


class DecisionReviewReadinessTest(FlowScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.readiness = importlib.import_module("common.task.readiness")

    def _ready_task(self, root: Path) -> Path:
        task_dir = root / ".cowork-flow" / "tasks" / "05-19-parent"
        self._write_ready_task_files(root, task_dir)
        return task_dir

    def _write_decision_review(
        self,
        task_dir: Path,
        *,
        resolution: str = "accepted",
        record: dict[str, object] | None = None,
    ) -> None:
        evidence = record if record is not None else {
            "acceptanceId": "AC-007A",
            "claim": "L2 work requires structured decision review evidence.",
            "contract": "Missing or invalid evidence blocks start_task action.",
            "reviewerContext": "fresh",
            "findings": [],
            "resolution": resolution,
        }
        (task_dir / "decision-review.jsonl").write_text(
            json.dumps(evidence, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _blockers(self, root: Path, task_dir: Path, *, level: str = "L2") -> list[str]:
        self._write_l2_change_fixture(
            root,
            level=level,
            task_link=".cowork-flow/tasks/05-19-parent",
        )
        return self.readiness.task_readiness_blockers(root, task_dir)

    def test_l2_missing_decision_review_blocks_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._ready_task(root)
            (task_dir / "decision-review.jsonl").unlink()

            blockers = self._blockers(root, task_dir)

        self.assertTrue(
            any(
                "decision-review.jsonl is missing or empty" in blocker
                for blocker in blockers
            ),
            blockers,
        )

    def test_l2_invalid_decision_review_blocks_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._ready_task(root)
            self._write_decision_review(task_dir, record={})

            blockers = self._blockers(root, task_dir)

        self.assertTrue(
            any(
                "decision review line 1" in blocker
                and "missing required fields" in blocker
                for blocker in blockers
            ),
            blockers,
        )

    def test_l2_unaccepted_decision_review_blocks_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._ready_task(root)
            self._write_decision_review(task_dir, resolution="rejected")

            blockers = self._blockers(root, task_dir)

        self.assertTrue(
            any(
                "decision review line 1" in blocker
                and "resolution must be accepted" in blocker
                for blocker in blockers
            ),
            blockers,
        )

    def test_l2_valid_decision_review_allows_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._ready_task(root)
            self._write_decision_review(task_dir)

            blockers = self._blockers(root, task_dir)

        self.assertEqual([], blockers)

    def test_l0_and_l1_do_not_require_decision_review(self) -> None:
        for level in ("L0", "L1"):
            with self.subTest(level=level), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                task_dir = self._ready_task(root)
                (task_dir / "decision-review.jsonl").unlink()

                blockers = self._blockers(root, task_dir, level=level)

            self.assertEqual([], blockers)

    def test_rule_skill_and_definition_of_done_are_consistent(self) -> None:
        rules = json.loads(
            (
                ROOT
                / "template"
                / ".cowork-flow"
                / "spec"
                / "runtime"
                / "rules.json"
            ).read_text(encoding="utf-8")
        )
        definition_of_done = (
            ROOT
            / "template"
            / ".cowork-flow"
            / "spec"
            / "references"
            / "definition-of-done.md"
        ).read_text(encoding="utf-8")

        decision_rule = next(
            rule for rule in rules["rules"] if rule["id"] == "R-WF-006"
        )

        self.assertTrue((ROOT / "template" / "skills" / "decision-audit" / "SKILL.md").is_file())
        self.assertEqual("block", decision_rule["severity"])
        self.assertEqual("task_start", decision_rule["scope"])
        self.assertEqual(
            ".agents/skills/decision-audit/SKILL.md",
            decision_rule["source_file"],
        )
        self.assertEqual(
            "decision-review.jsonl",
            decision_rule["parameters"]["filename"],
        )
        self.assertIn("decision-review.jsonl", definition_of_done)
        self.assertNotIn("doubt-review.md", definition_of_done)
        self.assertNotIn("update-spec", definition_of_done)

    def test_decision_review_skill_preserves_adversarial_doubt_cycle(self) -> None:
        skill = (
            ROOT
            / "template"
            / "skills"
            / "decision-audit"
            / "SKILL.md"
        ).read_text(encoding="utf-8")

        markers = (
            "CLAIM",
            "EXTRACT",
            "DOUBT",
            "RECONCILE",
            "STOP",
            "ARTIFACT + CONTRACT",
            "not CLAIM",
            "reviewerContext",
            "decision-review.jsonl",
        )
        missing = [marker for marker in markers if marker not in skill]

        self.assertEqual([], missing)


if __name__ == "__main__":
    import unittest

    unittest.main()
