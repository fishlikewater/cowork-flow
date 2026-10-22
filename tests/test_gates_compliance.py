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
from services.workflow_runtime import RuntimeContextService  # noqa: E402


REVIEW_PREFIX = "LIFECYCLE-REVIEW-"
CHECKER_CONTEXT_ID = "rtx_gate_fixture"


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


class _StrictTaskFixture(unittest.TestCase):
    """A strict task in a real checkout, with a real bound checker context.

    A review receipt is only evidence when the runtime context it names
    exists and was bound to this task, so the fixture records one instead of
    naming a context that was never dispatched.
    """

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name)
        _git(self.root, "init")
        _git(self.root, "config", "user.email", "gate@example.com")
        _git(self.root, "config", "user.name", "gate")
        # A real checkout ignores .cowork-flow/, so the bound plan never shows
        # up in the change set. Without this the fixture would let the plan
        # test pass through the changed-path digest and leave the plan digest
        # itself unguarded.
        (self.root / ".gitignore").write_text("/.cowork-flow/\n", encoding="utf-8")
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

    def _ensure_checker_context(self) -> str:
        """A real bound cowork-check context for this task.

        A receipt is only evidence when the context it names exists in the
        runtime store and was bound to this task, so the fixture must record
        one instead of naming a context that was never dispatched.
        """
        existing = getattr(self, "_checker_context_id", None)
        if existing:
            return existing
        service = RuntimeContextService(self.root)
        service.initialize(
            CHECKER_CONTEXT_ID,
            {
                "schema_version": 2,
                "runtime_context_id": CHECKER_CONTEXT_ID,
                "scope": "subagent",
                "agent_type": "cowork-check",
                "task_dir": str(self.task_dir),
                "status": "pending",
                "dispatch_kind": "formal",
            },
        )
        service.bind(CHECKER_CONTEXT_ID, "zcode_gate_session")
        self._checker_context_id = CHECKER_CONTEXT_ID
        return CHECKER_CONTEXT_ID

    def _add_implement_entry(self, file_path: str) -> None:
        """Declare one more file in the task's scope index."""
        with (self.task_dir / "implement.jsonl").open(
            "a", encoding="utf-8", newline="\n"
        ) as handle:
            handle.write(
                json.dumps(
                    {"file": file_path, "reason": "演示", "type": "planned-file"},
                    ensure_ascii=False,
                )
                + "\n"
            )

    def _record_receipt(
        self,
        *,
        result: str = "pass",
        fingerprint: str | None = None,
        context_id: str | None = None,
    ) -> None:
        named_context = context_id or self._ensure_checker_context()
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
            "contextId": named_context,
            "agentType": "cowork-check",
            "bindingEvidence": "declared",
        }
        with (self.task_dir / REVIEW_FILE).open(
            "a", encoding="utf-8", newline="\n"
        ) as handle:
            handle.write(json.dumps(receipt, ensure_ascii=False) + "\n")

    def _make_light(self) -> None:
        """Declare the light profile the way the creation entry does."""
        data = json.loads(
            (self.task_dir / "task.json").read_text(encoding="utf-8")
        )
        data.setdefault("meta", {})["taskType"] = "tiny"
        (self.task_dir / "task.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )

    def _clear_acceptance(self) -> None:
        """Rewrite the anchor so `## 验收标准` declares no AC row."""
        (self.task_dir / "decision-anchor.md").write_text(
            "# Decision Anchor\n\n## 目标\n演示。\n\n## 验收标准\n",
            encoding="utf-8",
        )

    def _review_issues(self) -> list[str]:
        result = LifecycleCheckRunner(self.root).complete(self.task_dir)
        return [
            issue.code
            for issue in result.issues
            if issue.code.startswith(REVIEW_PREFIX)
        ]

    def _ac_issues(self, **kwargs: object) -> list[str]:
        result = LifecycleCheckRunner(self.root).complete(self.task_dir, **kwargs)
        return [
            issue.code
            for issue in result.issues
            if issue.code.startswith("LIFECYCLE-AC-")
        ]


class ReviewReceiptGateTest(_StrictTaskFixture):
    """The completion gate over independent review receipts (strict tasks)."""

    # -- tests ----------------------------------------------------------

    def test_strict_without_receipt_blocks_completion(self) -> None:
        self.assertEqual(["LIFECYCLE-REVIEW-001"], self._review_issues())

    def test_strict_failing_receipt_blocks_completion(self) -> None:
        self._record_receipt(result="fail")

        self.assertEqual(["LIFECYCLE-REVIEW-002"], self._review_issues())

    def test_strict_passing_receipt_allows_completion(self) -> None:
        self._record_receipt()

        self.assertEqual([], self._review_issues())

    def test_receipt_without_a_runtime_context_blocks_completion(self) -> None:
        # The receipt names a context that was never dispatched: appending a
        # JSON line is not evidence that a checker ran.
        self._record_receipt(context_id="rtx_never_dispatched")

        self.assertEqual(["LIFECYCLE-REVIEW-004"], self._review_issues())

    def test_receipt_from_a_checker_closed_after_review_allows_completion(
        self,
    ) -> None:
        # A finished checker closes its context; the receipt it recorded
        # before closing must stay valid (AC-004).
        self._record_receipt()
        RuntimeContextService(self.root).close(CHECKER_CONTEXT_ID)

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

    def test_spec_body_change_after_review_makes_the_receipt_stale(self) -> None:
        """The referenced spec's *body* is review input, not just its name.

        `.cowork-flow/spec/**` is gitignored, so the change set can never see
        it; only the spec content digest can notice a rewritten requirement.
        """
        spec = self.root / ".cowork-flow" / "spec" / "backend" / "demo.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text("原文要求。\n", encoding="utf-8")
        self._add_implement_entry(".cowork-flow/spec/backend/demo.md")
        self._record_receipt()

        spec.write_text("换了要求。\n", encoding="utf-8")

        self.assertEqual(["LIFECYCLE-REVIEW-003"], self._review_issues())

    def test_implement_scope_change_after_review_makes_the_receipt_stale(
        self,
    ) -> None:
        """A declared non-spec file moves the scope, and nothing else can see it.

        implement.jsonl lives under `.cowork-flow/tasks/**`, which the change
        set excludes, and a plain source path is not a spec pointer — so the
        scope digest is the only component that can report this.
        """
        self._record_receipt()

        self._add_implement_entry("src/extra.py")

        self.assertEqual(["LIFECYCLE-REVIEW-003"], self._review_issues())

    def test_closeout_metadata_keeps_the_receipt_valid(self) -> None:
        """Completing a task must not invalidate the receipt it just checked.

        Ticking an AC, appending evidence, and writing runtime metadata all
        happen around the completion gate; if any of them moved the
        fingerprint the gate would demand a fresh review forever.
        """
        self._record_receipt()
        anchor = (self.task_dir / "decision-anchor.md").read_text(encoding="utf-8")
        (self.task_dir / "decision-anchor.md").write_text(
            anchor.replace("- [ ] AC-001:", "- [x] AC-001:"), encoding="utf-8"
        )
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
        runtime = self.root / ".cowork-flow" / ".runtime" / "subagents"
        runtime.mkdir(parents=True, exist_ok=True)
        (runtime / "rtx_fixture.json").write_text("{}", encoding="utf-8")

        self.assertEqual([], self._review_issues())

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

    def test_runtime_metadata_is_excluded_even_when_git_can_see_it(self) -> None:
        """The path filter, not .gitignore, is what keeps runtime metadata out.

        A checkout that does not ignore .cowork-flow/ would otherwise put the
        task's own artifacts into the change set, and then recording evidence
        or ticking an AC would invalidate the receipt it belongs to.
        """
        (self.root / ".gitignore").unlink()
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
        runtime = self.root / ".cowork-flow" / ".runtime" / "subagents"
        runtime.mkdir(parents=True, exist_ok=True)
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

        # The receipt travels with the task directory, so the gate reads it
        # there instead of reporting a missing review (that would be 001).
        # Its runtime context, however, was bound to the pre-archive path, so
        # the binding check reports that separately.
        self.assertEqual(["LIFECYCLE-REVIEW-004"], self._review_issues())

    def test_legacy_task_skips_the_review_gate(self) -> None:
        self._write_task(gate_profile=None)

        self.assertEqual([], self._review_issues())

    def test_legacy_task_is_not_blocked_by_a_failing_receipt(self) -> None:
        self._write_task(gate_profile=None)
        self._record_receipt(result="fail")

        self.assertEqual([], self._review_issues())


class AcceptanceCompletionGateTest(_StrictTaskFixture):
    """The completion gate over acceptance criteria (strict vs legacy)."""

    def test_strict_task_with_cleared_acceptance_criteria_blocks_completion(
        self,
    ) -> None:
        self._clear_acceptance()
        self._record_receipt()

        self.assertEqual(["LIFECYCLE-AC-003"], self._ac_issues())

    def test_evidence_module_failure_blocks_completion(self) -> None:
        self._record_receipt()

        with mock.patch.dict(sys.modules, {"services.ac_evidence": None}):
            result = LifecycleCheckRunner(self.root).complete(self.task_dir)

        issues = {
            issue.code: issue.message
            for issue in result.issues
            if issue.code.startswith("LIFECYCLE-AC-")
        }
        self.assertEqual(["LIFECYCLE-AC-004"], list(issues))
        # The reason must survive into the message, or the operator cannot
        # tell a broken runtime copy from a missing declaration.
        self.assertIn("services.ac_evidence", issues["LIFECYCLE-AC-004"])

    def test_legacy_task_without_acceptance_criteria_completes(self) -> None:
        self._write_task(gate_profile=None)
        self._clear_acceptance()

        self.assertEqual([], self._ac_issues())

    def test_legacy_task_still_reports_a_checked_ac_without_evidence(self) -> None:
        """The compat path waives the new blockers, not the gate itself.

        Without this control the two legacy cases above would also pass if
        the whole gate stopped running, so they could not tell "exempt" from
        "never evaluated".
        """
        self._write_task(gate_profile=None)
        (self.task_dir / "decision-anchor.md").write_text(
            "# Decision Anchor\n\n## 目标\n演示。\n\n## 验收标准\n"
            "- [x] AC-001: 演示条款。\n",
            encoding="utf-8",
        )

        self.assertEqual(["LIFECYCLE-AC-002"], self._ac_issues())

    def test_legacy_task_survives_an_unreadable_evidence_module(self) -> None:
        self._write_task(gate_profile=None)

        with mock.patch.dict(sys.modules, {"services.ac_evidence": None}):
            self.assertEqual([], self._ac_issues())

    def test_allow_missing_evidence_does_not_exempt_empty_acceptance(self) -> None:
        self._clear_acceptance()
        self._record_receipt()

        self.assertEqual(
            ["LIFECYCLE-AC-003"],
            self._ac_issues(allow_missing_evidence=True),
        )

    def test_allow_missing_evidence_does_not_exempt_a_broken_module(self) -> None:
        self._record_receipt()

        with mock.patch.dict(sys.modules, {"services.ac_evidence": None}):
            self.assertEqual(
                ["LIFECYCLE-AC-004"],
                self._ac_issues(allow_missing_evidence=True),
            )


class LightTaskGateTest(_StrictTaskFixture):
    """The light profile waives three gates and nothing else."""

    def test_the_tiny_marker_is_what_flips_the_receipt_gate(self) -> None:
        """Same fixture twice: the marker, not the fixture, is the switch."""
        self.assertEqual(["LIFECYCLE-REVIEW-001"], self._review_issues())

        self._make_light()

        self.assertEqual([], self._review_issues())

    def test_light_task_completes_without_evidence_or_a_checked_ac(self) -> None:
        # The fixture anchor is unticked and evidence.jsonl is absent: a
        # non-light strict task cannot complete like this.
        self._make_light()

        self.assertEqual([], self._ac_issues())

    def test_light_task_still_requires_acceptance_rows(self) -> None:
        self._make_light()
        self._clear_acceptance()

        self.assertEqual(["LIFECYCLE-AC-003"], self._ac_issues())

    def test_light_task_still_blocks_on_a_broken_evidence_module(self) -> None:
        self._make_light()

        with mock.patch.dict(sys.modules, {"services.ac_evidence": None}):
            self.assertEqual(["LIFECYCLE-AC-004"], self._ac_issues())

    def test_light_task_still_blocks_on_unplanned_changed_files(self) -> None:
        """The light profile narrows the reading list, not the scope gate."""
        self._make_light()
        (self.root / "unplanned.py").write_text("value = 1\n", encoding="utf-8")

        result = LifecycleCheckRunner(self.root).complete(self.task_dir)

        self.assertTrue(
            any(
                "unplanned" in (issue.path or "") or "unplanned" in issue.message
                for issue in result.issues
            ),
            [f"{issue.code}: {issue.path}" for issue in result.issues],
        )


class _FakeCheckResult:
    def __init__(self, *, evidence_exemption=None) -> None:
        self.evidence_exemption = evidence_exemption


class ExemptionMetaPayloadTest(unittest.TestCase):
    """One builder for what is persisted, so the printed copy cannot drift."""

    def test_payloads_carry_the_flag_and_the_actor(self) -> None:
        from services.lifecycle_checks import exemption_meta_payloads

        payloads = exemption_meta_payloads(
            _FakeCheckResult(
                evidence_exemption={
                    "missing": ["AC-002"],
                    # Sentinel flag: the builder must pass the gate's own
                    # value through, so a re-hardcoded constant here would
                    # silently satisfy a test that used the real one.
                    "flag": "--sentinel-evidence-flag",
                },
            ),
            executor="zcode_sess_demo",
        )

        self.assertEqual(
            {
                "evidenceExempt": {
                    "flag": "--sentinel-evidence-flag",
                    "by": "zcode_sess_demo",
                    "missing": ["AC-002"],
                },
            },
            payloads,
        )

    def test_an_unresolved_actor_is_recorded_as_null(self) -> None:
        """No stand-in identity: an unknown actor is unknown."""
        from services.lifecycle_checks import exemption_meta_payloads

        payloads = exemption_meta_payloads(
            _FakeCheckResult(
                evidence_exemption={
                    "missing": ["AC-001"],
                    "flag": "--allow-missing-evidence",
                }
            ),
            executor=None,
        )

        self.assertIsNone(payloads["evidenceExempt"]["by"])
        self.assertEqual(["AC-001"], payloads["evidenceExempt"]["missing"])

    def test_no_exemption_yields_no_payload(self) -> None:
        from services.lifecycle_checks import exemption_meta_payloads

        self.assertEqual(
            {}, exemption_meta_payloads(_FakeCheckResult(), executor="x")
        )


class EnglishAcceptanceGateTest(unittest.TestCase):
    def test_english_acceptance_heading_parses_ac_rows(self) -> None:
        from services.task_gate_profiles import acceptance_row_blockers

        anchor = (
            "## Goal\n\nDemo.\n\n"
            "## Acceptance Criteria\n\n"
            "- [ ] AC-001: first\n"
            "- [x] AC-002: second\n"
        )
        self.assertEqual([], acceptance_row_blockers(anchor))

    def test_english_acceptance_heading_without_rows_blocks(self) -> None:
        from services.task_gate_profiles import acceptance_row_blockers

        blockers = acceptance_row_blockers(
            "## Goal\n\nDemo.\n\n## Acceptance Criteria\n\nNo rows.\n"
        )
        self.assertTrue(
            any("declares no acceptance criterion" in item for item in blockers),
            blockers,
        )

    def test_mixed_heading_sets_still_find_acceptance_rows(self) -> None:
        from services.task_gate_profiles import acceptance_row_blockers

        anchor = "## Goal\n\nDemo.\n\n## 验收标准\n\n- [ ] AC-001: row\n"
        self.assertEqual([], acceptance_row_blockers(anchor))

    def test_english_acceptance_heading_flags_non_ac_list_rows(self) -> None:
        from services.task_gate_profiles import acceptance_row_blockers

        blockers = acceptance_row_blockers(
            "## Acceptance Criteria\n\n- [ ] AC-001: row\n- not an AC row\n"
        )
        self.assertTrue(
            any("not AC rows" in item for item in blockers),
            blockers,
        )


if __name__ == "__main__":
    unittest.main()
