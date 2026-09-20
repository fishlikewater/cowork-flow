"""Every test module must be visible to the unittest collector.

The release gate runs ``python -m unittest``, which only collects
``unittest.TestCase`` subclasses. Module-level ``def test_*`` functions run
under pytest and silently disappear from the gate, so the same corpus would
mean two different things depending on who runs it. This guard keeps the
corpus honest for both collectors.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"


def _module_level_test_functions(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ]


class TestCollectionTest(unittest.TestCase):
    def test_no_test_module_hides_cases_from_the_unittest_collector(self) -> None:
        offenders: list[str] = []
        for path in sorted(TESTS.rglob("test_*.py")):
            if "__pycache__" in path.parts:
                continue
            for name in _module_level_test_functions(path):
                offenders.append(f"{path.relative_to(ROOT)}: def {name}()")

        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
