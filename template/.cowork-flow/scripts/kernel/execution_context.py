"""Execution context helpers for coordinator and worker scoped cowork-flow commands."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .paths import DIR_WORKFLOW, get_repo_root


MODE_NONE = "none"
MODE_COORDINATOR = "coordinator"
MODE_WORKER = "worker"
MODE_SUBAGENT = "subagent"


class ExecutionContextError(ValueError):
    """Raised when execution context flags are invalid."""


@dataclass(frozen=True)
class ExecutionContext:
    mode: str = MODE_NONE
    assignment: str | None = None
    task_dir: str | None = None
    prompt_file: str | None = None
    context_file: str | None = None
    title: str | None = None
    role: str | None = None
    goal: str | None = None

    @property
    def is_worker(self) -> bool:
        return self.mode == MODE_WORKER

    @property
    def is_coordinator(self) -> bool:
        return self.mode == MODE_COORDINATOR

    @property
    def is_subagent(self) -> bool:
        return self.mode == MODE_SUBAGENT

    @property
    def is_default(self) -> bool:
        return (
            self.mode == MODE_NONE
            and self.assignment is None
            and self.task_dir is None
            and self.prompt_file is None
            and self.context_file is None
        )


def _strip(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _load_context_file(path: str) -> dict[str, object]:
    context_path = Path(path)
    try:
        return json.loads(context_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ExecutionContextError(f"context file not found: {path}") from error
    except json.JSONDecodeError as error:
        raise ExecutionContextError(f"context file is not valid JSON: {path}") from error
    except OSError as error:
        raise ExecutionContextError(f"failed to read context file: {path}") from error


def execution_context_from_values(
    *,
    mode: str | None,
    assignment: str | None,
    task_dir: str | None,
    prompt_file: str | None,
    context_file: str | None,
) -> ExecutionContext:
    file_data: dict[str, object] = {}
    if context_file:
        file_data = _load_context_file(context_file)

    resolved_mode = _strip(mode) or _strip(file_data.get("mode")) or MODE_NONE
    if resolved_mode not in {MODE_NONE, MODE_COORDINATOR, MODE_WORKER, MODE_SUBAGENT}:
        raise ExecutionContextError(f"unsupported execution mode: {resolved_mode}")

    resolved_assignment = _strip(assignment) or _strip(file_data.get("assignment"))
    resolved_task_dir = _strip(task_dir) or _strip(file_data.get("taskDir"))
    resolved_prompt_file = _strip(prompt_file) or _strip(file_data.get("promptFile"))
    resolved_title = _strip(file_data.get("title"))
    resolved_role = _strip(file_data.get("role"))
    resolved_goal = _strip(file_data.get("goal"))

    if resolved_mode == MODE_WORKER:
        if not resolved_task_dir or not resolved_assignment:
            raise ExecutionContextError(
                "worker mode requires task dir and assignment (pass --context-file or --task-dir with --assignment)"
            )
        if not resolved_prompt_file:
            raise ExecutionContextError("worker mode requires prompt file")
    elif resolved_mode == MODE_SUBAGENT:
        if not resolved_title:
            raise ExecutionContextError("subagent mode requires title (pass --context-file from subagent init)")
    elif resolved_mode == MODE_COORDINATOR:
        if resolved_assignment or resolved_prompt_file:
            raise ExecutionContextError("assignment-scoped execution fields require worker mode")
    elif resolved_assignment or resolved_task_dir or resolved_prompt_file:
        raise ExecutionContextError("scoped execution fields require worker, coordinator, or subagent mode")

    return ExecutionContext(
        mode=resolved_mode,
        assignment=resolved_assignment,
        task_dir=resolved_task_dir,
        prompt_file=resolved_prompt_file,
        context_file=_strip(context_file),
        title=resolved_title,
        role=resolved_role,
        goal=resolved_goal,
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
    context_data = _load_context_file(context.context_file) if context.context_file else {}
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
    context_data = _load_context_file(context.context_file) if context.context_file else {}
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
