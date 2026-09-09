#!/usr/bin/env python3
"""codex host policy: the codex-specific behaviors of the workflow hook.

Rendering stays in workflow_state_hook.py; this module owns only the codex
transport specifics — the dispatch-mode preamble (config-driven, the codex
wrapper surfaces it above every injection) and the probe-based session-start
detection (codex registers UserPromptSubmit only, so the digest shape derives
from the session state file probe). PostToolUse reuses the neutral spec-only
stderr path shared with claude-code.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from adapters.host.workflow_state_hook import HostPolicy


def codex_dispatch_mode(root: Path) -> str:
    from adapters.host.workflow_state_hook import _load_common

    _load_common(root)
    try:
        from infra.config import get_codex_dispatch_mode
    except Exception:
        return "sub-agent"
    try:
        return get_codex_dispatch_mode(root)
    except Exception:
        return "sub-agent"


def preamble(root: Path) -> tuple[str, ...]:
    dispatch_mode = codex_dispatch_mode(root)
    return (
        f"<codex-dispatch-mode>{dispatch_mode}</codex-dispatch-mode>",
        (
            "<codex-runtime>\n"
            "dispatch_mode_meaning: workflow dispatch hint, not current "
            "thread role\n"
            "runtime_context_identity: formal subagent sessions bind "
            "before workflow-state injection\n"
            "</codex-runtime>"
        ),
    )


def post_tool_use(root: Path, hook_input: dict[str, Any]) -> tuple[str, int]:
    from adapters.host.workflow_state_hook import spec_only_post_tool_use

    return spec_only_post_tool_use(root, hook_input, POLICY)


POLICY = HostPolicy(
    host="codex",
    session_start_event=None,  # probe the session state file instead
    preamble=preamble,
    post_tool_use=post_tool_use,
)
