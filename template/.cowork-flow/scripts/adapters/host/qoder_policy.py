#!/usr/bin/env python3
"""qoder host policy: the Qoder behaviors of the workflow hook.

Rendering stays in workflow_state_hook.py; this module owns only what Qoder
changes. Qoder shares the JSON envelope shape (`hookSpecificOutput`) with
claude-code and codex, but its `PostToolUse` is not a blockable event: exit 2
there is ignored, so the edit-phase spec advisory must travel as
`additionalContext` on exit 0 instead of stderr.

Host assets (hooks declaration, fixed subagents, commands, skills) ship as a
machine-level Qoder plugin, so the hook reaches this entry through the plugin
shim and the project is located from the payload `cwd`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from adapters.host.workflow_state_hook import HostPolicy

QODER_PREAMBLE = (
    (
        "<qoder-runtime>\n"
        "hooks: SessionStart, UserPromptSubmit, PostToolUse\n"
        "</qoder-runtime>"
    ),
)


def preamble(root: Path) -> tuple[str, ...]:
    return QODER_PREAMBLE


def post_tool_use(root: Path, hook_input: dict[str, Any]) -> tuple[str, int]:
    from adapters.host.workflow_state_hook import spec_edit_warning

    return spec_edit_warning(root, hook_input, POLICY), 0


POLICY = HostPolicy(
    host="qoder",
    preamble=preamble,
    post_tool_use=post_tool_use,
)
