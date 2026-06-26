"""Tests for the shallow test scanner (Phase 5)."""

from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"


class TestQualityTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPTS))
        cls.tq = importlib.import_module("common.test_quality")

    @classmethod
    def tearDownClass(cls) -> None:
        sys.path.remove(str(SCRIPTS))
        for name in ("common.test_quality", "common"):
            sys.modules.pop(name, None)

    def _write_file(self, parent: Path, name: str, content: str) -> Path:
        path = parent / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    # -- scan_test_file: Python shallow patterns --------------------------

    def test_rejects_assert_true(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = self._write_file(Path(d), "test_x.py", "def test_it():\n    assert True\n")
            violations = self.tq.scan_test_file(p)
            self.assertEqual(1, len(violations))
            self.assertIn("shallow assertion", violations[0])

    def test_rejects_self_assert_true_true(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = self._write_file(
                Path(d), "test_x.py",
                "class TestX:\n    def test_it(self):\n        self.assertTrue(True)\n"
            )
            violations = self.tq.scan_test_file(p)
            self.assertEqual(1, len(violations))
            self.assertIn("shallow assertion", violations[0])

    def test_accepts_meaningful_assertion(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = self._write_file(
                Path(d), "test_x.py",
                "def test_it():\n    result = add(1, 2)\n    assert result == 3\n"
            )
            violations = self.tq.scan_test_file(p)
            self.assertEqual([], violations)

    def test_rejects_existence_only_test(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = self._write_file(
                Path(d), "test_x.py",
                "def test_exists():\n    pass\n"
            )
            violations = self.tq.scan_test_file(p)
            self.assertEqual(1, len(violations))
            self.assertIn("existence-only", violations[0])

    def test_accepts_test_with_self_assertEqual(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = self._write_file(
                Path(d), "test_x.py",
                "class TestX:\n"
                "    def test_it(self):\n"
                "        result = add(1, 2)\n"
                "        self.assertEqual(3, result)\n"
            )
            violations = self.tq.scan_test_file(p)
            self.assertEqual([], violations)

    def test_accepts_test_with_unittest_main(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = self._write_file(
                Path(d), "test_x.py",
                "import unittest\n"
                "class TestX(unittest.TestCase):\n"
                "    def test_it(self):\n"
                "        self.assertIsNotNone(get_id())\n"
            )
            violations = self.tq.scan_test_file(p)
            self.assertEqual([], violations)

    # -- scan_test_file: JavaScript shallow patterns -----------------------

    def test_rejects_js_expect_true_to_be_true(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = self._write_file(
                Path(d), "test_x.test.ts",
                "test('nothing', () => {\n  expect(true).toBe(true);\n});\n"
            )
            violations = self.tq.scan_test_file(p)
            self.assertEqual(1, len(violations))
            self.assertIn("shallow assertion", violations[0])

    def test_accepts_meaningful_js_test(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = self._write_file(
                Path(d), "test_x.test.ts",
                "test('adds numbers', () => {\n"
                "  expect(add(1, 2)).toBe(3);\n"
                "});\n"
            )
            violations = self.tq.scan_test_file(p)
            self.assertEqual([], violations)

    def test_accepts_non_test_files_silently(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = self._write_file(
                Path(d), "models.py",
                "class User:\n    pass\n"
            )
            violations = self.tq.scan_test_file(p)
            self.assertEqual([], violations)

    # -- scan_test_files batch ---------------------------------------------

    def test_scan_test_files_returns_ok_when_clean(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            task_dir = Path(d)
            self._write_file(
                task_dir, "test_x.py",
                "def test_it():\n    assert add(1, 2) == 3\n"
            )
            result = self.tq.scan_test_files(task_dir)
            self.assertTrue(result["ok"])
            self.assertEqual([], result["violations"])

    def test_scan_test_files_returns_not_ok_with_shallow_tests(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            task_dir = Path(d)
            self._write_file(
                task_dir, "test_bad.py",
                "def test_it():\n    assert True\n"
            )
            result = self.tq.scan_test_files(task_dir)
            self.assertFalse(result["ok"])
            self.assertGreater(len(result["violations"]), 0)

    # -- is_pass_only_test -------------------------------------------------

    def test_pass_only_returns_true_for_pass_body(self) -> None:
        self.assertTrue(self.tq._is_pass_only_test(["pass"]))

    def test_pass_only_returns_false_for_assert_body(self) -> None:
        self.assertFalse(self.tq._is_pass_only_test(["assert 1 == 1"]))

    def test_pass_only_returns_false_for_self_assertEqual(self) -> None:
        self.assertFalse(self.tq._is_pass_only_test(["self.assertEqual(1, 1)"]))


if __name__ == "__main__":
    unittest.main()
