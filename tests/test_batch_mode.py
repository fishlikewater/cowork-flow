from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.flow_test_support import FlowScriptTestCase


class BatchModeFailClosedTest(FlowScriptTestCase):
    def test_batch_runtime_returns_stable_disabled_error(self) -> None:
        batch_mode = importlib.import_module("common.task.batch_mode")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            task_dir.mkdir(parents=True)
            stderr = io.StringIO()

            with contextlib.redirect_stderr(stderr):
                result = batch_mode.run_batch_entry(
                    root,
                    task_dir,
                    argparse.Namespace(auto=True, approved=True),
                )

            self.assertEqual(batch_mode.BATCH_DISABLED_EXIT_CODE, result)
            self.assertIn(batch_mode.BATCH_DISABLED_CODE, stderr.getvalue())

    def test_cmd_start_auto_rejection_does_not_mutate_task_or_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            task_json = task_dir / "task.json"
            task_json.write_text(
                json.dumps({"status": "planning", "completedAt": None}),
                encoding="utf-8",
            )
            (task_dir / "decision-anchor.md").write_text(
                "# Demo\n\n## 验收标准\n- AC-001: fail closed\n",
                encoding="utf-8",
            )
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text(
                    '{"file":"AGENTS.md","reason":"rules"}\n',
                    encoding="utf-8",
                )
            self._write_rules_file(root, [])
            before = task_json.read_text(encoding="utf-8")
            stderr = io.StringIO()

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with (
                    patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}),
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(stderr),
                ):
                    result = self.task.cmd_start(
                        argparse.Namespace(
                            dir=str(task_dir),
                            auto=True,
                            approved=True,
                        )
                    )
            finally:
                os.chdir(previous_cwd)

            batch_mode = importlib.import_module("common.task.batch_mode")
            self.assertEqual(batch_mode.BATCH_DISABLED_EXIT_CODE, result)
            self.assertIn(batch_mode.BATCH_DISABLED_CODE, stderr.getvalue())
            self.assertEqual(before, task_json.read_text(encoding="utf-8"))
            self.assertFalse(
                (root / ".cowork-flow" / ".runtime" / "sessions" / "main.json").exists()
            )


if __name__ == "__main__":
    unittest.main()
