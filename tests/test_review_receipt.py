from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from services.review_receipt import (  # noqa: E402
    REVIEW_FILE,
    ReviewReceiptError,
    submit_review_receipt,
)
from services.workflow_runtime import RuntimeContextService  # noqa: E402


CONTEXT_ID = "rtx_review_receipt_test"


def _context(task_dir: Path, **overrides) -> dict:
    context = {
        "schema_version": 2,
        "runtime_context_id": CONTEXT_ID,
        "scope": "subagent",
        "host": "codex",
        "adapter": "codex",
        "agent_type": "cowork-check",
        "role": "cowork-check",
        "task_dir": str(task_dir),
        "status": "pending",
        "dispatch_kind": "formal",
    }
    context.update(overrides)
    return context


class ReviewReceiptTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name)
        (self.root / ".cowork-flow").mkdir()
        self.task_dir = self.root / ".cowork-flow" / "tasks" / "demo-task"
        self.task_dir.mkdir(parents=True)
        self.service = RuntimeContextService(self.root)

    def _bound_checker(self, **overrides) -> None:
        recorded = overrides.pop("task_dir", str(self.task_dir))
        self.service.initialize(CONTEXT_ID, _context(recorded, **overrides))
        self.service.bind(CONTEXT_ID, "codex_test_session")

    def _submit(self, **overrides) -> dict:
        kwargs = {
            "context_id": CONTEXT_ID,
            "result": "pass",
            "findings": [{"clause": "AC-002", "command": "pytest -q"}],
            "changed_fingerprint": "abc123",
        }
        kwargs.update(overrides)
        return submit_review_receipt(self.service, self.task_dir, **kwargs)

    def _refusal(self, **overrides) -> ReviewReceiptError:
        with self.assertRaises(ReviewReceiptError) as caught:
            self._submit(**overrides)
        return caught.exception

    def test_submit_passes_for_bound_cowork_check(self) -> None:
        self._bound_checker()

        receipt = self._submit()

        self.assertEqual("pass", receipt["result"])
        self.assertEqual(CONTEXT_ID, receipt["contextId"])
        self.assertEqual("cowork-check", receipt["agentType"])
        self.assertEqual("abc123", receipt["changedFingerprint"])

    def test_receipt_recorded_in_review_jsonl(self) -> None:
        self._bound_checker()

        self._submit(result="fail")
        self._submit(result="pass")

        lines = [
            line
            for line in (self.task_dir / REVIEW_FILE).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        records = [json.loads(line) for line in lines]
        self.assertEqual(["fail", "pass"], [record["result"] for record in records])
        self.assertEqual(1, records[0]["schemaVersion"])
        self.assertTrue(records[0]["id"].startswith("rr-"))
        self.assertNotEqual(records[0]["id"], records[1]["id"])

    def test_submit_rejects_unknown_context(self) -> None:
        error = self._refusal()

        self.assertEqual("REVIEW-RECEIPT-001", error.code)

    def test_submit_rejects_main_session(self) -> None:
        self._bound_checker(scope="session")

        error = self._refusal()

        self.assertEqual("REVIEW-RECEIPT-002", error.code)

    def test_submit_rejects_implement_agent(self) -> None:
        self._bound_checker(agent_type="cowork-implement")

        error = self._refusal()

        self.assertEqual("REVIEW-RECEIPT-003", error.code)

    def test_submit_rejects_wrong_task(self) -> None:
        other = self.root / ".cowork-flow" / "tasks" / "other-task"
        other.mkdir(parents=True)
        self._bound_checker(task_dir=str(other))

        error = self._refusal()

        self.assertEqual("REVIEW-RECEIPT-004", error.code)

    def test_submit_rejects_unbound_context(self) -> None:
        self.service.initialize(CONTEXT_ID, _context(self.task_dir))

        error = self._refusal()

        self.assertEqual("REVIEW-RECEIPT-005", error.code)

    def test_submit_rejects_closed_context(self) -> None:
        self._bound_checker()
        self.service.close(CONTEXT_ID)

        error = self._refusal()

        self.assertEqual("REVIEW-RECEIPT-005", error.code)

    def test_submit_accepts_repo_relative_task_dir(self) -> None:
        relative = self.task_dir.relative_to(self.root).as_posix()
        self._bound_checker(task_dir=relative)

        receipt = self._submit()

        self.assertEqual("pass", receipt["result"])

    def test_submit_rejects_invalid_payload(self) -> None:
        self._bound_checker()

        self.assertEqual("REVIEW-RECEIPT-006", self._refusal(result="maybe").code)
        self.assertEqual(
            "REVIEW-RECEIPT-006",
            self._refusal(changed_fingerprint="   ").code,
        )
        self.assertEqual(
            "REVIEW-RECEIPT-006",
            self._refusal(findings="not-a-list").code,
        )

    def test_nothing_is_written_when_a_receipt_is_refused(self) -> None:
        self._bound_checker(agent_type="cowork-implement")

        self._refusal()

        self.assertFalse((self.task_dir / REVIEW_FILE).exists())


if __name__ == "__main__":
    unittest.main()
