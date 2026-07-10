#!/usr/bin/env python3
"""Delivery adapter for task archive commands."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from application.task_archive import TaskArchiveError, TaskArchiveService
from commands.task_support import (
    Colors,
    colored,
    resolve_task_dir,
    run_hooks,
)
from commands.task_tree_commands import cmd_list
from common.core.paths import (
    DIR_ARCHIVE,
    DIR_CHANGES,
    DIR_TASKS,
    DIR_WORKFLOW,
    FILE_TASK_JSON,
    get_repo_root,
)
from common.git.git_context import _run_git_command


DONE_STATUSES = ("completed", "done")


def is_git_dirty(repo_root) -> bool:
    try:
        return _run_git_command(
            ["status", "--porcelain"],
            cwd=repo_root,
        )[0] != 0
    except (OSError, Exception):
        return False


def linked_active_changes_for_task(repo_root, task_dir) -> list[str]:
    from commands.change import linked_active_changes_for_task as find_changes

    return find_changes(repo_root, (task_dir,))


def linked_changes_ready_for_archive(repo_root, slugs: list[str]) -> bool:
    from commands.change import validate_change

    ready = True
    for slug in slugs:
        if not validate_change(repo_root, slug, quiet=True):
            print(
                colored(
                    f"Error: Linked change is not ready to archive: {slug}",
                    Colors.RED,
                ),
                file=sys.stderr,
            )
            ready = False
    return ready


def archive_linked_changes(repo_root, slugs: list[str]) -> bool:
    from commands.change import archive_change_by_slug

    for slug in slugs:
        if archive_change_by_slug(repo_root, slug) is None:
            print(
                colored(
                    f"Error: Failed to archive linked change: {slug}",
                    Colors.RED,
                ),
                file=sys.stderr,
            )
            return False
        print(
            colored(f"Archived linked change: {slug}", Colors.GREEN),
            file=sys.stderr,
        )
    return True


def auto_commit_archive(task_name: str, repo_root) -> None:
    archive_rels = [
        relative
        for relative in (
            f"{DIR_WORKFLOW}/{DIR_TASKS}",
            f"{DIR_WORKFLOW}/{DIR_CHANGES}",
        )
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


def cmd_archive(args) -> int:
    repo_root = get_repo_root()
    task_name = args.name
    if not task_name:
        print(
            colored("Error: Task name is required", Colors.RED),
            file=sys.stderr,
        )
        return 1

    task_dir = resolve_task_dir(task_name, repo_root)
    if not task_dir.is_dir():
        print(
            colored(f"Error: Task not found: {task_name}", Colors.RED),
            file=sys.stderr,
        )
        print("Active tasks:", file=sys.stderr)
        cmd_list(argparse.Namespace(mine=False, status=None))
        return 1

    linked_changes = linked_active_changes_for_task(repo_root, task_dir)
    if linked_changes and not linked_changes_ready_for_archive(
        repo_root,
        linked_changes,
    ):
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

    try:
        result = TaskArchiveService(repo_root).archive(
            task_dir,
            archived_at=datetime.now().strftime("%Y-%m-%d"),
        )
    except TaskArchiveError as error:
        if error.code == "TASK-ARCHIVE-LOAD-001":
            message = (
                f"Task '{task_name}' task.json is unreadable — refusing archive."
            )
        elif error.code == "TASK-ARCHIVE-STATUS-001":
            status = error.detail.removeprefix("task status is ")
            message = (
                f"Task '{task_name}' is in status '{status}', not in "
                f"{DONE_STATUSES}. Run `task complete` first, then retry archive."
            )
        else:
            message = f"Failed to archive task: {error.detail}"
        print(colored(f"Error: {message}", Colors.RED), file=sys.stderr)
        return 1

    archive_dest = result.destination
    year_month = archive_dest.parent.name
    print(
        colored(
            f"Archived: {result.task_name} -> archive/{year_month}/",
            Colors.GREEN,
        ),
        file=sys.stderr,
    )
    if linked_changes and not archive_linked_changes(repo_root, linked_changes):
        return 1
    if getattr(args, "commit", False):
        auto_commit_archive(result.task_name, repo_root)

    print(
        f"{DIR_WORKFLOW}/{DIR_TASKS}/{DIR_ARCHIVE}/"
        f"{year_month}/{result.task_name}"
    )
    run_hooks(
        "after_archive",
        archive_dest / FILE_TASK_JSON,
        repo_root,
    )
    return 0
