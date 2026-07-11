#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AST-based test intent classification.

Classifies test functions into: pass / warn / block / missing.

- pass: meaningful assertions found
- warn: weak assertions only (assertIsNotNone, assertIn, etc.)
- block: shallow tests (assert True, import-only, mock-only, existence checks)
- missing: testName does not resolve to a function

Inspired by dev branch test_intent.py — uses Python AST to locate test
function bodies, then strips string/comment literals before analysis.
"""

from __future__ import annotations

import ast
from pathlib import Path


# ---------------------------------------------------------------------------
# Assertion strength markers
# ---------------------------------------------------------------------------

STRONG_ASSERT_MARKERS = (
    "assertEqual", "assertNotEqual",
    "assertTrue", "assertFalse",
    "assertIs", "assertIsNot",
    "assertIsNone", "assertIsNotNone",
    "assertIn", "assertNotIn",
    "assertIsInstance", "assertNotIsInstance",
    "assertRaises", "assertRaisesRegex",
    "assertGreater", "assertGreaterEqual",
    "assertLess", "assertLessEqual",
    "assertRegex", "assertNotRegex",
    "assertCountEqual", "assertMultiLineEqual",
    "assertListEqual", "assertTupleEqual",
    "assertSetEqual", "assertDictEqual",
    "assertAlmostEqual", "assertNotAlmostEqual",
    "assertWarns", "assertLogs",
    "assert_",  # custom assertion helpers
)

WEAK_ASSERT_MARKERS = (
    "assertIsNotNone",  # existence check
    "assertIsInstance",  # type check only
    "assertIn",  # membership check
    "assertNotIn",
)

SHALLOW_PATTERNS = (
    "assert True",
    "assert True,",
    "assertTrue(True)",
    "self.assertTrue(True)",
    "self.assertTrue( true",
    "assert 1",
    "assert not False",
)

JS_SHALLOW_PATTERNS = (
    "expect(true).toBe(true)",
    "expect( true ).toBe( true ",
    "expect(true).toBe( true",
    "expect(true).toBeTruthy(",
    "expect(true).toEqual(true)",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_test_file(path: Path) -> list[dict]:
    """Classify all test functions in a file.

    Returns a list of dicts with keys:
    function, classification, reason, line
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    if path.suffix == ".py":
        return _classify_python(text, path)
    if path.suffix in (".ts", ".tsx", ".js", ".jsx"):
        return _classify_javascript(text, path)
    return []


def scan_test_files(task_dir: Path) -> dict:
    """Scan all test files in a task directory.

    Returns a dict with 'ok' (bool) and 'violations' (list[str]).
    """
    violations: list[str] = []
    test_patterns = (
        "test_*.py", "*_test.py",
        "test_*.ts", "*.test.ts",
        "test_*.tsx", "*.test.tsx",
        "test_*.js", "*.test.js",
        "test_*.jsx", "*.test.jsx",
    )
    for pattern in test_patterns:
        for path in task_dir.rglob(pattern):
            if path.is_file() and "__pycache__" not in str(path):
                results = classify_test_file(path)
                for r in results:
                    if r["classification"] == "block":
                        violations.append(
                            f"{path}:{r['line']}: {r['function']} — {r['reason']}"
                        )
    return {"ok": len(violations) == 0, "violations": violations}


# ---------------------------------------------------------------------------
# Python AST classifier
# ---------------------------------------------------------------------------


def _classify_python(source: str, path: Path) -> list[dict]:
    """Parse Python AST and classify each test function."""
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    results: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if not node.name.startswith("test_"):
            continue
        classification, reason = _classify_function_body(node)
        results.append({
            "function": node.name,
            "classification": classification,
            "reason": reason,
            "line": node.lineno,
        })
    return results


def _classify_function_body(func: ast.FunctionDef) -> tuple[str, str]:
    """Classify a single test function body.

    Returns (classification, reason).
    """
    body = func.body

    # Empty body or only docstring + pass
    if _is_empty_body(body):
        return "block", "empty test body (pass-only or docstring-only)"

    # Collect all assertion calls in the function (self.assertEqual, etc.)
    assertions = _collect_assertions(func)

    # Also detect bare assert statements (ast.Assert, not ast.Call)
    has_bare_assert = any(
        isinstance(n, ast.Assert) for n in ast.walk(func)
    )

    # Check for shallow patterns in original AST (not re-unparsed)
    # Check Assert nodes for trivial conditions like `assert True`
    if _has_trivial_assert(func):
        return "block", "trivial assertion (assert True / assert 1 / assert not False)"

    if not assertions and not has_bare_assert:
        # Check for raise statements
        has_raise = any(
            isinstance(n, ast.Raise) for n in ast.walk(func)
        )
        if has_raise:
            return "pass", "uses raise for expected failure"
        return "block", "no assertions found — existence-only test"

    # Classify assertion strength
    has_strong = has_bare_assert or any(a.get("strong") for a in assertions)
    has_weak_only = not has_bare_assert and all(a.get("weak") for a in assertions)

    if has_strong:
        strong_names = [a['name'] for a in assertions if a['strong']]
        if has_bare_assert:
            strong_names.insert(0, "assert")
        return "pass", f"meaningful assertions: {', '.join(strong_names)}"
    if has_weak_only:
        return "warn", f"weak assertions only: {', '.join(a['name'] for a in assertions)}"

    return "pass", "assertions present"


def _has_trivial_assert(func: ast.FunctionDef) -> bool:
    """Check if any bare assert statements have trivial conditions."""
    for node in ast.walk(func):
        if isinstance(node, ast.Assert):
            test = node.test
            # assert True / assert False
            if isinstance(test, ast.Constant) and isinstance(test.value, bool):
                return True
            # assert 1 / assert 0 / assert not False
            if isinstance(test, ast.Constant) and test.value in (0, 1):
                return True
            # assert not False → UnaryOp(Not, Constant(False))
            if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
                if isinstance(test.operand, ast.Constant) and test.operand.value is False:
                    return True
    return False


def _is_empty_body(body: list[ast.stmt]) -> bool:
    """Check if function body is empty (pass-only or docstring-only)."""
    if not body:
        return True
    if len(body) == 1 and isinstance(body[0], ast.Pass):
        return True
    if len(body) == 1 and isinstance(body[0], ast.Expr) and isinstance(body[0].value, (ast.Constant, ast.Str)):
        return True  # docstring only
    if all(
        isinstance(stmt, ast.Pass) or (
            isinstance(stmt, ast.Expr) and isinstance(stmt.value, (ast.Constant, ast.Str))
        )
        for stmt in body
    ):
        return True
    return False


def _collect_assertions(func: ast.FunctionDef) -> list[dict]:
    """Collect assertion-related calls from a function body.

    Only returns calls whose name matches known assertion markers.
    """
    assertions: list[dict] = []
    all_markers = set()
    for m in STRONG_ASSERT_MARKERS:
        all_markers.add(m)
    for m in WEAK_ASSERT_MARKERS:
        all_markers.add(m)
    all_markers.discard("assert_")  # too generic
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            name = _get_call_name(node)
            if not name:
                continue
            # Only include if it looks like an assertion call
            if not any(name.startswith(m) or name == m for m in all_markers):
                continue
            is_strong = any(name.startswith(m) or name == m for m in STRONG_ASSERT_MARKERS) and not any(
                name.startswith(m) or name == m for m in WEAK_ASSERT_MARKERS
            )
            is_weak = any(name.startswith(m) or name == m for m in WEAK_ASSERT_MARKERS)
            assertions.append({
                "name": name,
                "strong": is_strong,
                "weak": is_weak,
            })
    return assertions


def _get_call_name(node: ast.Call) -> str:
    """Extract the function name from a Call node."""
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return ""


# ---------------------------------------------------------------------------
# JavaScript classifier (pattern-based, kept simple)
# ---------------------------------------------------------------------------


def _classify_javascript(source: str, path: Path) -> list[dict]:
    """Classify JS/TS test functions using pattern matching."""
    results: list[dict] = []
    lines = source.splitlines()
    in_test = False
    test_name = ""
    test_start = 0
    test_body_lines: list[str] = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Detect test() or it() calls
        if stripped.startswith(("test(", "it(")):
            in_test = True
            test_name = stripped.split("(")[1].split(",")[0].strip("'\"")
            test_start = i
            test_body_lines = []
            continue
        if in_test:
            test_body_lines.append(stripped)
            if stripped == "});" or stripped == "}":
                # End of test block
                classification, reason = _classify_js_body(test_body_lines)
                results.append({
                    "function": test_name,
                    "classification": classification,
                    "reason": reason,
                    "line": test_start,
                })
                in_test = False
    return results


def _classify_js_body(body_lines: list[str]) -> tuple[str, str]:
    """Classify a JS test body."""
    body = "\n".join(body_lines)
    for pattern in JS_SHALLOW_PATTERNS:
        if pattern in body:
            return "block", f"shallow assertion: {pattern!r}"
    # Check for meaningful assertions
    strong_markers = (".toBe(", ".toEqual(", ".toMatch(", ".toThrow(", ".toHaveLength(")
    weak_markers = (".toBeDefined(", ".not.toBeNull(", ".toBeInstanceOf(")
    has_strong = any(m in body for m in strong_markers)
    has_weak = any(m in body for m in weak_markers)
    if has_strong:
        return "pass", "meaningful assertions found"
    if has_weak:
        return "warn", "weak assertions only"
    return "block", "no meaningful assertions"
