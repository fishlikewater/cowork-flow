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

from services.context_paths import DEFAULT_SCOPE_RULES  # noqa: E402
from services.fact_view import (  # noqa: E402
    STAGE_CONTRACT_BUDGET,
    STAGE_CONTRACT_SCOPE_LIMIT,
    STAGE_CONTRACT_SPECS_LIMIT,
    STAGE_CONTRACT_VERIFY_LIMIT,
    build_stage_contract,
    file_scope_whitelist,
    parse_decision_anchor,
    spec_digest_items,
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
        self.assertEqual(self.matrix["budget"], STAGE_CONTRACT_BUDGET)

    def test_default_rules_match_fact_view_constants(self) -> None:
        """The embedded defaults and the fact_view budgets are one contract:
        the render path falls back to the constants when scope-rules.json is
        absent, so a divergence would make the live budget depend on which
        file happens to exist."""
        constants = {
            "budget": STAGE_CONTRACT_BUDGET,
            "scopeLimit": STAGE_CONTRACT_SCOPE_LIMIT,
            "specLimit": STAGE_CONTRACT_SPECS_LIMIT,
            "verifyLimit": STAGE_CONTRACT_VERIFY_LIMIT,
        }
        for key, constant in constants.items():
            with self.subTest(limit=key):
                self.assertEqual(
                    constant, DEFAULT_SCOPE_RULES["stageContract"][key]
                )

    def test_worst_case_keeps_verify_row(self) -> None:
        """Worst realistic input under the shipped defaults: Verify is the
        first row _fit_stage_contract drops, so it must survive at full
        capacity — a dropped Verify row means declared commands silently
        disappear from the prompt."""
        spec_paths = [
            f".cowork-flow/spec/backend/guide-{i}-{'y' * 20}.md" for i in range(4)
        ]
        case = {
            "status": "in_progress",
            "entries": [
                {"file": f"src/module-{i}/{'p' * 70}.py", "reason": "long"}
                for i in range(8)
            ]
            + [{"file": path, "reason": "spec"} for path in spec_paths],
            "anchor": {"validationCommands": ["c" * 120] * 10},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_path = _write_case_project(root, case)
            task_dir = root / ".cowork-flow" / "tasks" / task_path.rsplit("/", 1)[-1]
            for path in spec_paths:
                spec_file = root / path
                spec_file.parent.mkdir(parents=True, exist_ok=True)
                spec_file.write_text(
                    "\n".join(
                        f"## 章节 {i}-{'z' * 30}\n\n- 正文\n" for i in range(6)
                    ),
                    encoding="utf-8",
                )
            whitelist = file_scope_whitelist(root, task_dir)
            spec_files = spec_pointer_files(task_dir)
            parsed = parse_decision_anchor(
                (task_dir / "decision-anchor.md").read_text(encoding="utf-8")
            )
            block = build_stage_contract(
                task_path,
                whitelist,
                spec_files,
                parsed,
                digests=spec_digest_items(root, spec_files),
            )
        self.assertIn("Verify:", block)
        self.assertLessEqual(len(block), STAGE_CONTRACT_BUDGET)

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
                    budget = case.get("budget", self.matrix["budget"])
                    block = build_stage_contract(
                        task_path,
                        whitelist,
                        spec_files,
                        parsed,
                        mutable=mutable,
                        rules={"stageContract": {"budget": budget}},
                    )

                assert_def = dict(case.get("assert", {}))
                # The length assertion tracks the budget the case renders
                # under, so it cannot drift from the shipped value.
                assert_def.setdefault("maxLen", budget)
                _check_asserts(block, assert_def)


if __name__ == "__main__":
    unittest.main()