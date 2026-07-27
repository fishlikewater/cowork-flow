"""CLI resume text rendering for execution contexts."""

from __future__ import annotations

import json
from pathlib import Path

from infra.paths import DIR_WORKFLOW, get_repo_root
from runtime.execution_context import (
    ExecutionContext,
    load_execution_context_file,
)


def worker_command_block_message(
    context: ExecutionContext,
    command: str,
    reason: str,
) -> str:
    assignment = context.assignment or "unknown-assignment"
    return f"Blocked: worker mode cannot run `{command}` for assignment {assignment}. {reason}"


def _append_allowed_context(
    lines: list[str],
    allowed_context: object,
    *,
    allow_string_items: bool,
) -> None:
    if not isinstance(allowed_context, list) or not allowed_context:
        return
    lines.extend(["", "## Allowed context"])
    for item in allowed_context:
        if allow_string_items and isinstance(item, str) and item.strip():
            lines.append(f"- {item.strip()}")
        elif isinstance(item, dict):
            _append_file_reason_item(lines, item)


def _append_file_reason_item(lines: list[str], item: dict) -> None:
    file_value = item.get("file")
    reason = item.get("reason")
    if isinstance(file_value, str) and file_value.strip():
        suffix = f" - {reason}" if isinstance(reason, str) and reason.strip() else ""
        lines.append(f"- {file_value}{suffix}")


def _append_string_list_section(
    lines: list[str],
    title: str,
    values: object,
) -> None:
    if not isinstance(values, list) or not values:
        return
    items = [value.strip() for value in values if isinstance(value, str) and value.strip()]
    if not items:
        return
    lines.extend(["", title])
    lines.extend(f"- {item}" for item in items)


def _append_context_metadata(
    lines: list[str],
    context_data: dict[str, object],
) -> None:
    metadata_fields = [
        ("runtimeContextId", "Runtime context"),
        ("runtimeContextStatus", "Runtime context status"),
        ("agentType", "Agent type"),
        ("dispatchReliability", "Dispatch reliability"),
    ]
    runtime_context_id = (
        context_data.get("runtimeContextId")
        or context_data.get("runtime_context_id")
    )
    if isinstance(runtime_context_id, str) and runtime_context_id.strip():
        lines.append(f"Runtime context: {runtime_context_id}")
    for key, label in metadata_fields[1:]:
        value = context_data.get(key)
        if isinstance(value, str) and value.strip():
            lines.append(f"{label}: {value}")


def _append_status_file(
    lines: list[str],
    repo_root: Path,
    status_file: object,
) -> None:
    if not isinstance(status_file, str) or not status_file.strip():
        return
    status_path = repo_root / status_file
    if not status_path.is_file():
        return
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        lines.extend(["", "## Current status", f"Status file unreadable: {status_file}"])
        return
    lines.extend(["", "## Current status", f"Status: {status.get('status', 'unknown')}"])
    note = status.get("note")
    if isinstance(note, str) and note.strip():
        lines.append(f"Note: {note}")


def _append_recent_events(
    lines: list[str],
    repo_root: Path,
    events_file: object,
) -> None:
    if not isinstance(events_file, str) or not events_file.strip():
        return
    events_path = repo_root / events_file
    if not events_path.is_file():
        return
    events = events_path.read_text(encoding="utf-8").splitlines()[-5:]
    if events:
        lines.extend(["", "## Recent events"])
        lines.extend(f"- {event}" for event in events)


def _worker_resume_header(context: ExecutionContext) -> list[str]:
    lines = [
        "========================================",
        "WORKER CONTEXT",
        "========================================",
        "",
        "## EXECUTION MODE",
        f"Mode: {context.mode}",
        f"Assignment: {context.assignment or 'unknown'}",
        f"Task directory: {context.task_dir or 'unknown'}",
    ]
    if context.prompt_file:
        lines.append(f"Prompt file: {context.prompt_file}")
    if context.context_file:
        lines.append(f"Context file: {context.context_file}")
    return lines


def _append_worker_read_first(
    lines: list[str],
    context: ExecutionContext,
    repo_root: Path,
    context_data: dict[str, object],
) -> None:
    lines.extend(["", "## READ FIRST", f"- Read worker brief: {context.prompt_file or '(missing prompt file)'}"])
    _append_allowed_context(
        lines,
        context_data.get("allowedContext"),
        allow_string_items=False,
    )
    decision_anchor = repo_root / (context.task_dir or "") / "decision-anchor.md"
    if context.task_dir and decision_anchor.is_file():
        lines.append(f"- Read task decision-anchor: {context.task_dir}/decision-anchor.md")
    lines.append("- Follow only the files, steps, and commands named in the worker brief.")


def _append_worker_rules(lines: list[str], context: ExecutionContext) -> None:
    lines.extend(
        [
            "",
            "## RULES",
            "- You are the leaf executor for this assignment. Do not switch into coordinator behavior.",
            "- Do not run unscoped cowork-flow workflow commands from this worker thread.",
            "- If you are blocked by missing context, unclear scope, or ambiguous requirements, report NEEDS_CONTEXT",
            "  with the specific missing fact. The coordinator will update the assignment context and retry.",
            "- Do not activate tasks, coordinate other workers, or elevate your own permissions.",
            "",
            f"Use scoped cowork-flow commands like: ./{DIR_WORKFLOW}/run --context-file "
            f"{context.context_file or '<assignment-context.json>'} resume",
            "",
            "========================================",
        ]
    )


def build_worker_resume_text(
    context: ExecutionContext,
    repo_root: Path | None = None,
) -> str:
    if repo_root is None:
        repo_root = get_repo_root()

    lines = _worker_resume_header(context)
    context_data = load_execution_context_file(context.context_file) if context.context_file else {}
    _append_worker_read_first(lines, context, repo_root, context_data)
    _append_string_list_section(
        lines,
        "## FORBIDDEN ACTIONS",
        context_data.get("forbiddenActions"),
    )
    _append_worker_rules(lines, context)
    return "\n".join(lines)


def _subagent_resume_header(
    context: ExecutionContext,
    context_data: dict[str, object],
) -> list[str]:
    lines = [
        "========================================",
        "COWORK-FLOW SUBAGENT RESUME",
        "========================================",
        "Use this only for a runtime-context subagent's own scoped recovery.",
        "Do not switch back into the coordinator workflow from this entrypoint.",
        "",
        "## SUBAGENT CONTEXT",
        f"Mode: {context.mode}",
        f"Title: {context.title or 'unknown'}",
        f"Role: {context.role or 'unknown'}",
        f"Goal: {context.goal or 'unknown'}",
    ]
    _append_context_metadata(lines, context_data)
    if context.context_file:
        lines.append(f"Context file: {context.context_file}")
    return lines


def _append_subagent_rules(lines: list[str]) -> None:
    lines.extend([
        "",
        "## RULES",
        "- Execute only when the bound runtime context exists, is open, and names this agent type.",
        "- If runtime context is missing, closed, invalid, or mismatched, report needs_context and do not execute it.",
        "- Generic worker dispatch is advisory only and cannot complete formal Implement or Check.",
        "- Read only prompt-named files and allowed context unless you ask for more context.",
        "- Do not run standalone lifecycle commands, unscoped resume, archive, or commit actions.",
        "- Stop only with success, needs_context, or blocked status evidence.",
        "",
        "========================================",
    ])


def build_subagent_resume_text(
    context: ExecutionContext,
    repo_root: Path | None = None,
) -> str:
    if repo_root is None:
        repo_root = get_repo_root()
    context_data = load_execution_context_file(context.context_file) if context.context_file else {}
    lines = _subagent_resume_header(context, context_data)
    _append_allowed_context(
        lines,
        context_data.get("allowedContext"),
        allow_string_items=True,
    )
    _append_string_list_section(
        lines,
        "## Forbidden actions",
        context_data.get("forbiddenActions"),
    )
    _append_status_file(lines, repo_root, context_data.get("statusFile"))
    _append_recent_events(lines, repo_root, context_data.get("eventsFile"))
    _append_subagent_rules(lines)
    return "\n".join(lines)
