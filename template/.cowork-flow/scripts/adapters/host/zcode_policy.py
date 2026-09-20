#!/usr/bin/env python3
"""zcode host policy: the zcode-specific behaviors of the workflow hook.

Rendering stays in workflow_state_hook.py (single source shared with the
other hosts); this module owns only what is zcode-specific — the digest
policy wording, the newest-session fallback for unbound hook sessions, the
rebind hints and essential-files check ported from the zcode JS hook, the
merged scope+spec edit warning, and the PostToolUse transport contract the
zcode shim relies on.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from adapters.host.workflow_state_hook import HostPolicy

# Digest policy wording frozen by context-injection.md (zcode drops the
# registry-warning line and asks for the fingerprint on every hook).
ZCODE_DIGEST_POLICY = (
    "policy: repeat fingerprint every hook; "
    "read full spec files only before listed actions."
)

# The zcode shim (hooks/inject-context.js) pre-filters Bash events with the
# same rule; this entry keeps the transport contract correct standalone.
LIFECYCLE_BASH_RE = re.compile(r"\brun(?:\.cmd)?\s+(?:task|subagent|resume)\b")

# Port of the zcode hook's essential-files check (inject-context.js
# checkEssentialFiles): appended to the zcode context when any guard file of
# the workflow install is missing.
ESSENTIAL_FILES = (
    "AGENTS.md",
    ".cowork-flow/config.yaml",
    ".cowork-flow/run",
    ".cowork-flow/spec/runtime/contract-registry.json",
    ".cowork-flow/spec/contracts/workflow-state-templates.md",
)


def is_lifecycle_bash(hook_input: dict[str, Any]) -> bool:
    tool_input = hook_input.get("tool_input")
    command = (
        tool_input.get("command") if isinstance(tool_input, dict) else None
    )
    if not isinstance(command, str):
        return False
    normalized = command.replace("\\", "/")
    return ".cowork-flow/run" in normalized or bool(
        LIFECYCLE_BASH_RE.search(normalized)
    )


# Activation intent inside a lifecycle Bash command: `task next <dir> --run`,
# `task start <dir>`, `resume <dir>` (the run prefix is optional). Query
# forms (`task next --json`, `task next --run` without a dir) match nothing
# claimable — the captured token must be a task dir whose task.json exists.
ACTIVATION_COMMAND_RE = re.compile(
    r"\btask\s+next\s+(?P<next>\S+)\s+--run\b"
    r"|\btask\s+start\s+(?P<start>\S+?)(?=\s|$)"
    r"|(?<![\w./-])resume\s+(?P<resume>\S+?)(?=\s|$)"
)


def _resolvable_task_path(root: Path, token: str) -> str | None:
    candidates = [token]
    if not token.startswith(".cowork-flow/"):
        candidates.append(f".cowork-flow/tasks/{token}")
    for candidate in candidates:
        normalized = candidate.replace("\\", "/").strip("/")
        if (root / normalized / "task.json").is_file():
            return normalized
    return None


def claim_after_lifecycle_bash(root: Path, hook_input: dict[str, Any]) -> None:
    """Bind the activated task to this hook session's own identity.

    The lifecycle Bash CLI resolves a process-fallback identity, so the
    binding it writes is shared across windows; PostToolUse re-binds with the
    hook input's session id via session_state.claim_active_task (explicit /
    host_session provenance only). Commands without an activation intent or
    with an unresolvable task dir claim nothing, and claim failure stays
    silent — the refresh path below still renders the state."""
    tool_input = hook_input.get("tool_input")
    command = (
        tool_input.get("command") if isinstance(tool_input, dict) else None
    )
    if not isinstance(command, str):
        return
    match = ACTIVATION_COMMAND_RE.search(command.replace("\\", "/"))
    if match is None:
        return
    token = next(value for value in match.groupdict().values() if value)
    if token.startswith("-"):
        return
    task_path = _resolvable_task_path(root, token)
    if task_path is None:
        return
    try:
        from runtime.session_state import claim_active_task

        claim_active_task(root, task_path, hook_input)
    except Exception:
        pass


def rebind_hints(root: Path) -> str:
    """Port of the zcode hook's formatRebindHints: one-level task scan for
    bindable (non-completed) tasks, appended to no_task/missing bodies."""
    tasks_dir = root / ".cowork-flow" / "tasks"
    try:
        children = sorted(tasks_dir.iterdir())
    except OSError:
        return ""
    entries: list[str] = []
    for child in children:
        if not child.is_dir():
            continue
        relative = f".cowork-flow/tasks/{child.name}"
        task_json = child / "task.json"
        if not task_json.is_file():
            continue
        try:
            data = json.loads(task_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            status = "unknown"
        else:
            status = str(data.get("status") or "unknown").strip() or "unknown"
        if status == "completed":
            continue
        entries.append(f"- {relative} ({status})")
    if not entries:
        return ""
    return (
        "\n活动任务（可用 ./.cowork-flow/run task next <dir> 改绑）：\n"
        + "\n".join(entries)
    )


def essential_files_warning(root: Path) -> str:
    missing = [rel for rel in ESSENTIAL_FILES if not (root / rel).exists()]
    if not missing:
        return ""
    return (
        "\n\n⚠️ 缺少必要文件："
        + ", ".join(missing)
        + "。\n请立即创建这些文件以保障工作流正常运行。"
    )


def edit_scope_warning(root: Path, hook_input: dict[str, Any]) -> str:
    """Per-edit out-of-scope warning (zcode-only capability). Port of the
    zcode hook's editScopeWarning: at most one line when the edited file is
    outside the task's file-scope whitelist. Silence rules match the JS
    source, including the newest-session display fallback for sessions with
    no resolvable identity. Never raises."""
    from adapters.host.workflow_state_hook import (
        STAGE_CONTRACT_STATES,
        _get_active_task_with_fallback,
        _session_scope,
    )

    try:
        task_path, status, _source = _get_active_task_with_fallback(
            root, hook_input, POLICY.fallback_for_unbound
        )
    except Exception:
        return ""
    if not task_path or status not in STAGE_CONTRACT_STATES:
        return ""
    if _session_scope(root, hook_input) == "subagent":
        return ""
    tool_input = hook_input.get("tool_input")
    file_path = (
        tool_input.get("file_path") if isinstance(tool_input, dict) else None
    )
    if not isinstance(file_path, str) or not file_path.strip():
        return ""
    # Hosts pass absolute edit paths; whitelist entries are repo-relative.
    # Same normalization the spec path applies in run_edit_checks.
    normalized = file_path.replace("\\", "/").strip()
    try:
        normalized = (
            Path(normalized).resolve().relative_to(root.resolve()).as_posix()
        )
    except (ValueError, OSError):
        pass
    try:
        from services.fact_view import file_scope_whitelist, path_in_scope

        whitelist = file_scope_whitelist(root, root / task_path)
        if path_in_scope(whitelist, normalized).get("inScope"):
            return ""
    except Exception:
        return ""
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return (
        f"⚠️ {normalized} is outside the task's declared scope. "
        "If intended, add it with `task context add` (agent-mutable) "
        "or revert the edit."
    )


def merged_edit_warning(root: Path, hook_input: dict[str, Any]) -> str:
    """zcode PostToolUse Edit/Write/MultiEdit context: the scope warning and
    the spec-check warning merged into one additionalContext payload, at
    most one line each, joined by a newline (port of the zcode hook's
    mergedEditWarning)."""
    from adapters.host.workflow_state_hook import spec_edit_warning

    scope_line = edit_scope_warning(root, hook_input)
    spec_line = spec_edit_warning(root, hook_input, POLICY)
    if scope_line and spec_line:
        return f"{scope_line}\n{spec_line}"
    return scope_line or spec_line


def post_tool_use(root: Path, hook_input: dict[str, Any]) -> tuple[str, int]:
    """zcode PostToolUse transport: Edit/Write/MultiEdit get the merged
    edit warning; Bash events refresh the full state only for workflow
    lifecycle commands (the shim pre-filters the common case, this keeps
    the entry correct standalone). Edit storms must not multiply the
    injection payload."""
    tool_name = str(hook_input.get("tool_name") or "")
    tool_input = hook_input.get("tool_input")
    file_path = (
        tool_input.get("file_path") if isinstance(tool_input, dict) else None
    )
    if (
        tool_name in {"Edit", "Write", "MultiEdit"}
        and isinstance(file_path, str)
        and file_path.strip()
    ):
        return merged_edit_warning(root, hook_input), 0
    if not is_lifecycle_bash(hook_input):
        return "", 0
    claim_after_lifecycle_bash(root, hook_input)
    from adapters.host.workflow_state_hook import build_hook_context

    context = build_hook_context(
        root,
        hook_input,
        host=POLICY.host,
        adapter="zcode.plugin",
        preamble=(),
        session_start=False,
        policy=POLICY,
    )
    return context, 0


POLICY = HostPolicy(
    host="zcode",
    digest_policy=ZCODE_DIGEST_POLICY,
    digest_warning_silent=True,
    rebind_hints=rebind_hints,
    essential_files_warning=essential_files_warning,
    fallback_for_unbound=True,
    post_tool_use=post_tool_use,
    emit_indent=True,
    emit_not_initialized=True,
)
