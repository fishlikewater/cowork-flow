#!/usr/bin/env python3
"""Emit cowork-flow workflow context for Codex hooks."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _read_input() -> dict[str, Any]:
    raw = sys.stdin.buffer.read()
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _find_root(start: Path) -> Path | None:
    current = start.resolve()
    while True:
        if (current / ".cowork-flow").is_dir():
            return current
        if current == current.parent:
            return None
        current = current.parent


def main() -> int:
    if (
        os.environ.get("COWORK_FLOW_HOOKS") == "0"
        or os.environ.get("COWORK_FLOW_DISABLE_HOOKS") == "1"
    ):
        return 0
    hook_input = _read_input()
    cwd_value = hook_input.get("cwd")
    cwd = (
        Path(cwd_value)
        if isinstance(cwd_value, str) and cwd_value.strip()
        else Path.cwd()
    )
    root = _find_root(cwd)
    if root is None:
        return 0
    scripts_dir = root / ".cowork-flow" / "scripts"
    sys.path.insert(0, str(scripts_dir))
    from adapters.host.workflow_state_hook import (
        build_hook_context,
        codex_dispatch_mode,
    )

    dispatch_mode = codex_dispatch_mode(root)
    event_name = (
        hook_input.get("hook_event_name")
        or hook_input.get("hookEventName")
        or "UserPromptSubmit"
    )
    context = build_hook_context(
        root,
        hook_input,
        host="codex",
        adapter="codex.spawn_agent",
        preamble=(
            f"<codex-dispatch-mode>{dispatch_mode}</codex-dispatch-mode>",
            (
                "<codex-runtime>\n"
                "dispatch_mode_meaning: workflow dispatch hint, not current "
                "thread role\n"
                "runtime_context_identity: formal subagent sessions bind "
                "before workflow-state injection\n"
                "</codex-runtime>"
            ),
        ),
        # Codex registers UserPromptSubmit only, so event_name carries no
        # session-start signal; build_hook_context falls back to the session
        # state file probe (full on first injection, slim afterwards).
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event_name,
                    "additionalContext": context,
                }
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    _configure_stdio()
    raise SystemExit(main())
