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
    DIR_CHANGES,
    DIR_TASKS,
    DIR_WORKFLOW,
    FILE_TASK_JSON,
    get_repo_root,
)
from adapters.git.git_context import _run_git_command
from infra.archive_utils import archive_directory_resumable


from kernel.task_state import DONE_STATUSES  # noqa: F401


def is_git_dirty(repo_root) -> bool:
    rc, stdout, _ = _run_git_command(
        ["status", "--porcelain"],
        cwd=repo_root,
    )
    return rc != 0 or bool(stdout.strip())


def linked_active_changes_for_task(repo_root, task_dir) -> list[str]:
    from adapters.cli.change import linked_active_changes_for_task as find_changes

    return find_changes(repo_root, (task_dir,))


def linked_changes_ready_for_archive(repo_root, slugs: list[str]) -> bool:
    from adapters.cli.change import validate_change

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


def _linked_change_paths(repo_root, slug: str):
    source = repo_root / DIR_WORKFLOW / DIR_CHANGES / slug
    month = datetime.now().astimezone().strftime("%Y-%m")
    destination = (
        repo_root
        / DIR_WORKFLOW
        / DIR_CHANGES
        / DIR_ARCHIVE
        / month
        / slug
    )
    return source, destination


def _restore_linked_changes(
    repo_root,
    slugs: list[str],
    metadata: dict[str, bytes],
) -> bool:
    restored = True
    for slug in reversed(slugs):
        source, destination = _linked_change_paths(repo_root, slug)
        if destination.is_dir():
            result = archive_directory_resumable(destination, source)
            if not result.ok:
                print(
                    colored(
                        f"Error: Failed to restore linked change: {slug}: "
                        f"{result.message}",
                        Colors.RED,
                    ),
                    file=sys.stderr,
                )
                restored = False
                continue
        if source.is_dir():
            try:
                (source / "change.yaml").write_bytes(metadata[slug])
            except OSError as error:
                print(
                    colored(
                        f"Error: Failed to restore linked change metadata: "
                        f"{slug}: {error}",
                        Colors.RED,
                    ),
                    file=sys.stderr,
                )
                restored = False
    return restored


def archive_linked_changes(repo_root, slugs: list[str]) -> bool:
    from adapters.cli.change import archive_change_by_slug

    metadata: dict[str, bytes] = {}
    try:
        for slug in slugs:
            source, _ = _linked_change_paths(repo_root, slug)
            metadata[slug] = (source / "change.yaml").read_bytes()
    except OSError as error:
        print(
            colored(
                f"Error: Failed to snapshot linked change metadata: {error}",
                Colors.RED,
            ),
            file=sys.stderr,
        )
        return False

    archived: list[str] = []
    for slug in slugs:
        if archive_change_by_slug(repo_root, slug) is None:
            print(
                colored(
                    f"Error: Failed to archive linked change: {slug}",
                    Colors.RED,
                ),
                file=sys.stderr,
            )
            _restore_linked_changes(repo_root, slugs, metadata)
            return False
        archived.append(slug)

    for slug in archived:
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


def _archive_task(repo_root, task_name: str, task_dir, linked_changes: list[str]):
    try:
        return TaskArchiveService(repo_root).archive(
            task_dir,
            archived_at=datetime.now().strftime("%Y-%m-%d"),
            finalize=(
                lambda: archive_linked_changes(repo_root, linked_changes)
            )
            if linked_changes
            else None,
        )
    except TaskArchiveError as error:
        message = _archive_error_message(task_name, error)
        print(colored(f"Error: {message}", Colors.RED), file=sys.stderr)
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

    result = _archive_task(repo_root, task_name, task_dir, linked_changes)
    if result is None:
        return 1

    if getattr(args, "commit", False):
        auto_commit_archive(result.task_name, repo_root)
    _print_archive_result(result, repo_root)
    return 0
