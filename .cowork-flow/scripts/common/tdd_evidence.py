#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TDD evidence reader — supports both tdd.jsonl (preferred) and quality.json (fallback).

JSONL format: one JSON object per line, each representing one acceptance
criterion's red→green evidence trail.

Example line:
{"acceptanceId":"AC-001","testFile":"tests/test_foo.py","testName":"test_bar",
 "redCommand":"pytest tests/test_foo.py::test_bar -q","redExitCode":1,
 "redOutputExcerpt":"FAILED tests/test_foo.py::test_bar - AssertionError",
 "failureReason":"assertion failure","whyThisTestMatters":"proves bar() returns correct value",
 "greenCommand":"pytest tests/test_foo.py::test_bar -q","greenExitCode":0,
 "broaderVerification":"all tests pass"}

Legacy format (quality.json) is still supported for backward compatibility.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class TddRecord:
    """Single TDD evidence record for one acceptance criterion."""
    acceptance_id: str
    test_file: str
    test_name: str
    red_command: str = ""
    red_exit_code: int | None = None
    red_output_excerpt: str = ""
    failure_reason: str = ""
    why_this_test_matters: str = ""
    green_command: str = ""
    green_exit_code: int | None = None
    broader_verification: str = ""
    exempt: bool = False
    exempt_reason: str = ""


@dataclass
class TddEvidence:
    """Complete TDD evidence for a task."""
    records: list[TddRecord] = field(default_factory=list)
    source: str = ""  # "tdd.jsonl" or "quality.json"
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_red_evidence(self) -> bool:
        return any(r.red_exit_code is not None and r.red_exit_code != 0 for r in self.records)

    @property
    def has_green_evidence(self) -> bool:
        return any(r.green_exit_code == 0 for r in self.records)

    @property
    def is_complete(self) -> bool:
        """True when every non-exempt record has both red and green evidence."""
        for r in self.records:
            if r.exempt:
                continue
            if r.red_exit_code is None or r.green_exit_code != 0:
                return False
        return len(self.records) > 0


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def load_tdd_evidence(task_dir: Path) -> TddEvidence:
    """Load TDD evidence — prefers tdd.jsonl, falls back to quality.json."""
    jsonl_path = task_dir / "tdd.jsonl"
    if jsonl_path.is_file():
        return _load_jsonl(jsonl_path)
    # Fallback to quality.json
    quality_path = task_dir / "quality.json"
    if quality_path.is_file():
        return _load_quality_json(quality_path)
    return TddEvidence()


def _load_jsonl(path: Path) -> TddEvidence:
    """Load TDD evidence from tdd.jsonl format."""
    evidence = TddEvidence(source="tdd.jsonl")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        evidence.errors.append(f"Cannot read {path.name}: {e}")
        return evidence

    for line_num, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as e:
            evidence.errors.append(f"{path.name}:{line_num}: invalid JSON — {e}")
            continue
        record = _parse_record(data, line_num, evidence)
        if record:
            evidence.records.append(record)

    _validate_evidence(evidence)
    return evidence


def _parse_record(data: dict, line_num: int, evidence: TddEvidence) -> TddRecord | None:
    """Parse a single JSONL line into a TddRecord."""
    # Support exemption records
    if data.get("exempt"):
        return TddRecord(
            acceptance_id=data.get("acceptanceId", ""),
            test_file="",
            test_name="",
            exempt=True,
            exempt_reason=data.get("exemptReason", ""),
        )
    # Required fields
    if not data.get("acceptanceId"):
        evidence.errors.append(f"tdd.jsonl:{line_num}: missing acceptanceId")
        return None
    if not data.get("testName"):
        evidence.errors.append(f"tdd.jsonl:{line_num}: missing testName")
        return None

    return TddRecord(
        acceptance_id=data.get("acceptanceId", ""),
        test_file=data.get("testFile", ""),
        test_name=data.get("testName", ""),
        red_command=data.get("redCommand", ""),
        red_exit_code=data.get("redExitCode"),
        red_output_excerpt=data.get("redOutputExcerpt", "")[:500],  # cap length
        failure_reason=data.get("failureReason", ""),
        why_this_test_matters=data.get("whyThisTestMatters", ""),
        green_command=data.get("greenCommand", ""),
        green_exit_code=data.get("greenExitCode"),
        broader_verification=data.get("broaderVerification", ""),
    )


def _load_quality_json(path: Path) -> TddEvidence:
    """Load TDD evidence from legacy quality.json format."""
    evidence = TddEvidence(source="quality.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        evidence.errors.append(f"Cannot read {path.name}: {e}")
        return evidence

    work_type = data.get("workType", "behavior_change")
    if work_type in ("docs_chore", "refactor_no_behavior_change"):
        # Not TDD-required — mark as exempt
        evidence.records.append(TddRecord(
            acceptance_id="N/A",
            test_file="",
            test_name="",
            exempt=True,
            exempt_reason=f"workType '{work_type}' does not require TDD",
        ))
        return evidence

    # Convert testPlan + red + green into TddRecords
    test_plan = data.get("testPlan", [])
    red = data.get("red", {})
    green = data.get("green", {})

    for i, plan_entry in enumerate(test_plan):
        if not isinstance(plan_entry, dict):
            continue
        ac_id = plan_entry.get("acceptancePoint", f"AC-{i + 1:03d}")
        test_cmd = plan_entry.get("testCommand", "")
        # Try to extract test file and name from command
        test_file, test_name = _extract_test_location(test_cmd)
        record = TddRecord(
            acceptance_id=ac_id,
            test_file=test_file,
            test_name=test_name,
            red_command=red.get("command", test_cmd),
            red_exit_code=red.get("exitCode"),
            red_output_excerpt=(red.get("outputExcerpt", "") or "")[:500],
            failure_reason=plan_entry.get("breaksWhen", ""),
            why_this_test_matters=plan_entry.get("acceptancePoint", ""),
            green_command=green.get("command", test_cmd),
            green_exit_code=green.get("exitCode"),
        )
        evidence.records.append(record)

    _validate_evidence(evidence)
    return evidence


def _extract_test_location(command: str) -> tuple[str, str]:
    """Extract test file and function name from a test command."""
    # pytest format: pytest tests/test_foo.py::test_bar
    if "::" in command:
        parts = command.split("::")
        test_file = parts[0].split()[-1] if parts[0] else ""
        test_name = parts[1].strip() if len(parts) > 1 else ""
        return test_file, test_name
    # python -m unittest format: python -m unittest tests.test_foo.TestClass.test_bar
    if "unittest" in command:
        parts = command.split()
        if parts:
            last = parts[-1]
            if "." in last:
                segments = last.rsplit(".", 1)
                return segments[0].replace(".", "/") + ".py", segments[1]
    return command, ""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_evidence(evidence: TddEvidence) -> None:
    """Add validation warnings/errors to the evidence."""
    for record in evidence.records:
        if record.exempt:
            continue
        if record.red_exit_code is not None and record.red_exit_code == 0:
            evidence.errors.append(
                f"TDD record {record.acceptance_id}: red phase exitCode is 0, "
                f"but red phase requires a failing test (non-zero exit code)."
            )
        if record.red_exit_code is None and not record.red_command:
            evidence.warnings.append(
                f"TDD record {record.acceptance_id}: missing red phase evidence."
            )
        if record.green_exit_code != 0 and record.green_command:
            evidence.errors.append(
                f"TDD record {record.acceptance_id}: green phase exitCode is "
                f"{record.green_exit_code}, expected 0."
            )
        if not record.failure_reason:
            evidence.warnings.append(
                f"TDD record {record.acceptance_id}: missing failureReason."
            )
        if not record.why_this_test_matters:
            evidence.warnings.append(
                f"TDD record {record.acceptance_id}: missing whyThisTestMatters."
            )


# ---------------------------------------------------------------------------
# Writer helper
# ---------------------------------------------------------------------------


def write_tdd_record(task_dir: Path, record: TddRecord) -> None:
    """Append a single TddRecord to tdd.jsonl."""
    path = task_dir / "tdd.jsonl"
    data = {
        "acceptanceId": record.acceptance_id,
        "testFile": record.test_file,
        "testName": record.test_name,
        "redCommand": record.red_command,
        "redExitCode": record.red_exit_code,
        "redOutputExcerpt": record.red_output_excerpt,
        "failureReason": record.failure_reason,
        "whyThisTestMatters": record.why_this_test_matters,
        "greenCommand": record.green_command,
        "greenExitCode": record.green_exit_code,
        "broaderVerification": record.broader_verification,
    }
    if record.exempt:
        data = {
            "exempt": True,
            "acceptanceId": record.acceptance_id,
            "exemptReason": record.exempt_reason,
        }
    line = json.dumps(data, ensure_ascii=False)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
