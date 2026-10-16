#!/usr/bin/env python3
"""claude-code host policy: the claude-code-specific behaviors of the
workflow hook.

Rendering stays in workflow_state_hook.py; this module owns only the
claude-code transport specifics — the runtime preamble block.
"""

from __future__ import annotations

from pathlib import Path

from adapters.host.policy_base import HostPolicy

CLAUDE_PREAMBLE = (
    (
        "<claude-code-runtime>\n"
        "hooks: UserPromptSubmit, SessionStart\n"
        "</claude-code-runtime>"
    ),
)


def preamble(root: Path) -> tuple[str, ...]:
    return CLAUDE_PREAMBLE


POLICY = HostPolicy(
    host="claude-code",
    preamble=preamble,
)
