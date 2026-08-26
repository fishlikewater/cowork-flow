#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Task workflow entry point and CLI command composition."""

from __future__ import annotations

import argparse
import sys

if __package__:
    from . import _bootstrap as _bootstrap  # noqa: F401
else:
    import _bootstrap  # noqa: F401

from services.task_context import (
    detect_installed_platforms as _detect_installed_platforms,
    discover_spec_files as _discover_spec_files,
    get_check_context,
    get_debug_context,
    get_implement_backend,
    get_implement_base,
    get_implement_frontend,
    get_implement_spec,
    is_skill_path as _is_skill_path,
    iter_jsonl_lines as _iter_jsonl_lines,
    skill_path as _skill_path,
    use_claude_skill_context as _use_claude_skill_context,
    write_jsonl as _write_jsonl,
)
from adapters.cli.task_archive_commands import cmd_archive
from adapters.cli.task_context_commands import (
    cmd_add_planned_file,
    cmd_add_context,
    cmd_init_context,
    cmd_list_context,
    cmd_validate,
)
from adapters.cli.task_create_command import cmd_create, ensure_tasks_dir
from adapters.cli import task_navigation
from adapters.cli.task_lifecycle_commands import (
    cmd_complete,
    cmd_current,
    cmd_finish,
    cmd_review,
    cmd_start,
)
from adapters.cli.task_parser import build_parser, show_usage
from adapters.cli.task_next_runner import (
    NextActionHandlers,
    namespace_with as _args_with,
    run_next_action,
)
from adapters.cli.task_support import (
    Colors,
    colored,
    resolve_task_dir as _resolve_task_dir,
)
from adapters.cli.task_tree_commands import (
    cmd_add_subtask,
    cmd_list,
    cmd_list_json,
    cmd_list_archive,
    cmd_remove_subtask,
)
from adapters.cli.execution_context_args import execution_context_from_namespace
from adapters.cli.execution_resume import worker_command_block_message


def cmd_next(args: argparse.Namespace) -> int:
    """Show or run the next workflow action."""
    if getattr(args, "list_tasks", False):
        if getattr(args, "run", False):
            print(
                colored("Error: --list is read-only; remove --run", Colors.RED),
                file=sys.stderr,
            )
            return 1
        if getattr(args, "json", False):
            return cmd_list_json(
                _args_with(
                    args,
                    mine=bool(getattr(args, "mine", False)),
                    status=getattr(args, "status", None),
                )
            )
        return cmd_list(
            _args_with(
                args,
                mine=bool(getattr(args, "mine", False)),
                status=getattr(args, "status", None),
            )
        )
    if getattr(args, "validate", False):
        if getattr(args, "run", False):
            print(
                colored("Error: --validate is read-only; remove --run", Colors.RED),
                file=sys.stderr,
            )
            return 1
        if not getattr(args, "dir", None):
            print(
                colored("Error: --validate requires a task dir", Colors.RED),
                file=sys.stderr,
            )
            return 1
        return cmd_validate(_args_with(args, dir=args.dir))
    if getattr(args, "run", False):
        return run_next_action(
            args,
            NextActionHandlers(
                create=cmd_create,
                start=cmd_start,
                review=cmd_review,
                complete=cmd_complete,
                archive=cmd_archive,
            ),
        )
    return task_navigation.cmd_next(args)


WORKER_BLOCKED_COMMANDS = frozenset()

COMMANDS = {
    "next": cmd_next,
}


def _worker_command_blocked(execution_context, command: str) -> bool:
    if not execution_context.is_worker or command not in WORKER_BLOCKED_COMMANDS:
        return False
    print(
        worker_command_block_message(
            execution_context,
            f"task {command}",
            "Workers must not activate, archive, or mutate "
            "cowork-flow task state.",
        ),
        file=sys.stderr,
    )
    return True


def main() -> int:
    """CLI entry point."""
    args = build_parser().parse_args()
    execution_context = execution_context_from_namespace(args)
    if not args.command:
        show_usage()
        return 1

    if _worker_command_blocked(execution_context, args.command):
        return 2

    command = COMMANDS.get(args.command)
    if command is None:
        show_usage()
        return 1
    return command(args)


if __name__ == "__main__":
    raise SystemExit(main())
