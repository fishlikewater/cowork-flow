"""Spec-driven gate tests: Approach A.

User-edited spec files surface rules to the LLM via a checklist. The
workflow no longer uses a hardwired ``_NL_VALIDATORS`` registry to block the
gate on natural-language matches — only UTF-8 / IO-encoding remains a hard
block, and ``collect_machine_checks`` emits advisory (non-blocking) hints the
LLM may choose to follow.
"""
from __future__ import annotations

import importlib.machinery
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

    # ---- helpers ----

    def _seed_service(self, body: str) -> None:
        self._write("src/service.py", body)
        self._stage(".")
        self._commit("base")

    # ---- test_01: spec rules are still parseable ----

    def test_01_spec_rules_are_parsed(self) -> None:
        self._write(".cowork-flow/spec/backend/quality-guidelines.md",
                    "## 默认门禁\n"
                    "- 禁止在业务代码中 print。\n"
                    "- 禁止硬编码密码或 API key。\n"
                    "- 禁止吞掉异常（空 except）。\n"
                    "- 禁止在代码后面跟注释。\n")
        self._stage(".cowork-flow/spec/backend/quality-guidelines.md")
        self._commit("base spec")

        rules = self.vc.load_spec_rules(self.tmp)
        self.assertEqual(4, len(rules))
        # Rules must be discoverable even though no hardcoded validator matches.
        self.assertIn(
            "在代码后面跟注释",
            " ".join(r["text"] for r in rules),
            "User-authored rule '禁止在代码后面跟注释' must show up in parsed rules "
            "even without a matching python validator",
        )

    # ---- test_02: validate_coding_standards no longer hard-blocks NL ----

    def test_02_validate_coding_standards_never_blocks_on_NL(self) -> None:
        self._write(".cowork-flow/spec/backend/quality-guidelines.md",
                    "## 默认门禁\n"
                    "- 禁止硬编码密码或 API key。\n")
        self._seed_service(
            "def work():\n"
            "    password = 'supersecret'\n"
            "    try:\n"
            "        do_it()\n"
            "    except Exception:\n"
            "        pass\n",
        )

        violations = self.vc.validate_coding_standards(self.tmp)
        block_severity = [v for v in violations if v.get("severity") == "block"]
        self.assertEqual(
            [], block_severity,
            f"validate_coding_standards must NOT block on natural-language rules; "
            f"found {[v['rule_id'] for v in block_severity]}",
        )

    # ---- test_03: collect_machine_checks emits advisory hints ----

    def test_03_collect_machine_checks_emits_advisories(self) -> None:
        # Seed a clean commit, then stage a violating change.
        self._seed_service("def work():\n    return 1\n")
        self._write("src/service.py",
                    "def work():\n"
                    "    print('debug')\n"
                    "    password = 'supersecret'\n"
                    "    try:\n"
                    "        do_it()\n"
                    "    except Exception:\n"
                    "        pass\n")
        self._stage("src/service.py")

        advisories = self.vc.collect_machine_checks(self.tmp)
        self.assertGreater(len(advisories), 0)
        self.assertTrue(
            all(a["severity"] == "advisory" for a in advisories),
            "Every machine-check emission must be severity=advisory (non-blocking).",
        )
        fired = {a["rule_id"] for a in advisories}
        # At least the print + empty-except pattern triggers when present.
        self.assertIn("MACHINE-DEBUG-PRINT-001", fired)
        self.assertIn("MACHINE-SILENT-EXCEPT-001", fired)

    # ---- test_04: summary still renders checklist for LLM review ----

    def test_04_summary_renders_user_rules_for_llm_review(self) -> None:
        self._write(".cowork-flow/spec/backend/quality-guidelines.md",
                    "## 默认门禁\n"
                    "- 禁止在业务代码中 print。\n"
                    "- 禁止在代码后面跟注释。\n")
        self._seed_service(
            "import logging\ndef work():\n    logging.info('print rule test')\n",
        )
        # Stage a follow-up .py change so the summary has a backend file to key on.
        self._write("src/service.py",
                    "import logging\ndef work():\n    logging.info('changed')\n")
        self._stage("src/service.py")

        summary = self.vc.get_coding_standards_summary(self.tmp, self.tmp)
        self.assertIn("在业务代码中 print", summary)
        self.assertIn("在代码后面跟注释", summary)

    # ---- test_05: backend-vs-frontend routing still works ----

    def test_05_summary_routes_backend_vs_frontend(self) -> None:
        # Backend changed only -> frontend rules must not appear.
        self._write(".cowork-flow/spec/backend/quality-guidelines.md",
                    "## 后端门禁\n"
                    "- 禁止后端专有规则被破坏\n")
        self._write(".cowork-flow/spec/frontend/quality-guidelines.md",
                    "## 前端门禁\n"
                    "- 禁止前端专有规则被破坏\n")
        self._write("src/svc.py", "def work():\n    return 1\n")
        self._stage(".")
        self._commit("base")
        self._write("src/svc.py", "def work():\n    return 2\n")
        self._stage("src/svc.py")

        summary = self.vc.get_coding_standards_summary(self.tmp, self.tmp)
        self.assertIn("后端专有规则被破坏", summary)
        self.assertNotIn("前端专有规则被破坏", summary)

    # ---- test_06: UTF-8 hard block still enforced ----

    def test_06_utf8_hard_block_still_enforced(self) -> None:
        import os
        # Valid UTF-8 baseline commit.
        self._write("src/svc.py", "def work():\n    return 1\n")
        self._stage(".")
        self._commit("clean")
        # Overwrite with an invalid UTF-8 byte and stage it.
        raw = b"def work():\n    return '\xff'\n"
        (self.tmp / "src" / "svc.py").write_bytes(raw)
        self._stage("src/svc.py")

        violations = self.vc.validate_coding_standards(self.tmp)
        blocked = [v for v in violations if v.get("severity") == "block"]
        self.assertGreater(
            len(blocked), 0,
            "Non-UTF-8 changed files must still be a hard block (existing contract).",
        )

    # ---- test_07: empty spec produces no NL errors ----

    def test_07_empty_spec_does_not_error(self) -> None:
        self._seed_service("def work():\n    return 1\n")
        # Re-spec to a file with no rules (headers only).
        self._write(".cowork-flow/spec/backend/quality-guidelines.md",
                    "# Quality guidelines (no rules yet)\n")
        self._stage(".cowork-flow/spec/backend/quality-guidelines.md")
        self._commit("remove rules")

        rules = self.vc.load_spec_rules(self.tmp)
        self.assertEqual([], rules)
        # Must not raise.
        violations = self.vc.validate_coding_standards(self.tmp)
        self.assertEqual([], violations)


if __name__ == "__main__":
    unittest.main()
