"""Spec-driven gate tests: Approach A.

User-edited spec files surface rules to the LLM via a checklist. The
workflow no longer uses a hardwired ``_NL_VALIDATORS`` registry to block the
gate on natural-language matches — only UTF-8 / IO-encoding remains a hard
block, and ``collect_machine_checks`` emits warn-level non-blocking hints the
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
from unittest import mock

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

    # ---- test_03: collect_machine_checks emits warning hints ----

    def test_03_collect_machine_checks_emits_warnings(self) -> None:
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

        warnings = self.vc.collect_machine_checks(self.tmp)
        self.assertGreater(len(warnings), 0)
        self.assertTrue(
            all(warning["severity"] == "warn" for warning in warnings),
            "Every machine-check emission must be severity=warn (non-blocking).",
        )
        fired = {warning["rule_id"] for warning in warnings}
        # At least the print + empty-except pattern triggers when present.
        self.assertIn("MACHINE-DEBUG-PRINT-001", fired)
        self.assertIn("MACHINE-SILENT-EXCEPT-001", fired)

    def test_machine_checks_ignore_unchanged_historical_prints(self) -> None:
        self._seed_service(
            "def work():\n"
            "    print('historical cli output')\n"
            "    return 1\n"
        )
        self._write(
            "src/service.py",
            "def work():\n"
            "    print('historical cli output')\n"
            "    return 2\n",
        )

        warnings = self.vc.collect_machine_checks(self.tmp)

        self.assertNotIn(
            "MACHINE-DEBUG-PRINT-001",
            {warning["rule_id"] for warning in warnings},
        )

    def test_machine_checks_scan_untracked_files_as_new_content(self) -> None:
        self._seed_service("def work():\n    return 1\n")
        self._write(
            "src/new_service.py",
            "def work():\n"
            "    print('new debug output')\n"
            "    return 2\n",
        )

        warnings = self.vc.collect_machine_checks(self.tmp)

        self.assertIn(
            "MACHINE-DEBUG-PRINT-001",
            {warning["rule_id"] for warning in warnings},
        )

    def test_machine_checks_allow_cli_output_prints(self) -> None:
        self._seed_service("def work():\n    return 1\n")
        self._write(
            "template/.cowork-flow/scripts/commands/demo.py",
            "def main():\n"
            "    print('user-visible command output')\n",
        )
        self._stage("template/.cowork-flow/scripts/commands/demo.py")

        warnings = self.vc.collect_machine_checks(self.tmp)

        self.assertNotIn(
            "MACHINE-DEBUG-PRINT-001",
            {warning["rule_id"] for warning in warnings},
        )

    def test_machine_checks_ignore_print_inside_string_fixture(self) -> None:
        self._seed_service("def work():\n    return 1\n")
        self._write(
            "tests/test_demo.py",
            "FIXTURE = \"    print('fixture text')\\n\"\n",
        )
        self._stage("tests/test_demo.py")

        warnings = self.vc.collect_machine_checks(self.tmp)

        self.assertNotIn(
            "MACHINE-DEBUG-PRINT-001",
            {warning["rule_id"] for warning in warnings},
        )

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


class GatePipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _bootstrap_common()
        cls.gates = _load(
            "common.gates.gates",
            GATES_DIR / "gates.py",
        )
        cls.models = sys.modules["common.gates.models"]
        cls.registry = sys.modules["common.gates.registry"]

    def tearDown(self) -> None:
        sys.modules.pop("common.gates._test_validator", None)

    def _registry_for_result(self, raw_result: object):
        validator_module = types.ModuleType("common.gates._test_validator")
        validator_module.validate = lambda: raw_result
        sys.modules["common.gates._test_validator"] = validator_module

        registry = self.gates.GateRegistry()
        registry.register_validator(
            self.models.ValidatorBinding(
                key="test_validator",
                module="_test_validator",
                function="validate",
            )
        )
        registry.register_gate(
            self.models.GateDefinition(
                id="test_gate",
                validator_key="test_validator",
                required=True,
                block_message="Test gate blocked",
            )
        )
        return registry

    def _run_test_gate(self, raw_result: object):
        registry = self._registry_for_result(raw_result)
        with mock.patch.dict(
            self.gates.STAGE_GATES,
            {"task_start": ("test_gate",)},
        ):
            return self.gates.GatePipeline(registry).run(
                self.models.GateContext(ROOT, "task_start", ROOT)
            )

    def test_missing_required_gate_blocks(self) -> None:
        original_import = __import__

        def import_without_rules(
            name: str,
            globals_: dict | None = None,
            locals_: dict | None = None,
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ):
            if name == "validate_rules" and level == 1:
                raise ImportError("required validator is unavailable")
            return original_import(name, globals_, locals_, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=import_without_rules):
            result = self.gates.GateRunner(ROOT).run("task_review", ROOT)

        self.assertTrue(result.blocked)
        self.assertEqual("GATE-LOAD-001", result.blockers[0]["rule_id"])
        self.assertEqual("task_review", result.blockers[0]["scope"])
        self.assertEqual("block", result.blockers[0]["severity"])

    def test_registry_rejects_duplicate_validator_and_gate_ids(self) -> None:
        registry = self.gates.GateRegistry()
        binding = self.models.ValidatorBinding(
            key="duplicate",
            module="_test_validator",
            function="validate",
        )
        registry.register_validator(binding)
        with self.assertRaisesRegex(
            self.registry.GateRegistryError,
            "duplicate validator key",
        ):
            registry.register_validator(binding)

        definition = self.models.GateDefinition(
            id="duplicate_gate",
            validator_key="duplicate",
            required=True,
            block_message="Blocked",
        )
        registry.register_gate(definition)
        with self.assertRaisesRegex(
            self.registry.GateRegistryError,
            "duplicate gate id",
        ):
            registry.register_gate(definition)

    def test_registry_rejects_unknown_validator_key(self) -> None:
        registry = self.gates.GateRegistry()
        with self.assertRaisesRegex(
            self.registry.GateRegistryError,
            "references unknown validator",
        ):
            registry.register_gate(
                self.models.GateDefinition(
                    id="unknown_gate",
                    validator_key="missing",
                    required=True,
                    block_message="Blocked",
                )
            )

    def test_non_list_validator_result_blocks_with_protocol_error(self) -> None:
        result = self._run_test_gate({"rule_id": "INVALID"})

        self.assertTrue(result.blocked)
        self.assertEqual("GATE-PROTOCOL-001", result.blockers[0]["rule_id"])
        self.assertEqual("test_gate", result.blockers[0]["gate_id"])

    def test_violation_missing_required_metadata_blocks(self) -> None:
        invalid_violations = (
            {"severity": "block", "message": "missing rule id"},
            {"rule_id": "TEST-001", "message": "missing severity"},
            {"rule_id": "TEST-001", "severity": "block"},
        )
        for violation in invalid_violations:
            with self.subTest(violation=violation):
                result = self._run_test_gate([violation])
                self.assertTrue(result.blocked)
                self.assertEqual(
                    "GATE-PROTOCOL-001",
                    result.blockers[0]["rule_id"],
                )

    def test_review_complete_difference_lives_in_stage_configuration(self) -> None:
        self.assertIn("implementation", self.gates.STAGE_GATES["task_review"])
        self.assertIn("implementation", self.gates.STAGE_GATES["task_complete"])
        self.assertEqual("implementation", self.gates.STAGE_GATES["task_complete"][0])
        self.assertEqual(
            {
                "id",
                "validator_key",
                "required",
                "block_message",
                "warning_message",
                "log_violations",
            },
            set(self.models.GateDefinition.__dataclass_fields__),
        )

        registry = self.gates.build_default_registry()
        executions: list[tuple[str, str]] = []

        def record_execution(definition, context):
            executions.append((context.scope, definition.id))
            return []

        with mock.patch.object(
            registry,
            "invoke",
            side_effect=record_execution,
        ):
            pipeline = self.gates.GatePipeline(registry)
            review_result = pipeline.run(
                self.models.GateContext(ROOT, "task_review", ROOT)
            )
            complete_result = pipeline.run(
                self.models.GateContext(ROOT, "task_complete", ROOT)
            )

        self.assertEqual(
            list(self.gates.STAGE_GATES["task_review"]),
            [gate_id for scope, gate_id in executions if scope == "task_review"],
        )
        self.assertEqual(
            list(self.gates.STAGE_GATES["task_complete"]),
            [gate_id for scope, gate_id in executions if scope == "task_complete"],
        )
        self.assertEqual([], review_result.violations)
        self.assertEqual([], complete_result.violations)


if __name__ == "__main__":
    unittest.main()
