#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shallow test scanner for quality gate enforcement.

Rejects tests that exist only to satisfy the process and do not prove
behavior. Conservative — only blocks clear junk patterns.
"""

from __future__ import annotations

from pathlib import Path

# -- Shallow patterns to reject ----------------------------------------------


PY_SHALLOW_PATTERNS = (
    "assert True",
    "self.assertTrue(True)",
    "self.assertTrue( true",
    "self.assertTrue(true,",
    "self.assertTrue( True",
    "self.assertTrue(True,",
)

PY_EXISTENCE_ONLY = (
    # A test function with only 'pass' and no assertions
    # Detected heuristically when the body contains no assert/raise
)

JS_SHALLOW_PATTERNS = (
    "expect(true).toBe(true)",
    "expect( true ).toBe( true ",
    "expect(true).toBe( true",
    "expect(true).toBeTruthy(",
)


def scan_test_file(path: Path) -> list[str]:
    """Scan a single test file for shallow test patterns.

    Returns a list of violation descriptions (empty if clean).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return [f"Could not read {_rel(path)}"]

    violations: list[str] = []

    if path.suffix == ".py":
        violations.extend(_scan_python(text, path))
    elif path.suffix in (".ts", ".tsx", ".js", ".jsx"):
        violations.extend(_scan_javascript(text, path))

    return violations


def _rel(path: Path) -> str:
    """Return a display-safe relative path."""
    return str(path)


# -- Python scanner ----------------------------------------------------------


def _scan_python(text: str, path: Path) -> list[str]:
    violations: list[str] = []

    for pattern in PY_SHALLOW_PATTERNS:
        if pattern in text:
            violations.append(
                f"{_rel(path)}: shallow assertion '{pattern}' found"
            )
            break  # one violation per pattern type per file

    # Detect existence-only test functions
    violations.extend(_scan_python_existence_only(text, path))

    return violations


def _scan_python_existence_only(text: str, path: Path) -> list[str]:
    """Detect test functions that contain only 'pass' and no assertion."""
    violations: list[str] = []
    lines = text.splitlines()
    in_test = False
    test_name = ""
    test_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("def test_") and stripped.endswith(":"):
            if in_test and _is_pass_only_test(test_lines):
                violations.append(
                    f"{_rel(path)}: existence-only test '{test_name}'"
                    " has no assertions"
                )
            in_test = True
            test_name = stripped.split("(")[0].replace("def ", "")
            test_lines = []
            continue

        if in_test:
            # Use original line (before strip) to detect dedent
            if stripped and not (line.startswith((" ", "\t")) or stripped.startswith("#")):
                # dedent — test function ended
                if _is_pass_only_test(test_lines):
                    violations.append(
                        f"{_rel(path)}: existence-only test '{test_name}'"
                        " has no assertions"
                    )
                in_test = False
                test_lines = []
            else:
                test_lines.append(stripped)

    # Check last test function at EOF
    if in_test and test_lines and _is_pass_only_test(test_lines):
        violations.append(
            f"{_rel(path)}: existence-only test '{test_name}'"
            " has no assertions"
        )

    return violations


def _is_pass_only_test(lines: list[str]) -> bool:
    """Return True when test body contains no meaningful assertions."""
    body = "\n".join(lines)
    # Must have at least one non-blank, non-comment line
    code_lines = [
        l for l in lines if l and not l.startswith("#")
    ]
    if not code_lines:
        return False  # empty body — weird but not pass-only
    # If all code lines are just 'pass' or docstrings
    if all(l == "pass" or l.startswith('"""') or l.startswith("'''") for l in code_lines):
        return True
    # No assert, no self.assert, no raise, no with self.assertRaises
    assertion_markers = ("assert ", "self.assert", "self.fail", "unittest", "pytest")
    has_assertion = any(
        any(marker in l for marker in assertion_markers) for l in code_lines
    )
    return not has_assertion


# -- JavaScript scanner ------------------------------------------------------


def _scan_javascript(text: str, path: Path) -> list[str]:
    violations: list[str] = []

    for pattern in JS_SHALLOW_PATTERNS:
        if pattern in text:
            violations.append(
                f"{_rel(path)}: shallow assertion '{pattern}' found"
            )
            break

    return violations


# -- Batch scanning ----------------------------------------------------------


def scan_test_files(task_dir: Path) -> dict:
    """Scan all test files changed in a task and return a standards-compatible result.

    Returns a dict with 'ok' (bool) and 'violations' (list[str]).
    """
    violations: list[str] = []

    test_patterns = ("test_*.py", "*_test.py", "test_*.ts", "*.test.ts",
                     "test_*.tsx", "*.test.tsx", "test_*.js", "*.test.js",
                     "test_*.jsx", "*.test.jsx")

    for pattern in test_patterns:
        for path in task_dir.rglob(pattern):
            if path.is_file() and "__pycache__" not in str(path):
                violations.extend(scan_test_file(path))

    return {
        "ok": len(violations) == 0,
        "violations": violations,
    }
