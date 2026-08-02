#!/usr/bin/env python3
"""Delivery adapters for task context commands."""

from __future__ import annotations

import argparse
from pathlib import Path

from services.task_context import (
    CONTEXT_JSONL_FILES,
    TaskContextError,
    TaskContextService,
)
from adapters.cli.task_support import Colors, colored, resolve_task_dir
from infra.paths import get_repo_root


PLANNED_FILE_HINT = (
    "If this is a planned new file, add "
    '"type": "planned-file"; if this is an already-deleted file in scope, add '
    '"type": "deleted-file" before running `task next --run`.'
)


def _report_jsonl_skip(path: Path, reason: str) -> None:
    print(f"  {colored('[SKIP]', Colors.YELLOW)} {path.name}: {reason}")


def cmd_init_context(args: argparse.Namespace) -> int:
    """Initialize JSONL context files for a task."""
    repo_root = get_repo_root()
    target_dir = resolve_task_dir(args.dir, repo_root)
    dev_type = args.type

    if not dev_type:
        print(colored("Error: Missing arguments", Colors.RED))
        print(
            "Internal context adapter; public workflow uses `task next` actions "
            "and direct task JSONL files."
        )
        print(
            "  dev_type: backend | frontend | fullstack | "
            "test | docs | spec"
        )
        return 1
    if not target_dir.is_dir():
        print(
            colored(
                f"Error: Directory not found: {target_dir}",
                Colors.RED,
            )
        )
        return 1

    service = TaskContextService(repo_root)
    try:
        result = service.initialize(target_dir, dev_type)
    except TaskContextError:
        print(
            colored(
                f"Error: Directory not found: {target_dir}",
                Colors.RED,
            )
        )
        return 1

    _report_init_context_result(target_dir, dev_type, result)
    return 0


def _report_init_context_result(
    target_dir: Path,
    dev_type: str,
    result,
) -> None:
    print(
        colored(
            "=== Initializing Agent Context Files ===",
            Colors.BLUE,
        )
    )
    print(f"Target dir: {target_dir}")
    print(f"Dev type: {dev_type}")
    print()
    for file_name in CONTEXT_JSONL_FILES:
        context_file = target_dir / file_name
        if file_name in result.skipped:
            _report_jsonl_skip(
                context_file,
                "already exists, skipping",
            )
            continue
        print(colored(f"Creating {file_name}...", Colors.CYAN))
        print(
            f"  {colored('[OK]', Colors.GREEN)} "
            f"{result.entry_counts[file_name]} entries"
        )


def cmd_add_context(args: argparse.Namespace) -> int:
    """Add an entry to a JSONL context file."""
    repo_root = get_repo_root()
    target_dir = resolve_task_dir(args.dir, repo_root)
    path = args.path
    reason = args.reason or "Added manually"

    try:
        result = TaskContextService(repo_root).add(
            target_dir,
            args.file,
            path,
            reason,
            entry_type=getattr(args, "entry_type", None),
        )
    except TaskContextError as error:
        if error.code == "TASK-CONTEXT-PATH-001":
            print(
                colored(
                    f"Error: Path not found: {path}",
                    Colors.RED,
                )
            )
        elif error.code in ("TASK-CONTEXT-PATH-002", "TASK-CONTEXT-TYPE-001"):
            print(colored(f"Error: {error.detail}", Colors.RED))
        else:
            print(
                colored(
                    f"Error: Directory not found: {target_dir}",
                    Colors.RED,
                )
            )
        return 1

    if not result.added:
        print(
            colored(
                f"Warning: Entry already exists for {result.path}",
                Colors.YELLOW,
            )
        )
        return 0
    print(
        colored(
            f"Added {result.entry_type}: {result.path}",
            Colors.GREEN,
        )
    )
    return 0


def cmd_add_planned_file(args: argparse.Namespace) -> int:
    """Add a planned-file entry to a JSONL context file."""
    args.entry_type = "planned-file"
    return cmd_add_context(args)


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate JSONL context files."""
    repo_root = get_repo_root()
    target_dir = resolve_task_dir(args.dir, repo_root)
    if not target_dir.is_dir():
        print(colored("Error: task directory required", Colors.RED))
        return 1

    print(colored("=== Validating Context Files ===", Colors.BLUE))
    print(f"Target dir: {target_dir}")
    print()
    service = TaskContextService(repo_root)
    total_errors = 0
    for jsonl_name in CONTEXT_JSONL_FILES:
        result = service.validate_file(target_dir, jsonl_name)
        if not result.exists:
            print(
                f"  {colored(f'{jsonl_name}: not found (skipped)', Colors.YELLOW)}"
            )
            continue

        for issue in result.issues:
            print(
                f"  {colored(f'{jsonl_name}:{issue.line}: {issue.message}', Colors.RED)}"
            )
            if issue.code == "file_not_found":
                print(f"    Hint: {PLANNED_FILE_HINT}")
        error_count = len(result.issues)
        total_errors += error_count
        if error_count == 0:
            print(
                f"  {colored(f'{jsonl_name}: [OK] ({result.entry_count} entries)', Colors.GREEN)}"
            )
        else:
            print(
                f"  {colored(f'{jsonl_name}: [FAIL] ({error_count} errors)', Colors.RED)}"
            )

    print()
    if total_errors == 0:
        print(colored("[OK] All validations passed", Colors.GREEN))
        return 0
    print(
        colored(
            f"[FAIL] Validation failed ({total_errors} errors)",
            Colors.RED,
        )
    )
    return 1


def cmd_list_context(args: argparse.Namespace) -> int:
    """List JSONL context entries."""
    repo_root = get_repo_root()
    target_dir = resolve_task_dir(args.dir, repo_root)
    if not target_dir.is_dir():
        print(colored("Error: task directory required", Colors.RED))
        return 1

    print(colored("=== Context Files ===", Colors.BLUE))
    print()
    service = TaskContextService(repo_root)
    for jsonl_name in CONTEXT_JSONL_FILES:
        entries = service.entries(target_dir, jsonl_name)
        if not entries and not (target_dir / jsonl_name).is_file():
            continue

        print(colored(f"[{jsonl_name}]", Colors.CYAN))
        for count, data in enumerate(entries, start=1):
            file_path = data.get("file", "?")
            entry_type = data.get("type", "file")
            reason = data.get("reason", "-")
            if entry_type == "directory":
                print(
                    f"  {colored(f'{count}.', Colors.GREEN)} "
                    f"[DIR] {file_path}"
                )
            elif entry_type == "planned-file":
                print(
                    f"  {colored(f'{count}.', Colors.GREEN)} "
                    f"[PLANNED] {file_path}"
                )
            else:
                print(
                    f"  {colored(f'{count}.', Colors.GREEN)} "
                    f"{file_path}"
                )
            print(f"     {colored('->', Colors.YELLOW)} {reason}")
        print()
    return 0
