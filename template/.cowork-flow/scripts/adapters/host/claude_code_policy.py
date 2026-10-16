#!/usr/bin/env python3
"""claude-code host policy: the claude-code-specific behaviors of the
workflow hook.

Rendering stays in workflow_state_hook.py; this module owns only the
claude-code transport specifics — the runtime preamble block and the
PostToolUse edit-scope advisory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from adapters.host.edit_scope import edit_scope_warning
from adapters.host.policy_base import HostPolicy

CLAUDE_PREAMBLE = (
    (
        "<claude-code-runtime>\n"
        "hooks: UserPromptSubmit, SessionStart, PostToolUse\n"
        "</claude-code-runtime>"
    ),
)


def preamble(root: Path) -> tuple[str, ...]:
    return CLAUDE_PREAMBLE


def post_tool_use(root: Path, hook_input: dict[str, Any]) -> tuple[str, int]:
    """PostToolUse transport: the edit-scope advisory rides the standard
    additionalContext envelope, exit 0 — the edit already happened, so
    this decorates the result and never blocks it."""
    return edit_scope_warning(root, hook_input), 0


POLICY = HostPolicy(
    host="claude-code",
    preamble=preamble,
    post_tool_use=post_tool_use,
)
