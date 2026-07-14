from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"


class QualityReviewGateTest(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        self.quality_review = importlib.import_module("common.gates.quality_review")

    def _cleanup_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        for module_name in (
            "common.gates.quality_review",
            "common.gates.validate_coding_standards",
            "common.gates.coding_standards",
            "common.git.git_snapshot",
            "common",
        ):
            sys.modules.pop(module_name, None)

    @staticmethod
    def _write_entries(task_dir: Path, entries: list[dict]) -> None:
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "quality-review.jsonl").write_text(
            "".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in entries),
            encoding="utf-8",
        )

    @staticmethod
    def _valid_entries(*, files: list[str] | None = None) -> list[dict]:
        files = files or ["src/service.py"]
        return [
            {
                "id": "QR-DOD-001",
                "source": ".cowork-flow/spec/references/definition-of-done.md",
                "type": "dod",
                "status": "pass",
                "files": files,
                "evidence": (
                    "Verified acceptance coverage, scoped git status, and "
                    "required validation command evidence for src/service.py."
                ),
                "verification": [
                    "git status --porcelain=v1 -uall",
                    "python -m unittest tests.test_quality_review_gate -v",
                ],
            },
            {
                "id": "QR-001",
                "source": ".cowork-flow/spec/protocols/review.md",
                "type": "checklist",
                "status": "pass",
                "files": files,
                "evidence": (
                    "Reviewed src/service.py against review protocol quality "
                    "requirements and found no unresolved blocker."
                ),
                "verification": [
                    "python -m unittest tests.test_quality_review_gate -v",
                ],
            },
        ]

    def test_missing_quality_review_jsonl_blocks_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-14-demo"
            task_dir.mkdir(parents=True)

            violations = self.quality_review.validate_quality_review(root, task_dir)

            self.assertEqual(["QUALITY-REVIEW-MISSING-001"], [v["rule_id"] for v in violations])
            self.assertTrue(all(v["severity"] == "block" for v in violations))

    def test_invalid_jsonl_and_missing_fields_block_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-14-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "quality-review.jsonl").write_text(
                "{invalid\n{}\n",
                encoding="utf-8",
            )

            violations = self.quality_review.validate_quality_review(root, task_dir)

            rule_ids = {v["rule_id"] for v in violations}
            expected = {"QUALITY-REVIEW-JSONL-001", "QUALITY-REVIEW-SCHEMA-001"}
            self.assertEqual(expected, rule_ids & expected)

    def test_fail_status_and_vague_evidence_block_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-14-demo"
            entries = self._valid_entries()
            entries[0]["status"] = "fail"
            entries[1]["evidence"] = "已检查"
            self._write_entries(task_dir, entries)

            violations = self.quality_review.validate_quality_review(root, task_dir)

            rule_ids = {v["rule_id"] for v in violations}
            expected = {"QUALITY-REVIEW-STATUS-001", "QUALITY-REVIEW-EVIDENCE-001"}
            self.assertEqual(expected, rule_ids & expected)

    def test_valid_quality_review_passes_without_machine_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-14-demo"
            self._write_entries(task_dir, self._valid_entries())

            violations = self.quality_review.validate_quality_review(root, task_dir)

            self.assertEqual([], violations)

    def test_machine_warning_requires_matching_quality_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-14-demo"
            src = root / "src"
            src.mkdir()
            (src / "service.py").write_text("def work():\n    return 1\n", encoding="utf-8")
            self._run_git(root, "init")
            self._run_git(root, "config", "user.name", "Test User")
            self._run_git(root, "config", "user.email", "test@example.com")
            self._run_git(root, "add", "-A")
            self._run_git(root, "commit", "-m", "baseline")
            (src / "service.py").write_text(
                "def work():\n    print('debug')\n    return 1\n",
                encoding="utf-8",
            )
            self._write_entries(task_dir, self._valid_entries())

            missing_ack = self.quality_review.validate_quality_review(root, task_dir)
            self.assertEqual(
                {"QUALITY-REVIEW-MACHINE-WARNING-001"},
                {v["rule_id"] for v in missing_ack}
                & {"QUALITY-REVIEW-MACHINE-WARNING-001"},
            )

            entries = self._valid_entries()
            entries.append(
                {
                    "id": "QR-MW-001",
                    "source": "MACHINE-DEBUG-PRINT-001",
                    "type": "machine_warning",
                    "status": "acknowledged_warning",
                    "files": ["src/service.py"],
                    "evidence": (
                        "Reviewed the debug print warning in src/service.py "
                        "and explicitly accepted it for this targeted fixture."
                    ),
                    "verification": [
                        "python -m unittest tests.test_quality_review_gate -v",
                    ],
                }
            )
            self._write_entries(task_dir, entries)

            self.assertEqual([], self.quality_review.validate_quality_review(root, task_dir))

    def _run_git(self, root: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return result.stdout.strip()


if __name__ == "__main__":
    unittest.main()
