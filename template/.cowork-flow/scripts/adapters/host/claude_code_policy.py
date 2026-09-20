#!/usr/bin/env python3
"""claude-code host policy: the claude-code-specific behaviors of the
workflow hook.

Rendering stays in workflow_state_hook.py; this module owns only the
claude-code transport specifics — the runtime preamble block and the
PostToolUse spec-advisory path (stderr + exit 2, shared with codex via the
neutral helper).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from adapters.host.workflow_state_hook import HostPolicy

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
    from adapters.host.workflow_state_hook import spec_only_post_tool_use

    return spec_only_post_tool_use(root, hook_input, POLICY)


POLICY = HostPolicy(
    host="claude-code",
    preamble=preamble,
    post_tool_use=post_tool_use,
)
