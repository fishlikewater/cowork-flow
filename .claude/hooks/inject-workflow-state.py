#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Emit cowork-flow workflow context for Claude Code hooks.

This is a thin host-specific wrapper around common.inject_workflow_state.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent / ".cowork-flow" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from common.inject_workflow_state import (
    build_context,
    build_contract_digest,
    emit_hook_output,
    find_repo_root,
    get_active_task,
    load_breadcrumbs,
    read_hook_input,
    resolve_runtime_context,
    should_skip,
    subagent_runtime_lines,
)

HOST = "claude-code"
ADAPTER = "claude-code.hooks"


def _normalize_hook_input(hook_input: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(hook_input)
    if "claude_session_id" not in normalized:
        session_id = normalized.get("session_id")
        if isinstance(session_id, str) and session_id.strip():
            normalized["claude_session_id"] = session_id
    return normalized


def _hook_event_name(hook_input: dict[str, Any]) -> str:
    value = hook_input.get("hook_event_name") or hook_input.get("hookEventName")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "UserPromptSubmit"


def _build_host_block(root: Path) -> str:
    contract_digest = build_contract_digest(root, HOST, ADAPTER)
    return "\n\n".join(
        [
            "<claude-code-runtime>\nhooks: UserPromptSubmit, SessionStart\n</claude-code-runtime>",
            contract_digest,
        ]
    )


def main() -> int:
    if should_skip():
        return 0

    hook_input = _normalize_hook_input(read_hook_input())
    cwd_value = hook_input.get("cwd")
    cwd = (
        Path(cwd_value)
        if isinstance(cwd_value, str) and cwd_value.strip()
        else Path.cwd()
    )
    root = find_repo_root(cwd)
    if root is None:
        return 0

    event_name = _hook_event_name(hook_input)
    breadcrumbs = load_breadcrumbs(root)
    runtime_context, runtime_context_id = (
        resolve_runtime_context(root, hook_input)
        if event_name == "UserPromptSubmit"
        else (None, None)
    )
    extra_lines: list[str] | None = None
    if runtime_context is not None:
        task_dir = runtime_context.get("task_dir")
        task_path = (
            task_dir.strip() if isinstance(task_dir, str) and task_dir.strip() else None
        )
        status = "delegated_subtask"
        source = f"runtime-context:{runtime_context.get('runtime_context_id')}"
        extra_lines = subagent_runtime_lines(runtime_context)
    elif runtime_context_id:
        task_path = None
        status = "delegated_subtask"
        source = f"runtime-context-invalid:{runtime_context_id}"
        extra_lines = [
            f"Runtime context: {runtime_context_id}",
            "Scope: subagent",
            "Runtime context is missing, closed, or invalid. Do not run start/resume/task start/archive/commit/spawn.",
        ]
    else:
        task_path, status, source = get_active_task(root, hook_input)

    additional_context = build_context(
        root,
        task_path,
        status,
        source,
        breadcrumbs,
        lambda: _build_host_block(root),
        extra_lines,
    )
    return emit_hook_output(event_name, additional_context)


if __name__ == "__main__":
    raise SystemExit(main())
