from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from unittest import mock
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

    def _run_doctor(self, root: Path) -> tuple[int, str]:
        stderr = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            result = self.doctor._run_checks(root)
        return result, stderr.getvalue()

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

    def _source_checkout_fixture(self, root: Path) -> None:
        shutil.copytree(TEMPLATE / ".cowork-flow" / "scripts", root / "template" / ".cowork-flow" / "scripts")
        shutil.copytree(TEMPLATE / "skills", root / "template" / "skills")
        for relative in (
            ".cowork-flow/spec/runtime/host-assets.json",
            ".cowork-flow/spec/runtime/contract-registry.json",
        ):
            source_contract = TEMPLATE / relative
            target_contract = root / "template" / relative
            target_contract.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_contract, target_contract)

    def test_installed_codex_project_does_not_require_source_template(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._install_codex_project(root)
            result, stderr = self._run_doctor(root)

        self.assertEqual(0, result)
        self.assertEqual("", stderr)

    def test_installed_project_reports_corrupt_skill_manifest_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._install_codex_project(root)
            manifest = root / ".agents" / "skills" / "runtime-health" / "manifest.json"
            manifest.write_text("{not-json}\n", encoding="utf-8")

            result, stderr = self._run_doctor(root)

        self.assertEqual(1, result)
        self.assertIn("Skill manifest error", stderr)
        self.assertIn("invalid Skill manifest", stderr)
        self.assertIn("runtime-health/manifest.json", stderr.replace("\\", "/"))

    def test_installed_project_reports_missing_skill_command_script_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._install_codex_project(root)
            script = root / ".agents" / "skills" / "runtime-health" / "scripts" / "doctor.py"
            script.unlink()

            result, stderr = self._run_doctor(root)

        self.assertEqual(1, result)
        self.assertIn("Skill manifest error", stderr)
        self.assertIn("manifest command script is missing", stderr)
        self.assertIn("runtime-health/scripts/doctor.py", stderr.replace("\\", "/"))

    def test_installed_project_reports_skill_command_conflict_owner_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._install_codex_project(root)
            skill_dir = root / ".agents" / "skills" / "demo-conflict"
            skill_dir.mkdir(parents=True)
            script = skill_dir / "scripts" / "doctor_conflict.py"
            script.parent.mkdir()
            script.write_text("print('conflict')\n", encoding="utf-8")
            manifest = skill_dir / "manifest.json"
            data = {
                "schemaVersion": 1,
                "skill": "demo-conflict",
                "commands": [
                    {
                        "name": "doctor",
                        "aliases": [],
                        "script": "scripts/doctor_conflict.py",
                    }
                ],
            }
            manifest.write_text(json.dumps(data), encoding="utf-8")

            result, stderr = self._run_doctor(root)

        self.assertEqual(1, result)
        self.assertIn("Skill command has multiple owners: doctor", stderr)
        self.assertIn("demo-conflict", stderr)
        self.assertIn("runtime-health", stderr)

    def test_installed_project_reports_host_asset_validation_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._install_codex_project(root)
            target = root / ".codex" / "hooks" / "inject-workflow-state.py"
            target.unlink()

            result, stderr = self._run_doctor(root)

        self.assertEqual(1, result)
        self.assertIn("missing command target", stderr)
        self.assertIn(".codex/hooks/inject-workflow-state.py", stderr.replace("\\", "/"))

    def test_all_json_reports_stable_payload_without_text_noise(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._install_codex_project(root)
            stdout = io.StringIO()
            stderr = io.StringIO()

            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = self.doctor._run_checks(root, structured=True)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(0, result)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(True, payload["ok"])
        self.assertEqual([], payload["errors"])
        self.assertEqual([], payload["issues"]["hostAdapters"])
        self.assertEqual([], payload["issues"]["taskHygiene"])

    def test_host_adapter_json_reports_stable_issue_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._install_codex_project(root)
            target = root / ".codex" / "hooks" / "inject-workflow-state.py"
            target.unlink()
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                result = self.doctor._run_host_checks(
                    root,
                    structured=True,
                )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(1, result)
        self.assertEqual(1, len(payload["issues"]))
        issue = payload["issues"][0]
        self.assertEqual(
            {
                "code": "HOST-ASSET-MISSING-COMMAND-TARGET",
                "severity": "error",
                "path": ".codex/hooks/inject-workflow-state.py",
                "commandHint": "",
                "contract": "runtime-health:host-adapters",
            },
            {key: issue[key] for key in (
                "code",
                "severity",
                "path",
                "commandHint",
                "contract",
            )},
        )
        self.assertIn("missing command target", issue["message"])

    def test_source_checkout_does_not_require_full_ignored_live_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._source_checkout_fixture(root)

            errors = self.doctor.check_distribution(root)

        self.assertEqual([], errors)

    def test_source_checkout_detects_present_runtime_contract_registry_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._source_checkout_fixture(root)
            source = (
                root
                / "template"
                / ".cowork-flow"
                / "spec"
                / "runtime"
                / "contract-registry.json"
            )
            live = (
                root
                / ".cowork-flow"
                / "spec"
                / "runtime"
                / "contract-registry.json"
            )
            live.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, live)
            payload = json.loads(live.read_text(encoding="utf-8"))
            payload["schemaVersion"] = payload.get("schemaVersion", 1) + 1
            live.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            self.assertNotEqual(source.read_bytes(), live.read_bytes())

            errors = self.doctor.check_distribution(root)

        self.assertTrue(
            any(
                "local live runtime drift" in error
                and "contract-registry.json" in error.replace("\\", "/")
                for error in errors
            ),
            errors,
        )

    def test_source_checkout_detects_present_navigation_runtime_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._source_checkout_fixture(root)
            source = root / "template" / ".cowork-flow" / "scripts" / "adapters" / "cli" / "task_navigation.py"
            bootstrap = root / ".cowork-flow" / "scripts" / "adapters" / "cli" / "task_navigation.py"
            bootstrap.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, bootstrap)
            bootstrap.write_text(
                bootstrap.read_text(encoding="utf-8") + "\n# local drift\n",
                encoding="utf-8",
            )

            errors = self.doctor.check_distribution(root)

        self.assertTrue(any("local live runtime drift" in error for error in errors), errors)

    def test_source_checkout_detects_present_local_live_runtime_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._source_checkout_fixture(root)
            source = root / "template" / ".cowork-flow" / "scripts" / "runtime" / "session_state.py"
            live = root / ".cowork-flow" / "scripts" / "runtime" / "session_state.py"
            live.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, live)
            live.write_text(
                live.read_text(encoding="utf-8") + "\n# local drift\n",
                encoding="utf-8",
            )

            errors = self.doctor.check_distribution(root)

        self.assertTrue(any("local live runtime drift" in error for error in errors), errors)

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

        self.assertTrue(
            any("scripts/run.py" in error.replace("\\", "/") for error in errors),
            errors,
        )

    def test_task_hygiene_reports_stale_tasks_without_failing_health(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tasks = root / ".cowork-flow" / "tasks"
            completed = tasks / "05-19-completed"
            in_progress = tasks / "05-20-in-progress"
            missing_context = tasks / "05-21-missing-context"
            for task_dir, status in (
                (completed, "completed"),
                (in_progress, "in_progress"),
                (missing_context, "planning"),
            ):
                task_dir.mkdir(parents=True)
                (task_dir / "task.json").write_text(
                    f'{{"status": "{status}", "assignee": "codex"}}\n',
                    encoding="utf-8",
                )
            (missing_context / "implement.jsonl").write_text('{"file": "README.md"}\n', encoding="utf-8")

            issues = self.doctor.check_task_hygiene(root)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                io.StringIO()
            ):
                result = self.doctor._run_task_hygiene_checks(root)
            with contextlib.redirect_stdout(stdout):
                structured_result = self.doctor._run_task_hygiene_checks(
                    root,
                    structured=True,
                )

        kinds = {issue["kind"] for issue in issues}
        payload = json.loads(stdout.getvalue())
        structured_issues = payload["issues"]
        envelope_keys = {
            "code",
            "severity",
            "path",
            "message",
            "commandHint",
            "contract",
        }
        self.assertEqual(0, result)
        self.assertEqual(0, structured_result)
        self.assertIn("completed_unarchived", kinds)
        self.assertIn("in_progress_unbound", kinds)
        self.assertIn("missing_task_context", kinds)
        self.assertEqual(
            [],
            [issue for issue in issues if not envelope_keys <= set(issue)],
        )
        self.assertEqual(
            [],
            [
                issue
                for issue in structured_issues
                if issue["commandHint"] != issue["hint"]
            ],
        )
        self.assertEqual(
            [],
            [
                issue
                for issue in structured_issues
                if issue["severity"] != "warning"
                or issue["contract"] != "runtime-health:task-hygiene"
            ],
        )
        self.assertEqual(
            {
                "TASK-HYGIENE-COMPLETED-UNARCHIVED",
                "TASK-HYGIENE-IN-PROGRESS-UNBOUND",
                "TASK-HYGIENE-MISSING-TASK-CONTEXT",
            },
            {issue["code"] for issue in structured_issues},
        )
        self.assertEqual(
            [],
            [issue for issue in structured_issues if issue["severity"] == "error"],
        )
        self.assertEqual(
            [],
            [
                issue
                for issue in issues
                if not issue["hint"].startswith("./.cowork-flow/run ")
            ],
        )

    def test_state_recovery_reports_locks_and_pending_operations_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = root / ".cowork-flow" / ".runtime"
            target = runtime / "sessions" / "main.json"
            lock_path = target.with_name(f"{target.name}.lock")
            lock_path.parent.mkdir(parents=True)
            operation_path = runtime / "operations" / "op-demo.json"
            operation_path.parent.mkdir(parents=True)
            operation_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "operation_id": "op-demo",
                        "kind": "runtime-context-bind",
                        "phase": "prepared",
                        "participants": [{"path": str(target)}],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            conflict_path = runtime / "operations" / "op-conflict.json"
            conflict_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "operation_id": "op-conflict",
                        "kind": "task-lifecycle-start",
                        "phase": "conflicted",
                        "participants": [{"path": str(target)}],
                        "error": {
                            "code": "STATE-CONFLICT-001",
                            "path": str(target),
                            "detail": "expected revision 1, found 2",
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            self.doctor.StateStore._write_lock_file(
                lock_path,
                target,
                pid=424242,
                created_at="2000-01-01T00:00:00Z",
            )

            with mock.patch.object(
                self.doctor.StateStore,
                "_pid_exists",
                return_value=False,
            ):
                issues = self.doctor.check_state_recovery(root)

            lock_issues = [issue for issue in issues if issue["kind"] == "state_lock"]
            operation_issues = [
                issue for issue in issues if issue["kind"] == "pending_operation"
            ]
            self.assertEqual(1, len(lock_issues), issues)
            self.assertEqual(2, len(operation_issues), issues)
            lock_issue = lock_issues[0]
            self.assertEqual("STATE-RECOVERY-LOCK-RECOVERABLE", lock_issue["code"])
            self.assertEqual("recoverable", lock_issue["status"])
            self.assertEqual("missing", lock_issue["ownerAvailability"])
            self.assertEqual(str(target), lock_issue["target"])
            self.assertIn("ageSeconds", lock_issue)
            self.assertIn("remove_stale_lock", lock_issue["commandHint"])
            self.assertTrue(lock_path.exists())
            operation_issue = next(
                issue
                for issue in operation_issues
                if issue["operationId"] == "op-demo"
            )
            self.assertEqual("STATE-RECOVERY-PENDING-OPERATION", operation_issue["code"])
            self.assertEqual("prepared", operation_issue["phase"])
            self.assertIn("UnitOfWork.recover_all", operation_issue["commandHint"])
            conflict_issue = next(
                issue
                for issue in operation_issues
                if issue["operationId"] == "op-conflict"
            )
            self.assertEqual(
                "STATE-RECOVERY-CONFLICTED-OPERATION",
                conflict_issue["code"],
            )
            self.assertEqual("conflicted", conflict_issue["phase"])
            self.assertIn("STATE-CONFLICT-001", conflict_issue["message"])
            self.assertNotIn("UnitOfWork.recover_all", conflict_issue["commandHint"])


if __name__ == "__main__":
    unittest.main()
