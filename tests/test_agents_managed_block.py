"""Root and template AGENTS.md must ship an identical managed block.

The managed block is the only region sync rewrites in place; if the source
checkout copy and the distribution source drift apart, downstream projects
receive a different rule set than the repository claims to ship.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
START = "<!-- COWORK-FLOW:START -->"
END = "<!-- COWORK-FLOW:END -->"


def _managed_block(relative_path: str) -> str:
    content = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
    start = content.index(START)
    end = content.index(END, start)
    return content[start : end + len(END)]


def test_root_and_template_managed_blocks_are_byte_identical() -> None:
    assert _managed_block("AGENTS.md") == _managed_block("template/AGENTS.md")


def test_managed_block_points_at_spec_check_contract() -> None:
    block = _managed_block("template/AGENTS.md")
    assert "spec/contracts/spec-checks.md" in block
    assert "run spec-check" in block
