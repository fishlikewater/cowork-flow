from __future__ import annotations

import contextlib
import importlib.util
import io
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
DOCTOR_PATH = TEMPLATE / "skills" / "runtime-health" / "scripts" / "doctor.py"


def _load_doctor():
    spec = importlib.util.spec_from_file_location("cowork_flow_runtime_health", DOCTOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Doctor: {DOCTOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RuntimeHealthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doctor = _load_doctor()

    def _install_codex_project(self, root: Path) -> None:
        shutil.copytree(TEMPLATE / ".cowork-flow", root / ".cowork-flow")
        shutil.copytree(TEMPLATE / ".codex", root / ".codex")
        shutil.copytree(TEMPLATE / "skills", root / ".agents" / "skills")
        shutil.copy2(TEMPLATE / "AGENTS.md", root / "AGENTS.md")

    def _distribution_fixture(self, root: Path) -> None:
        for relative in (
            ".cowork-flow/spec/runtime/host-assets.json",
            ".cowork-flow/scripts/run.py",
            ".cowork-flow/scripts/kernel/workflow_route.py",
            ".cowork-flow/scripts/services/task_routing.py",
            ".cowork-flow/scripts/services/task_context.py",
            ".cowork-flow/scripts/infra/skill_manifest.py",
            ".cowork-flow/scripts/adapters/cli/task_navigation.py",
        ):
            source = TEMPLATE / relative
            for target_root in (root / "template", root):
                target = target_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        for skill in (
            "brainstorming",
            "task-planning",
            "cowork-flow",
            "task-review",
            "batch-execution",
            "runtime-health",
        ):
            skill_source = TEMPLATE / "skills" / skill
            for source in skill_source.rglob("*"):
                if not source.is_file() or "__pycache__" in source.parts:
                    continue
                relative = source.relative_to(skill_source)
                for target in (
                    root / "template" / "skills" / skill / relative,
                    root / ".agents" / "skills" / skill / relative,
                    root / ".claude" / "skills" / skill / relative,
                ):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)

    def test_installed_codex_project_does_not_require_source_template(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._install_codex_project(root)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                io.StringIO()
            ):
                result = self.doctor._run_checks(root)

        self.assertEqual(0, result)

    def test_distribution_detects_claude_skill_replica_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._distribution_fixture(root)
            replica = root / ".claude" / "skills" / "cowork-flow" / "manifest.json"
            replica.write_text(
                replica.read_text(encoding="utf-8").replace("start task", "start drifted task"),
                encoding="utf-8",
            )

            errors = self.doctor.check_distribution(root)

        self.assertTrue(any(".claude" in error for error in errors), errors)

    def test_distribution_detects_non_core_skill_replica_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._distribution_fixture(root)
            replica = root / ".claude" / "skills" / "runtime-health" / "SKILL.md"
            replica.write_text(
                replica.read_text(encoding="utf-8") + "\nDrifted guidance.\n",
                encoding="utf-8",
            )

            errors = self.doctor.check_distribution(root)

        self.assertTrue(any("runtime-health" in error for error in errors), errors)

    def test_distribution_detects_non_core_runtime_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._distribution_fixture(root)
            runtime = root / ".cowork-flow" / "scripts" / "run.py"
            runtime.write_text(
                runtime.read_text(encoding="utf-8") + "\n# drift\n",
                encoding="utf-8",
            )

            errors = self.doctor.check_distribution(root)

        self.assertTrue(any("scripts/run.py" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
