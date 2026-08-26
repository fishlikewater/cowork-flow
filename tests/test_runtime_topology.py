from __future__ import annotations

import ast
import unittest
from pathlib import Path

from tests.architecture_test_support import import_violations, text_marker_violations
from tests.flow_test_support import ROOT


SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"


class RuntimeTopologyTest(unittest.TestCase):
    def test_scripts_top_level_exposes_layered_runtime_shape(self) -> None:
        top_level = {
            path.name
            for path in SCRIPTS.iterdir()
            if path.name != "__pycache__"
        }

        self.assertEqual(
            {"__init__.py", "run.py", "kernel", "services", "adapters", "infra", "runtime"},
            top_level,
        )

    def test_kernel_contains_only_pure_workflow_domain(self) -> None:
        kernel_files = {
            path.name
            for path in (SCRIPTS / "kernel").iterdir()
            if path.is_file() and path.name != "__pycache__"
        }

        self.assertEqual(
            {"__init__.py", "task_state.py", "workflow_route.py"},
            kernel_files,
        )

    def test_workflow_routing_policy_lives_in_kernel(self) -> None:
        self.assertTrue((SCRIPTS / "kernel" / "workflow_route.py").is_file())
        self.assertTrue((SCRIPTS / "services" / "task_routing.py").is_file())

    def test_execution_context_cli_args_live_in_adapter(self) -> None:
        self.assertTrue(
            (SCRIPTS / "adapters" / "cli" / "execution_context_args.py").is_file()
        )
        self.assertTrue(
            (SCRIPTS / "adapters" / "cli" / "execution_resume.py").is_file()
        )
        self.assertTrue((SCRIPTS / "runtime" / "execution_context.py").is_file())

    def test_task_cli_lifecycle_commands_live_in_dedicated_adapter(self) -> None:
        task_source = (
            SCRIPTS / "adapters" / "cli" / "task.py"
        ).read_text(encoding="utf-8")
        lifecycle_commands = (
            SCRIPTS / "adapters" / "cli" / "task_lifecycle_commands.py"
        )

        self.assertTrue(lifecycle_commands.is_file())
        for forbidden in (
            "def cmd_start(",
            "def cmd_review(",
            "def cmd_complete(",
            "def cmd_finish(",
            "def cmd_current(",
            "TaskLifecycleService",
            "TaskContextService",
            "from datetime import datetime",
            "get_active_task",
            "clear_active_task",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, task_source)

    def test_kernel_does_not_import_outer_layers_or_infra(self) -> None:
        self.assertEqual(
            [],
            self._imports_between("kernel", {"services", "adapters", "infra", "runtime"}),
        )

    def test_kernel_does_not_own_io_or_cli_concerns(self) -> None:
        self.assertEqual(
            [],
            self._imports_between(
                "kernel",
                {"argparse", "json", "os", "pathlib", "subprocess", "sys"},
            ),
        )

    def test_kernel_does_not_own_skill_or_delivery_text(self) -> None:
        source = (SCRIPTS / "kernel" / "workflow_route.py").read_text(
            encoding="utf-8"
        )

        for forbidden in (
            "activatedSkill",
            "recommendedSkill",
            "./.cowork-flow/run",
            "label",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_services_do_not_import_adapters(self) -> None:
        self.assertEqual(
            [],
            self._imports_between("services", {"adapters"}),
        )

    def test_services_do_not_emit_cli_output(self) -> None:
        self.assertEqual([], self._imports_between("services", {"sys"}))
        self.assertEqual([], self._calls_named("services", {"print"}))

    def test_services_do_not_own_cli_command_text(self) -> None:
        self.assertEqual(
            [],
            self._text_markers_in(
                "services",
                {"./.cowork-flow/run", "task next --run", "--intent"},
            ),
        )

    def test_services_do_not_own_infra_concerns(self) -> None:
        self.assertFalse((SCRIPTS / "services" / "developer_profile.py").exists())
        self.assertFalse((SCRIPTS / "services" / "quality_sources.py").exists())
        self.assertFalse((SCRIPTS / "services" / "runtime_context.py").exists())
        self.assertTrue((SCRIPTS / "services" / "workflow_runtime.py").is_file())

    def test_kernel_does_not_import_delivery_storage_or_skill_implementations(self) -> None:
        self.assertEqual(
            [],
            import_violations(
                SCRIPTS / "kernel",
                SCRIPTS,
                {
                    "adapters": "kernel must not depend on CLI/Host/Git adapters",
                    "infra.storage": "kernel must not depend on concrete storage",
                    "subprocess": "kernel must not spawn subprocesses",
                    "skills": "kernel must not import Skill-local implementations",
                },
            ),
        )
        self.assertEqual(
            [],
            text_marker_violations(
                SCRIPTS / "kernel",
                SCRIPTS,
                {
                    "template/skills/": "kernel must not call Skill-local scripts",
                    "skills/": "kernel must not call Skill-local scripts",
                    "skills\\": "kernel must not call Skill-local scripts",
                },
            ),
        )

    def test_infra_storage_does_not_depend_on_services_or_adapters(self) -> None:
        self.assertEqual(
            [],
            import_violations(
                SCRIPTS / "infra" / "storage",
                SCRIPTS,
                {
                    "services": "storage must stay below use-case services",
                    "adapters": "storage must not depend on delivery adapters",
                },
            ),
        )

    def test_services_do_not_depend_on_delivery_adapters_or_cli_modules(self) -> None:
        self.assertEqual(
            [],
            import_violations(
                SCRIPTS / "services",
                SCRIPTS,
                {
                    "adapters": "services must not depend on delivery adapters",
                    "argparse": "services must not parse CLI arguments",
                    "click": "services must not own CLI command surfaces",
                },
            ),
        )

    def test_runtime_modules_do_not_reverse_import_specific_skills(self) -> None:
        self.assertEqual(
            [],
            import_violations(
                SCRIPTS / "runtime",
                SCRIPTS,
                {"skills": "runtime must not import Skill-local implementations"},
            ),
        )
        self.assertEqual(
            [],
            text_marker_violations(
                SCRIPTS / "runtime",
                SCRIPTS,
                {
                    "template/skills/": "runtime must not call Skill-local scripts",
                    "skills/": "runtime must not call Skill-local scripts",
                    "skills\\": "runtime must not call Skill-local scripts",
                },
            ),
        )

    def test_infra_owns_non_domain_helpers(self) -> None:
        self.assertTrue((SCRIPTS / "infra" / "developer_profile.py").is_file())
        self.assertTrue((SCRIPTS / "infra" / "quality_sources.py").is_file())

    def _imports_between(
        self,
        source_package: str,
        blocked_packages: set[str],
    ) -> list[str]:
        issues: list[str] = []
        for path in (SCRIPTS / source_package).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                module = self._import_module(node)
                if module and module.split(".", 1)[0] in blocked_packages:
                    rel = path.relative_to(SCRIPTS).as_posix()
                    issues.append(f"{rel}: imports {module}")
        return sorted(issues)

    def _text_markers_in(
        self,
        source_package: str,
        blocked_markers: set[str],
    ) -> list[str]:
        issues: list[str] = []
        for path in (SCRIPTS / source_package).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for marker in blocked_markers:
                if marker in text:
                    rel = path.relative_to(SCRIPTS).as_posix()
                    issues.append(f"{rel}: contains {marker}")
        return sorted(issues)

    def _calls_named(
        self,
        source_package: str,
        blocked_names: set[str],
    ) -> list[str]:
        issues: list[str] = []
        for path in (SCRIPTS / source_package).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    name = self._call_name(node)
                    if name in blocked_names:
                        rel = path.relative_to(SCRIPTS).as_posix()
                        issues.append(f"{rel}: calls {name}")
        return sorted(issues)

    @staticmethod
    def _import_module(node: ast.AST) -> str | None:
        if isinstance(node, ast.ImportFrom):
            return node.module
        if isinstance(node, ast.Import) and node.names:
            return node.names[0].name
        return None

    @staticmethod
    def _call_name(node: ast.Call) -> str | None:
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None


if __name__ == "__main__":
    unittest.main()
