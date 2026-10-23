from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.flow_test_support import FlowScriptTestCase, ROOT
from tests.test_plan_readiness import ANCHOR_TEXT, PLAN_TEXT


class PlanCliTest(FlowScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.plan = __import__("adapters.cli.plan", fromlist=["main"])
        self.template = (
            ROOT / "template" / ".cowork-flow" / "templates" / "plan-template.md"
        )

    def _root(self) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        target = root / ".cowork-flow" / "templates" / "plan-template.md"
        target.parent.mkdir(parents=True)
        shutil.copyfile(self.template, target)
        return root

    def _task(self, root: Path) -> Path:
        plan_path = root / ".cowork-flow" / "plans" / "2026-10-23-demo.md"
        plan_path.parent.mkdir(parents=True)
        plan_path.write_text(PLAN_TEXT, encoding="utf-8")
        task_dir = root / ".cowork-flow" / "tasks" / "10-23-demo"
        task_dir.mkdir(parents=True)
        (task_dir / "task.json").write_text(
            json.dumps(
                {
                    "status": "planning",
                    "dev_type": "backend",
                    "meta": {
                        "planFile": ".cowork-flow/plans/2026-10-23-demo.md",
                        "gateProfile": "strict",
                        "planReadyRequired": True,
                    },
                }
            ),
            encoding="utf-8",
        )
        (task_dir / "decision-anchor.md").write_text(
            ANCHOR_TEXT, encoding="utf-8"
        )
        (task_dir / "implement.jsonl").write_text(
            '{"file": "AGENTS.md"}\n', encoding="utf-8"
        )
        return task_dir

    def _run(self, root: Path, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch.object(self.plan, "get_repo_root", return_value=root),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            result = self.plan.main(argv)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_new_writes_skeleton_and_refuses_overwrite(self) -> None:
        root = self._root()
        result, stdout, stderr = self._run(
            root,
            [
                "new",
                "--title",
                "演示",
                "--slug",
                "demo",
                "--date",
                "2026-10-23",
            ],
        )

        self.assertEqual(0, result, stderr)
        self.assertEqual(
            ".cowork-flow/plans/2026-10-23-demo.md",
            stdout.strip(),
        )
        self.assertTrue(
            (root / ".cowork-flow" / "plans" / "2026-10-23-demo.md").is_file()
        )

        result, _stdout, stderr = self._run(
            root,
            [
                "new",
                "--title",
                "演示",
                "--slug",
                "demo",
                "--date",
                "2026-10-23",
            ],
        )
        self.assertEqual(1, result)
        self.assertIn("already exists", stderr)

    def test_finalize_records_snapshot_and_reports_blockers(self) -> None:
        root = self._root()
        task_dir = self._task(root)

        result, stdout, stderr = self._run(
            root,
            ["finalize", str(task_dir), "--json"],
        )
        self.assertEqual(0, result, stderr)
        snapshot = json.loads(stdout)
        self.assertEqual(64, len(snapshot["planDigest"]))

        task = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
        self.assertEqual(snapshot, task["meta"]["planReady"])

        broken = task_dir / "decision-anchor.md"
        broken.write_text(
            ANCHOR_TEXT.replace(
                "AC-001: 演示行为。",
                "AC-001: 另一个行为。",
            ),
            encoding="utf-8",
        )
        result, _stdout, stderr = self._run(
            root,
            ["finalize", str(task_dir)],
        )
        self.assertEqual(1, result)
        self.assertIn("Plan is not ready", stderr)
        self.assertIn("differs", stderr)

    def test_new_requires_ascii_slug(self) -> None:
        root = self._root()
        result, _stdout, stderr = self._run(
            root,
            ["new", "--title", "中文标题", "--date", "2026-10-23"],
        )

        self.assertEqual(1, result)
        self.assertIn("--slug", stderr)


if __name__ == "__main__":
    unittest.main()
