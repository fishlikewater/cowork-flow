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
            "## Acceptance Criteria\n\nTask can start and report next action.\n",
            encoding="utf-8",
        )

    def test_fresh_init_supports_phase4_pattern_workflows(self) -> None:
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

            fanout = self._create_task(
                project,
                env,
                "P1 fanout",
                "--slug",
                "p1-fanout",
                "--priority",
                "P1",
                "--pattern",
                "fan_out",
            )
            child = self._create_task(
                project,
                env,
                "P1 child",
                "--slug",
                "p1-child",
                "--parent",
                "p1-fanout",
            )
            pipeline = self._create_task(
                project,
                env,
                "P2 pipeline",
                "--slug",
                "p2-pipeline",
                "--priority",
                "P2",
                "--pattern",
                "pipeline",
                "--meta",
                json.dumps({"stages": [{"name": "implement"}, {"name": "check"}]}),
            )
            human_loop = self._create_task(
                project,
                env,
                "P5 human loop",
                "--slug",
                "p5-human-loop",
                "--priority",
                "P5",
                "--pattern",
                "human_loop",
                "--meta",
                json.dumps({"decision_points": [{"question": "Approve release?"}]}),
            )

            for task_path in (fanout, child, pipeline, human_loop):
                self._make_ready(project, env, task_path)

            self._run(self._task_cmd(project, "start", fanout), cwd=project, env=env)
            fanout_next = self._run(self._task_cmd(project, "next", fanout), cwd=project, env=env)
            self.assertIn("Status: in_progress", fanout_next.stdout)
            self.assertIn("Pattern action: wait_children", fanout_next.stdout)
            self.assertIn("p1-child", fanout_next.stdout)

            self._run(self._task_cmd(project, "start", pipeline), cwd=project, env=env)
            pipeline_next = self._run(self._task_cmd(project, "next", pipeline), cwd=project, env=env)
            self.assertIn("Status: in_progress", pipeline_next.stdout)
            self.assertIn("Pattern action: review", pipeline_next.stdout)

            self._run(self._task_cmd(project, "start", human_loop), cwd=project, env=env)
            self._run(
                self._task_cmd(project, "block", human_loop, "--reason", "Need release approval"),
                cwd=project,
                env=env,
            )
            human_next = self._run(self._task_cmd(project, "next", human_loop), cwd=project, env=env)
            self.assertIn("Status: blocked", human_next.stdout)
            self.assertIn("Pattern action: human_decision", human_next.stdout)
