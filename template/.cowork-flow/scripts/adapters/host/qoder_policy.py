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

from adapters.host.policy_base import HostPolicy
from adapters.host.workflow_state_hook import hook_state_summary, spec_edit_warning

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
    return spec_edit_warning(root, hook_input, POLICY), 0


# The task directory name is user-chosen and unbounded, and the host renders
# the message as a single line: cap the name so the line cannot wrap (the
# longest status, delegated_subtask, still fits the 160-character budget).
TASK_NAME_BUDGET = 100


def system_message(root: Path, hook_input: dict[str, Any], event_name: str) -> str:
    """One-line trace of the injection for Qoder's CLI-side surfaces.

    Qoder's hook output schema accepts a top-level `systemMessage` and renders
    it in the interactive TUI (the model's context is unaffected); the desktop
    client renders no hook output text, so there the trace is the hook-summary
    tooltip on the reply, not this line.
    """
    status, task_name = hook_state_summary(root, hook_input, host="qoder", policy=POLICY)
    if task_name and len(task_name) > TASK_NAME_BUDGET:
        task_name = f"{task_name[: TASK_NAME_BUDGET - 1]}…"
    suffix = f" · task={task_name}" if task_name else ""
    return f"cowork-flow: 工作流状态已注入 · status={status}{suffix}"


POLICY = HostPolicy(
    host="qoder",
    preamble=preamble,
    post_tool_use=post_tool_use,
    system_message=system_message,
)
