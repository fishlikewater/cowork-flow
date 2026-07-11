"""Tests for the doctor release health aggregate command."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".cowork-flow" / "scripts"
DOCTOR = SCRIPTS / "doctor.py"


def _load_doctor_module():
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location("cowork_flow_doctor", DOCTOR)
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPTS))


class DoctorReleaseHealthTest(unittest.TestCase):
    def test_release_health_command_reports_all_required_checks(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(DOCTOR),
                "--release-health",
            ],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )

        self.assertEqual(
            0,
            result.returncode,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        for check_name in (
            "UTF-8/BOM",
            "root/template sync",
            "DB migration",
            "host adapter",
            "subagent safety",
            "pack boundary",
        ):
            self.assertIn(check_name, result.stdout)
        self.assertIn("[OK]", result.stdout)
        self.assertIn("Summary:", result.stdout)

    def test_release_health_failure_output_includes_repair_context(self) -> None:
        doctor = _load_doctor_module()
        output = doctor.format_release_health_results(
            [
                doctor.ReleaseHealthResult(
                    name="sample check",
                    status="FAIL",
                    current="sample current state",
                    blocker="sample blocker",
                    next_command="sample next command",
                    files=("sample/file.txt",),
                )
            ]
        )

        self.assertIn("[FAIL] sample check", output)
        self.assertIn("current: sample current state", output)
        self.assertIn("blocker: sample blocker", output)
        self.assertIn("next: sample next command", output)
        self.assertIn("files:", output)
        self.assertIn("sample/file.txt", output)

    def test_root_and_template_doctor_release_health_contracts_are_synced(self) -> None:
        root_text = DOCTOR.read_text(encoding="utf-8")
        template_text = (
            ROOT / "template" / ".cowork-flow" / "scripts" / "doctor.py"
        ).read_text(encoding="utf-8")

        for marker in (
            "ReleaseHealthResult",
            "format_release_health_results",
            "--release-health",
            "cmd_release_health",
        ):
            self.assertIn(marker, root_text)
            self.assertIn(marker, template_text)


if __name__ == "__main__":
    unittest.main()
