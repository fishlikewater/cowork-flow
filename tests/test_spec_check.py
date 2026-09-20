from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "template" / ".cowork-flow" / "scripts"

PY = sys.executable


def _spec(root: Path, relative: str, text: str) -> Path:
    path = root / ".cowork-flow" / "spec" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class SpecCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
            self.addCleanup(sys.path.remove, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        module = importlib.import_module("services.spec_check")
        self.run_checks = module.run_checks
        self.SpecCheckError = module.SpecCheckError
        self.normalized_one_line = module.normalized_one_line
        self.EDIT_PHASE_TIMEOUT = module.EDIT_PHASE_TIMEOUT

    def _cleanup_imports(self) -> None:
        for module_name in (
            "services.spec_check",
            "infra.paths",
        ):
            sys.modules.pop(module_name, None)

    def test_pass_and_violation_are_distinct_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _spec(
                root,
                "backend/ok.md",
                "---\n"
                "checks:\n"
                f"  - cmd: \"{PY}\" -c \"import sys; sys.exit(0)\"\n"
                "---\n\n# ok\n",
            )
            _spec(
                root,
                "backend/bad.md",
                "---\n"
                "checks:\n"
                f"  - cmd: \"{PY}\" -c \"import sys; sys.exit(3)\"\n"
                "---\n\n# bad\n",
            )
            report = self.run_checks(root, phase="lifecycle")
            by_status = {r["status"] for r in report["results"]}
            self.assertEqual(by_status, {"pass", "violation"})
            violation = next(r for r in report["results"] if r["status"] == "violation")
            self.assertEqual(violation["exitCode"], 3)
            self.assertEqual(
                report["summary"],
                {"pass": 1, "violation": 1, "unchecked": 0},
            )

    def test_missing_command_is_unchecked_never_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _spec(
                root,
                "backend/missing.md",
                "---\n"
                "checks:\n"
                "  - cmd: definitely-not-a-real-command-xyz --flag\n"
                "---\n",
            )
            report = self.run_checks(root, phase="lifecycle")
            self.assertEqual(len(report["results"]), 1)
            result = report["results"][0]
            self.assertEqual(result["status"], "unchecked")
            self.assertNotEqual(result["status"], "pass")
            self.assertIn("reason", result)
            self.assertEqual(report["summary"]["violation"], 0)

    def test_lifecycle_timeout_is_unchecked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _spec(
                root,
                "backend/slow.md",
                "---\n"
                "checks:\n"
                f"  - cmd: \"{PY}\" -c \"import time; time.sleep(30)\"\n"
                "    timeout: 0.5\n"
                "---\n",
            )
            report = self.run_checks(root, phase="lifecycle")
            result = report["results"][0]
            self.assertEqual(result["status"], "unchecked")
            self.assertIn("timed out", result["reason"])

    def test_edit_phase_clamps_timeout_to_edit_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _spec(
                root,
                "backend/slow-edit.md",
                "---\n"
                "checks:\n"
                f"  - cmd: \"{PY}\" -c \"import time; time.sleep(30)\"\n"
                "    timeout: 60\n"
                "    when: edit\n"
                "    files: src/\n"
                "---\n",
            )
            report = self.run_checks(
                root, phase="edit", changed_files=["src/a.py"]
            )
            result = report["results"][0]
            self.assertEqual(result["status"], "unchecked")
            self.assertIn("timed out", result["reason"])
            self.assertIn(f"{self.EDIT_PHASE_TIMEOUT:g}", result["reason"])

    def test_edit_phase_files_filter_directory_and_extension(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _spec(
                root,
                "backend/prefix.md",
                "---\n"
                "checks:\n"
                f"  - cmd: \"{PY}\" -c \"print('prefix-ran')\"\n"
                "    files: src/\n"
                "    when: edit\n"
                "---\n",
            )
            _spec(
                root,
                "backend/ext.md",
                "---\n"
                "checks:\n"
                f"  - cmd: \"{PY}\" -c \"print('ext-ran')\"\n"
                "    files: \"*.py\"\n"
                "    when: edit\n"
                "---\n",
            )
            hit = self.run_checks(
                root, phase="edit", changed_files=["src/deep/a.py"]
            )
            self.assertEqual(len(hit["results"]), 2)

            miss = self.run_checks(
                root, phase="edit", changed_files=["docs/readme.ts"]
            )
            self.assertEqual(len(miss["results"]), 0)

    def test_edit_phase_skips_lifecycle_only_decls_without_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _spec(
                root,
                "backend/lifecycle-only.md",
                "---\n"
                "checks:\n"
                f"  - cmd: \"{PY}\" -c \"print('lifecycle')\"\n"
                "    when: lifecycle\n"
                "---\n",
            )
            edit = self.run_checks(root, phase="edit", changed_files=["src/a.py"])
            self.assertEqual(len(edit["results"]), 0)
            lifecycle = self.run_checks(root, phase="lifecycle")
            self.assertEqual(len(lifecycle["results"]), 1)

    def test_unsupported_glob_form_is_parse_error_not_executed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _spec(
                root,
                "backend/glob.md",
                "---\n"
                "checks:\n"
                f"  - cmd: \"{PY}\" -c \"print('should-not-run')\"\n"
                "    files: src/**/*.ts\n"
                "---\n",
            )
            report = self.run_checks(root, phase="lifecycle")
            self.assertEqual(len(report["results"]), 0)
            self.assertEqual(len(report["parseErrors"]), 1)
            self.assertIn("unsupported files form", report["parseErrors"][0]["error"])

    def test_excluded_machine_subdirs_are_not_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _spec(
                root,
                "contracts/should-not-run.md",
                "---\n"
                "checks:\n"
                f"  - cmd: \"{PY}\" -c \"import sys; sys.exit(1)\"\n"
                "---\n",
            )
            report = self.run_checks(root, phase="lifecycle")
            self.assertEqual(len(report["results"]), 0)

    def test_spec_without_frontmatter_is_clean_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _spec(root, "backend/plain.md", "# 规范\n\n## 目标\n\n- 稳定\n")
            report = self.run_checks(root, phase="lifecycle")
            self.assertEqual(report["results"], [])
            self.assertEqual(report["parseErrors"], [])

    def test_normalized_one_line_is_single_line_and_names_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _spec(
                root,
                "backend/one.md",
                "---\n"
                "checks:\n"
                f"  - cmd: \"{PY}\" -c \"import sys; print('boom-line'); sys.exit(1)\"\n"
                "---\n",
            )
            report = self.run_checks(root, phase="lifecycle")
            line = self.normalized_one_line(report)
            self.assertEqual(len(line.splitlines()), 1)
            self.assertIn("backend/one.md", line)
            self.assertIn("boom-line", line)
            self.assertNotIn("\n", line)

    def test_edit_phase_files_filter_multi_value_quoted_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _spec(
                root,
                "backend/multi.md",
                "---\n"
                "checks:\n"
                f"  - cmd: \"{PY}\" -c \"print('multi-ran')\"\n"
                "    files: \"src/\", \"lib/\"\n"
                "    when: edit\n"
                "---\n",
            )
            hit = self.run_checks(
                root, phase="edit", changed_files=["src/a.py"]
            )
            self.assertEqual(len(hit["results"]), 1)
            hit_lib = self.run_checks(
                root, phase="edit", changed_files=["lib/b.py"]
            )
            self.assertEqual(len(hit_lib["results"]), 1)
            miss = self.run_checks(
                root, phase="edit", changed_files=["docs/readme.ts"]
            )
            self.assertEqual(len(miss["results"]), 0)

    def test_edit_checks_throttle_not_consumed_when_executor_crashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _spec(
                root,
                "backend/edit-gate.md",
                "---\n"
                "checks:\n"
                f"  - cmd: \"{PY}\" -c \"print('never-runs')\"\n"
                "    when: edit\n"
                "    files: src/\n"
                "---\n",
            )
            module = importlib.import_module("services.spec_check")
            calls: list[list[str]] = []

            def crashing_run_checks(repo_root, *, phase, changed_files=None, **_):
                calls.append(list(changed_files or []))
                raise RuntimeError("executor crashed")

            original = module.run_checks
            module.run_checks = crashing_run_checks
            try:
                first = module.run_edit_checks(root, "src/a.py", now=1000.0)
                retry = module.run_edit_checks(root, "src/a.py", now=1005.0)
            finally:
                module.run_checks = original
            self.assertEqual(first, "")
            self.assertEqual(retry, "")
            self.assertEqual(len(calls), 2)
            throttle_path = root / ".cowork-flow" / ".runtime" / "spec-edit-throttle.json"
            self.assertFalse(throttle_path.exists())

    def test_edit_checks_throttle_same_file_within_interval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _spec(
                root,
                "backend/edit-gate.md",
                "---\n"
                "checks:\n"
                f"  - cmd: \"{PY}\" -c \"import sys; print('edit-boom'); sys.exit(1)\"\n"
                "    when: edit\n"
                "    files: src/\n"
                "---\n",
            )
            module = importlib.import_module("services.spec_check")
            first = module.run_edit_checks(root, "src/a.py", now=1000.0)
            self.assertIn("edit-boom", first)
            throttled = module.run_edit_checks(root, "src/a.py", now=1005.0)
            self.assertEqual("", throttled)
            again = module.run_edit_checks(root, "src/a.py", now=1011.0)
            self.assertIn("edit-boom", again)

    def test_edit_checks_match_absolute_paths_repo_relatively(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            _spec(
                root,
                "backend/edit-gate.md",
                "---\n"
                "checks:\n"
                f"  - cmd: \"{PY}\" -c \"import sys; print('abs-boom'); sys.exit(1)\"\n"
                "    when: edit\n"
                "    files: src/\n"
                "---\n",
            )
            module = importlib.import_module("services.spec_check")
            line = module.run_edit_checks(
                root, str(root / "src" / "deep" / "a.py"), throttled=False
            )
            self.assertIn("abs-boom", line)

    def test_edit_checks_silent_when_no_declaration_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module = importlib.import_module("services.spec_check")
            self.assertEqual(
                module.run_edit_checks(root, "docs/readme.ts", throttled=False),
                "",
            )


if __name__ == "__main__":
    unittest.main()
