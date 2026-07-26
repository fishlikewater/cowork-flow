#!/usr/bin/env python3
"""Test intent helpers for cowork-flow review guidance.

The lifecycle kernel does not run test-quality gates. These helpers remain
available to review code or prompts that need a lightweight classifier for a
concrete test body.
"""

from __future__ import annotations

import ast
import io
import tokenize

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


def validate_test_intent(*_args, **_kwargs) -> list[dict]:
    """Return no lifecycle violations.

    Test quality is reviewed from changed test files and verification output,
    not from lifecycle gates or task-local evidence files.
    """
    return []


def classify_test_content(content: str, test_name: str) -> str:
    """Classify one concrete test body as pass, warn, block, or missing."""
    return _classify_test_content(content, test_name)


def _classify_test_content(content: str, test_name: str) -> str:
    target_content = _target_test_content(content, test_name)
    if target_content is None:
        return "missing"
    scan_content = _strip_string_and_comment_literals(target_content)
    lower = scan_content.lower()

    if any(marker.lower() in lower for marker in BLOCK_MARKERS):
        return "block"

    if _looks_mock_only(lower):
        return "block"

    if _looks_import_only(content, lower):
        return "block"

    if _looks_ambiguous(lower):
        return "warn"

    return "pass"


def _strip_string_and_comment_literals(content: str) -> str:
    try:
        tokens = []
        for token in tokenize.generate_tokens(io.StringIO(content).readline):
            if token.type in (tokenize.STRING, tokenize.COMMENT):
                tokens.append(token._replace(string='""'))
            else:
                tokens.append(token)
        return tokenize.untokenize(tokens)
    except (IndentationError, tokenize.TokenError):
        return content


def _target_test_content(content: str, test_name: str) -> str | None:
    parse_content = content.lstrip("\ufeff")
    try:
        tree = ast.parse(parse_content)
    except SyntaxError:
        return parse_content if test_name and test_name in parse_content else None

    target_class, target_function = _parse_test_name(test_name)
    if not target_function:
        return None

    for node in ast.walk(tree):
        if target_class and isinstance(node, ast.ClassDef) and node.name == target_class:
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name == target_function:
                    return ast.get_source_segment(parse_content, child) or parse_content
            return None
        if not target_class and isinstance(node, ast.FunctionDef) and node.name == target_function:
            return ast.get_source_segment(parse_content, node) or parse_content
    return None


def _parse_test_name(test_name: str) -> tuple[str | None, str | None]:
    normalized = test_name.strip()
    if not normalized:
        return None, None
    parts = [part for part in normalized.split(".") if part]
    if not parts:
        return None, None
    target_function = parts[-1]
    target_class = parts[-2] if len(parts) >= 2 and parts[-2][:1].isupper() else None
    return target_class, target_function


def _looks_import_only(content: str, lower: str) -> bool:
    if "assert" in lower:
        return False
    if "expect(" in lower or ".to" in lower:
        return False
    return "def test_" in lower or "class " in lower


def _looks_mock_only(lower: str) -> bool:
    mock_markers = ("assert_called", "call_count", "assert_not_called", "mock(", "Mock(")
    return any(marker in lower for marker in mock_markers) and not any(
        marker in lower
        for marker in (
            "assertequal(",
            "assertequals(",
            "assertraises(",
            "assertin(",
            "asserttrue(",
            "assertfalse(",
        )
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
