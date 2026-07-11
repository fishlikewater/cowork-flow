#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration tests for spec-driven coding gate."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

for p in [
    str(ROOT / ".cowork-flow" / "scripts"),
    str(ROOT / "template" / ".cowork-flow" / "scripts"),
]:
    if p not in sys.path:
        sys.path.insert(0, p)

from common.spec_coding_gate import (
    load_spec_rules,
    validate_spec_coding,
)


class TestLoadSpecRules(unittest.TestCase):
    """Tests for load_spec_rules parsing."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="spec_cg_test_"))
        self.addCleanup(self._cleanup)
        self._init_git()

    def _cleanup(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _init_git(self):
        subprocess.run(["git", "init"], cwd=self.tmp, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "<EMAIL>"],
            cwd=self.tmp, capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=self.tmp, capture_output=True, check=True,
        )

    def _write_spec(self, category: str, filename: str, content: str):
        spec_dir = self.tmp / ".cowork-flow" / "spec" / category
        spec_dir.mkdir(parents=True, exist_ok=True)
        (spec_dir / filename).write_text(content, encoding="utf-8")

    def test_parse_backend_rules(self):
        content = """# Backend Guidelines\n\n- 禁止硬编码密码或 API 密钥\n- Must not use print in production code\n- Should use structured logging\n"""
        self._write_spec("backend", "security.md", content)
        rules = load_spec_rules(self.tmp)
        self.assertTrue(len(rules) >= 3)
        texts = " ".join(r["text"] for r in rules)
        self.assertIn("硬编码", texts)

    def test_parse_chinese_rules(self):
        content = "禁止使用 print 进行调试输出\n"
        self._write_spec("backend", "debug.md", content)
        rules = load_spec_rules(self.tmp)
        self.assertTrue(len(rules) >= 1)
        self.assertTrue(any("print" in r["text"] for r in rules))

    def test_ignores_index_and_headings(self):
        content = "# Main Title\n\nSome normal description.\n\nNot a rule line.\n"
        self._write_spec("backend", "index.md", content)
        rules = load_spec_rules(self.tmp)
        self.assertEqual(rules, [])

    def test_validators_activated(self):
        content = "禁止 print 调试\n"
        self._write_spec("backend", "rules.md", content)
        rules = load_spec_rules(self.tmp)
        self.assertTrue(len(rules) > 0)
        total_validators = sum(len(r["validators"]) for r in rules)
        self.assertTrue(total_validators > 0)


class TestValidateSpecCoding(unittest.TestCase):
    """Tests for validate_spec_coding with real git changes."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="spec_cg_val_test_"))
        self.addCleanup(self._cleanup)
        self._init_git()

    def _cleanup(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _init_git(self):
        subprocess.run(["git", "init"], cwd=self.tmp, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "<EMAIL>"],
            cwd=self.tmp, capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=self.tmp, capture_output=True, check=True,
        )
        spec_dir = self.tmp / ".cowork-flow" / "spec" / "backend"
        spec_dir.mkdir(parents=True)
        (spec_dir / "rules.md").write_text("禁止 print 调试\n", encoding="utf-8")

    def test_no_violations_clean_code(self):
        """Passes when changed code has no rule violations."""
        (self.tmp / "main.py").write_text("import logging\nlogger = logging.getLogger(__name__)\n", encoding="utf-8")
        violations = validate_spec_coding(self.tmp, self.tmp)
        self.assertEqual(violations, [])

    def test_violation_detected(self):
        """Detects print() call when spec forbids prints."""
        (self.tmp / "main.py").write_text('print("debug info")\n', encoding="utf-8")
        violations = validate_spec_coding(self.tmp, self.tmp)
        self.assertTrue(len(violations) > 0)
        rule_ids = [v["rule_id"] for v in violations]
        self.assertTrue(any("debug" in rid for rid in rule_ids))

    def test_hardcoded_secret_detected(self):
        """Detects hard-coded password."""
        (self.tmp / ".cowork-flow" / "spec" / "backend" / "rules.md").write_text(
            "禁止硬编码密码或密钥\n", encoding="utf-8"
        )
        (self.tmp / "config.py").write_text('api_key = "sk-proj-abcdef1234567890abcdef1234567890"\n', encoding="utf-8")
        violations = validate_spec_coding(self.tmp, self.tmp)
        self.assertTrue(len(violations) > 0)

    def test_empty_except_detected(self):
        """Detects empty except handler."""
        (self.tmp / ".cowork-flow" / "spec" / "backend" / "rules.md").write_text(
            "禁止静默吞掉异常\n", encoding="utf-8"
        )
        (self.tmp / "handler.py").write_text("try:\n    do_something()\nexcept:\n    pass\n", encoding="utf-8")
        violations = validate_spec_coding(self.tmp, self.tmp)
        self.assertTrue(len(violations) > 0)

    def test_user_removes_rule_violation_goes_away(self):
        """When user removes the rule, the violation disappears."""
        spec_path = self.tmp / ".cowork-flow" / "spec" / "backend" / "rules.md"
        (self.tmp / "main.py").write_text('print("debug")\n', encoding="utf-8")
        # With rule → violation
        spec_path.write_text("禁止 print 调试\n", encoding="utf-8")
        v1 = validate_spec_coding(self.tmp, self.tmp)
        self.assertTrue(len(v1) > 0)
        # Without rule → no violation
        spec_path.write_text("# Empty spec\n", encoding="utf-8")
        v2 = validate_spec_coding(self.tmp, self.tmp)
        self.assertEqual(v2, [])


class TestCLIMode(unittest.TestCase):
    """Test CLI interface for spec coding gate."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="spec_cg_cli_test_"))
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_list_output(self):
        spec_dir = self.tmp / ".cowork-flow" / "spec" / "backend"
        spec_dir.mkdir(parents=True)
        (spec_dir / "rules.md").write_text("禁止 print\n", encoding="utf-8")
        import io
        from contextlib import redirect_stdout
        from common.spec_coding_gate import main
        buf = io.StringIO()
        with redirect_stdout(buf):
            import sys
            old_argv = sys.argv
            try:
                sys.argv = ["spec_coding_gate.py", "--list", "--repo-root", str(self.tmp), "--task-dir", str(self.tmp)]
                main()
            finally:
                sys.argv = old_argv
        output = buf.getvalue()
        self.assertIn("backend", output)
        self.assertIn("print", output)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
