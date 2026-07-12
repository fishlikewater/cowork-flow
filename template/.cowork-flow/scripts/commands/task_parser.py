#!/usr/bin/env python3
"""Argument parser and usage rendering for task commands."""

from __future__ import annotations

import argparse
from pathlib import Path

from common.core.execution_context import (
    build_internal_execution_context_parser,
)


def _add_create_command(subparsers: argparse._SubParsersAction) -> None:
    create = subparsers.add_parser("create", help="Create new task")
    create.add_argument("title", help="Task title")
    create.add_argument("--slug", "-s", help="Task slug")
    create.add_argument("--assignee", "-a", help="Assignee developer")
    create.add_argument(
        "--priority",
        "-p",
        default="P2",
        help="Priority (P0-P3)",
    )
    create.add_argument("--description", "-d", help="Task description")
    create.add_argument(
        "--parent",
        help="Parent task directory (establishes subtask link)",
    )
    create.add_argument(
        "--from-plan",
        "-f",
        help="Path to plan file (auto-generate decision-anchor skeleton)",
    )


USAGE_TEXT = """Task Management Script for cowork-flow workflow

Usage:
  ./.cowork-flow/run task create <title>                     Create new task directory
  ./.cowork-flow/run task create <title> --parent <dir>      Create task as child of parent
  ./.cowork-flow/run task init-context <dir> <dev_type>      Initialize jsonl files
  ./.cowork-flow/run task add-context <dir> <jsonl> <path> [reason] [--type TYPE]
                                                                  Add entry to jsonl
  ./.cowork-flow/run task add-planned-file <dir> <jsonl> <path> [reason]
                                                                  Add planned file entry
  ./.cowork-flow/run task validate <dir>                     Validate jsonl files
  ./.cowork-flow/run task list-context <dir>                 List jsonl entries
  ./.cowork-flow/run task start <dir>                        Set active session task
  ./.cowork-flow/run task review [dir]                       Mark task ready for check
  ./.cowork-flow/run task complete [dir]                     Mark task completed
  ./.cowork-flow/run task finish                             Clear active session task
  ./.cowork-flow/run task next [dir] [--json] [--intent I]   Show next safe workflow action
  ./.cowork-flow/run task archive <task-name>                Archive completed task and linked changes
  ./.cowork-flow/run task add-subtask <parent> <child>       Link child task to parent
  ./.cowork-flow/run task remove-subtask <parent> <child>    Unlink child from parent
  ./.cowork-flow/run task list [--mine] [--status <status>]  List tasks
  ./.cowork-flow/run task list-archive [YYYY-MM]             List archived tasks

Arguments:
  dev_type: backend | frontend | fullstack | test | docs

List options:
  --mine, -m           Show only tasks assigned to current developer
  --status, -s <s>     Filter by status (planning, in_progress, review, completed)

Examples:
  ./.cowork-flow/run task create "Add login feature" --slug add-login
  ./.cowork-flow/run task create "Child task" --slug child --parent .cowork-flow/tasks/01-21-parent
  ./.cowork-flow/run task init-context .cowork-flow/tasks/01-21-add-login backend
  ./.cowork-flow/run task next
  ./.cowork-flow/run task add-context <dir> implement .cowork-flow/spec/backend/auth.md "Auth guidelines"
  ./.cowork-flow/run task add-context <dir> implement src/new.py "Planned source" --type planned-file
  ./.cowork-flow/run task add-planned-file <dir> implement src/new.py "Planned source"
  ./.cowork-flow/run task start .cowork-flow/tasks/01-21-add-login
  ./.cowork-flow/run task review
  ./.cowork-flow/run task complete
  ./.cowork-flow/run task finish
  ./.cowork-flow/run task archive add-login
  ./.cowork-flow/run task add-subtask parent-task child-task
  ./.cowork-flow/run task remove-subtask parent-task child-task
  ./.cowork-flow/run task list
  ./.cowork-flow/run task list --mine
  ./.cowork-flow/run task list --mine --status in_progress
"""


def _add_init_context_command(subparsers: argparse._SubParsersAction) -> None:
    init_context = subparsers.add_parser(
        "init-context",
        help="Initialize context files",
    )
    init_context.add_argument("dir", help="Task directory")
    init_context.add_argument(
        "type",
        help="Dev type: backend|frontend|fullstack|test|docs",
    )


def _add_add_context_command(subparsers: argparse._SubParsersAction) -> None:
    add_context = subparsers.add_parser(
        "add-context",
        help="Add context entry",
    )
    add_context.add_argument("dir", help="Task directory")
    add_context.add_argument(
        "file",
        help="JSONL file (implement|check|debug)",
    )
    add_context.add_argument("path", help="File path to add")
    add_context.add_argument(
        "reason",
        nargs="?",
        help="Reason for adding",
    )
    add_context.add_argument(
        "--type",
        dest="entry_type",
        choices=("file", "directory", "planned-file"),
        default=None,
        help="Context entry type; planned-file may target a file not created yet",
    )


def _add_add_planned_file_command(subparsers: argparse._SubParsersAction) -> None:
    add_planned_file = subparsers.add_parser(
        "add-planned-file",
        help="Add planned file context entry",
    )
    add_planned_file.add_argument("dir", help="Task directory")
    add_planned_file.add_argument(
        "file",
        help="JSONL file (implement|check|debug)",
    )
    add_planned_file.add_argument("path", help="Planned file path to add")
    add_planned_file.add_argument(
        "reason",
        nargs="?",
        help="Reason for adding",
    )


def _add_context_validation_commands(subparsers: argparse._SubParsersAction) -> None:
    validate = subparsers.add_parser(
        "validate",
        help="Validate context files",
    )
    validate.add_argument("dir", help="Task directory")

    list_context = subparsers.add_parser(
        "list-context",
        help="List context entries",
    )
    list_context.add_argument("dir", help="Task directory")


def _add_context_commands(subparsers: argparse._SubParsersAction) -> None:
    _add_init_context_command(subparsers)
    _add_add_context_command(subparsers)
    _add_add_planned_file_command(subparsers)
    _add_context_validation_commands(subparsers)


def _add_start_and_batch_commands(subparsers: argparse._SubParsersAction) -> None:
    start = subparsers.add_parser(
        "start",
        help="Set active session task",
    )
    start.add_argument("dir", help="Task directory")
    start.add_argument(
        "--auto",
        action="store_true",
        help="Enable batch mode (requires --approved)",
    )
    start.add_argument(
        "--approved",
        action="store_true",
        help="User has approved the plan",
    )

    batch_resume = subparsers.add_parser(
        "batch-resume",
        help="Resume a paused Batch operation",
    )
    batch_resume.add_argument(
        "operation_id",
        help="Batch operation id",
    )

    batch_result = subparsers.add_parser(
        "batch-record-result",
        help="Record one Host action result and advance Batch",
    )
    batch_result.add_argument(
        "operation_id",
        help="Batch operation id",
    )
    batch_result.add_argument(
        "--file",
        type=Path,
        required=True,
        help="UTF-8 JSON Host action result",
    )


def _add_optional_task_dir(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "dir",
        nargs="?",
        help="Task directory or name",
    )


def _add_review_command(subparsers: argparse._SubParsersAction) -> None:
    review = subparsers.add_parser(
        "review",
        help="Mark task ready for check",
    )
    _add_optional_task_dir(review)


def _add_complete_command(subparsers: argparse._SubParsersAction) -> None:
    complete = subparsers.add_parser(
        "complete",
        help="Mark task completed",
    )
    _add_optional_task_dir(complete)


def _add_next_command(subparsers: argparse._SubParsersAction) -> None:
    next_parser = subparsers.add_parser(
        "next",
        help="Show next safe workflow action",
    )
    _add_optional_task_dir(next_parser)
    next_parser.add_argument(
        "--json",
        action="store_true",
        help="Render the stable machine-readable navigation contract",
    )
    next_parser.add_argument(
        "--intent",
        choices=(
            "question",
            "clarify",
            "plan",
            "implement",
            "review",
            "debug",
            "discuss",
            "batch",
        ),
        help="Classified user intent for structured routing",
    )


def _add_lifecycle_commands(subparsers: argparse._SubParsersAction) -> None:
    subparsers.add_parser(
        "current",
        help="Show active session task",
    )
    _add_review_command(subparsers)
    _add_complete_command(subparsers)
    _add_next_command(subparsers)
    subparsers.add_parser(
        "finish",
        help="Clear active session task",
    )


def _add_archive_command(subparsers: argparse._SubParsersAction) -> None:
    archive = subparsers.add_parser("archive", help="Archive task")
    archive.add_argument("name", help="Task name")
    archive.add_argument(
        "--commit",
        action="store_true",
        help="Auto git commit after archive",
    )


def _add_list_command(subparsers: argparse._SubParsersAction) -> None:
    list_parser = subparsers.add_parser("list", help="List tasks")
    list_parser.add_argument(
        "--mine",
        "-m",
        action="store_true",
        help="My tasks only",
    )
    list_parser.add_argument(
        "--status",
        "-s",
        help="Filter by status",
    )


def _add_subtask_commands(subparsers: argparse._SubParsersAction) -> None:
    add_subtask = subparsers.add_parser(
        "add-subtask",
        help="Link child task to parent",
    )
    add_subtask.add_argument(
        "parent_dir",
        help="Parent task directory",
    )
    add_subtask.add_argument(
        "child_dir",
        help="Child task directory",
    )

    remove_subtask = subparsers.add_parser(
        "remove-subtask",
        help="Unlink child task from parent",
    )
    remove_subtask.add_argument(
        "parent_dir",
        help="Parent task directory",
    )
    remove_subtask.add_argument(
        "child_dir",
        help="Child task directory",
    )


def _add_list_archive_command(subparsers: argparse._SubParsersAction) -> None:
    list_archive = subparsers.add_parser(
        "list-archive",
        help="List archived tasks",
    )
    list_archive.add_argument(
        "month",
        nargs="?",
        help="Month (YYYY-MM)",
    )


def _add_archive_and_listing_commands(subparsers: argparse._SubParsersAction) -> None:
    _add_archive_command(subparsers)
    _add_list_command(subparsers)
    _add_subtask_commands(subparsers)
    _add_list_archive_command(subparsers)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Task Management Script for cowork-flow workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[build_internal_execution_context_parser()],
    )
    subparsers = parser.add_subparsers(
        dest="command",
        help="Commands",
    )

    _add_create_command(subparsers)
    _add_context_commands(subparsers)
    _add_start_and_batch_commands(subparsers)
    _add_lifecycle_commands(subparsers)
    _add_archive_and_listing_commands(subparsers)
    return parser


def show_usage() -> None:
    """Show usage help."""
    print(USAGE_TEXT)
