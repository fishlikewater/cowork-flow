#!/usr/bin/env python3
"""Delivery adapter for task creation."""

from __future__ import annotations

import argparse
import sys

from services.task_creation import (
    TaskCreationError,
    TaskCreationRequest,
    TaskCreationService,
    ensure_tasks_dir,
)
from adapters.cli.task_support import Colors, colored, run_hooks, slugify
from infra.paths import (
    DIR_TASKS,
    DIR_WORKFLOW,
    FILE_TASK_JSON,
    get_developer,
    get_repo_root,
)
from runtime.session_state import set_active_task


def cmd_create(args: argparse.Namespace) -> int:
    """Create a new task."""
    repo_root = get_repo_root()
    request = _build_create_request(args, repo_root)
    if request is None:
        return 1

    result = _create_task(repo_root, request)
    if result is None:
        return 1

    _activate_created_task(repo_root, result)
    _print_create_result(result)
    run_hooks(
        "after_create",
        result.task_dir / FILE_TASK_JSON,
        repo_root,
    )
    return 0


def _build_create_request(
    args: argparse.Namespace,
    repo_root,
) -> TaskCreationRequest | None:
    if not args.title:
        print(colored("Error: title is required", Colors.RED), file=sys.stderr)
        return None

    assignee = args.assignee or get_developer(repo_root)
    if not assignee:
        print(
            colored(
                "Error: No developer set. Use --assignee <name> for "
                "this task, or initialize a developer profile separately.",
                Colors.RED,
            ),
            file=sys.stderr,
        )
        return None

    creator = get_developer(repo_root) or assignee
    slug = args.slug or slugify(args.title)
    if not slug:
        print(
            colored(
                "Error: could not generate slug from title",
                Colors.RED,
            ),
            file=sys.stderr,
        )
        return None

    return TaskCreationRequest(
        title=args.title,
        slug=slug,
        assignee=assignee,
        priority=args.priority,
        description=args.description,
        creator=creator,
        parent=args.parent,
        from_plan=getattr(args, "from_plan", None),
    )


def _create_task(repo_root, request: TaskCreationRequest):
    try:
        return TaskCreationService(repo_root).create(request)
    except TaskCreationError as error:
        print(
            colored(
                f"Error: Failed to create task: {error.detail}",
                Colors.RED,
            ),
            file=sys.stderr,
        )
        return None


def _activate_created_task(repo_root, result) -> None:
    try:
        relative = result.task_dir.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return
    set_active_task(repo_root, relative.as_posix())


def _print_create_result(result) -> None:
    dir_name = result.task_dir.name
    if result.directory_existed:
        print(
            colored(
                f"Warning: Task directory already exists: {dir_name}",
                Colors.YELLOW,
            ),
            file=sys.stderr,
        )
    if result.missing_parent:
        print(
            colored(
                "Warning: Parent task.json not found: "
                f"{result.missing_parent}",
                Colors.YELLOW,
            ),
            file=sys.stderr,
        )
    if result.linked_parent:
        print(
            colored(
                f"Linked as child of: {result.linked_parent}",
                Colors.GREEN,
            ),
            file=sys.stderr,
        )
    if result.generated_anchor:
        print(
            f"  {colored('[OK]', Colors.GREEN)} "
            "Generated decision-anchor.md from plan"
        )

    print(
        colored(f"Created task: {dir_name}", Colors.GREEN),
        file=sys.stderr,
    )
    _print_next_steps()
    print(f"{DIR_WORKFLOW}/{DIR_TASKS}/{dir_name}")


def _print_next_steps() -> None:
    print("", file=sys.stderr)
    print(colored("Next steps:", Colors.BLUE), file=sys.stderr)
    print(
        "  1. Create decision-anchor.md with requirements",
        file=sys.stderr,
    )
    print(
        "  2. Write required context JSONL files or use the planning Skill action",
        file=sys.stderr,
    )
    print(
        "  3. Run: ./.cowork-flow/run task next <dir> --run",
        file=sys.stderr,
    )
    print(
        "  Validate first: ./.cowork-flow/run task next <dir> --validate",
        file=sys.stderr,
    )
    print(
        "  Planned new files: write a planned-file entry to the task JSONL: "
        "<dir> implement <path> \"reason\"",
        file=sys.stderr,
    )
    print(
        "  Deleted files: write a deleted-file entry to the task JSONL.",
        file=sys.stderr,
    )
    print("", file=sys.stderr)
