from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from tests.flow_test_support import FlowScriptTestCase, ROOT


class PlanScaffoldTest(FlowScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.scaffold = __import__(
            "services.plan_scaffold",
            fromlist=["PlanScaffoldError", "PlanScaffoldService"],
        )
        self.template = (
            ROOT / "template" / ".cowork-flow" / "templates" / "plan-template.md"
        )

    def _root_with_template(self, source: Path | None = None) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        target = root / ".cowork-flow" / "templates" / "plan-template.md"
        target.parent.mkdir(parents=True)
        shutil.copyfile(source or self.template, target)
        return root

    def test_creates_template_skeleton_with_title_and_utf8_lf(self) -> None:
        root = self._root_with_template()
        path = self.scaffold.PlanScaffoldService(root).create(
            "演示计划",
            "demo",
            date_prefix="2026-10-23",
        )

        self.assertEqual(
            root / ".cowork-flow" / "plans" / "2026-10-23-demo.md",
            path,
        )
        data = path.read_bytes()
        text = data.decode("utf-8")
        self.assertFalse(data.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r\n", data)
        self.assertTrue(text.endswith("\n"))
        self.assertFalse(text.endswith("\n\n"))
        self.assertTrue(text.startswith("# 演示计划 实施计划\n"))
        self.assertIn("## 验收标准", text)
        self.assertNotIn("<功能>", text)

    def test_title_already_ending_with_marker_is_not_duplicated(self) -> None:
        root = self._root_with_template()
        path = self.scaffold.PlanScaffoldService(root).create(
            "发布 2.4.1 实施计划",
            "release",
            date_prefix="2026-10-23",
        )

        self.assertTrue(
            path.read_text(encoding="utf-8").startswith(
                "# 发布 2.4.1 实施计划\n"
            )
        )

    def test_existing_plan_requires_force(self) -> None:
        root = self._root_with_template()
        service = self.scaffold.PlanScaffoldService(root)
        service.create("演示", "demo", date_prefix="2026-10-23")

        with self.assertRaises(self.scaffold.PlanScaffoldError) as raised:
            service.create("演示", "demo", date_prefix="2026-10-23")
        self.assertEqual("PLAN-NEW-EXISTS-001", raised.exception.code)

        path = service.create(
            "覆盖后的计划",
            "demo",
            date_prefix="2026-10-23",
            force=True,
        )
        self.assertIn(
            "# 覆盖后的计划 实施计划",
            path.read_text(encoding="utf-8"),
        )

    def test_missing_template_reports_sync_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with self.assertRaises(self.scaffold.PlanScaffoldError) as raised:
                self.scaffold.PlanScaffoldService(root).create(
                    "演示",
                    "demo",
                )
        self.assertEqual("PLAN-NEW-TEMPLATE-001", raised.exception.code)
        self.assertIn("cwf project sync", raised.exception.detail)

    def test_invalid_slug_and_date_are_rejected(self) -> None:
        root = self._root_with_template()
        service = self.scaffold.PlanScaffoldService(root)
        with self.assertRaises(self.scaffold.PlanScaffoldError) as slug_error:
            service.create("演示", "演示 slug")
        self.assertEqual("PLAN-NEW-SLUG-001", slug_error.exception.code)
        with self.assertRaises(self.scaffold.PlanScaffoldError) as date_error:
            service.create("演示", "demo", date_prefix="23-10-2026")
        self.assertEqual("PLAN-NEW-DATE-001", date_error.exception.code)
        with self.assertRaises(self.scaffold.PlanScaffoldError) as newline_error:
            service.create("演示", "demo", date_prefix="2026-10-23\n")
        self.assertEqual("PLAN-NEW-DATE-001", newline_error.exception.code)


if __name__ == "__main__":
    unittest.main()
