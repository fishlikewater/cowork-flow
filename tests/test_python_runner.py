from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "template" / ".cowork-flow" / "run"
WINDOWS_RUNNER = ROOT / "template" / ".cowork-flow" / "run.cmd"
PYTHON_RUNNER = ROOT / "template" / ".cowork-flow" / "scripts" / "run.py"
POSIX_ONLY = unittest.skipIf(
    os.name == "nt",
    "POSIX shell runner execution is covered on POSIX hosts",
)


class PythonRunnerTest(unittest.TestCase):
    def make_fake_python(
        self,
        directory: Path,
        name: str,
        *,
        version_ok: bool = True,
    ) -> Path:
        path = directory / name
        path.write_text(
            textwrap.dedent(
                f"""\
                #!/bin/sh
                printf '%s\\n' "$0 $*" >> "$COWORK_FLOW_FAKE_LOG"
                if [ "${{1:-}}" = "-3" ] && [ "${{2:-}}" = "-c" ]; then
                  exit {0 if version_ok else 1}
                fi
                if [ "${{1:-}}" = "-c" ]; then
                  exit {0 if version_ok else 1}
                fi
                exit 0
                """
            ),
            encoding="utf-8",
        )
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    def run_with_fake_path(
        self,
        temp_dir: Path,
        args: list[str],
        *,
        env_overrides: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        fake_bin = temp_dir / "bin"
        log_file = temp_dir / "python.log"
        env = {
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "COWORK_FLOW_FAKE_LOG": str(log_file),
        }
        if env_overrides:
            env.update(env_overrides)

        return subprocess.run(
            [str(RUNNER), *args],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def read_log(self, temp_dir: Path) -> list[str]:
        log_file = temp_dir / "python.log"
        if not log_file.exists():
            return []
        return log_file.read_text(encoding="utf-8").splitlines()

    @POSIX_ONLY
    def test_runner_is_executable_template_entrypoint(self) -> None:
        self.assertTrue(RUNNER.is_file())
        self.assertTrue(os.access(RUNNER, os.X_OK))

    def test_windows_runner_is_thin_python_bootstrap(self) -> None:
        self.assertTrue(WINDOWS_RUNNER.is_file())
        content = WINDOWS_RUNNER.read_text(encoding="utf-8")

        self.assertIn("COWORK_FLOW_PYTHON", content)
        self.assertIn("PYTHON", content)
        self.assertIn("python3", content)
        self.assertIn("python", content)
        self.assertIn("py -3", content)
        self.assertIn("Python 3.8+", content)
        self.assertIn(r"scripts\run.py", content)
        self.assertNotIn("task.py", content)
        self.assertNotIn(":run_task", content)
        self.assertNotIn("REST_ARGS", content)

    def test_shared_python_runner_maps_commands_to_workflow_scripts(self) -> None:
        self.assertTrue(PYTHON_RUNNER.is_file())
        content = PYTHON_RUNNER.read_text(encoding="utf-8")

        self.assertIn('"task": "task.py"', content)
        self.assertNotIn('"agent' + '-team": "agent' + '_team.py"', content)
        self.assertIn('"get-context": "get_context.py"', content)

    @POSIX_ONLY
    def test_python3_is_preferred_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp_dir = Path(temp_name)
            fake_bin = temp_dir / "bin"
            fake_bin.mkdir()
            python3 = self.make_fake_python(fake_bin, "python3")
            self.make_fake_python(fake_bin, "python")

            result = self.run_with_fake_path(temp_dir, ["python", "-V"])

            self.assertEqual(0, result.returncode, result.stderr)
            expected_script = ROOT / "template" / ".cowork-flow" / "scripts" / "run.py"
            self.assertEqual(f"{python3} {expected_script} python -V", self.read_log(temp_dir)[-1])

    @POSIX_ONLY
    def test_runner_falls_back_to_python_when_python3_is_not_usable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp_dir = Path(temp_name)
            fake_bin = temp_dir / "bin"
            fake_bin.mkdir()
            self.make_fake_python(fake_bin, "python3", version_ok=False)
            python = self.make_fake_python(fake_bin, "python")

            result = self.run_with_fake_path(temp_dir, ["python", "-V"])

            self.assertEqual(0, result.returncode, result.stderr)
            expected_script = ROOT / "template" / ".cowork-flow" / "scripts" / "run.py"
            self.assertEqual(f"{python} {expected_script} python -V", self.read_log(temp_dir)[-1])

    @POSIX_ONLY
    def test_runner_respects_explicit_python_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp_dir = Path(temp_name)
            fake_bin = temp_dir / "bin"
            fake_bin.mkdir()
            custom_python = self.make_fake_python(fake_bin, "custom-python")
            self.make_fake_python(fake_bin, "python3")

            result = self.run_with_fake_path(
                temp_dir,
                ["python", "-V"],
                env_overrides={"COWORK_FLOW_PYTHON": str(custom_python)},
            )

            self.assertEqual(0, result.returncode, result.stderr)
            expected_script = ROOT / "template" / ".cowork-flow" / "scripts" / "run.py"
            self.assertEqual(f"{custom_python} {expected_script} python -V", self.read_log(temp_dir)[-1])

    @POSIX_ONLY
    def test_runner_rejects_candidates_below_minimum_python_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp_dir = Path(temp_name)
            fake_bin = temp_dir / "bin"
            fake_bin.mkdir()
            self.make_fake_python(fake_bin, "python3", version_ok=False)
            self.make_fake_python(fake_bin, "python", version_ok=False)

            result = self.run_with_fake_path(temp_dir, ["python", "-V"])

            self.assertEqual(127, result.returncode)
            self.assertIn("Python 3.8+", result.stderr)
            self.assertIn("COWORK_FLOW_PYTHON", result.stderr)

    @POSIX_ONLY
    def test_runner_maps_commands_to_workflow_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp_dir = Path(temp_name)
            fake_bin = temp_dir / "bin"
            fake_bin.mkdir()
            python3 = self.make_fake_python(fake_bin, "python3")

            result = self.run_with_fake_path(temp_dir, ["task", "list"])

            self.assertEqual(0, result.returncode, result.stderr)
            expected_script = ROOT / "template" / ".cowork-flow" / "scripts" / "run.py"
            self.assertEqual(f"{python3} {expected_script} task list", self.read_log(temp_dir)[-1])

if __name__ == "__main__":
    unittest.main()
