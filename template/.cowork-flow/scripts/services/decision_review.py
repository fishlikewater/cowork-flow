#!/usr/bin/env python3
"""Structured decision review evidence validation."""

from __future__ import annotations

import json
from pathlib import Path


DECISION_REVIEW_FILE = "decision-review.jsonl"
REQUIRED_FIELDS = (
    "acceptanceId",
    "claim",
    "contract",
    "reviewerContext",
    "findings",
    "resolution",
)


def _is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_decision_review_file(path: Path) -> list[str]:
    """Return structural issues for a decision-review JSONL artifact."""
    path = Path(path)
    if not path.is_file() or not path.read_text(encoding="utf-8").strip():
        return [f"{DECISION_REVIEW_FILE} is missing or empty"]

    issues: list[str] = []
    valid_records = 0
    with path.open("r", encoding="utf-8") as stream:
        for line_number, raw_line in enumerate(stream, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                issues.append(
                    f"decision review line {line_number}: invalid JSON ({error.msg})"
                )
                continue
            if not isinstance(record, dict):
                issues.append(
                    f"decision review line {line_number}: record must be an object"
                )
                continue

            missing = [field for field in REQUIRED_FIELDS if field not in record]
            if missing:
                issues.append(
                    f"decision review line {line_number}: missing required fields: "
                    + ", ".join(missing)
                )
                continue

            line_issues: list[str] = []
            acceptance_id = record["acceptanceId"]
            if not _is_nonempty_string(acceptance_id) or not str(
                acceptance_id
            ).startswith("AC-"):
                line_issues.append("acceptanceId must start with AC-")
            for field in ("claim", "contract"):
                if not _is_nonempty_string(record[field]):
                    line_issues.append(f"{field} must be a non-empty string")
            if record["reviewerContext"] != "fresh":
                line_issues.append("reviewerContext must be fresh")
            if not isinstance(record["findings"], list):
                line_issues.append("findings must be a list")
            if record["resolution"] != "accepted":
                line_issues.append("resolution must be accepted")

            if line_issues:
                issues.extend(
                    f"decision review line {line_number}: {issue}"
                    for issue in line_issues
                )
                continue
            valid_records += 1

    if not issues and valid_records == 0:
        return [f"{DECISION_REVIEW_FILE} contains no records"]
    return issues
