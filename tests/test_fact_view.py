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
    build_fact_view,
    build_stage_contract,
    parse_decision_anchor,
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
                {"id": "AC-001", "text": "输出合法 JSON"},
                {"id": "AC-002", "text": "无绑定降级为 task null"},
                {"id": "AC-003", "text": "测试锁定解析行为"},
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
        self.assertEqual([], view["sessions"])
        self.assertIsNone(view["snapshot"])


class StageContractBuildTest(unittest.TestCase):
    """Budget-aware assembly: closing tag and guard rows (Scope/Gates) always
    survive, mutable=False renders the read-only variant for delegated
    sessions, and spec pointers skip directory entries."""

    TASK_PATH = ".cowork-flow/tasks/08-30-demo"

    def _build(
        self,
        whitelist,
        spec_files=(),
        anchor=None,
        mutable=True,
    ) -> str:
        return build_stage_contract(
            self.TASK_PATH,
            whitelist,
            list(spec_files),
            anchor or {"validationCommands": []},
            mutable=mutable,
        )

    def test_under_budget_keeps_exact_legacy_shape(self) -> None:
        block = self._build([{"file": "src/demo.py", "type": "file"}])
        self.assertTrue(block.endswith("</stage-contract>"))
        self.assertIn("Scope: src/demo.py [agent-mutable]", block)
        self.assertIn(
            "scope is agent-mutable (self-declared via task context add)",
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
        block = self._build(whitelist, spec_files, anchor)
        self.assertLessEqual(len(block), 1200)
        self.assertTrue(block.endswith("</stage-contract>"))
        self.assertIn("Gates: edits outside Scope are review blockers", block)
        self.assertIn(
            "scope is agent-mutable (self-declared via task context add)",
            block,
        )
        self.assertRegex(block, r"Scope: src/module-0")

    def test_extreme_over_budget_shrinks_scope_keeps_guard_rows(self) -> None:
        whitelist = [{"file": "s" * 300, "type": "file"} for _ in range(8)]
        block = self._build(
            whitelist,
            anchor={"validationCommands": ["x" * 120] * 3},
        )
        self.assertLessEqual(len(block), 1200)
        self.assertTrue(block.endswith("</stage-contract>"))
        self.assertIn("Scope: ", block)
        self.assertIn("Gates: edits outside Scope are review blockers", block)

    def test_readonly_variant_for_delegated(self) -> None:
        block = self._build(
            [{"file": "src/a.py", "type": "file"}],
            mutable=False,
        )
        self.assertIn("Scope: src/a.py [read-only]", block)
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


if __name__ == "__main__":
    unittest.main()