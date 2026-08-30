from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
MATRIX_FILE = ROOT / "test" / "fixtures" / "stage-contract-matrix.json"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from services.fact_view import (  # noqa: E402
    build_stage_contract,
    file_scope_whitelist,
    parse_decision_anchor,
    spec_pointer_files,
)


def _write_case_project(root: Path, case: dict) -> str:
    """Write the matrix-case task artifacts; returns the task path."""
    task_path = case.get("taskPath", ".cowork-flow/tasks/08-30-demo")
    task_dir = root / ".cowork-flow" / "tasks" / task_path.rsplit("/", 1)[-1]
    task_dir.mkdir(parents=True)
    underlying = case.get("underlying", case.get("status", "in_progress"))
    (task_dir / "task.json").write_text(
        json.dumps({"status": underlying, "title": "Demo"}), encoding="utf-8"
    )
    entries = case.get("entries") or []
    (task_dir / "implement.jsonl").write_text(
        "".join(json.dumps(entry) + "\n" for entry in entries),
        encoding="utf-8",
    )
    anchor = case.get("anchor")
    if anchor:
        lines = ["# Decision Anchor", "", "## 目标", "", anchor.get("goal", "Goal."), ""]
        acceptance = anchor.get("acceptance") or []
        if acceptance:
            lines += ["## 验收标准", ""]
            for item in acceptance:
                lines.append(f"- [ ] {item}")
            lines.append("")
        commands = anchor.get("validationCommands") or []
        if commands:
            lines += ["## 验证命令", ""]
            for cmd in commands:
                lines.append(f"- {cmd}")
            lines.append("")
        if anchor.get("scopeBoundary"):
            lines += ["## 范围边界", "", anchor["scopeBoundary"]]
        (task_dir / "decision-anchor.md").write_text(
            "\n".join(lines), encoding="utf-8"
        )
    return f".cowork-flow/tasks/{task_path.rsplit('/', 1)[-1]}"


SCOPE_EXACT_RE = None  # built per assertion


def _check_asserts(block: str, asserts: dict) -> None:
    if asserts.get("closed"):
        assert block.endswith("</stage-contract>"), "block must be closed"
    if asserts.get("maxLen"):
        assert len(block) <= asserts["maxLen"], f"budget: {len(block)} chars"
    if asserts.get("scopeMin"):
        scope = next(
            (line for line in block.splitlines() if line.startswith("Scope: ")),
            None,
        )
        assert scope is not None, "Scope row must exist"
        entries = [
            part
            for part in scope[7:].split("; ")
            if not part.startswith("(")
        ]
        assert len(entries) >= asserts["scopeMin"], "Scope must keep entries"
    if asserts.get("scopeExact"):
        assert asserts["scopeExact"] in block, f"missing scope row: {block}"
    if asserts.get("scopeContains"):
        assert asserts["scopeContains"] in block, f"missing scope text: {block}"
    if asserts.get("gates"):
        assert "Gates: edits outside Scope are review blockers" in block
    if asserts.get("gatesReadonly"):
        assert asserts["gatesReadonly"] in block
    if asserts.get("noAgentMutable"):
        assert "[agent-mutable]" not in block
    if asserts.get("noVerify"):
        assert "Verify:" not in block


class StageContractMatrixTest(unittest.TestCase):
    """Python side of the shared fixture matrix: every case must satisfy the
    same assert contract the node matrix test enforces on all three host
    lines (byte equality across hosts is locked by the node test)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.matrix = json.loads(MATRIX_FILE.read_text(encoding="utf-8"))

    def test_budget_constant_matches_matrix(self) -> None:
        from services.fact_view import STAGE_CONTRACT_BUDGET

        self.assertEqual(self.matrix["budget"], STAGE_CONTRACT_BUDGET)

    def test_every_matrix_case_satisfies_its_asserts(self) -> None:
        for case in self.matrix["cases"]:
            with self.subTest(case=case["name"]):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    task_path = _write_case_project(root, case)
                    task_dir = root / ".cowork-flow" / "tasks" / task_path.rsplit("/", 1)[-1]
                    whitelist = file_scope_whitelist(root, task_dir)
                    spec_files = spec_pointer_files(task_dir)
                    anchor_path = task_dir / "decision-anchor.md"
                    if anchor_path.is_file():
                        parsed = parse_decision_anchor(
                            anchor_path.read_text(encoding="utf-8")
                        )
                    else:
                        # Missing anchors degrade exactly like the hook path.
                        parsed = {"validationCommands": []}
                    mutable = case.get("status") != "delegated_subtask"
                    block = build_stage_contract(
                        task_path,
                        whitelist,
                        spec_files,
                        parsed,
                        mutable=mutable,
                    )

                _check_asserts(block, case.get("assert", {}))


if __name__ == "__main__":
    unittest.main()