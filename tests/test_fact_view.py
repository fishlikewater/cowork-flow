from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from services.fact_view import (  # noqa: E402
    _cut_scope_rows,
    build_fact_view,
    build_stage_contract,
    parse_decision_anchor,
    spec_entries_for_task,
    spec_pointer_files,
)

ANCHOR_TEXT = "\n".join(
    [
        "# Decision Anchor",
        "",
        "## 目标",
        "让事实视图可被机器消费。",
        "",
        "## 验收标准",
        "- [ ] AC-001: 输出合法 JSON",
        "- [ ] AC-002: 无绑定降级为 task null",
        "- [x] AC-003: 测试锁定解析行为",
        "",
        "## 被拒方案",
        "- **方案B（Node 侧实现）**: 拒绝——事实层与宿主无关",
        "- **方案C（注入全文）**: 拒绝——token 成本不可控",
        "",
        "## 验证命令",
        "- npm run test:fast",
        "- python3 -m pytest tests/ -q",
        "",
        "## 范围边界",
        "范围内: services/ only",
    ]
)


class ParseDecisionAnchorTest(unittest.TestCase):
    def test_parses_goal_acceptance_and_rejected_options(self) -> None:
        parsed = parse_decision_anchor(ANCHOR_TEXT)
        self.assertEqual("让事实视图可被机器消费。", parsed["goal"])
        self.assertEqual(
            [
                {"id": "AC-001", "text": "输出合法 JSON", "checked": False},
                {"id": "AC-002", "text": "无绑定降级为 task null", "checked": False},
                {"id": "AC-003", "text": "测试锁定解析行为", "checked": True},
            ],
            parsed["acceptanceCriteria"],
        )
        self.assertEqual(
            ["方案B（Node 侧实现）", "方案C（注入全文）"],
            parsed["rejectedOptions"],
        )
        self.assertEqual(
            ["npm run test:fast", "python3 -m pytest tests/ -q"],
            parsed["validationCommands"],
        )
        self.assertEqual("范围内: services/ only", parsed["scopeBoundary"])

    def test_degrades_to_empty_without_sections(self) -> None:
        parsed = parse_decision_anchor("# Decision Anchor\n\n没有章节。")
        self.assertEqual("", parsed["goal"])
        self.assertEqual([], parsed["acceptanceCriteria"])
        self.assertEqual([], parsed["rejectedOptions"])

    def test_goal_is_truncated(self) -> None:
        parsed = parse_decision_anchor("## 目标\n" + "x" * 500)
        self.assertEqual(300, len(parsed["goal"]))

    def test_verify_command_max_caps_parsed_commands(self) -> None:
        commands = [f"cmd-{i} " + "x" * 100 for i in range(12)]
        parsed = parse_decision_anchor(
            "## 验证命令\n" + "\n".join(f"- {command}" for command in commands)
        )
        self.assertEqual(commands[:10], parsed["validationCommands"])

    def test_spec_check_lines_are_not_validation_commands(self) -> None:
        text = "\n".join(
            [
                "## 验证命令",
                "- npm run test:fast",
                "- 规范核对：逐条核对 `.cowork-flow/spec/backend/` 适用规范 "
                "→ pass（理由：已核对）。",
                "- Spec check: clause-by-clause check against applicable "
                "`.cowork-flow/spec/backend/` rules -> not_applicable (reason: none).",
            ]
        )
        parsed = parse_decision_anchor(text)
        self.assertEqual(["npm run test:fast"], parsed["validationCommands"])

    def test_comments_in_verification_are_not_validation_commands(self) -> None:
        text = "\n".join(
            [
                "## 验证命令",
                "- npm run test:fast",
                "<!-- strict tasks: replace the placeholder before starting -->",
                "- 规范核对：逐条核对 `.cowork-flow/spec/backend/` 适用规范 "
                "→ <pass / not_applicable + 理由>。",
            ]
        )
        parsed = parse_decision_anchor(text)
        self.assertEqual(["npm run test:fast"], parsed["validationCommands"])


class BuildFactViewTest(unittest.TestCase):
    def _make_project(self, root: Path) -> Path:
        task_dir = root / ".cowork-flow" / "tasks" / "08-28-demo"
        task_dir.mkdir(parents=True)
        (task_dir / "task.json").write_text(
            json.dumps(
                {
                    "status": "in_progress",
                    "title": "Demo",
                    "meta": {"planFile": ".cowork-flow/plans/demo.md"},
                    "_state": {"revision": 3},
                }
            ),
            encoding="utf-8",
        )
        (task_dir / "decision-anchor.md").write_text(
            ANCHOR_TEXT, encoding="utf-8"
        )
        (task_dir / "implement.jsonl").write_text(
            "\n".join(
                (
                    json.dumps({"file": "src/demo.py", "reason": "main"}),
                    json.dumps(
                        {
                            "file": "src/next.py",
                            "reason": "planned",
                            "type": "planned-file",
                        }
                    ),
                    json.dumps(
                        {"file": "src/", "reason": "dir ctx", "type": "directory"}
                    ),
                )
            )
            + "\n",
            encoding="utf-8",
        )
        sessions = root / ".cowork-flow" / ".runtime" / "sessions"
        sessions.mkdir(parents=True)
        (sessions / "zcode_a.json").write_text(
            json.dumps(
                {
                    "active_task_path": ".cowork-flow/tasks/08-28-demo",
                    "scope": "main",
                    "platform": "zcode",
                    "last_seen_at": "2026-08-28T00:00:00Z",
                }
            ),
            encoding="utf-8",
        )
        # Another session bound elsewhere must not appear.
        (sessions / "codex_b.json").write_text(
            json.dumps({"active_task_path": ".cowork-flow/tasks/other"}),
            encoding="utf-8",
        )
        snapshot = root / ".cowork-flow" / ".runtime" / "state-snapshot.json"
        snapshot.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "activeTaskPath": ".cowork-flow/tasks/08-28-demo",
                    "status": "in_progress",
                    "breadcrumbKey": "in_progress",
                }
            ),
            encoding="utf-8",
        )
        return task_dir

    def test_aggregates_all_fact_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._make_project(root)

            view = build_fact_view(root, task_dir)

        self.assertEqual(1, view["schemaVersion"])
        self.assertEqual(".cowork-flow/tasks/08-28-demo", view["taskPath"])
        self.assertEqual("in_progress", view["task"]["status"])
        self.assertEqual(3, view["task"]["_state"]["revision"])
        self.assertTrue(view["decisionAnchor"]["exists"])
        self.assertEqual("让事实视图可被机器消费。", view["decisionAnchor"]["goal"])
        self.assertEqual(3, len(view["decisionAnchor"]["acceptanceCriteria"]))
        self.assertEqual(
            {"total": 3, "withEvidence": 0, "missing": ["AC-001", "AC-002", "AC-003"]},
            view["evidenceCoverage"],
        )
        self.assertEqual(2, len(view["decisionAnchor"]["rejectedOptions"]))
        # Directory entries authorize nothing: file-scope only.
        self.assertEqual(
            ["src/demo.py", "src/next.py"],
            [entry["file"] for entry in view["whitelist"]],
        )
        self.assertEqual(
            {"src/next.py": "planned-file"},
            {e["file"]: e["type"] for e in view["whitelist"] if e["type"] != "file"},
        )
        self.assertTrue(view["plan"]["bound"])
        self.assertEqual(".cowork-flow/plans/demo.md", view["plan"]["file"])
        self.assertEqual(
            ["zcode_a"],
            [session["contextKey"] for session in view["sessions"]],
        )
        self.assertEqual("in_progress", view["snapshot"]["status"])

    def test_snapshot_mismatch_is_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._make_project(root)
            snapshot = root / ".cowork-flow" / ".runtime" / "state-snapshot.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "activeTaskPath": ".cowork-flow/tasks/08-28-demo",
                        "status": "review",
                        "breadcrumbKey": "review",
                    }
                ),
                encoding="utf-8",
            )

            view = build_fact_view(root, task_dir)

        self.assertIsNone(view["snapshot"])

    def test_evidence_records_drive_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._make_project(root)
            (task_dir / "evidence.jsonl").write_text(
                json.dumps(
                    {
                        "ac": "AC-003",
                        "kind": "command",
                        "ref": "python3 -m pytest tests/test_fact_view.py -q",
                        "recordedAt": "2026-10-06",
                        "by": "probe",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            view = build_fact_view(root, task_dir)

        self.assertEqual(
            {"total": 3, "withEvidence": 1, "missing": ["AC-001", "AC-002"]},
            view["evidenceCoverage"],
        )

    def test_missing_anchor_and_plan_degrade(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "08-28-bare"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                json.dumps({"status": "planning"}), encoding="utf-8"
            )

            view = build_fact_view(root, task_dir)

        self.assertFalse(view["decisionAnchor"]["exists"])
        self.assertFalse(view["plan"]["bound"])
        self.assertIsNone(view["evidenceCoverage"])
        self.assertEqual([], view["sessions"])
        self.assertIsNone(view["snapshot"])


class StageContractBuildTest(unittest.TestCase):
    """Budget-aware assembly: closing tag and guard rows (Scope/Gates) always
    survive, mutable=False renders the read-only variant for delegated
    sessions, and spec pointers skip directory entries."""

    TASK_PATH = ".cowork-flow/tasks/08-30-demo"
    # Degradation is asserted against a pinned budget so these cases keep
    # exercising _fit_stage_contract when the shipped budget changes; 700 is
    # the smallest value that still renders the guard rows whole here. The
    # same fixture is also built unbounded, so each case proves its input
    # really is over the pinned budget instead of passing by construction.
    DEGRADE_BUDGET = 700
    UNBOUNDED_BUDGET = 10**6

    def _build(
        self,
        whitelist,
        spec_files=(),
        anchor=None,
        mutable=True,
        budget=None,
    ) -> str:
        rules = {"stageContract": {"budget": budget}} if budget else None
        return build_stage_contract(
            self.TASK_PATH,
            whitelist,
            list(spec_files),
            anchor or {"validationCommands": []},
            mutable=mutable,
            rules=rules,
        )

    def test_under_budget_keeps_exact_legacy_shape(self) -> None:
        block = self._build([{"file": "src/demo.py", "type": "file"}])
        lines = block.splitlines()
        self.assertEqual(lines[0], f'<stage-contract task="{self.TASK_PATH}">')
        self.assertEqual(lines[-1], "</stage-contract>")
        self.assertRegex(block, r"(?m)^Scope: src/demo\.py \[agent-mutable\]$")
        self.assertIn(
            "scope is agent-mutable (declare more in implement.jsonl)",
            block,
        )

    def test_over_budget_keeps_closing_and_gates(self) -> None:
        whitelist = [
            {"file": f"src/module-{i}/long-{'x' * 60}-name.py", "type": "file"}
            for i in range(8)
        ]
        spec_files = [
            f".cowork-flow/spec/backend/guide-{i}-{'y' * 30}.md"
            for i in range(4)
        ]
        anchor = {
            "validationCommands": [f"cmd {'v' * 118}" for _ in range(3)]
        }
        block = self._build(
            whitelist, spec_files, anchor, budget=self.DEGRADE_BUDGET
        )
        unbounded = self._build(
            whitelist, spec_files, anchor, budget=self.UNBOUNDED_BUDGET
        )
        self.assertGreater(len(unbounded), self.DEGRADE_BUDGET)
        self.assertLessEqual(len(block), self.DEGRADE_BUDGET)
        self.assertTrue(block.endswith("</stage-contract>"))
        self.assertIn("Gates: edits outside Scope are review blockers", block)
        self.assertIn(
            "scope is agent-mutable (declare more in implement.jsonl)",
            block,
        )
        self.assertRegex(block, r"Scope: src/module-0")

    def test_extreme_over_budget_shrinks_scope_keeps_guard_rows(self) -> None:
        whitelist = [{"file": "s" * 300, "type": "file"} for _ in range(8)]
        anchor = {"validationCommands": ["x" * 120] * 3}
        block = self._build(
            whitelist,
            anchor=anchor,
            budget=self.DEGRADE_BUDGET,
        )
        unbounded = self._build(
            whitelist,
            anchor=anchor,
            budget=self.UNBOUNDED_BUDGET,
        )
        self.assertGreater(len(unbounded), self.DEGRADE_BUDGET)
        self.assertLessEqual(len(block), self.DEGRADE_BUDGET)
        self.assertTrue(block.endswith("</stage-contract>"))
        self.assertIn("Scope: ", block)
        self.assertIn("Gates: edits outside Scope are review blockers", block)

    def test_budget_sweep_keeps_block_parseable(self) -> None:
        """Every budget must still render a block consumers can match. The
        opening tag carries the task identity and the Gates row carries the
        edit policy, so a body-wide cut would silently delete one of them
        while still "ending with the closing tag"."""
        whitelist = [{"file": "src/module-0/" + "p" * 70 + ".py", "type": "file"}]
        for budget in (1, 19, 40, 90, 120, 200, 300, 400, 3400):
            with self.subTest(budget=budget):
                block = self._build(whitelist, budget=budget)
                self.assertRegex(
                    block,
                    r'<stage-contract task="[^"]*">[\s\S]*?</stage-contract>',
                )
                self.assertIn("Scope: ", block)
                self.assertIn(
                    "Gates: edits outside Scope are review blockers", block
                )

    def test_budget_below_floor_returns_whole_block(self) -> None:
        """Below the size the fixed rows need, the block is returned whole
        and exceeds the budget: the guard rows outrank it, and the failure
        mode stays "over budget" instead of "block consumers cannot see"."""
        whitelist = [{"file": "src/module-0/" + "p" * 70 + ".py", "type": "file"}]
        block = self._build(whitelist, budget=40)
        self.assertGreater(len(block), 40)
        self.assertRegex(
            block, r'<stage-contract task="[^"]*">[\s\S]*?</stage-contract>'
        )
        self.assertIn("Scope: ", block)
        self.assertIn("Gates: edits outside Scope are review blockers", block)
        # The same input fits once the budget can hold the fixed rows.
        roomy = self._build(whitelist, budget=400)
        self.assertLessEqual(len(roomy), 400)

    def test_budget_cut_never_drops_the_scope_row_label(self) -> None:
        """A cut landing inside the entry's leading whitespace would rstrip
        the row label away, leaving a bare `Scope:` that `^Scope: (.+)$`
        consumers cannot match — a dropped guard row by another name."""
        whitelist = [{"file": " src/a.py", "type": "file"}]
        for budget in range(260, 300):
            with self.subTest(budget=budget):
                block = self._build(whitelist, budget=budget)
                self.assertRegex(block, r"(?m)^Scope: .+$")
                self.assertIn(
                    "Gates: edits outside Scope are review blockers", block
                )

    def test_budget_below_floor_never_shortens_a_long_scope_row(self) -> None:
        """The floor is not redundant with the label check. With a negative
        `room` the slice is `line[:-k]`, which keeps a long row's front —
        label included — so the label check alone would wave through a row
        chopped at the tail and still over budget. Only the floor stops
        that, by returning the block whole."""
        long_path = "src/module-0/" + "p" * 380 + ".py"
        block = self._build([{"file": long_path, "type": "file"}], budget=40)
        self.assertGreater(len(block), 40)
        self.assertIn(f"Scope: {long_path} [agent-mutable]", block)
        self.assertIn("Gates: edits outside Scope are review blockers", block)

    def test_scope_row_cut_accounts_for_every_scope_row(self) -> None:
        """The room left after the fixed rows is shared by every Scope row.
        The renderer emits exactly one, so the multi-row shape is handed to
        the helper directly: under the single-row formula the extra row's
        width overshoots the budget while both rows stay truncated."""
        lines = [
            '<stage-contract task=".cowork-flow/tasks/08-30-demo">',
            "Scope: src/" + "a" * 80 + " [agent-mutable]",
            "Scope: src/" + "b" * 80 + " [agent-mutable]",
            "Gates: " + "g" * 100,
            "</stage-contract>",
        ]
        cut = _cut_scope_rows(lines, budget=300)
        self.assertIsNotNone(cut)
        assert cut is not None
        self.assertLessEqual(len("\n".join(cut)), 300)
        self.assertEqual(
            2, sum(1 for line in cut if line.startswith("Scope: "))
        )

    def test_readonly_variant_for_delegated(self) -> None:
        block = self._build(
            [{"file": "src/a.py", "type": "file"}],
            mutable=False,
        )
        self.assertRegex(block, r"(?m)^Scope: src/a\.py \[read-only\]$")
        self.assertIn(
            "scope is inherited from the parent task (read-only reference)",
            block,
        )
        self.assertNotIn("self-declared", block)
        self.assertNotIn("[agent-mutable]", block)

    def test_spec_pointers_skip_directory_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            task_dir = Path(temp_dir) / "task"
            task_dir.mkdir()
            (task_dir / "implement.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "file": ".cowork-flow/spec/backend/index.md",
                                "reason": "backend",
                            }
                        ),
                        json.dumps(
                            {
                                "file": ".cowork-flow/spec/",
                                "type": "directory",
                                "reason": "dir",
                            }
                        ),
                        json.dumps(
                            {
                                "file": ".cowork-flow/spec/guides/index.md",
                                "reason": "guides",
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            files = spec_pointer_files(task_dir)

        self.assertEqual(
            [
                ".cowork-flow/spec/backend/index.md",
                ".cowork-flow/spec/guides/index.md",
            ],
            files,
        )


class SpecEntriesForTaskDevTypeTest(unittest.TestCase):
    """`dev_type` is what makes dev-type spec pointers appear in the reading
    list; a task that declares none must not be handed them."""

    def _task_dir(self, root: Path, dev_type: object) -> Path:
        task_dir = root / ".cowork-flow" / "tasks" / "10-09-demo"
        task_dir.mkdir(parents=True)
        payload: dict = {"status": "planning", "title": "Demo"}
        if dev_type is not None:
            payload["dev_type"] = dev_type
        (task_dir / "task.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        return task_dir

    def _files(self, root: Path, dev_type: object) -> tuple[object, list[str]]:
        task_dir = self._task_dir(root, dev_type)
        resolved, entries = spec_entries_for_task(root, task_dir)
        return resolved, [entry["file"] for entry in entries]

    def test_backend_dev_type_adds_backend_spec_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            resolved, files = self._files(root, "backend")

        self.assertEqual("backend", resolved)
        self.assertIn(".cowork-flow/spec/backend/index.md", files)

    def test_fullstack_dev_type_adds_both_packs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            resolved, files = self._files(root, "fullstack")

        self.assertEqual("fullstack", resolved)
        self.assertEqual(
            [
                ".cowork-flow/spec/backend/index.md",
                ".cowork-flow/spec/frontend/index.md",
            ],
            [
                f
                for f in files
                if f.startswith(".cowork-flow/spec/backend/")
                or f.startswith(".cowork-flow/spec/frontend/")
            ],
        )

    def test_spec_dev_type_adds_contract_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            resolved, files = self._files(root, "spec")

        self.assertEqual("spec", resolved)
        self.assertEqual(
            [
                ".cowork-flow/spec/index.md",
                ".cowork-flow/spec/contracts/index.md",
                ".cowork-flow/spec/schemas/index.md",
            ],
            [
                f
                for f in files
                if f.startswith(".cowork-flow/spec/")
                and not f.startswith(".cowork-flow/spec/guides/")
            ],
        )

    def test_absent_dev_type_yields_no_spec_pointers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            resolved, files = self._files(root, None)

        self.assertEqual(None, resolved)
        self.assertEqual(
            [
                f
                for f in files
                if f.startswith(".cowork-flow/spec/backend/")
                or f.startswith(".cowork-flow/spec/frontend/")
            ],
            [],
        )


if __name__ == "__main__":
    unittest.main()