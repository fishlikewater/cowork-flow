#!/usr/bin/env python3
"""Delivery adapters for task tree commands."""

from __future__ import annotations

import sys

from application.task_tree import TaskTreeError, TaskTreeService
from commands.task_support import Colors, colored, resolve_task_dir
from common.core.paths import (
    DIR_TASKS,
    DIR_WORKFLOW,
    get_developer,
    get_repo_root,
)
from common.task.active_task import get_active_task


def cmd_add_subtask(args) -> int:
    repo_root = get_repo_root()
    parent_dir = resolve_task_dir(args.parent_dir, repo_root)
    child_dir = resolve_task_dir(args.child_dir, repo_root)
    try:
        TaskTreeService(repo_root).link(parent_dir, child_dir)
    except TaskTreeError as error:
        if error.code == "TASK-TREE-PARENT-LOAD-001":
            message = f"Parent task.json not found: {args.parent_dir}"
        elif error.code == "TASK-TREE-CHILD-LOAD-001":
            message = f"Child task.json not found: {args.child_dir}"
        elif error.code == "TASK-TREE-PARENT-001":
            existing_parent = error.detail.removeprefix(
                "child already has parent "
            )
            message = f"Child task already has a parent: {existing_parent}"
        else:
            message = "Failed to update task.json"
        print(colored(f"Error: {message}", Colors.RED), file=sys.stderr)
        return 1
    print(
        colored(
            f"Linked: {child_dir.name} -> {parent_dir.name}",
            Colors.GREEN,
        ),
        file=sys.stderr,
    )
    return 0


def cmd_remove_subtask(args) -> int:
    repo_root = get_repo_root()
    parent_dir = resolve_task_dir(args.parent_dir, repo_root)
    child_dir = resolve_task_dir(args.child_dir, repo_root)
    try:
        TaskTreeService(repo_root).unlink(parent_dir, child_dir)
    except TaskTreeError as error:
        if error.code == "TASK-TREE-PARENT-LOAD-001":
            message = f"Parent task.json not found: {args.parent_dir}"
        elif error.code == "TASK-TREE-CHILD-LOAD-001":
            message = f"Child task.json not found: {args.child_dir}"
        else:
            message = "Failed to update task.json"
        print(colored(f"Error: {message}", Colors.RED), file=sys.stderr)
        return 1
    print(
        colored(
            f"Unlinked: {child_dir.name} from {parent_dir.name}",
            Colors.GREEN,
        ),
        file=sys.stderr,
    )
    return 0


def cmd_list(args) -> int:
    repo_root = get_repo_root()
    active_task = get_active_task(repo_root).task_path
    developer = get_developer(repo_root)
    filter_mine = args.mine
    filter_status = args.status

    if filter_mine:
        if not developer:
            print(
                colored(
                    "Error: No developer set. Run init_developer.py first",
                    Colors.RED,
                ),
                file=sys.stderr,
            )
            return 1
        print(colored(f"My tasks (assignee: {developer}):", Colors.BLUE))
    else:
        print(colored("All active tasks:", Colors.BLUE))
    print()

    service = TaskTreeService(repo_root)
    all_tasks = service.active_nodes()
    count = 0

    def print_task(dir_name: str, indent: int = 0) -> None:
        nonlocal count
        info = all_tasks[dir_name]
        if filter_mine and info.assignee != developer:
            return
        if filter_status and info.status != filter_status:
            return

        relative_path = f"{DIR_WORKFLOW}/{DIR_TASKS}/{dir_name}"
        marker = (
            f" {colored('<- active', Colors.GREEN)}"
            if relative_path == active_task
            else ""
        )
        done, total = service.children_progress(info.children, all_tasks)
        progress = f" [{done}/{total} done]" if info.children else ""
        prefix = "  " * indent + "  - "
        if filter_mine:
            print(f"{prefix}{dir_name}/ ({info.status}){progress}{marker}")
        else:
            print(
                f"{prefix}{dir_name}/ ({info.status}){progress} "
                f"[{colored(info.assignee, Colors.CYAN)}]{marker}"
            )
        count += 1
        for child_name in info.children:
            if child_name in all_tasks:
                print_task(child_name, indent + 1)

    for dir_name in service.root_names(all_tasks):
        print_task(dir_name)

    if count == 0:
        print(
            "  (no tasks assigned to you)"
            if filter_mine
            else "  (no active tasks)"
        )
    print()
    print(f"Total: {count} task(s)")
    return 0


def cmd_list_archive(args) -> int:
    repo_root = get_repo_root()
    month = args.month
    archives = TaskTreeService(repo_root).archived_tasks(month)

    print(colored("Archived tasks:", Colors.BLUE))
    print()
    if month:
        if month in archives:
            print(f"[{month}]")
            for task_name in archives[month]:
                print(f"  - {task_name}/")
        else:
            print(f"  No archives for {month}")
    else:
        for month_name, task_names in archives.items():
            print(f"[{month_name}] - {len(task_names)} task(s)")
    return 0
