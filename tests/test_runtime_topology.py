from __future__ import annotations

import ast
import unittest
from pathlib import Path

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

    def test_services_do_not_import_adapters(self) -> None:
        self.assertEqual(
            [],
            self._imports_between("services", {"adapters"}),
        )

    def test_services_do_not_own_infra_concerns(self) -> None:
        self.assertFalse((SCRIPTS / "services" / "developer_profile.py").exists())
        self.assertFalse((SCRIPTS / "services" / "quality_sources.py").exists())
        self.assertFalse((SCRIPTS / "services" / "runtime_context.py").exists())
        self.assertTrue((SCRIPTS / "services" / "workflow_runtime.py").is_file())

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

    @staticmethod
    def _import_module(node: ast.AST) -> str | None:
        if isinstance(node, ast.ImportFrom):
            return node.module
        if isinstance(node, ast.Import) and node.names:
            return node.names[0].name
        return None


if __name__ == "__main__":
    unittest.main()
