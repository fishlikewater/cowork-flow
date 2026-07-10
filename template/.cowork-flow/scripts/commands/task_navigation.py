#!/usr/bin/env python3
"""Read-only task workflow navigation command."""

from __future__ import annotations

from pathlib import Path

from application.task_context import TaskContextService
from commands.task_archive_commands import linked_active_changes_for_task
from commands.task_support import resolve_task_dir
from common.core.paths import get_repo_root
from common.gates.gates import GateRunner
from common.task.active_task import get_active_task
from common.task.readiness import task_readiness_blockers
from common.task.task_repository import TaskRepository, TaskRepositoryError


CHECK_STATUSES = ("review",)
DONE_STATUSES = ("completed", "done")


def _display(repo_root: Path, task_dir: Path) -> str:
    try:
        return task_dir.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(task_dir)


def _status(repo_root: Path, task_dir: Path) -> str:
    try:
        data = TaskRepository(repo_root).load(task_dir)
    except TaskRepositoryError:
        return "stale"
    status = data.get("status")
    return status.strip() if isinstance(status, str) and status.strip() else "unknown"


def _blockers(repo_root: Path, task_dir: Path) -> list[str]:
    blockers = list(TaskContextService(repo_root).start_blockers(task_dir))
    blockers.extend(task_readiness_blockers(repo_root, task_dir))
    result = GateRunner(repo_root).run("task_start", task_dir)
    blockers.extend(
        f"{item.get('rule_id') or item.get('id')}: {item.get('message') or 'Gate blocked'}"
        for item in result.blockers
    )
    return blockers


def _print_blockers(blockers: list[str]) -> None:
    if not blockers:
        print("Blockers: none")
        return
    print("Blockers:")
    for blocker in blockers:
        print(f"  - {blocker}")


def _implementation(task_path: str) -> None:
    print("Next action: execute implementation plan")
    print(f"TDD reminder: for behavior changes, write a failing test and record red evidence in {task_path}/tdd.jsonl before modifying code.")
    print(
        f"Command: ./.cowork-flow/run subagent init --role implement "
        f"--agent-type cowork-implement --execution-task-dir {task_path} "
        f"--title \"Implement {Path(task_path).name}\""
    )
    print("Then: pass cowork_runtime_context_id and cowork_host_context_key through the active Host Adapter")
    print("Then: child first step runs ./.cowork-flow/run subagent bind <runtime_context_id> <host_context_key>")
    print("Then: verify status=bound and bound_context_key before accepting output")
    print(f"Then: wait, verify output, close runtime context, then ./.cowork-flow/run task review {task_path}")


def cmd_next(args) -> int:
    repo_root = get_repo_root()
    target = getattr(args, "dir", None)
    active_target = False
    print("Workflow Next")
    if target:
        task_dir = resolve_task_dir(target, repo_root)
        task_path = _display(repo_root, task_dir)
        source = "argument"
    else:
        active = get_active_task(repo_root)
        source = f"{active.source}:{active.context_key or '-'}"
        if not active.task_path:
            print("Status: no_task")
            print(f"Source: {source}")
            print("Next action: create or start a task before repository changes")
            print('Command: ./.cowork-flow/run task create "<title>" --slug <task-name>')
            print("Then: ./.cowork-flow/run task start <task-dir>")
            print("Runtime-context subagent state is injected by hook/plugin; do not infer it from prompt text.")
            return 0
        task_path = active.task_path
        task_dir = repo_root / task_path
        active_target = True

    print(f"Task: {task_path}")
    if not task_dir.is_dir():
        print("Status: stale")
        print(f"Source: {source}")
        print("Next action: clear or replace the missing active task")
        print("Command: ./.cowork-flow/run task list")
        print("Blockers:")
        print(f"  - task directory not found: {task_path}")
        return 0

    status = _status(repo_root, task_dir)
    blockers = _blockers(repo_root, task_dir)
    print(f"Status: {status}")
    print(f"Source: {source}")
    if status == "planning":
        if blockers:
            print("Next action: finish planning prerequisites before starting task")
            print(f"Command: ./.cowork-flow/run task init-context {task_path} <dev_type>")
            print(f"Then: ./.cowork-flow/run task start {task_path}")
        elif active_target:
            _implementation(task_path)
        else:
            print("Next action: start task")
            print(f"Command: ./.cowork-flow/run task start {task_path}")
    elif status == "in_progress":
        _implementation(task_path)
    elif status in CHECK_STATUSES:
        print("Next action: verify implementation")
        print(f"Command: ./.cowork-flow/run subagent init --role check --agent-type cowork-check --execution-task-dir {task_path} --title \"Check {Path(task_path).name}\"")
        print("Then: pass cowork_runtime_context_id and cowork_host_context_key through the active Host Adapter or run equivalent inline check")
        print("Then: child first step runs ./.cowork-flow/run subagent bind <runtime_context_id> <host_context_key>")
        print("Then: verify status=bound and bound_context_key before accepting output")
        print(f"Then: ./.cowork-flow/run task complete {task_path}")
    elif status in DONE_STATUSES:
        print("Next action: finalize, archive, commit, and record session")
        print("Command: git status --short")
        changes = linked_active_changes_for_task(repo_root, task_dir)
        print(f"Then: ./.cowork-flow/run task archive {Path(task_path).name}")
        for slug in changes:
            print(f"Then: ./.cowork-flow/run change archive {slug} (handled by task archive)")
    else:
        print("Next action: inspect task status and repair workflow state")
        print(f"Command: ./.cowork-flow/run task validate {task_path}")
    _print_blockers(blockers)
    return 0
