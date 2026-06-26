"""Tests for coding standard scanners (Phase 6)."""

from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"


class CodingStandardsTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPTS))
        cls.cs = importlib.import_module("common.coding_standards")

    @classmethod
    def tearDownClass(cls) -> None:
        sys.path.remove(str(SCRIPTS))
        for name in ("common.coding_standards", "common"):
            sys.modules.pop(name, None)

    # -- BOM scan ----------------------------------------------------------

    def test_bom_scan_detects_utf8_bom(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad_file.py"
            p.write_bytes(b"\xef\xbb\xbf# -*- coding: utf-8 -*-\nprint('hi')\n")
            result = self.cs.scan_bom([p])
            self.assertFalse(result["ok"])
            self.assertTrue(any("BOM" in v for v in result["violations"]))

    def test_bom_scan_passes_clean_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "good_file.py"
            p.write_text("# -*- coding: utf-8 -*-\nprint('hi')\n", encoding="utf-8")
            result = self.cs.scan_bom([p])
            self.assertTrue(result["ok"])

    def test_bom_scan_skips_non_text_files(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "image.png"
            p.write_bytes(b"\xef\xbb\xbf\x89PNG")
            result = self.cs.scan_bom([p])
            self.assertTrue(result["ok"])

    def test_bom_scan_directory(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "clean.py").write_text("# ok\n", encoding="utf-8")
            (root / "bad.md").write_bytes(b"\xef\xbb\xbf# Title\n")
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "bad.py").write_bytes(b"\xef\xbb\xbf# cached\n")
            result = self.cs.scan_bom([root])
            self.assertFalse(result["ok"])
            self.assertTrue(any("bad.md" in v for v in result["violations"]))
            # __pycache__ files should be skipped
            self.assertFalse(any("pycache" in v for v in result["violations"]))

    # -- Encoding scan -----------------------------------------------------

    def test_encoding_scan_detects_missing_utf8_in_read_text(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "reader.py"
            p.write_text(
                "from pathlib import Path\n"
                "def read():\n"
                "    return Path('f.txt').read_text()\n",
                encoding="utf-8",
            )
            result = self.cs.scan_encoding([p])
            self.assertFalse(result["ok"])
            self.assertTrue(any("read_text" in v for v in result["violations"]))

    def test_encoding_scan_accepts_explicit_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "reader.py"
            p.write_text(
                "from pathlib import Path\n"
                "def read():\n"
                "    return Path('f.txt').read_text(encoding='utf-8')\n",
                encoding="utf-8",
            )
            result = self.cs.scan_encoding([p])
            self.assertTrue(result["ok"])

    def test_encoding_scan_detects_missing_utf8_in_open(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "opener.py"
            p.write_text(
                "def read_file(path):\n"
                "    with open(path, 'r') as f:\n"
                "        return f.read()\n",
                encoding="utf-8",
            )
            result = self.cs.scan_encoding([p])
            self.assertFalse(result["ok"])
            self.assertTrue(any("open" in v for v in result["violations"]))

    def test_encoding_scan_accepts_open_with_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "opener.py"
            p.write_text(
                "def read_file(path):\n"
                "    with open(path, 'r', encoding='utf-8') as f:\n"
                "        return f.read()\n",
                encoding="utf-8",
            )
            result = self.cs.scan_encoding([p])
            self.assertTrue(result["ok"])

    def test_encoding_scan_skips_binary_open(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "binary.py"
            p.write_text(
                "def read_bin(path):\n"
                "    with open(path, 'rb') as f:\n"
                "        return f.read()\n",
                encoding="utf-8",
            )
            result = self.cs.scan_encoding([p])
            self.assertTrue(result["ok"])

    def test_encoding_scan_accepts_write_text_with_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "writer.py"
            p.write_text(
                "Path('f.txt').write_text('hi', encoding='utf-8')\n",
                encoding="utf-8",
            )
            result = self.cs.scan_encoding([p])
            self.assertTrue(result["ok"])

    def test_encoding_scan_detects_missing_utf8_in_write_text(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "writer.py"
            p.write_text(
                "Path('f.txt').write_text('hi')\n",
                encoding="utf-8",
            )
            result = self.cs.scan_encoding([p])
            self.assertFalse(result["ok"])
            self.assertTrue(any("write_text" in v for v in result["violations"]))

    def test_encoding_scan_skips_binary_open_method(self) -> None:
        """path.open('rb') method-call form should be skipped."""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "binary.py"
            p.write_text(
                "from pathlib import Path\n"
                "def read_bin(path):\n"
                "    with Path(path).open('rb') as f:\n"
                "        return f.read()\n",
                encoding="utf-8",
            )
            result = self.cs.scan_encoding([p])
            self.assertTrue(result["ok"], f"violations: {result.get('violations', [])}")

    # -- JS/TS encoding scan ---------------------------------------------

    def test_js_encoding_scan_detects_missing_utf8(self) -> None:
        """JS readFile without encoding must be detected."""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "reader.js"
            p.write_text(
                "const fs = require('fs');\n"
                "fs.readFile('data.txt', (err, data) => { console.log(data); });\n",
                encoding="utf-8",
            )
            result = self.cs.scan_encoding_js([p])
            self.assertFalse(result["ok"])
            self.assertTrue(any("readFile" in v for v in result["violations"]))

    def test_js_encoding_scan_accepts_inline_utf8(self) -> None:
        """JS readFile with 'utf8' string arg must pass."""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "reader.js"
            p.write_text(
                "const fs = require('fs');\n"
                "fs.readFile('data.txt', 'utf8', (err, data) => {});\n",
                encoding="utf-8",
            )
            result = self.cs.scan_encoding_js([p])
            self.assertTrue(result["ok"], f"violations: {result.get('violations', [])}")

    def test_js_encoding_scan_accepts_writefile_with_utf8(self) -> None:
        """TS writeFileSync with encoding option must pass."""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "writer.ts"
            p.write_text(
                "import * as fs from 'fs';\n"
                "fs.writeFileSync('out.txt', data, {encoding: 'utf-8'});\n",
                encoding="utf-8",
            )
            result = self.cs.scan_encoding_js([p])
            self.assertTrue(result["ok"], f"violations: {result.get('violations', [])}")

    # -- scan_standards integration ----------------------------------------

    def test_scan_standards_produces_valid_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            task_dir = Path(d) / "task"
            task_dir.mkdir()
            (task_dir / "clean.py").write_text("# ok\n", encoding="utf-8")
            result = self.cs.scan_standards(task_dir, ROOT)
            self.assertIn("encodingScan", result)
            self.assertIn("bomScan", result)
            self.assertIn("whitespaceCheck", result)
            self.assertIsInstance(result["encodingScan"]["ok"], bool)
            self.assertIsInstance(result["bomScan"]["ok"], bool)
            self.assertIsInstance(result["whitespaceCheck"]["ok"], bool)


if __name__ == "__main__":
    unittest.main()
