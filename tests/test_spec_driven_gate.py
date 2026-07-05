"""Spec-driven gate tests: user-edited spec files drive review/complete gates."""
from __future__ import annotations

import importlib.machinery
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
GATES_DIR = TEMPLATE / ".cowork-flow" / "scripts" / "common" / "gates"


def _load(name: str, file_path: Path) -> types.ModuleType:
    # Pre-register the module in ``sys.modules`` BEFORE executing it, so
    # that dataclasses (which resolve their annotation globals at class
    # creation time) can find their own module globals.
    loader = importlib.machinery.SourceFileLoader(name, str(file_path))
    mod = types.ModuleType(name)
    mod.__package__ = name.rsplit('.', 1)[0] if '.' in name else ''
    mod.__module__ = name
    mod.__name__ = name
    mod.__loader__ = loader
    mod.__file__ = str(file_path)
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


def _bootstrap_common() -> types.ModuleType:
    sys.path.insert(0, str(TEMPLATE / ".cowork-flow" / "scripts"))
    common = types.ModuleType("common")
    common.__path__ = [str(TEMPLATE / ".cowork-flow" / "scripts" / "common")]
    sys.modules["common"] = common

    git_dir = TEMPLATE / ".cowork-flow" / "scripts" / "common" / "git"
    common_git = types.ModuleType("common.git")
    common_git.__path__ = [str(git_dir)]
    sys.modules["common.git"] = common_git
    common.git = common_git
    for f in ("git_snapshot", "git_context", "git_context"):
        src = _load(f"common.git.{f}", git_dir / f"{f}.py")
        setattr(common_git, f, src)
        sys.modules[f"common.git.{f}"] = src

    core_dir = TEMPLATE / ".cowork-flow" / "scripts" / "common" / "core"
    common_core = types.ModuleType("common.core")
    common_core.__path__ = [str(core_dir)]
    sys.modules["common.core"] = common_core
    common.core = common_core
    for f in ("execution_context", "developer", "config", "paths", "files"):
        src = _load(f"common.core.{f}", core_dir / f"{f}.py")
        setattr(common_core, f, src)
        sys.modules[f"common.core.{f}"] = src

    cs = _load("common.gates.coding_standards", GATES_DIR / "coding_standards.py")
    sys.modules["common.gates.coding_standards"] = cs
    cg = types.ModuleType("common.gates")
    cg.__path__ = [str(GATES_DIR)]
    sys.modules["common.gates"] = cg
    cg.coding_standards = cs

    vc = _load("common.gates.validate_coding_standards", GATES_DIR / "validate_coding_standards.py")
    sys.modules["common.gates.validate_coding_standards"] = vc
    cg.validate_coding_standards = vc
    return vc


class SpecDrivenGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vc = _bootstrap_common()

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="specgate-"))
        shutil.copytree(str(TEMPLATE / ".cowork-flow" / "spec"),
                        str(self.tmp / ".cowork-flow" / "spec"),
                        dirs_exist_ok=True)
        subprocess.run(["git", "init", "-q"], cwd=self.tmp, check=True)
        subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=self.tmp, check=True)
        subprocess.run(["git", "config", "user.name", "A"], cwd=self.tmp, check=True)

    def _write(self, rel: str, text: str) -> None:
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def _stage(self, *rels: str) -> None:
        subprocess.run(["git", "add", *rels], cwd=self.tmp, check=True)

    def _commit(self, msg: str) -> None:
        subprocess.run(["git", "commit", "-q", "-m", msg], cwd=self.tmp, check=True)

    def test_01_spec_rules_activation(self) -> None:
        # Backend spec with 3 rules -> spec parser finds 3
        self._write(".cowork-flow/spec/backend/quality-guidelines.md",
                    "## 默认门禁\n"
                    "- 禁止在业务代码中 print。\n"
                    "- 禁止硬编码密码或 API key。\n"
                    "- 禁止吞掉异常（空 except）。\n")
        self._stage(".")
        self._commit("base")

        rules = self.vc.load_spec_rules(self.tmp)
        self.assertEqual(len(rules), 3)
        self.assertTrue(all(r["validators"] for r in rules),
                        f"Some rules did not activate a validator: {rules}")

    def test_02_violations_fired(self) -> None:
        # Same spec; a violating change -> 3 spec violations
        self._write(".cowork-flow/spec/backend/quality-guidelines.md",
                    "## 默认门禁\n"
                    "- 禁止在业务代码中 print。\n"
                    "- 禁止硬编码密码或 API key。\n"
                    "- 禁止吞掉异常（空 except）。\n")
        self._write("src/service.py",
                    "import logging\ndef work():\n    logging.info('ok')\n")
        self._stage(".")
        self._commit("base")

        self._write("src/service.py",
                    "def work():\n"
                    "    print('debug')\n"
                    "    password = 'supersecret'\n"
                    "    try:\n"
                    "        do_it()\n"
                    "    except Exception:\n"
                    "        pass\n")
        self._stage("src/service.py")

        violations = self.vc.validate_coding_standards(self.tmp)
        fired = {v["rule_id"] for v in violations}
        self.assertIn("SPEC-_no_debug_prints", fired)
        self.assertIn("SPEC-_no_hardcoded_secrets", fired)
        self.assertIn("SPEC-_no_silent_except", fired)

    def test_03_user_removes_rule_violation_goes_away(self) -> None:
        # User customizes spec by removing the 'print' rule
        self._write(".cowork-flow/spec/backend/quality-guidelines.md",
                    "## 默认门禁\n"
                    "- 禁止硬编码密码或 API key。\n"
                    "- 禁止吞掉异常（空 except）。\n")
        self._write("src/service.py",
                    "import logging\ndef work():\n    logging.info('ok')\n")
        self._stage(".")
        self._commit("base")

        self._write("src/service.py",
                    "def work():\n"
                    "    print('debug')\n"
                    "    password = 'supersecret'\n"
                    "    try:\n"
                    "        do_it()\n"
                    "    except Exception:\n"
                    "        pass\n")
        self._stage("src/service.py")

        violations = self.vc.validate_coding_standards(self.tmp)
        fired = {v["rule_id"] for v in violations}
        self.assertNotIn("SPEC-_no_debug_prints", fired,
                         "After user removes the print rule, it must not fire anymore")
        self.assertIn("SPEC-_no_hardcoded_secrets", fired)
        self.assertIn("SPEC-_no_silent_except", fired)

    def test_04_user_adds_rule_violation_returns(self) -> None:
        # Customize spec back to include the print rule; a fresh violating
        # change reactivates the print rule.
        self._write(".cowork-flow/spec/backend/quality-guidelines.md",
                    "## 默认门户\n"
                    "- 禁止硬编码密码或 API key。\n"
                    "- 禁止吞掉异常（空 except）。\n")
        self._write("src/service.py",
                    "import logging\ndef work():\n    logging.info('ok')\n")
        self._stage(".")
        self._commit("base")
        self._write(".cowork-flow/spec/backend/quality-guidelines.md",
                    "## 默认门禁\n"
                    "- 禁止在业务代码中 print。\n"
                    "- 禁止硬编码密码或 API key。\n"
                    "- 禁止吞掉异常（空 except）。\n")
        self._stage(".")
        self._commit("more rules")

        self._write("src/other.py",
                    "def other():\n"
                    "    print('more debug')\n"
                    "    password = 'anothersecret'\n")
        self._stage("src/other.py")

        violations = self.vc.validate_coding_standards(self.tmp)
        fired = {v["rule_id"] for v in violations}
        self.assertIn("SPEC-_no_debug_prints", fired)
        self.assertIn("SPEC-_no_hardcoded_secrets", fired)

    def test_05_get_coding_standards_summary_contains_activated_rules(self) -> None:
        self._write(".cowork-flow/spec/backend/quality-guidelines.md",
                    "## 默认门禁\n"
                    "- 禁止在业务代码中 print。\n")
        self._write("src/service.py",
                    "import logging\ndef work():\n    logging.info('ok')\n")
        self._stage(".")
        self._commit("base")
        self._write("src/service.py",
                    "import logging\ndef work():\n    logging.info('print rule test')\n")
        self._stage("src/service.py")

        summary = self.vc.get_coding_standards_summary(self.tmp, self.tmp)
        self.assertIn("在业务代码中 print", summary.strip())


if __name__ == "__main__":
    unittest.main()
