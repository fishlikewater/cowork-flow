#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Acceptance-criteria evidence facts for task completion.

Single read entry for the completion gate, the fact view, and injection:
which AC ids the decision anchor declares, which are checked, and which
have at least one evidence record in the task's evidence.jsonl. Judgment
about whether a record really proves an AC stays with review; the machine
only decides existence facts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.fact_view import parse_decision_anchor

EVIDENCE_FILE = "evidence.jsonl"
EVIDENCE_KINDS = ("test", "command", "manual")


def read_decision_anchor(task_dir: Path) -> str | None:
    path = Path(task_dir) / "decision-anchor.md"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return text or None


def load_acceptance_criteria(task_dir: Path) -> list[dict[str, Any]]:
    """AC rows (id / text / checked) declared by the task's decision anchor.

    Empty list when the anchor is missing or declares no AC rows — the
    compatibility path that keeps pre-existing tasks exempt from the gate."""
    text = read_decision_anchor(task_dir)
    if not text:
        return []
    return list(parse_decision_anchor(text)["acceptanceCriteria"])


def read_evidence(task_dir: Path) -> list[dict[str, Any]]:
    """Valid evidence records appended by the implementer.

    Bad lines and malformed records are skipped, never fatal: the gate
    blocks on missing coverage, not on file noise."""
    path = Path(task_dir) / EVIDENCE_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    records: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and _valid_record(record):
            records.append(record)
    return records


def _valid_record(record: dict[str, Any]) -> bool:
    ac = record.get("ac")
    ref = record.get("ref")
    kind = record.get("kind")
    return (
        isinstance(ac, str)
        and bool(ac.strip())
        and isinstance(ref, str)
        and bool(ref.strip())
        and kind in EVIDENCE_KINDS
    )


def evidence_coverage(
    acceptance: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Coverage facts over declared AC ids: total, covered, missing ids."""
    covered = {
        record["ac"].strip()
        for record in evidence
    }
    ids = [item["id"] for item in acceptance]
    missing = [ac_id for ac_id in ids if ac_id not in covered]
    return {
        "total": len(ids),
        "withEvidence": len(ids) - len(missing),
        "missing": missing,
    }


def coverage_summary(task_dir: Path) -> dict[str, Any] | None:
    """End-to-end coverage facts for one task.

    None when the task declares no acceptance criteria — consumers treat
    that as "gate not applicable" instead of a fake zero."""
    acceptance = load_acceptance_criteria(task_dir)
    if not acceptance:
        return None
    return evidence_coverage(acceptance, read_evidence(task_dir))
