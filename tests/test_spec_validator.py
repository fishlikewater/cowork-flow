#!/usr/bin/env python3
"""TDD RED — these tests should fail before implementation."""

import tempfile
from pathlib import Path

from common.gates.spec_validator import validate_sections


def _write(tmpdir: str, content: str) -> Path:
    p = Path(tmpdir) / "spec.md"
    p.write_text(content, encoding="utf-8")
    return p


def test_valid_contract_returns_true():
    content = """# My Contract

## Goal
Ensure quality.

## When to Use
When building specs.

## Rules
- Rule 1
- Rule 2

## Examples
Example here.
"""
    with tempfile.TemporaryDirectory() as d:
        p = _write(d, content)
        valid, errors = validate_sections(p, "contract")
        assert valid is True, f"Expected valid, got errors: {errors}"
        assert errors == []


def test_missing_section_returns_false():
    content = """# My Contract

## Goal
Ensure quality.

## Rules
- Rule 1
"""
    with tempfile.TemporaryDirectory() as d:
        p = _write(d, content)
        valid, errors = validate_sections(p, "contract")
        assert valid is False
        assert any("Missing" in e and "When to Use" in e for e in errors)


def test_empty_section_body_counts_as_missing():
    content = """# My Contract

## Goal
Ensure quality.

## Rules


## Examples
Example here.
"""
    with tempfile.TemporaryDirectory() as d:
        p = _write(d, content)
        valid, errors = validate_sections(p, "contract")
        assert valid is False
        assert any("Empty" in e and "Rules" in e for e in errors)


def test_unknown_spec_type_returns_error():
    content = """# Test

## Goal
Test.
"""
    with tempfile.TemporaryDirectory() as d:
        p = _write(d, content)
        valid, errors = validate_sections(p, "nonexistent_type")
        assert valid is False
        assert any("Unknown spec type" in e for e in errors)
