#!/usr/bin/env python3
"""Tests for validate_jsonl utility (TDD RED stage — expected to fail first)."""

import json
import tempfile
from pathlib import Path

from common.gates.validate_jsonl import validate_format


def _write(tmpdir: str, content: str) -> Path:
    p = Path(tmpdir) / "test.jsonl"
    p.write_text(content, encoding="utf-8")
    return p


def test_valid_file_returns_true_empty_errors():
    with tempfile.TemporaryDirectory() as d:
        p = _write(d, '{"a":1}\n{"b":2}\n')
        valid, errors = validate_format(p)
        assert valid is True
        assert errors == []


def test_empty_file_returns_false_with_message():
    with tempfile.TemporaryDirectory() as d:
        p = _write(d, "")
        valid, errors = validate_format(p)
        assert valid is False
        assert any("empty" in e.lower() for e in errors)


def test_invalid_json_line_returns_false_with_line_number():
    with tempfile.TemporaryDirectory() as d:
        p = _write(d, '{"good":1}\n{bad json}\n')
        valid, errors = validate_format(p)
        assert valid is False
        assert any("2" in e for e in errors), f"Expected line number 2 in errors: {errors}"
