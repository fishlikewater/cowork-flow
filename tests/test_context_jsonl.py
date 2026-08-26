from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "template" / ".cowork-flow" / "scripts"


class ContextJsonlCodecTest(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        module = importlib.import_module("services.context_jsonl")
        self.read_context_jsonl_entries = module.read_context_jsonl_entries
        self.write_jsonl = module.write_jsonl
        self.iter_jsonl_lines = module.iter_jsonl_lines

    def _cleanup_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        sys.modules.pop("services.context_jsonl", None)

    def test_reader_preserves_line_numbers_raw_text_and_line_endings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            context_file = Path(temp_dir) / "implement.jsonl"
            allowed_name = "src/\u5141\u8bb8.py"
            reason = "\u4e2d\u6587"
            with context_file.open("w", encoding="utf-8", newline="") as stream:
                stream.write(
                    json.dumps({"file": allowed_name, "reason": reason}, ensure_ascii=False)
                    + "\r\n\r\nnot-json\r\n"
                    + json.dumps(["not", "object"])
                    + "\n"
                )

            result = self.read_context_jsonl_entries(context_file)

            self.assertTrue(result.exists)
            self.assertEqual(3, result.entry_count)
            self.assertEqual([1, 4], [entry.line for entry in result.entries])
            self.assertEqual(["\r\n", "\n"], [entry.line_ending for entry in result.entries])
            self.assertEqual(allowed_name, result.entries[0].data["file"])
            self.assertEqual([("invalid_json", 3)], [(issue.code, issue.line) for issue in result.issues])

    def test_write_jsonl_uses_utf8_and_ensure_ascii_false(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            context_file = Path(temp_dir) / "implement.jsonl"
            entry = {"file": "\u8bf4\u660e.md", "reason": "\u4e2d\u6587\u539f\u56e0"}

            self.write_jsonl(context_file, [entry])

            raw = context_file.read_bytes()
            self.assertIn(entry["file"].encode("utf-8"), raw)
            self.assertNotIn(b"\\u8bf4", raw)
            self.assertEqual(
                [entry],
                [json.loads(line) for line in context_file.read_text(encoding="utf-8").splitlines()],
            )

    def test_iter_jsonl_lines_reports_line_numbers_without_lf_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            context_file = Path(temp_dir) / "implement.jsonl"
            with context_file.open("w", encoding="utf-8", newline="") as stream:
                stream.write("first\r\nsecond\n")

            self.assertEqual(
                [(1, "first"), (2, "second")],
                list(self.iter_jsonl_lines(context_file)),
            )


if __name__ == "__main__":
    unittest.main()
