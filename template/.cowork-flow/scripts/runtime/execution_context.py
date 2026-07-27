"""Execution context values for coordinator and worker scoped commands."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


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


def load_execution_context_file(path: str) -> dict[str, object]:
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
        file_data = load_execution_context_file(context_file)

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
