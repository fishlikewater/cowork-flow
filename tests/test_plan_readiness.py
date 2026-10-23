from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from tests.flow_test_support import ROOT, FlowScriptTestCase


PLAN_TEXT = """# 演示实施计划

| 字段 | 内容 |
|----|------|
| **任务类型** | Normal |
| **执行策略** | Serial |
| **成功标准** | AC-001 / AC-002 |
| **最终验证** | `python -m pytest` → exit 0 |
| **主要风险** | Low |

**目标:** 演示行为。

## 目标

演示行为。

## 验收标准

- AC-001: 演示行为。
- AC-002: 演示验证。

## 全局约束

- 不扩大范围。

## 文件边界

- `AGENTS.md`

## 任务

### 任务 1：演示

**目的**
- 完成演示。

**代码事实来源**
- Read: `AGENTS.md`

**文件边界**
- Modify: `AGENTS.md`

**关键符号**
- Change: `demo`

**实现说明**
```python
value = 1
```

**测试证明**
- 断言演示行为。

**验证命令**
```bash
python -m pytest tests/test_demo.py -q
```

**完成条件**
- 命令 exit 0。

**禁止漂移**
- 不改范围。

**偏差条件**
- 测试失败时停止。

## 最终验证

规范核对：逐条核对 `.cowork-flow/spec/backend/` 适用规范 → pass（理由：演示）。
"""

ANCHOR_TEXT = """# Decision Anchor

## 目标

演示行为。

## 验收标准

- [ ] AC-001: 演示行为。
- [ ] AC-002: 演示验证。

## 验证命令

规范核对：逐条核对 `.cowork-flow/spec/backend/` 适用规范 → pass（理由：演示）。
"""

ANCHOR_TEXT_EN = """# Decision Anchor

## Goal

演示行为。

## Acceptance Criteria

- [ ] AC-001: 演示行为。
- [ ] AC-002: 演示验证。

## Verification Commands

Spec check: clause-by-clause check against `.cowork-flow/spec/backend/` applicable rules -> pass (reason: demo).
"""

TINY_TASK = """### 任务 1：演示

**文件边界**
- Modify: `AGENTS.md`

**验证命令**
```bash
python -m pytest tests/test_demo.py -q
```

**完成条件**
- 命令 exit 0。
"""


class PlanReadinessTest(FlowScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.readiness = __import__(
            "services.plan_readiness",
            fromlist=[
                "PlanReadinessError",
                "PlanReadinessService",
                "plan_ready_snapshot_blockers",
                "plan_readiness_blockers",
            ],
        )

    def _write_task(
        self,
        root: Path,
        *,
        plan_text: str = PLAN_TEXT,
        anchor_text: str = ANCHOR_TEXT,
        status: str = "planning",
        implement_text: str = '{"file": "AGENTS.md"}\n',
        task_type: str | None = None,
        language: str | None = None,
        template_source: Path | None = None,
    ) -> Path:
        template_path = (
            root / ".cowork-flow" / "templates" / "plan-template.md"
        )
        template_path.parent.mkdir(parents=True, exist_ok=True)
        source = template_source or (
            ROOT
            / "template"
            / ".cowork-flow"
            / "templates"
            / "plan-template.md"
        )
        template_path.write_bytes(source.read_bytes())
        if language is not None:
            config = root / ".cowork-flow" / "config.yaml"
            config.write_text(
                f"language: {language}\n", encoding="utf-8", newline="\n"
            )
        plan_path = root / ".cowork-flow" / "plans" / "2026-10-23-demo.md"
        plan_path.parent.mkdir(parents=True)
        plan_path.write_text(plan_text, encoding="utf-8")
        task_dir = root / ".cowork-flow" / "tasks" / "10-23-demo"
        task_dir.mkdir(parents=True)
        meta = {
            "planFile": ".cowork-flow/plans/2026-10-23-demo.md",
            "gateProfile": "strict",
            "planReadyRequired": True,
        }
        if task_type:
            meta["taskType"] = task_type
        (task_dir / "task.json").write_text(
            json.dumps(
                {
                    "status": status,
                    "dev_type": "backend",
                    "meta": meta,
                }
            ),
            encoding="utf-8",
        )
        (task_dir / "decision-anchor.md").write_text(
            anchor_text, encoding="utf-8"
        )
        (task_dir / "implement.jsonl").write_text(
            implement_text, encoding="utf-8"
        )
        (task_dir / "check.jsonl").write_text("", encoding="utf-8")
        return task_dir

    def _blockers(self, root: Path, task_dir: Path) -> list[str]:
        task_data = json.loads(
            (task_dir / "task.json").read_text(encoding="utf-8")
        )
        return self.readiness.plan_readiness_blockers(
            root, task_dir, task_data
        )

    def _plan_from_template(
        self,
        template_text: str,
        language: str,
        target_field: str,
    ) -> str:
        if language == "en-US":
            replacements = {
                "# <Feature> Implementation Plan": "# Demo Implementation Plan",
                "**Goal:** <One sentence describing the observable behavior change>":
                    "**Goal:** 演示行为。",
                "<1-3 sentences describing the expected observable behavior.>":
                    "演示行为。",
                "- AC-001: <observable behavior>": "- AC-001: 演示行为。",
                "- AC-002: <observable behavior>": "- AC-002: 演示验证。",
                "<Architecture boundary, compatibility requirement, command, or "
                "output field that must be preserved>": "Do not expand scope.",
                "<Explicitly prohibited scope expansion>": "Do not add dependencies.",
                "`path/a.py`: <responsibility; only change this function or region>":
                    "`AGENTS.md`: demo responsibility.",
                "`tests/test_a.py`: <responsibility; only add or modify these tests>":
                    "`tests/test_demo.py`: demo tests.",
                "### Task N: <small goal>": "### Task 1: demo",
            }
            task_heading = "## Tasks"
            final_heading = "## Final Verification"
        else:
            replacements = {
                "# <功能> 实施计划": "# 演示 实施计划",
                "**目标:** <一句话描述可观察的行为变化>":
                    "**目标:** 演示行为。",
                "<1-3 句话描述预期可观察行为。>": "演示行为。",
                "- AC-001: <可验证行为>": "- AC-001: 演示行为。",
                "- AC-002: <可验证行为>": "- AC-002: 演示验证。",
                "<必须保留的架构边界、兼容要求、命令或输出字段>": "不扩大范围。",
                "<明确禁止的范围扩张>": "不新增依赖。",
                "`path/a.py`：<职责；只改这个函数或区域>":
                    "`AGENTS.md`：演示职责。",
                "`tests/test_a.py`：<职责；只新增或修改这些测试>":
                    "`tests/test_demo.py`：演示测试。",
                "### 任务 N：<小目标>": "### 任务 1：演示",
            }
            task_heading = "## 任务"
            final_heading = "## 最终验证"
        text = template_text
        for old, new in replacements.items():
            text = text.replace(old, new)

        lines = text.splitlines()
        task_start = next(
            index for index, line in enumerate(lines)
            if line.strip() == task_heading
        )
        task_end = next(
            (
                index
                for index in range(task_start + 1, len(lines))
                if lines[index].strip().startswith("## ")
            ),
            len(lines),
        )
        field_indexes = [
            (index, match.group(1))
            for index in range(task_start + 1, task_end)
            if (match := re.match(r"^\*\*(.+?)\*\*\s*$", lines[index].strip()))
        ]
        for position in reversed(range(len(field_indexes))):
            index, label = field_indexes[position]
            if label == target_field:
                continue
            body_end = (
                field_indexes[position + 1][0]
                if position + 1 < len(field_indexes)
                else task_end
            )
            if label in ("验证命令", "Verification Command"):
                body = ["```bash", "python -m pytest tests/test_demo.py -q", "```"]
            elif label in ("实现说明", "Implementation Notes"):
                body = ["```python", "value = 1", "```"]
            else:
                body = ["- 已填充内容。"]
            lines[index + 1 : body_end] = body

        final_start = next(
            index for index, line in enumerate(lines)
            if line.strip() == final_heading
        )
        final_lines = lines[final_start:]
        if language == "en-US":
            final_lines = [
                line.replace("<command>", "python -m pytest")
                .replace(
                    "<pass / not_applicable + reason>",
                    "pass (reason: demo)",
                )
                for line in final_lines
            ]
        else:
            final_lines = [
                line.replace("<command>", "python -m pytest")
                .replace(
                    "<pass / not_applicable + 理由>",
                    "pass（理由：演示）",
                )
                for line in final_lines
            ]
        lines[final_start:] = final_lines
        return "\n".join(lines) + "\n"

    def test_installed_template_field_placeholders_are_rejected(self) -> None:
        cases = (
            (
                "zh-CN",
                ROOT
                / "template"
                / ".cowork-flow"
                / "templates"
                / "plan-template.md",
                ANCHOR_TEXT,
            ),
            (
                "en-US",
                ROOT
                / "template"
                / "locales"
                / "en-US"
                / ".cowork-flow"
                / "templates"
                / "plan-template.md",
                ANCHOR_TEXT_EN,
            ),
        )
        for language, template_path, anchor_text in cases:
            template_text = template_path.read_text(encoding="utf-8")
            for field in self.readiness.TASK_FIELDS[language]:
                with self.subTest(language=language, field=field):
                    plan = self._plan_from_template(
                        template_text, language, field
                    )
                    with tempfile.TemporaryDirectory() as temp_dir:
                        root = Path(temp_dir)
                        task_dir = self._write_task(
                            root,
                            plan_text=plan,
                            anchor_text=anchor_text,
                            language=language,
                            template_source=template_path,
                        )

                        blockers = self._blockers(root, task_dir)

                    self.assertTrue(
                        any(field in item for item in blockers),
                        blockers,
                    )

    def test_finalize_records_snapshot_and_clears_snapshot_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._write_task(root)

            snapshot = self.readiness.PlanReadinessService(root).finalize(task_dir)
            task = json.loads(
                (task_dir / "task.json").read_text(encoding="utf-8")
            )
            blockers = self.readiness.plan_ready_snapshot_blockers(
                root, task_dir, task, required=True
            )

        self.assertEqual(64, len(snapshot["planDigest"]))
        self.assertEqual(64, len(snapshot["anchorDigest"]))
        self.assertEqual(snapshot, task["meta"]["planReady"])
        self.assertEqual([], blockers)

    def test_plan_or_anchor_edit_after_finalize_makes_snapshot_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._write_task(root)
            service = self.readiness.PlanReadinessService(root)
            service.finalize(task_dir)

            plan_path = root / ".cowork-flow" / "plans" / "2026-10-23-demo.md"
            plan_path.write_text(
                plan_path.read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )
            task = json.loads(
                (task_dir / "task.json").read_text(encoding="utf-8")
            )
            plan_blockers = self.readiness.plan_ready_snapshot_blockers(
                root, task_dir, task, required=True
            )

            service.finalize(task_dir)
            anchor_path = task_dir / "decision-anchor.md"
            anchor_path.write_text(
                anchor_path.read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )
            task = json.loads(
                (task_dir / "task.json").read_text(encoding="utf-8")
            )
            anchor_blockers = self.readiness.plan_ready_snapshot_blockers(
                root, task_dir, task, required=True
            )

        self.assertTrue(any("stale" in item for item in plan_blockers))
        self.assertTrue(any("stale" in item for item in anchor_blockers))

    def test_dev_type_change_after_finalize_makes_snapshot_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._write_task(root)
            service = self.readiness.PlanReadinessService(root)
            service.finalize(task_dir)

            task_file = task_dir / "task.json"
            task = json.loads(task_file.read_text(encoding="utf-8"))
            task["dev_type"] = "frontend"
            task_file.write_text(json.dumps(task), encoding="utf-8")
            blockers = self.readiness.plan_ready_snapshot_blockers(
                root, task_dir, task, required=True
            )

        self.assertTrue(any("stale" in item for item in blockers), blockers)

    def test_legacy_task_without_snapshot_is_not_blocked_unless_required(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._write_task(root)
            task = json.loads(
                (task_dir / "task.json").read_text(encoding="utf-8")
            )
            task["meta"].pop("planReadyRequired")

            optional = self.readiness.plan_ready_snapshot_blockers(
                root, task_dir, task, required=False
            )
            required = self.readiness.plan_ready_snapshot_blockers(
                root, task_dir, task, required=True
            )

        self.assertEqual([], optional)
        self.assertTrue(any("plan finalize" in item for item in required))

    def test_missing_acceptance_rows_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plan = PLAN_TEXT.replace(
                "- AC-001: 演示行为。\n- AC-002: 演示验证。\n",
                "",
            )
            task_dir = self._write_task(root, plan_text=plan)

            blockers = self._blockers(root, task_dir)

        self.assertTrue(any("no AC-NNN" in item for item in blockers), blockers)

    def test_template_placeholders_are_rejected(self) -> None:
        cases = {
            "acceptance": (
                PLAN_TEXT.replace(
                    "- AC-001: 演示行为。\n- AC-002: 演示验证。\n",
                    "- AC-001: <可验证行为>\n- AC-002: <可验证行为>\n",
                ),
                "template placeholders",
            ),
            "file-boundary": (
                PLAN_TEXT.replace(
                    "## 文件边界\n\n- `AGENTS.md`\n",
                    "## 文件边界\n\n"
                    "- `path/a.py`：<职责；只改这个函数或区域>\n"
                    "- `tests/test_a.py`：<职责；只新增或修改这些测试>\n",
                ),
                "文件边界",
            ),
            "task-brief": (
                PLAN_TEXT.replace(
                    "**代码事实来源**\n- Read: `AGENTS.md`\n",
                    "**代码事实来源**\n"
                    "- Read: `path/a.py::function_name`\n",
                ),
                "代码事实来源",
            ),
            "impl-notes": (
                PLAN_TEXT.replace(
                    "**实现说明**\n```python\nvalue = 1\n```\n",
                    "**实现说明**\n```python\n"
                    "# 核心控制流草图；按现有代码调整名称。\n"
                    "# 不要把完整实现复制进计划。\n"
                    "...\n```\n",
                ),
                "实现说明",
            ),
            "deviation": (
                PLAN_TEXT.replace(
                    "**偏差条件**\n- 测试失败时停止。\n",
                    "**偏差条件**\n"
                    "- 如果 <计划外文件/层> 变得必要，必须停止并报告，"
                    "因为文件边界有误。\n",
                ),
                "偏差条件",
            ),
        }
        for name, (plan, expected) in cases.items():
            with self.subTest(name):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    task_dir = self._write_task(root, plan_text=plan)

                    blockers = self._blockers(root, task_dir)

                self.assertTrue(
                    any(expected in item for item in blockers),
                    blockers,
                )

    def test_real_symbols_resembling_placeholders_are_accepted(self) -> None:
        plan = PLAN_TEXT.replace(
            "## 文件边界\n\n- `AGENTS.md`\n",
            "## 文件边界\n\n- `tests/test_a.py`\n",
        ).replace(
            "**代码事实来源**\n- Read: `AGENTS.md`\n",
            "**代码事实来源**\n"
            "- Read: `tests/test_a.py::test_real_behavior`\n",
        ).replace(
            "**关键符号**\n- Change: `demo`\n",
            "**关键符号**\n- Change: `function_name`\n",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._write_task(root, plan_text=plan)

            blockers = self._blockers(root, task_dir)

        self.assertEqual([], blockers)

    def test_missing_task_brief_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plan = PLAN_TEXT.replace(
                "**测试证明**\n- 断言演示行为。\n\n",
                "",
            )
            task_dir = self._write_task(root, plan_text=plan)

            blockers = self._blockers(root, task_dir)

        self.assertTrue(any("测试证明" in item for item in blockers), blockers)

    def test_anchor_acceptance_and_goal_must_match_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            anchor = ANCHOR_TEXT.replace(
                "AC-001: 演示行为。",
                "AC-001: 另一个行为。",
            )
            task_dir = self._write_task(root, anchor_text=anchor)

            blockers = self._blockers(root, task_dir)

        self.assertTrue(
            any("acceptance IDs" in item or "text differs" in item for item in blockers),
            blockers,
        )

    def test_placeholder_spec_check_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._write_task(
                root,
                anchor_text=ANCHOR_TEXT.replace(
                    "→ pass（理由：演示）。",
                    "→ <pass / not_applicable + 理由>。",
                ),
            )

            blockers = self._blockers(root, task_dir)

        self.assertTrue(
            any("spec-check" in item for item in blockers),
            blockers,
        )

    def test_implement_index_and_planning_status_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._write_task(
                root,
                status="in_progress",
                implement_text="   \n",
            )

            blockers = self._blockers(root, task_dir)

        self.assertTrue(any("planning task" in item for item in blockers), blockers)
        self.assertTrue(any("implement.jsonl" in item for item in blockers), blockers)

    def test_start_gate_requires_current_plan_ready_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = self._write_task(root)
            context = __import__(
                "services.task_context",
                fromlist=["TaskContextService"],
            ).TaskContextService(root)

            missing = context.start_blockers(task_dir)
            self.assertTrue(
                any("plan-ready snapshot" in item for item in missing),
                missing,
            )

            self.readiness.PlanReadinessService(root).finalize(task_dir)
            self.assertEqual((), context.start_blockers(task_dir))

            plan_path = root / ".cowork-flow" / "plans" / "2026-10-23-demo.md"
            plan_path.write_text(
                plan_path.read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )
            stale = context.start_blockers(task_dir)
            self.readiness.PlanReadinessService(root).finalize(task_dir)
            refreshed = context.start_blockers(task_dir)

        self.assertTrue(any("stale" in item for item in stale), stale)
        self.assertEqual((), refreshed)

    def test_tiny_task_brief_accepts_reduced_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plan = PLAN_TEXT.replace(
                "| **任务类型** | Normal |",
                "| **任务类型** | Tiny |",
            ).replace(
                PLAN_TEXT[PLAN_TEXT.index("### 任务 1") : PLAN_TEXT.index("## 最终验证")],
                TINY_TASK + "\n",
            )
            task_dir = self._write_task(root, plan_text=plan, task_type="tiny")

            blockers = self._blockers(root, task_dir)

        self.assertEqual([], blockers)


if __name__ == "__main__":
    unittest.main()
