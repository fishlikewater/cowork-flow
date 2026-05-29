"""Execution context helpers for coordinator and worker scoped cowork-flow commands."""

from __future__ import annotations

import argparse
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


def _build_parser(
    *,
    add_help: bool,
    mode_flag: str,
    assignment_flag: str,
    task_dir_flag: str,
    prompt_file_flag: str,
    context_file_flag: str,
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=add_help)
    parser.add_argument(mode_flag, choices=[MODE_NONE, MODE_COORDINATOR, MODE_WORKER, MODE_SUBAGENT], help=argparse.SUPPRESS)
    parser.add_argument(assignment_flag, help=argparse.SUPPRESS)
    parser.add_argument(task_dir_flag, help=argparse.SUPPRESS)
    parser.add_argument(prompt_file_flag, help=argparse.SUPPRESS)
    parser.add_argument(context_file_flag, help=argparse.SUPPRESS)
    return parser


def build_public_execution_context_parser(add_help: bool = False) -> argparse.ArgumentParser:
    return _build_parser(
        add_help=add_help,
        mode_flag="--mode",
        assignment_flag="--assignment",
        task_dir_flag="--task-dir",
        prompt_file_flag="--prompt-file",
        context_file_flag="--context-file",
    )


def build_internal_execution_context_parser(add_help: bool = False) -> argparse.ArgumentParser:
    return _build_parser(
        add_help=add_help,
        mode_flag="--execution-mode",
        assignment_flag="--execution-assignment",
        task_dir_flag="--execution-task-dir",
        prompt_file_flag="--execution-prompt-file",
        context_file_flag="--execution-context-file",
    )


def _context_from_values(
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


def parse_public_execution_context_args(argv: list[str]) -> tuple[ExecutionContext, list[str]]:
    parser = build_public_execution_context_parser(add_help=False)
    leading: list[str] = []
    remaining = list(argv)
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in {"--mode", "--assignment", "--task-dir", "--prompt-file", "--context-file"}:
            if index + 1 >= len(argv):
                raise ExecutionContextError(f"missing value for {token}")
            leading.extend([token, argv[index + 1]])
            index += 2
            continue
        break

    remaining = argv[index:]
    namespace, leftover = parser.parse_known_args(leading)
    if leftover:
        raise ExecutionContextError(f"unsupported execution context arguments: {' '.join(leftover)}")
    context = _context_from_values(
        mode=getattr(namespace, "mode", None),
        assignment=getattr(namespace, "assignment", None),
        task_dir=getattr(namespace, "task_dir", None),
        prompt_file=getattr(namespace, "prompt_file", None),
        context_file=getattr(namespace, "context_file", None),
    )
    return context, remaining


def execution_context_from_namespace(namespace: argparse.Namespace) -> ExecutionContext:
    return _context_from_values(
        mode=getattr(namespace, "execution_mode", None),
        assignment=getattr(namespace, "execution_assignment", None),
        task_dir=getattr(namespace, "execution_task_dir", None),
        prompt_file=getattr(namespace, "execution_prompt_file", None),
        context_file=getattr(namespace, "execution_context_file", None),
    )


def context_to_internal_cli_args(context: ExecutionContext) -> list[str]:
    if context.is_default:
        return []
    if context.context_file:
        return ["--execution-context-file", context.context_file]

    args = ["--execution-mode", context.mode]
    if context.task_dir:
        args.extend(["--execution-task-dir", context.task_dir])
    if context.assignment:
        args.extend(["--execution-assignment", context.assignment])
    if context.prompt_file:
        args.extend(["--execution-prompt-file", context.prompt_file])
    return args


def worker_command_block_message(
    context: ExecutionContext,
    command: str,
    reason: str,
) -> str:
    assignment = context.assignment or "unknown-assignment"
    return f"Blocked: worker mode cannot run `{command}` for assignment {assignment}. {reason}"


def build_worker_resume_text(
    context: ExecutionContext,
    repo_root: Path | None = None,
) -> str:
    if repo_root is None:
        repo_root = get_repo_root()

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
    lines.extend(
        [
            "",
            "## READ FIRST",
            f"- Read worker brief: {context.prompt_file or '(missing prompt file)'}",
        ]
    )
    context_data = _load_context_file(context.context_file) if context.context_file else {}
    allowed_context = context_data.get("allowedContext")
    if isinstance(allowed_context, list) and allowed_context:
        lines.extend(["", "## Allowed context"])
        for item in allowed_context:
            if not isinstance(item, dict):
                continue
            file_value = item.get("file")
            reason = item.get("reason")
            if isinstance(file_value, str) and file_value.strip():
                suffix = f" - {reason}" if isinstance(reason, str) and reason.strip() else ""
                lines.append(f"- {file_value}{suffix}")
    if context.task_dir and (repo_root / context.task_dir / "prd.md").is_file():
        lines.append(f"- Read task PRD: {context.task_dir}/prd.md")
    lines.append("- Follow only the files, steps, and commands named in the worker brief.")

    forbidden_actions = context_data.get("forbiddenActions")
    if isinstance(forbidden_actions, list) and forbidden_actions:
        lines.extend(["", "## FORBIDDEN ACTIONS"])
        for action in forbidden_actions:
            if isinstance(action, str) and action.strip():
                lines.append(f"- {action.strip()}")

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
    return "\n".join(lines)


def build_subagent_resume_text(
    context: ExecutionContext,
    repo_root: Path | None = None,
) -> str:
    if repo_root is None:
        repo_root = get_repo_root()
    context_data = _load_context_file(context.context_file) if context.context_file else {}
    allowed_context = context_data.get("allowedContext")
    forbidden_actions = context_data.get("forbiddenActions")
    status_file = context_data.get("statusFile")
    events_file = context_data.get("eventsFile")
    dispatch_id = context_data.get("dispatchId")
    ack_token = context_data.get("ackToken")
    dispatch_status = context_data.get("dispatchStatus")
    agent_type = context_data.get("agentType")
    dispatch_reliability = context_data.get("dispatchReliability")
    expected_ack = context_data.get("expectedAck")
    lines = [
        "========================================",
        "COWORK-FLOW SUBAGENT RESUME",
        "========================================",
        "Use this only for a delegated subagent's own scoped recovery.",
        "Do not switch back into the coordinator workflow from this entrypoint.",
        "",
        "## SUBAGENT CONTEXT",
        f"Mode: {context.mode}",
        f"Title: {context.title or 'unknown'}",
        f"Role: {context.role or 'unknown'}",
        f"Goal: {context.goal or 'unknown'}",
    ]
    if isinstance(dispatch_id, str) and dispatch_id.strip():
        lines.append(f"Dispatch ID: {dispatch_id}")
    if isinstance(dispatch_status, str) and dispatch_status.strip():
        lines.append(f"Dispatch status: {dispatch_status}")
    if isinstance(agent_type, str) and agent_type.strip():
        lines.append(f"Agent type: {agent_type}")
    if isinstance(dispatch_reliability, str) and dispatch_reliability.strip():
        lines.append(f"Dispatch reliability: {dispatch_reliability}")
    if isinstance(ack_token, str) and ack_token.strip():
        lines.append(f"ACK token: {ack_token}")
    if isinstance(expected_ack, str) and expected_ack.strip():
        lines.append(f"Expected ACK: {expected_ack}")
    if context.context_file:
        lines.append(f"Context file: {context.context_file}")
    if isinstance(allowed_context, list) and allowed_context:
        lines.extend(["", "## Allowed context"])
        for item in allowed_context:
            if isinstance(item, str) and item.strip():
                lines.append(f"- {item.strip()}")
            elif isinstance(item, dict):
                file_value = item.get("file")
                reason = item.get("reason")
                if isinstance(file_value, str) and file_value.strip():
                    suffix = f" - {reason}" if isinstance(reason, str) and reason.strip() else ""
                    lines.append(f"- {file_value}{suffix}")
    if isinstance(forbidden_actions, list) and forbidden_actions:
        lines.extend(["", "## Forbidden actions"])
        for action in forbidden_actions:
            if isinstance(action, str) and action.strip():
                lines.append(f"- {action.strip()}")
    if isinstance(status_file, str) and status_file.strip():
        status_path = repo_root / status_file
        if status_path.is_file():
            try:
                status = json.loads(status_path.read_text(encoding="utf-8"))
                lines.extend(["", "## Current status", f"Status: {status.get('status', 'unknown')}"])
                note = status.get("note")
                if isinstance(note, str) and note.strip():
                    lines.append(f"Note: {note}")
            except (json.JSONDecodeError, OSError):
                lines.extend(["", "## Current status", f"Status file unreadable: {status_file}"])
    if isinstance(events_file, str) and events_file.strip():
        events_path = repo_root / events_file
        if events_path.is_file():
            events = events_path.read_text(encoding="utf-8").splitlines()[-5:]
            if events:
                lines.extend(["", "## Recent events"])
                lines.extend(f"- {event}" for event in events)
    lines.extend([
        "",
        "## RULES",
        "- If you have not acknowledged this dispatch, first return only: COWORK_ACK <dispatch_id> <ack_token>.",
        "- Execute only after the coordinator sends EXECUTE <dispatch_id> for this same dispatch.",
        "- If a message names a different dispatch_id, report needs_context and do not execute it.",
        "- Generic worker dispatch is best-effort only; no ACK means the coordinator must close or retry it.",
        "- Read only prompt-named files and allowed context unless you ask for more context.",
        "- Do not run task start, task finish, task archive, or unscoped resume.",
        "- Stop only with success, needs_context, or blocked status evidence.",
        "",
        "========================================",
    ])
    return "\n".join(lines)
