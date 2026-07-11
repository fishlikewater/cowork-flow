#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for test_intent.py — AST-based test classification."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".cowork-flow" / "scripts"
sys.path.insert(0, str(SCRIPTS))


class TestPythonClassification(unittest.TestCase):
    """Tests for test_intent._classify_python."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="intent_test_"))
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _classify(self, source: str) -> list:
        from common import test_intent
        path = self.tmp / "test_sample.py"
        path.write_text(source, encoding="utf-8")
        return test_intent._classify_python(source, path)

    def test_pass_meaningful_assertions(self):
        source = (
            "def test_addition():\n"
            "    assert 1 + 1 == 2\n"
        )
        result = self._classify(source)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["classification"], "pass")

    def test_block_assert_true(self):
        source = (
            "def test_something():\n"
            "    assert True\n"
        )
        result = self._classify(source)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["classification"], "block")

    def test_block_no_assertions(self):
        source = (
            "def test_existence():\n"
            "    obj = SomeClass()\n"
        )
        result = self._classify(source)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["classification"], "block")

    def test_block_empty_body(self):
        source = (
            "def test_empty():\n"
            "    pass\n"
        )
        result = self._classify(source)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["classification"], "block")

    def test_warn_weak_assertions(self):
        source = (
            "def test_type():\n"
            "    obj = get_obj()\n"
            "    self.assertIsInstance(obj, MyClass)\n"
        )
        result = self._classify(source)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["classification"], "warn")

    def test_pass_unittest_style(self):
        source = (
            "def test_calculation(self):\n"
            "    self.assertEqual(calc(2), 4)\n"
        )
        result = self._classify(source)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["classification"], "pass")

    def test_pass_raises(self):
        source = (
            "def test_error():\n"
            "    with self.assertRaises(ValueError):\n"
            "        bad_call()\n"
        )
        result = self._classify(source)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["classification"], "pass")

    def test_syntax_error_returns_empty(self):
        source = "def test_broken(:\n"
        result = self._classify(source)
        self.assertEqual(result, [])


class TestJavaScriptClassification(unittest.TestCase):
    """Tests for test_intent._classify_javascript."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="intent_js_test_"))
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_block_expect_true(self):
        from common import test_intent
        source = (
            "test('should work', () => {\n"
            "  expect(true).toBe(true);\n"
            "});\n"
        )
        result = test_intent._classify_javascript(source, self.tmp / "test.js")
        self.assertTrue(any(r["classification"] == "block" for r in result))

    def test_pass_meaningful_expect(self):
        from common import test_intent
        source = (
            "test('adds numbers', () => {\n"
            "  expect(1 + 1).toBe(2);\n"
            "});\n"
        )
        result = test_intent._classify_javascript(source, self.tmp / "test.js")
        self.assertTrue(any(r["classification"] == "pass" for r in result))


class TestScanTestFiles(unittest.TestCase):
    """Tests for test_intent.scan_test_files."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="scan_test_"))
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_scan_clean_test(self):
        from common import test_intent
        (self.tmp / "test_clean.py").write_text(
            "def test_ok():\n    assert 1 + 1 == 2\n",
            encoding="utf-8",
        )
        result = test_intent.scan_test_files(self.tmp)
        self.assertTrue(result["ok"])
        self.assertEqual(result["violations"], [])

    def test_scan_blocked_test(self):
        from common import test_intent
        (self.tmp / "test_bad.py").write_text(
            "def test_shallow():\n    assert True\n",
            encoding="utf-8",
        )
        result = test_intent.scan_test_files(self.tmp)
        self.assertFalse(result["ok"])
        self.assertTrue(len(result["violations"]) > 0)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
