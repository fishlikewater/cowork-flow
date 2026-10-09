from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = (
    Path(__file__).resolve().parents[1]
    / "template"
    / ".cowork-flow"
    / "scripts"
)
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from services.task_gate_profiles import (  # noqa: E402
    GATE_PROFILE_LEGACY,
    GATE_PROFILE_STRICT,
    acceptance_row_blockers,
    dev_type_blocker,
    resolve_gate_profile,
)


def _anchor(acceptance_lines: list[str]) -> str:
    body = "\n".join(acceptance_lines)
    return f"# Decision Anchor\n\n## 目标\n\n演示。\n\n## 验收标准\n{body}\n"


class ResolveGateProfileTest(unittest.TestCase):
    def test_marked_task_is_strict(self) -> None:
        self.assertEqual(
            GATE_PROFILE_STRICT,
            resolve_gate_profile({"meta": {"gateProfile": "strict"}}),
        )

    def test_unmarked_task_is_legacy(self) -> None:
        self.assertEqual(GATE_PROFILE_LEGACY, resolve_gate_profile({}))
        self.assertEqual(
            GATE_PROFILE_LEGACY,
            resolve_gate_profile({"meta": {}}),
        )
        self.assertEqual(
            GATE_PROFILE_LEGACY,
            resolve_gate_profile({"meta": {"planFile": "x.md"}}),
        )

    def test_unknown_marker_is_legacy(self) -> None:
        self.assertEqual(
            GATE_PROFILE_LEGACY,
            resolve_gate_profile({"meta": {"gateProfile": "whatever"}}),
        )

    def test_marker_is_case_and_space_insensitive(self) -> None:
        self.assertEqual(
            GATE_PROFILE_STRICT,
            resolve_gate_profile({"meta": {"gateProfile": " STRICT "}}),
        )


class AcceptanceRowBlockersTest(unittest.TestCase):
    def test_empty_section_blocks(self) -> None:
        blockers = acceptance_row_blockers(_anchor([]))
        self.assertEqual(1, len(blockers))
        self.assertIn("declares no acceptance criterion", blockers[0])

    def test_prose_only_section_blocks(self) -> None:
        blockers = acceptance_row_blockers(
            _anchor(["验收标准见计划文件。"])
        )
        self.assertIn("declares no acceptance criterion", blockers[0])

    def test_valid_rows_pass(self) -> None:
        self.assertEqual(
            [],
            acceptance_row_blockers(
                _anchor(
                    [
                        "- [ ] AC-001: 输出合法 JSON",
                        "- [x] AC-002: 兼容路径可查",
                    ]
                )
            ),
        )

    def test_duplicate_ids_block(self) -> None:
        blockers = acceptance_row_blockers(
            _anchor(
                [
                    "- [ ] AC-001: 第一条",
                    "- [ ] AC-001: 重复",
                ]
            )
        )
        self.assertTrue(
            any("duplicate acceptance criterion id" in b for b in blockers),
            blockers,
        )
        self.assertIn("AC-001", blockers[0])

    def test_malformed_list_row_blocks(self) -> None:
        blockers = acceptance_row_blockers(
            _anchor(["- [ ] NO-ID: 少了 AC 前缀"])
        )
        self.assertTrue(
            any("not AC rows" in b for b in blockers), blockers
        )

    def test_rows_outside_the_section_are_ignored(self) -> None:
        text = (
            "# Decision Anchor\n\n## 目标\n\n演示。\n\n"
            "## 验收标准\n\n- [ ] AC-001: 真标准\n\n"
            "## 被拒方案\n\n- [ ] AC-999: 这里不是验收标准\n"
        )
        self.assertEqual([], acceptance_row_blockers(text))

    def test_missing_section_blocks_as_empty(self) -> None:
        blockers = acceptance_row_blockers("# Decision Anchor\n\n## 目标\n\n演示。\n")
        self.assertIn("declares no acceptance criterion", blockers[0])


class DevTypeBlockerTest(unittest.TestCase):
    def test_declared_dev_type_passes(self) -> None:
        self.assertEqual([], dev_type_blocker({"dev_type": "backend"}))

    def test_absent_dev_type_blocks(self) -> None:
        self.assertEqual(1, len(dev_type_blocker({})))

    def test_null_dev_type_blocks(self) -> None:
        self.assertEqual(1, len(dev_type_blocker({"dev_type": None})))

    def test_blank_dev_type_blocks(self) -> None:
        self.assertEqual(1, len(dev_type_blocker({"dev_type": "  "})))


class StartGateIntegrationTest(unittest.TestCase):
    """The gate is chosen per task: strict tasks get the new blockers,
    unmarked tasks keep exactly the old ones."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.TaskContextService = importlib.import_module(
            "services.task_context"
        ).TaskContextService

    def _task(
        self,
        root: Path,
        *,
        gate_profile: str | None,
        dev_type: str | None,
        acceptance_lines: list[str],
    ) -> Path:
        task_dir = root / ".cowork-flow" / "tasks" / "10-09-demo"
        task_dir.mkdir(parents=True)
        meta: dict = {"taskType": "tiny"}
        if gate_profile is not None:
            meta["gateProfile"] = gate_profile
        (task_dir / "task.json").write_text(
            json.dumps(
                {"status": "planning", "dev_type": dev_type, "meta": meta},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (task_dir / "decision-anchor.md").write_text(
            _anchor(acceptance_lines), encoding="utf-8"
        )
        (task_dir / "implement.jsonl").write_text(
            json.dumps({"file": "src/a.py", "type": "planned-file"}) + "\n",
            encoding="utf-8",
        )
        return task_dir

    def _blockers(self, root: Path, **kwargs) -> tuple[str, ...]:
        task_dir = self._task(root, **kwargs)
        return self.TaskContextService(root).start_blockers(task_dir)

    def test_strict_empty_acceptance_and_no_dev_type_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            blockers = self._blockers(
                Path(temp_dir),
                gate_profile="strict",
                dev_type=None,
                acceptance_lines=[],
            )

        self.assertTrue(
            any("declares no acceptance criterion" in b for b in blockers),
            blockers,
        )
        self.assertTrue(
            any("declares no dev_type" in b for b in blockers), blockers
        )

    def test_strict_valid_acceptance_and_dev_type_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            blockers = self._blockers(
                Path(temp_dir),
                gate_profile="strict",
                dev_type="backend",
                acceptance_lines=["- [ ] AC-001: 真标准"],
            )

        self.assertEqual((), blockers)

    def test_legacy_task_keeps_the_old_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            blockers = self._blockers(
                Path(temp_dir),
                gate_profile=None,
                dev_type=None,
                acceptance_lines=[],
            )

        self.assertEqual((), blockers)

    def test_created_task_is_strict_and_gated(self) -> None:
        """A created task is strict, and the anchor skeleton a bound plan
        generates is no longer startable — it must be filled in first."""
        creation = importlib.import_module("services.task_creation")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plans_dir = root / ".cowork-flow" / "plans"
            plans_dir.mkdir(parents=True)
            plan_path = plans_dir / "2026-10-09-strict-demo.md"
            plan_path.write_text(
                "**目标:** 严格门禁演示\n", encoding="utf-8"
            )

            task_dir = creation.TaskCreationService(root).create(
                creation.TaskCreationRequest(
                    title="严格门禁",
                    slug="strict-demo",
                    assignee="codex",
                    priority="P2",
                    from_plan=plan_path,
                    created_at="2026-10-09",
                    date_prefix="10-09",
                )
            ).task_dir
            task_data = json.loads(
                (task_dir / "task.json").read_text(encoding="utf-8")
            )
            anchor_text = (task_dir / "decision-anchor.md").read_text(
                encoding="utf-8"
            )
            blockers = self.TaskContextService(root).start_blockers(task_dir)

        self.assertEqual("strict", task_data["meta"]["gateProfile"])
        self.assertNotIn("- [ ] \n", anchor_text)
        self.assertTrue(
            any("declares no acceptance criterion" in b for b in blockers),
            blockers,
        )
        self.assertTrue(
            any("declares no dev_type" in b for b in blockers), blockers
        )


if __name__ == "__main__":
    unittest.main()
