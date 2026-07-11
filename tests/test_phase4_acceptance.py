from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class Phase4FreshInstallAcceptanceTest(unittest.TestCase):
    def _run(
        self,
        args: list[str],
        *,
        cwd: Path,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            args,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(
            0,
            result.returncode,
            f"command failed: {args}\nstdout={result.stdout}\nstderr={result.stderr}",
        )
        return result

    def _task_cmd(self, project: Path, *args: str) -> list[str]:
        return [sys.executable, str(project / ".cowork-flow" / "scripts" / "run.py"), "task", *args]

    def _create_task(self, project: Path, env: dict[str, str], *args: str) -> str:
        result = self._run(self._task_cmd(project, "create", *args), cwd=project, env=env)
        return result.stdout.strip().splitlines()[-1]

    def _make_ready(self, project: Path, env: dict[str, str], task_path: str) -> None:
        self._run(self._task_cmd(project, "init-context", task_path, "implement"), cwd=project, env=env)
        (project / task_path / "prd.md").write_text(
            "# Acceptance Task\n\n"
            "## Goal\n\nVerify the fresh install workflow.\n\n"
            "## Scope\n\nOnly this temp project task.\n\n"
            "## Relevant Specs\n\n- .cowork-flow/spec/core/entry.md\n\n"
            "## Acceptance Criteria\n\nTask can start and report next action.\n",
            encoding="utf-8",
        )

    def test_fresh_init_supports_generic_pattern_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "demo"
            env = {**os.environ, "COWORK_FLOW_CONTEXT_ID": "phase4-test"}
            self._run(
                [
                    "node",
                    str(ROOT / "bin" / "cowork-flow.js"),
                    "init",
                    str(project),
                    "--developer",
                    "codex",
                    "--platform",
                    "codex",
                ],
                cwd=ROOT,
                env=env,
            )

            task = self._create_task(
                project,
                env,
                "P1 implementation task",
                "--slug",
                "p1-impl",
                "--priority",
                "P1",
            )
            self._make_ready(project, env, task)

            self._run(self._task_cmd(project, "start", task), cwd=project, env=env)
            next_result = self._run(self._task_cmd(project, "next", task), cwd=project, env=env)
            self.assertIn("Status: in_progress", next_result.stdout)
            self.assertIn("p1-impl", next_result.stdout)
