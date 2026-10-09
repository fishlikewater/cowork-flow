from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from services.lifecycle_checks import (  # noqa: E402
    LifecycleCheckRunner,
    compute_change_fingerprint,
)
from services.review_receipt import REVIEW_FILE  # noqa: E402


REVIEW_PREFIX = "LIFECYCLE-REVIEW-"


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


class ReviewReceiptGateTest(unittest.TestCase):
    """The completion gate over independent review receipts (strict tasks)."""

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name)
        _git(self.root, "init")
        _git(self.root, "config", "user.email", "gate@example.com")
        _git(self.root, "config", "user.name", "gate")
        (self.root / ".cowork-flow" / "tasks").mkdir(parents=True)
        (self.root / ".cowork-flow" / "plans").mkdir(parents=True)
        (self.root / "src.py").write_text("value = 1\n", encoding="utf-8")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-m", "baseline")
        self.baseline = _git(self.root, "rev-parse", "HEAD")

        self.plan = self.root / ".cowork-flow" / "plans" / "demo.md"
        self.plan.write_text("# 计划\n\n**目标:** 演示。\n", encoding="utf-8")
        self.task_dir = self.root / ".cowork-flow" / "tasks" / "demo-task"
        self._write_task(gate_profile="strict")

    # -- fixtures -------------------------------------------------------

    def _write_task(self, *, gate_profile: str | None) -> None:
        self.task_dir.mkdir(parents=True, exist_ok=True)
        meta: dict[str, str] = {"planFile": ".cowork-flow/plans/demo.md"}
        if gate_profile:
            meta["gateProfile"] = gate_profile
        (self.task_dir / "task.json").write_text(
            json.dumps(
                {
                    "id": "demo-task",
                    "status": "review",
                    "dev_type": "backend",
                    "meta": meta,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (self.task_dir / "decision-anchor.md").write_text(
            "# Decision Anchor\n\n"
            "## 目标\n"
            "演示完成复核门禁。\n\n"
            "## 验收标准\n"
            "- [ ] AC-001: 演示条款。\n",
            encoding="utf-8",
        )
        (self.task_dir / "implement.jsonl").write_text(
            json.dumps(
                {"file": "src.py", "reason": "演示", "type": "planned-file"},
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    def _record_receipt(
        self,
        *,
        result: str = "pass",
        fingerprint: str | None = None,
    ) -> None:
        receipt = {
            "schemaVersion": 1,
            "id": "rr-fixture",
            "result": result,
            "findings": [],
            "changedFingerprint": (
                compute_change_fingerprint(self.root, self.task_dir)
                if fingerprint is None
                else fingerprint
            ),
            "submittedAt": "2026-10-09T00:00:00Z",
            "contextId": "rtx_fixture",
            "agentType": "cowork-check",
        }
        with (self.task_dir / REVIEW_FILE).open(
            "a", encoding="utf-8", newline="\n"
        ) as handle:
            handle.write(json.dumps(receipt, ensure_ascii=False) + "\n")

    def _review_issues(self) -> list[str]:
        result = LifecycleCheckRunner(self.root).complete(self.task_dir)
        return [
            issue.code
            for issue in result.issues
            if issue.code.startswith(REVIEW_PREFIX)
        ]

    # -- tests ----------------------------------------------------------

    def test_strict_without_receipt_blocks_completion(self) -> None:
        self.assertEqual(["LIFECYCLE-REVIEW-001"], self._review_issues())

    def test_strict_failing_receipt_blocks_completion(self) -> None:
        self._record_receipt(result="fail")

        self.assertEqual(["LIFECYCLE-REVIEW-002"], self._review_issues())

    def test_strict_passing_receipt_allows_completion(self) -> None:
        self._record_receipt()

        self.assertEqual([], self._review_issues())

    def test_retry_pass_supersedes_an_earlier_failure(self) -> None:
        self._record_receipt(result="fail")
        self._record_receipt(result="pass")

        self.assertEqual([], self._review_issues())

    def test_later_failure_is_not_masked_by_an_earlier_pass(self) -> None:
        self._record_receipt(result="pass")
        self._record_receipt(result="fail")

        self.assertEqual(["LIFECYCLE-REVIEW-002"], self._review_issues())

    def test_code_change_after_review_makes_the_receipt_stale(self) -> None:
        self._record_receipt()
        (self.root / "src.py").write_text("value = 2\n", encoding="utf-8")

        self.assertEqual(["LIFECYCLE-REVIEW-003"], self._review_issues())

    def test_editing_an_already_changed_file_makes_the_receipt_stale(self) -> None:
        # The file is already inside the change set when the receipt is
        # recorded, so only the content digest can notice the second edit.
        (self.root / "src.py").write_text("value = 2\n", encoding="utf-8")
        self._record_receipt()
        (self.root / "src.py").write_text("value = 3\n", encoding="utf-8")

        self.assertEqual(["LIFECYCLE-REVIEW-003"], self._review_issues())

    def test_plan_change_after_review_makes_the_receipt_stale(self) -> None:
        self._record_receipt()
        self.plan.write_text("# 计划\n\n**目标:** 改了。\n", encoding="utf-8")

        self.assertEqual(["LIFECYCLE-REVIEW-003"], self._review_issues())

    def test_goal_change_after_review_makes_the_receipt_stale(self) -> None:
        self._record_receipt()
        (self.task_dir / "decision-anchor.md").write_text(
            "# Decision Anchor\n\n"
            "## 目标\n"
            "换了目标。\n\n"
            "## 验收标准\n"
            "- [ ] AC-001: 演示条款。\n",
            encoding="utf-8",
        )

        self.assertEqual(["LIFECYCLE-REVIEW-003"], self._review_issues())

    def test_ac_text_change_after_review_makes_the_receipt_stale(self) -> None:
        # Rewording what was accepted is a different judgment than ticking the
        # same criterion off, which must stay fingerprint-neutral.
        self._record_receipt()
        (self.task_dir / "decision-anchor.md").write_text(
            "# Decision Anchor\n\n"
            "## 目标\n"
            "演示完成复核门禁。\n\n"
            "## 验收标准\n"
            "- [ ] AC-001: 换了条款。\n",
            encoding="utf-8",
        )

        self.assertEqual(["LIFECYCLE-REVIEW-003"], self._review_issues())

    def test_spec_pointer_change_after_review_makes_the_receipt_stale(self) -> None:
        # The applicable-spec reading list is part of what the review judged,
        # and implement.jsonl is not itself a changed path, so only the spec
        # component can notice it.
        self._record_receipt()
        with (self.task_dir / "implement.jsonl").open(
            "a", encoding="utf-8", newline="\n"
        ) as handle:
            handle.write(
                json.dumps(
                    {
                        "file": ".cowork-flow/spec/backend/index.md",
                        "reason": "演示",
                        "type": "planned-file",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

        self.assertEqual(["LIFECYCLE-REVIEW-003"], self._review_issues())

    def test_dev_type_change_makes_the_receipt_stale(self) -> None:
        self._record_receipt()
        data = json.loads((self.task_dir / "task.json").read_text(encoding="utf-8"))
        data["dev_type"] = "frontend"
        (self.task_dir / "task.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )

        self.assertEqual(["LIFECYCLE-REVIEW-003"], self._review_issues())

    def test_evidence_append_does_not_invalidate_the_receipt(self) -> None:
        self._record_receipt()
        with (self.task_dir / "evidence.jsonl").open(
            "a", encoding="utf-8", newline="\n"
        ) as handle:
            handle.write(
                json.dumps(
                    {"ac": "AC-001", "kind": "test", "ref": "tests/demo.py"},
                    ensure_ascii=False,
                )
                + "\n"
            )

        self.assertEqual([], self._review_issues())

    def test_ac_tick_does_not_invalidate_the_receipt(self) -> None:
        self._record_receipt()
        anchor = (self.task_dir / "decision-anchor.md").read_text(encoding="utf-8")
        (self.task_dir / "decision-anchor.md").write_text(
            anchor.replace("- [ ] AC-001:", "- [x] AC-001:"), encoding="utf-8"
        )

        self.assertEqual([], self._review_issues())

    def test_runtime_metadata_change_does_not_invalidate_the_receipt(self) -> None:
        self._record_receipt()
        runtime = self.root / ".cowork-flow" / ".runtime" / "subagents"
        runtime.mkdir(parents=True)
        (runtime / "rtx_fixture.json").write_text("{}", encoding="utf-8")

        self.assertEqual([], self._review_issues())

    def test_receipt_is_found_after_the_task_moves_to_the_archive(self) -> None:
        self._record_receipt()
        archived = (
            self.root / ".cowork-flow" / "tasks" / "archive" / "2026-10" / "demo-task"
        )
        archived.parent.mkdir(parents=True)
        shutil.move(str(self.task_dir), str(archived))
        self.task_dir = archived

        self.assertEqual([], self._review_issues())

    def test_legacy_task_skips_the_review_gate(self) -> None:
        self._write_task(gate_profile=None)

        self.assertEqual([], self._review_issues())

    def test_legacy_task_is_not_blocked_by_a_failing_receipt(self) -> None:
        self._write_task(gate_profile=None)
        self._record_receipt(result="fail")

        self.assertEqual([], self._review_issues())


class SpecCheckFactTest(unittest.TestCase):
    """A spec-check executor that never ran must not read as "nothing to check"."""

    def _report(self) -> dict:
        from services.lifecycle_checks import _spec_check_report

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with mock.patch(
                "services.spec_check.run_checks",
                side_effect=RuntimeError("executor exploded"),
            ):
                return _spec_check_report(root)

    def test_executor_failure_is_classified_not_folded_into_unchecked(self) -> None:
        report = self._report()

        self.assertEqual("executor-failure", report["summary"]["classification"])
        self.assertEqual(1, report["summary"]["executorError"])

    def test_executor_failure_blocks_completion_even_with_allow_unchecked(self) -> None:
        from services.lifecycle_checks import _spec_check_completion_issues

        issues = _spec_check_completion_issues(
            self._report(),
            allow_unchecked_specs=True,
        )

        self.assertEqual(
            ["SPEC-CHECK-EXECUTOR-ERROR"], [issue.code for issue in issues]
        )

    def test_executor_failure_does_not_offer_the_exemption_flag(self) -> None:
        from services.lifecycle_checks import _spec_check_completion_issues

        issues = _spec_check_completion_issues(
            self._report(),
            allow_unchecked_specs=False,
        )

        # One precise blocker: the synthetic unchecked count is not a second
        # finding, and the message must not advertise the flag that would
        # wave the failure through as "nothing to check".
        self.assertEqual(
            ["SPEC-CHECK-EXECUTOR-ERROR"], [issue.code for issue in issues]
        )
        self.assertNotIn("--allow-unchecked", issues[0].message)

    def test_a_real_unchecked_command_stays_exemptible(self) -> None:
        from services.lifecycle_checks import _spec_check_completion_issues

        report = {
            "parseErrors": [],
            "results": [],
            "summary": {
                "pass": 0,
                "violation": 0,
                "unchecked": 1,
                "declarations": 1,
                "classification": "unchecked",
            },
        }

        self.assertEqual(
            [],
            _spec_check_completion_issues(report, allow_unchecked_specs=True),
        )
        self.assertEqual(
            ["SPEC-CHECK-UNCHECKED"],
            [
                issue.code
                for issue in _spec_check_completion_issues(
                    report, allow_unchecked_specs=False
                )
            ],
        )

    def test_executor_failure_yields_no_recorded_exemption(self) -> None:
        from services.lifecycle_checks import _spec_check_exemption

        self.assertIsNone(
            _spec_check_exemption(self._report(), allow_unchecked_specs=True)
        )


if __name__ == "__main__":
    unittest.main()
