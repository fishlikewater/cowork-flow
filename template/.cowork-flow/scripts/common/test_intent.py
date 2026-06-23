#!/usr/bin/env python3
"""Test intent validation for cowork-flow review gates."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from .tdd_evidence import EVIDENCE_FILE

REPORT_FIELD = "test_intent_review"

STRONG_ASSERT_MARKERS = (
    "assertEqual",
    "assertNotEqual",
    "assertGreater",
    "assertGreaterEqual",
    "assertLess",
    "assertLessEqual",
    "assertRaises",
    "assertRegex",
)

WEAK_ASSERT_MARKERS = (
    "assertIsNotNone",
    "assertIsInstance",
    "assertIn(",
    "assertNotIn(",
    "assertTrue(",
    "assertFalse(",
)

BLOCK_MARKERS = (
    "assert True",
    "assertTrue(True)",
    "assertFalse(False)",
    "hasattr(",
    "getattr(",
    "callable(",
    "assert_called",
    "call_count",
    "assert_not_called",
)


def validate_test_intent(repo_root: Path, task_dir: Path) -> list[dict]:
    """Return test intent warnings or blocks for the task's TDD evidence."""
    evidence_path = Path(task_dir) / EVIDENCE_FILE
    entries = _read_tdd_entries(evidence_path)
    if not entries:
        return []

    violations: list[dict] = []
    for index, entry in enumerate(entries, start=1):
        if entry.get("type") == "exemption":
            continue

        test_file = entry.get("testFile")
        test_name = str(entry.get("testName", "")).strip()
        if not isinstance(test_file, str) or not test_file.strip():
            violations.append(
                _violation(
                    "TEST-INTENT-001",
                    f"TDD evidence record {index} is missing testFile",
                    evidence_path,
                    "Point the evidence to a concrete test file.",
                    severity="block",
                )
            )
            continue

        test_path = Path(repo_root) / test_file
        content = _read_text(test_path)
        if not content:
            violations.append(
                _violation(
                    "TEST-INTENT-002",
                    f"TDD evidence record {index} references missing test file: {test_file}",
                    evidence_path,
                    "Point the evidence at an actual test file that exercises behavior.",
                    severity="block",
                )
            )
            continue

        classification = _classify_test_content(content, test_name)
        if classification == "block":
            violations.append(
                _violation(
                    "TEST-INTENT-003",
                    f"TDD evidence record {index} points to a shallow test such as assert True, import-only, mock-only, or function-existence checks",
                    test_path,
                    "Write a test that fails when the target behavior breaks.",
                    severity="block",
                )
            )
        elif classification == "warn":
            violations.append(
                _violation(
                    "TEST-INTENT-004",
                    f"TDD evidence record {index} looks weak (assertIsNotNone/assertIsInstance/assertIn) and should be reviewed carefully",
                    test_path,
                    "Prefer tests that assert meaningful behavior or state transitions.",
                    severity="warn",
                )
            )

    return violations


def _read_tdd_entries(path: Path) -> list[dict]:
    if not path.is_file():
        return []

    entries: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []

    for line in lines:
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            entries.append(data)
    return entries


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _classify_test_content(content: str, test_name: str) -> str:
    if not _appears_to_test_behavior(content, test_name):
        return "block"

    target_content = _target_test_content(content, test_name)
    lower = target_content.lower()

    if any(marker.lower() in lower for marker in BLOCK_MARKERS):
        return "block"

    if _looks_mock_only(lower):
        return "block"

    if _looks_import_only(content, lower):
        return "block"

    if _looks_ambiguous(lower):
        return "warn"

    return "pass"


def _target_test_content(content: str, test_name: str) -> str:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return content

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == test_name:
            return ast.get_source_segment(content, node) or content
    return content


def _appears_to_test_behavior(content: str, test_name: str) -> bool:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return bool(test_name and test_name in content)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == test_name:
            return True
    return bool(test_name)


def _looks_import_only(content: str, lower: str) -> bool:
    if "assert" in lower:
        return False
    if "expect(" in lower or ".to" in lower:
        return False
    return "def test_" in lower or "class " in lower


def _looks_mock_only(lower: str) -> bool:
    mock_markers = ("assert_called", "call_count", "assert_not_called", "mock(", "Mock(")
    return any(marker in lower for marker in mock_markers) and not any(
        marker in lower for marker in ("assertequal(", "assertraises(", "assertin(", "asserttrue(")
    )


def _looks_ambiguous(lower: str) -> bool:
    weak_only_markers = (
        "assertisnotnone(",
        "assertisinstance(",
        "assertin(",
        "assertnotin(",
    )
    if any(marker in lower for marker in weak_only_markers):
        strong_markers = (
            "assertequal(",
            "assertnotequal(",
            "assertgreater(",
            "assertraises(",
            "assertregex(",
        )
        return not any(marker in lower for marker in strong_markers)
    return False


def _violation(rule_id: str, message: str, file_path: Path, fix_hint: str, *, severity: str) -> dict:
    return {
        "rule_id": rule_id,
        "type": "test_intent",
        "severity": severity,
        "passed": False,
        "message": message,
        "file": str(file_path),
        "fix_hint": fix_hint,
    }
