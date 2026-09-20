"""Root and template AGENTS.md must ship an identical managed block.

The managed block is the only region sync rewrites in place; if the source
checkout copy and the distribution source drift apart, downstream projects
receive a different rule set than the repository claims to ship.
"""

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
START = "<!-- COWORK-FLOW:START -->"
END = "<!-- COWORK-FLOW:END -->"


def _managed_block(relative_path: str) -> str:
    content = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
    start = content.index(START)
    end = content.index(END, start)
    return content[start : end + len(END)]


class AgentsManagedBlockTest(unittest.TestCase):
    def test_root_and_template_managed_blocks_are_byte_identical(self) -> None:
        self.assertEqual(
            _managed_block("AGENTS.md"),
            _managed_block("template/AGENTS.md"),
        )

    def test_managed_block_points_at_spec_check_contract(self) -> None:
        block = _managed_block("template/AGENTS.md")
        self.assertIn("spec/contracts/spec-checks.md", block)
        self.assertIn("run spec-check", block)


if __name__ == "__main__":
    unittest.main()
