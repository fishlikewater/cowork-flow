#!/usr/bin/env python3
"""Delivery adapter for archive_task actions."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from services.task_archive import TaskArchiveError, TaskArchiveService
from adapters.cli.task_support import (
    Colors,
    colored,
    resolve_task_dir,
    run_hooks,
)
from adapters.cli.task_tree_commands import cmd_list
from infra.paths import (
    DIR_ARCHIVE,
    DIR_TASKS,
    DIR_WORKFLOW,
    FILE_TASK_JSON,
    get_repo_root,
)
from adapters.git.git_context import _run_git_command


from kernel.task_state import DONE_STATUSES  # noqa: F401


def is_git_dirty(repo_root) -> bool:
    rc, stdout, _ = _run_git_command(
        ["status", "--porcelain"],
        cwd=repo_root,
    )
    return rc != 0 or bool(stdout.strip())


def auto_commit_archive(task_name: str, repo_root) -> None:
    archive_rels = [
        relative
        for relative in (f"{DIR_WORKFLOW}/{DIR_TASKS}",)
        if (repo_root / relative).exists()
    ]
    _run_git_command(["add", "-A", *archive_rels], cwd=repo_root)
    rc, _, _ = _run_git_command(
        ["diff", "--cached", "--quiet", "--", *archive_rels],
        cwd=repo_root,
    )
    if rc == 0:
        print("[OK] No task changes to commit.", file=sys.stderr)
        return

    commit_message = f"chore(task): archive {task_name}"
    rc, _, error = _run_git_command(
        ["commit", "-m", commit_message],
        cwd=repo_root,
    )
    if rc == 0:
        print(f"[OK] Auto-committed: {commit_message}", file=sys.stderr)
    else:
        print(f"[WARN] Auto-commit failed: {error.strip()}", file=sys.stderr)


def _resolve_archive_task(repo_root, task_name: str):
    if not task_name:
        print(
            colored("Error: Task name is required", Colors.RED),
            file=sys.stderr,
        )
        return None

    task_dir = resolve_task_dir(task_name, repo_root)
    if not task_dir.is_dir():
        print(
            colored(f"Error: Task not found: {task_name}", Colors.RED),
            file=sys.stderr,
        )
        print("Active tasks:", file=sys.stderr)
        cmd_list(argparse.Namespace(mine=False, status=None))
        return None
    return task_dir


def _archive_error_message(task_name: str, error: TaskArchiveError) -> str:
    if error.code == "TASK-ARCHIVE-LOAD-001":
        return f"Task '{task_name}' task.json is unreadable — refusing archive."
    if error.code == "TASK-ARCHIVE-STATUS-001":
        status = error.detail.removeprefix("task status is ")
        return (
            f"Task '{task_name}' is in status '{status}', not in "
            f"{DONE_STATUSES}. Run `task next <task-dir> --run --intent review` first, then retry archive."
        )
    return f"Failed to archive task: {error.detail}"


def _print_rollback_issues(error: TaskArchiveError) -> None:
    if not error.rollback_issues:
        return
    print("Rollback issues:", file=sys.stderr)
    for issue in error.rollback_issues:
        print(
            f"- {issue.stage}: {issue.path} ? {issue.detail}",
            file=sys.stderr,
        )


def _archive_task(repo_root, task_name: str, task_dir):
    try:
        return TaskArchiveService(repo_root).archive(
            task_dir,
            archived_at=datetime.now().strftime("%Y-%m-%d"),
        )
    except TaskArchiveError as error:
        message = _archive_error_message(task_name, error)
        print(colored(f"Error: {message}", Colors.RED), file=sys.stderr)
        _print_rollback_issues(error)
        return None


def _print_archive_result(result, repo_root) -> None:
    archive_dest = result.destination
    year_month = archive_dest.parent.name
    print(
        colored(
            f"Archived: {result.task_name} -> archive/{year_month}/",
            Colors.GREEN,
        ),
        file=sys.stderr,
    )
    print(
        f"{DIR_WORKFLOW}/{DIR_TASKS}/{DIR_ARCHIVE}/"
        f"{year_month}/{result.task_name}"
    )
    run_hooks("after_archive", archive_dest / FILE_TASK_JSON, repo_root)


def cmd_archive(args) -> int:
    repo_root = get_repo_root()
    task_name = args.name
    task_dir = _resolve_archive_task(repo_root, task_name)
    if task_dir is None:
        return 1

    if is_git_dirty(repo_root):
        print(
            colored(
                "Warning: Uncommitted changes detected. Archive the task first, "
                "then commit the archived result.",
                Colors.YELLOW,
            ),
            file=sys.stderr,
        )

    result = _archive_task(repo_root, task_name, task_dir)
    if result is None:
        return 1

    if getattr(args, "commit", False):
        auto_commit_archive(result.task_name, repo_root)
    _print_archive_result(result, repo_root)
    return 0
