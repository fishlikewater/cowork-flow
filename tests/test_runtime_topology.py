from __future__ import annotations

import ast
import unittest
from pathlib import Path

from tests.flow_test_support import ROOT


SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"


class RuntimeTopologyTest(unittest.TestCase):
    def test_scripts_top_level_exposes_only_kernel_services_and_adapters(self) -> None:
        top_level = {
            path.name
            for path in SCRIPTS.iterdir()
            if path.name != "__pycache__"
        }

        self.assertEqual(
            {"__init__.py", "run.py", "kernel", "services", "adapters"},
            top_level,
        )

    def test_workflow_routing_policy_lives_in_services(self) -> None:
        self.assertTrue((SCRIPTS / "services" / "task_routing.py").is_file())
        self.assertFalse((SCRIPTS / "kernel" / "workflow_route.py").exists())

    def test_execution_context_cli_args_live_in_adapter(self) -> None:
        self.assertTrue(
            (SCRIPTS / "adapters" / "cli" / "execution_context_args.py").is_file()
        )

    def test_kernel_does_not_import_services_or_adapters(self) -> None:
        self.assertEqual(
            [],
            self._imports_between("kernel", {"services", "adapters"}),
        )

    def test_kernel_does_not_own_cli_argparse_construction(self) -> None:
        self.assertEqual(
            [],
            self._imports_between("kernel", {"argparse"}),
        )

    def test_services_do_not_import_adapters(self) -> None:
        self.assertEqual(
            [],
            self._imports_between("services", {"adapters"}),
        )

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
