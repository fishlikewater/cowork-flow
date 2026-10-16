#!/usr/bin/env python3
"""Shared edit-phase scope advisory (the PostToolUse short path).

At most one line when an edited file is outside the active task's
file-scope whitelist; empty string (silent) when in scope, when the task
is not in a spec-contract state, for subagent sessions, or on any error.
Hosts differ only in transport: inject.py hosts reach this through their
policy `post_tool_use` slot, the dsh preset plugin through its own Python
protocol. The wording is frozen by context-injection.md — never fork it
per host.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from adapters.host.workflow_state_hook import (
    STAGE_CONTRACT_STATES,
    _get_active_task_with_fallback,
    _session_scope,
)

_APPLY_PATCH_FILE_RE = re.compile(
    r"^\*\*\* (?:Update|Add|Delete) File: (.+?)\s*$", re.MULTILINE
)


def extract_edited_paths(tool_input: Any) -> list[str]:
    """Best-effort edited file paths from a PostToolUse tool_input payload.

    Hosts differ: claude-code, zcode, qoder and opencode pass file_path,
    while codex's apply_patch carries the paths inside the patch text.
    Returning every extractable path keeps a multi-file patch from
    silently skipping the warning; deduplication keeps one edit from
    checking the same file twice."""
    if not isinstance(tool_input, dict):
        return []
    paths: list[str] = []
    for key in ("file_path", "filePath", "path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            paths.append(value.strip())
    for key in ("input", "patch", "patchText"):
        text = tool_input.get(key)
        if isinstance(text, str):
            paths.extend(
                match.strip() for match in _APPLY_PATCH_FILE_RE.findall(text)
            )
    seen: set[str] = set()
    unique: list[str] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def edit_scope_warning(
    root: Path,
    hook_input: dict[str, Any],
    *,
    fallback_for_unbound: bool = False,
) -> str:
    """At most one line when the edited file is outside the task's
    file-scope whitelist. Silence rules: no active in_progress/review
    task, a subagent session, an in-scope path, an unreadable whitelist,
    or no extractable path. `fallback_for_unbound` follows the calling
    host's policy (zcode: true). Never raises — the edit has already
    happened."""
    try:
        task_path, status, _source = _get_active_task_with_fallback(
            root, hook_input, fallback_for_unbound
        )
    except Exception:
        return ""
    if not task_path or status not in STAGE_CONTRACT_STATES:
        return ""
    if _session_scope(root, hook_input) == "subagent":
        return ""
    paths = extract_edited_paths(hook_input.get("tool_input"))
    if not paths:
        return ""
    try:
        from services.fact_view import file_scope_whitelist, path_in_scope

        whitelist = file_scope_whitelist(root, root / task_path)
    except Exception:
        return ""
    for file_path in paths:
        # Hosts pass absolute edit paths; whitelist entries are
        # repo-relative. Same normalization as run_edit_checks took.
        normalized = file_path.replace("\\", "/").strip()
        try:
            normalized = (
                Path(normalized).resolve().relative_to(root.resolve()).as_posix()
            )
        except (ValueError, OSError):
            pass
        try:
            if path_in_scope(whitelist, normalized).get("inScope"):
                continue
        except Exception:
            return ""
        while normalized.startswith("./"):
            normalized = normalized[2:]
        return (
            f"⚠️ {normalized} is outside the task's declared scope. "
            "If intended, declare it in the task's `implement.jsonl` (agent-mutable) "
            "or revert the edit."
        )
    return ""
