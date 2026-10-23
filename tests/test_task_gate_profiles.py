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
    declares_light_profile,
    dev_type_blocker,
    is_light_task,
    resolve_gate_profile,
)


def _anchor(acceptance_lines: list[str], verification: str | None = None) -> str:
    body = "\n".join(acceptance_lines)
    text = f"# Decision Anchor\n\n## 目标\n\n演示。\n\n## 验收标准\n{body}\n"
    if verification is not None:
        text += f"\n## 验证命令\n\n{verification}\n"
    return text


STRICT_VERIFICATION = (
    "- 规范核对：逐条核对 `.cowork-flow/spec/backend/` 适用规范 "
    "→ pass（理由：演示）。"
)

STRICT_PLAN = "\n".join(
    [
        "# 演示实施计划",
        "",
        "**目标:** 演示",
        "",
        "## 目标",
        "演示。",
        "",
        "## 验收标准",
        "- AC-001: 演示。",
        "",
        "## 全局约束",
        "- 不扩大范围。",
        "",
        "## 文件边界",
        "- `src/a.py`",
        "",
        "## 任务",
        "### 任务 1：演示",
        "",
        "## 最终验证",
        STRICT_VERIFICATION,
        "",
    ]
)


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
        self.assertEqual(
            [
                "decision-anchor.md declares no acceptance criterion; a "
                "strict task needs at least one `- [ ] AC-xxx: ...` row"
            ],
            blockers,
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
        self.assertEqual(
            ["duplicate acceptance criterion id(s): AC-001"], blockers
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
        self.assertEqual(
            [
                "decision-anchor.md declares no acceptance criterion; a "
                "strict task needs at least one `- [ ] AC-xxx: ...` row"
            ],
            blockers,
        )
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

    def test_light_strict_task_is_exempt(self) -> None:
        """The light profile declares no dev type by design."""
        self.assertEqual(
            [],
            dev_type_blocker(
                {"meta": {"gateProfile": "strict", "taskType": "tiny"}}
            ),
        )

    def test_legacy_tiny_task_is_not_exempt_here(self) -> None:
        """Legacy tasks are filtered by the caller; the blocker itself must
        not invent a second exemption path for them."""
        self.assertEqual(
            1, len(dev_type_blocker({"meta": {"taskType": "tiny"}}))
        )


class DeclaresLightProfileTest(unittest.TestCase):
    """Field-level reading of `taskType`/`task_type`, wherever it is written."""

    def test_reads_every_known_field_location(self) -> None:
        cases = (
            {"taskType": "tiny"},
            {"task_type": "tiny"},
            {"meta": {"taskType": "tiny"}},
            {"meta": {"task_type": "tiny"}},
        )
        for task_data in cases:
            with self.subTest(task_data=task_data):
                self.assertTrue(declares_light_profile(task_data))

    def test_value_is_case_insensitive(self) -> None:
        self.assertTrue(declares_light_profile({"meta": {"taskType": "Tiny"}}))

    def test_value_comparison_keeps_the_legacy_exactness(self) -> None:
        """No strip: widening the value match would silently reclassify
        existing metadata, so the field-level reading stays byte-exact."""
        self.assertFalse(
            declares_light_profile({"meta": {"taskType": " tiny "}})
        )
        self.assertFalse(declares_light_profile({"meta": {"taskType": "tinyx"}}))

    def test_non_tiny_or_absent_values_are_false(self) -> None:
        cases = (
            {},
            {"meta": {}},
            {"meta": {"taskType": None}},
            {"meta": {"gateProfile": "strict"}},
            {"meta": {"taskType": "small"}},
            {"meta": "tiny"},
        )
        for task_data in cases:
            with self.subTest(task_data=task_data):
                self.assertFalse(declares_light_profile(task_data))

    def test_non_mapping_input_is_false(self) -> None:
        self.assertFalse(declares_light_profile(None))
        self.assertFalse(declares_light_profile(["tiny"]))


class IsLightTaskTest(unittest.TestCase):
    """Light = strict plus the marker. The profile half is not optional."""

    def test_strict_with_the_marker_is_light(self) -> None:
        self.assertTrue(
            is_light_task({"meta": {"gateProfile": "strict", "taskType": "tiny"}})
        )

    def test_the_marker_alone_is_not_light(self) -> None:
        """A pre-strict tiny task keeps its legacy behaviour everywhere the
        light profile would otherwise loosen a gate."""
        self.assertFalse(is_light_task({"meta": {"taskType": "tiny"}}))

    def test_strict_without_the_marker_is_not_light(self) -> None:
        self.assertFalse(
            is_light_task({"meta": {"gateProfile": "strict"}})
        )
        self.assertFalse(
            is_light_task({"meta": {"gateProfile": "strict", "taskType": "small"}})
        )


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
        task_type: str | None = "tiny",
        verification: str | None = None,
        plan_text: str | None = None,
    ) -> Path:
        task_dir = root / ".cowork-flow" / "tasks" / "10-09-demo"
        task_dir.mkdir(parents=True)
        meta: dict = {}
        if task_type is not None:
            meta["taskType"] = task_type
        if gate_profile is not None:
            meta["gateProfile"] = gate_profile
        if plan_text is not None:
            plan_path = root / ".cowork-flow" / "plans" / "demo.md"
            plan_path.parent.mkdir(parents=True, exist_ok=True)
            plan_path.write_text(plan_text, encoding="utf-8")
            meta["planFile"] = ".cowork-flow/plans/demo.md"
        (task_dir / "task.json").write_text(
            json.dumps(
                {"status": "planning", "dev_type": dev_type, "meta": meta},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (task_dir / "decision-anchor.md").write_text(
            _anchor(acceptance_lines, verification), encoding="utf-8"
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
                task_type=None,
            )

        self.assertTrue(
            any("declares no acceptance criterion" in b for b in blockers),
            blockers,
        )
        self.assertTrue(
            any("declares no dev_type" in b for b in blockers), blockers
        )
        self.assertTrue(
            any("验证命令" in b and "规范核对" in b for b in blockers), blockers
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

    def test_strict_non_light_valid_artifacts_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            blockers = self._blockers(
                Path(temp_dir),
                gate_profile="strict",
                dev_type="backend",
                acceptance_lines=["- [ ] AC-001: 真标准"],
                task_type=None,
                verification=STRICT_VERIFICATION,
                plan_text=STRICT_PLAN,
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

    def test_light_task_skips_the_dev_type_blocker(self) -> None:
        """strict + tiny with no dev_type is startable; the fixture would
        otherwise be blocked, so the marker is the only difference."""
        with tempfile.TemporaryDirectory() as temp_dir:
            blockers = self._blockers(
                Path(temp_dir),
                gate_profile="strict",
                dev_type=None,
                acceptance_lines=["- [ ] AC-001: 真标准"],
            )

        self.assertEqual((), blockers)

    def test_light_task_still_requires_acceptance_rows(self) -> None:
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

    def test_strict_non_light_task_without_dev_type_still_blocks(self) -> None:
        """The exemption boundary: without the marker the dev_type gate
        applies exactly as before."""
        with tempfile.TemporaryDirectory() as temp_dir:
            blockers = self._blockers(
                Path(temp_dir),
                gate_profile="strict",
                dev_type=None,
                acceptance_lines=["- [ ] AC-001: 真标准"],
                task_type=None,
                verification=STRICT_VERIFICATION,
                plan_text=STRICT_PLAN,
            )

        self.assertEqual(
            (
                "strict task declares no dev_type; pass --type <dev-type> at "
                "creation (or backfill it on a planning task)",
            ),
            blockers,
        )

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
        self.assertTrue(
            any("实施计划" in b for b in blockers), blockers
        )
        self.assertTrue(
            any("规范核对" in b for b in blockers), blockers
        )

    def test_created_light_task_persists_the_marker_and_starts(self) -> None:
        """The creation entry point is the only way in, so it has to write the
        marker — and a task created that way is startable without a plan file
        or a dev_type once its acceptance rows exist."""
        creation = importlib.import_module("services.task_creation")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = creation.TaskCreationService(root).create(
                creation.TaskCreationRequest(
                    title="轻量演示",
                    slug="light-demo",
                    assignee="codex",
                    priority="P2",
                    task_type="tiny",
                    created_at="2026-10-10",
                    date_prefix="10-10",
                )
            ).task_dir
            task_data = json.loads(
                (task_dir / "task.json").read_text(encoding="utf-8")
            )
            anchor_path = task_dir / "decision-anchor.md"
            anchor_path.write_text(
                "# Decision Anchor\n\n## 目标\n\n演示。\n\n"
                "## 验收标准\n- [ ] AC-001: 真标准\n",
                encoding="utf-8",
            )
            (task_dir / "implement.jsonl").write_text(
                json.dumps({"file": "src/a.py", "type": "planned-file"}) + "\n",
                encoding="utf-8",
            )

            self.assertTrue(is_light_task(task_data))
            blockers = self.TaskContextService(root).start_blockers(task_dir)

        self.assertEqual("tiny", task_data["meta"]["taskType"])
        self.assertEqual("strict", task_data["meta"]["gateProfile"])
        self.assertNotIn("planFile", task_data.get("meta", {}))
        self.assertEqual((), blockers)

    def test_creation_without_the_marker_stays_non_light(self) -> None:
        """The marker is opt-in: omitting it must not accidentally produce a
        light task, or the exemption would be free again."""
        creation = importlib.import_module("services.task_creation")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = creation.TaskCreationService(root).create(
                creation.TaskCreationRequest(
                    title="普通演示",
                    slug="plain-demo",
                    assignee="codex",
                    priority="P2",
                    created_at="2026-10-10",
                    date_prefix="10-10",
                )
            ).task_dir
            task_data = json.loads(
                (task_dir / "task.json").read_text(encoding="utf-8")
            )

        self.assertFalse(declares_light_profile(task_data))
        self.assertFalse(is_light_task(task_data))
        self.assertNotIn("taskType", task_data.get("meta", {}))
        self.assertEqual(GATE_PROFILE_STRICT, resolve_gate_profile(task_data))
        self.assertEqual(
            {"gateProfile": "strict", "planReadyRequired": True},
            task_data["meta"],
        )


if __name__ == "__main__":
    unittest.main()
