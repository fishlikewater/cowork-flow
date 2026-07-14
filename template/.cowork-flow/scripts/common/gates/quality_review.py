#!/usr/bin/env python3
"""Validate task-local quality review evidence."""

from __future__ import annotations

import json
from json import JSONDecodeError
from pathlib import Path
from typing import Iterable

from common.gates.validate_coding_standards import collect_machine_checks


QUALITY_REVIEW_FILE = "quality-review.jsonl"
REQUIRED_FIELDS = frozenset(
    {"id", "source", "type", "status", "files", "evidence", "verification"}
)
ALLOWED_TYPES = frozenset({"checklist", "machine_warning", "dod"})
ALLOWED_STATUSES = frozenset(
    {"pass", "fail", "not_applicable", "acknowledged_warning"}
)
VAGUE_EVIDENCE = frozenset(
    {
        "checked",
        "done",
        "ok",
        "pass",
        "passed",
        "n/a",
        "na",
        "已检查",
        "已确认",
        "通过",
        "无问题",
    }
)


def validate_quality_review(
    repo_root: Path,
    task_dir: Path | None,
) -> list[dict]:
    """Return blocking violations for missing or incomplete quality evidence."""
    if task_dir is None:
        return [
            _violation(
                "QUALITY-REVIEW-TASK-001",
                "",
                "Quality review gate requires a task directory",
                "Run task complete with an explicit or active task directory.",
            )
        ]

    evidence_path = Path(task_dir) / QUALITY_REVIEW_FILE
    entries, violations = _read_entries(evidence_path)
    if violations and not entries:
        return violations

    violations.extend(_validate_entries(entries, evidence_path))
    if not violations:
        violations.extend(_validate_machine_warning_coverage(repo_root, entries))
    return violations


def _read_entries(evidence_path: Path) -> tuple[list[dict], list[dict]]:
    if not evidence_path.is_file():
        return [], [
            _violation(
                "QUALITY-REVIEW-MISSING-001",
                str(evidence_path),
                "quality-review.jsonl is required before task complete",
                "Record quality checklist, machine warning, and DoD evidence in quality-review.jsonl.",
            )
        ]

    entries: list[dict] = []
    violations: list[dict] = []
    try:
        lines = evidence_path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return [], [
            _violation(
                "QUALITY-REVIEW-UTF8-001",
                str(evidence_path),
                "quality-review.jsonl must be valid UTF-8",
                "Rewrite quality-review.jsonl as UTF-8.",
            )
        ]
    except OSError as error:
        return [], [
            _violation(
                "QUALITY-REVIEW-READ-001",
                str(evidence_path),
                f"quality-review.jsonl could not be read: {error}",
                "Restore a readable quality-review.jsonl file.",
            )
        ]

    for index, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except JSONDecodeError as error:
            violations.append(
                _line_violation(
                    "QUALITY-REVIEW-JSONL-001",
                    evidence_path,
                    index,
                    f"quality-review.jsonl line is invalid JSON: {error.msg}",
                    "Write one JSON object per line.",
                )
            )
            continue
        if not isinstance(value, dict):
            violations.append(
                _line_violation(
                    "QUALITY-REVIEW-JSONL-001",
                    evidence_path,
                    index,
                    "quality-review.jsonl line must be a JSON object",
                    "Write one JSON object per evidence record.",
                )
            )
            continue
        entries.append(value)

    if not entries and not violations:
        violations.append(
            _violation(
                "QUALITY-REVIEW-EMPTY-001",
                str(evidence_path),
                "quality-review.jsonl must contain at least one evidence record",
                "Add checklist and DoD evidence records before completing the task.",
            )
        )
    return entries, violations


def _validate_entries(entries: list[dict], evidence_path: Path) -> list[dict]:
    violations: list[dict] = []
    has_dod = False
    for index, entry in enumerate(entries, start=1):
        missing = sorted(field for field in REQUIRED_FIELDS if field not in entry)
        if missing:
            violations.append(
                _line_violation(
                    "QUALITY-REVIEW-SCHEMA-001",
                    evidence_path,
                    index,
                    f"quality-review record is missing fields: {', '.join(missing)}",
                    "Include id, source, type, status, files, evidence, and verification.",
                )
            )
            continue

        entry_type = str(entry.get("type") or "").strip()
        status = str(entry.get("status") or "").strip()
        if entry_type not in ALLOWED_TYPES:
            violations.append(
                _line_violation(
                    "QUALITY-REVIEW-TYPE-001",
                    evidence_path,
                    index,
                    f"unsupported quality-review type: {entry_type}",
                    "Use checklist, machine_warning, or dod.",
                )
            )
        if status not in ALLOWED_STATUSES:
            violations.append(
                _line_violation(
                    "QUALITY-REVIEW-STATUS-002",
                    evidence_path,
                    index,
                    f"unsupported quality-review status: {status}",
                    "Use pass, fail, not_applicable, or acknowledged_warning.",
                )
            )
        if status == "fail":
            violations.append(
                _line_violation(
                    "QUALITY-REVIEW-STATUS-001",
                    evidence_path,
                    index,
                    "quality-review record is still failing",
                    "Resolve the finding or keep the task out of complete.",
                )
            )
        if entry_type == "dod" and status in {"pass", "not_applicable"}:
            has_dod = True

        violations.extend(_validate_files(entry, evidence_path, index))
        violations.extend(_validate_evidence(entry, evidence_path, index))
        violations.extend(_validate_verification(entry, evidence_path, index))

    if not has_dod:
        violations.append(
            _violation(
                "QUALITY-REVIEW-DOD-001",
                str(evidence_path),
                "quality-review.jsonl must include Definition of Done evidence",
                "Add a dod record for .cowork-flow/spec/references/definition-of-done.md.",
            )
        )
    return violations


def _validate_files(entry: dict, evidence_path: Path, index: int) -> list[dict]:
    files = entry.get("files")
    if _non_empty_string_list(files):
        return []
    return [
        _line_violation(
            "QUALITY-REVIEW-FILES-001",
            evidence_path,
            index,
            "quality-review files must be a non-empty list of paths",
            "List the reviewed changed files for this evidence record.",
        )
    ]


def _validate_evidence(entry: dict, evidence_path: Path, index: int) -> list[dict]:
    evidence = str(entry.get("evidence") or "").strip()
    normalized = evidence.casefold()
    if len(evidence) >= 24 and normalized not in VAGUE_EVIDENCE:
        return []
    return [
        _line_violation(
            "QUALITY-REVIEW-EVIDENCE-001",
            evidence_path,
            index,
            "quality-review evidence is too vague",
            "Describe the concrete file, rule, finding, or verification result.",
        )
    ]


def _validate_verification(entry: dict, evidence_path: Path, index: int) -> list[dict]:
    verification = entry.get("verification")
    if _non_empty_string_list(verification):
        return []
    return [
        _line_violation(
            "QUALITY-REVIEW-VERIFICATION-001",
            evidence_path,
            index,
            "quality-review verification must be a non-empty list of commands or reasons",
            "Record executed commands, or an explicit reason a command was not applicable.",
        )
    ]


def _validate_machine_warning_coverage(
    repo_root: Path,
    entries: list[dict],
) -> list[dict]:
    warnings = collect_machine_checks(Path(repo_root))
    if not warnings:
        return []

    acknowledgements = _machine_warning_acknowledgements(entries)
    violations: list[dict] = []
    for warning in warnings:
        rule_id = str(warning.get("rule_id") or "")
        file_path = str(warning.get("file") or "")
        if (rule_id, file_path) in acknowledgements:
            continue
        violations.append(
            _violation(
                "QUALITY-REVIEW-MACHINE-WARNING-001",
                file_path,
                f"machine warning {rule_id} is not addressed in quality-review.jsonl",
                "Fix the warning or add a machine_warning record with status acknowledged_warning.",
            )
        )
    return violations


def _machine_warning_acknowledgements(entries: Iterable[dict]) -> set[tuple[str, str]]:
    acknowledgements: set[tuple[str, str]] = set()
    for entry in entries:
        if entry.get("type") != "machine_warning":
            continue
        if entry.get("status") != "acknowledged_warning":
            continue
        source = str(entry.get("source") or entry.get("rule_id") or "").strip()
        files = entry.get("files")
        if not source or not isinstance(files, list):
            continue
        for file_path in files:
            if isinstance(file_path, str) and file_path.strip():
                acknowledgements.add((source, file_path.strip()))
    return acknowledgements


def _non_empty_string_list(value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and bool(item.strip()) for item in value)
    )


def _line_violation(
    rule_id: str,
    path: Path,
    line: int,
    message: str,
    fix_hint: str,
) -> dict:
    violation = _violation(rule_id, str(path), message, fix_hint)
    violation["line"] = line
    return violation


def _violation(
    rule_id: str,
    file_path: str,
    message: str,
    fix_hint: str,
) -> dict:
    return {
        "rule_id": rule_id,
        "type": "quality_review",
        "severity": "block",
        "passed": False,
        "message": message,
        "file": file_path,
        "fix_hint": fix_hint,
    }
