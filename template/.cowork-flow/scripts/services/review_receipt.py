#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent review receipts for task completion.

A receipt is accepted only from a runtime context that was dispatched as a
cowork-check agent *and* bound to the task under review: whether an
independent check actually ran is a runtime binding fact, not a `by` field
anyone can type. Judgment about whether the review is any good stays with
review; the machine only decides provenance facts.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.workflow_runtime import RuntimeContextService

REVIEW_FILE = "review.jsonl"
SCHEMA_VERSION = 1
RESULTS = ("pass", "fail")
REQUIRED_SCOPE = "subagent"
REQUIRED_AGENT_TYPE = "cowork-check"
# A context that was never bound to a host session carries no evidence that a
# checker ran, so `pending` is refused along with every terminal status.
SUBMITTABLE_STATUSES = ("bound", "active")


class ReviewReceiptError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def submit_review_receipt(
    runtime_service: RuntimeContextService,
    task_dir: Path,
    *,
    context_id: str,
    result: str,
    findings: list[dict[str, Any]],
    changed_fingerprint: str,
) -> dict[str, Any]:
    """Append one review receipt for `task_dir`, or refuse with a reason."""
    if result not in RESULTS:
        raise ReviewReceiptError(
            "REVIEW-RECEIPT-006",
            f"result must be one of {', '.join(RESULTS)}; got {result!r}",
        )
    fingerprint = changed_fingerprint.strip() if isinstance(changed_fingerprint, str) else ""
    if not fingerprint:
        raise ReviewReceiptError(
            "REVIEW-RECEIPT-006",
            "changed fingerprint is required: the receipt must name the "
            "change set it reviewed",
        )
    if not isinstance(findings, list):
        raise ReviewReceiptError(
            "REVIEW-RECEIPT-006",
            "findings must be a list of objects",
        )

    context = runtime_service.load(context_id)
    if not context:
        raise ReviewReceiptError(
            "REVIEW-RECEIPT-001",
            f"no runtime context: {context_id}",
        )
    if context.get("scope") != REQUIRED_SCOPE:
        raise ReviewReceiptError(
            "REVIEW-RECEIPT-002",
            "only subagent runtime contexts can submit a review receipt",
        )
    if context.get("agent_type") != REQUIRED_AGENT_TYPE:
        raise ReviewReceiptError(
            "REVIEW-RECEIPT-003",
            f"only a {REQUIRED_AGENT_TYPE} context can submit a review "
            f"receipt; got {context.get('agent_type')!r}",
        )
    if not _bound_to_task(runtime_service.repo_root, context, task_dir):
        raise ReviewReceiptError(
            "REVIEW-RECEIPT-004",
            "runtime context is not bound to this task: "
            f"{context.get('task_dir')!r} != {_display(task_dir)}",
        )
    status = context.get("status")
    if status not in SUBMITTABLE_STATUSES:
        raise ReviewReceiptError(
            "REVIEW-RECEIPT-005",
            f"runtime context status {status!r} cannot submit a review "
            f"receipt; expected {'/'.join(SUBMITTABLE_STATUSES)}",
        )

    receipt = {
        "schemaVersion": SCHEMA_VERSION,
        "id": f"rr-{uuid.uuid4().hex[:12]}",
        "result": result,
        "findings": findings,
        "changedFingerprint": fingerprint,
        "submittedAt": _now(),
        "contextId": context.get("runtime_context_id") or context_id,
        "agentType": context.get("agent_type"),
    }
    path = Path(task_dir) / REVIEW_FILE
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    return receipt


def _bound_to_task(repo_root: Path, context: dict[str, Any], task_dir: Path) -> bool:
    """Whether the context's recorded task path is the task under review.

    The runtime context stores the path as it was dispatched (repo-relative
    for a host session, absolute for a direct call), so both sides are
    resolved before comparing.
    """
    recorded = context.get("task_dir")
    if not isinstance(recorded, str) or not recorded.strip():
        return False
    candidate = Path(recorded.strip())
    if not candidate.is_absolute():
        candidate = Path(repo_root) / candidate
    try:
        return candidate.resolve() == Path(task_dir).resolve()
    except OSError:
        return False


def _display(task_dir: Path) -> str:
    return str(task_dir)


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
