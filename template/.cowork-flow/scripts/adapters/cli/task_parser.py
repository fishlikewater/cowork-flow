#!/usr/bin/env python3
"""Argument parser and usage rendering for the task workflow router."""

from __future__ import annotations

import argparse
from pathlib import Path

from adapters.cli.execution_context_args import build_internal_execution_context_parser


USAGE_TEXT = """Task workflow router for cowork-flow

Usage:
  ./.cowork-flow/run task next [dir] [--json] [--intent I]
  ./.cowork-flow/run task next [dir] --validate
  ./.cowork-flow/run task next --list [--json] [--mine] [--status S]
  ./.cowork-flow/run task next [dir] --run [--intent I]

Public contract:
  `task next` is the only public task workflow command. It reports the next
  safe action, the Skill to activate, the lifecycle check, and the exact
  `task next --run` form when an action is deterministic and executable.

Action inputs for `next --run`:
  --title <title>       Create a task when no task exists
  --slug <slug>         Optional task slug for create_task
  --assignee <name>     Optional task assignee for create_task
  --priority <P0-P3>    Optional task priority for create_task (default: P2)
  --description <text>  Optional task description for create_task
  --parent <dir>        Optional parent task directory for create_task
  --from-plan <path>    Plan path for create_task or planning-phase rebind
  --auto --approved     Optional batch start flags for start_task
  --commit             Optional archive auto-commit flag for archive_task

Examples:
  ./.cowork-flow/run task next
  ./.cowork-flow/run task next --json
  ./.cowork-flow/run task next --list
  ./.cowork-flow/run task next .cowork-flow/tasks/07-25-demo --validate
  ./.cowork-flow/run task next .cowork-flow/tasks/07-25-demo
  ./.cowork-flow/run task next .cowork-flow/tasks/07-25-demo --run
  ./.cowork-flow/run task next --run --title "Add login feature" --slug add-login --from-plan .cowork-flow/plans/YYYY-MM-DD-add-login.md
"""


def _add_optional_task_dir(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "dir",
        nargs="?",
        help="Task directory or name",
    )


def _add_next_output_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        help="Render the stable machine-readable navigation contract",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Execute the deterministic action reported by task next",
    )
    parser.add_argument(
        "--intent",
        choices=(
            "question",
            "clarify",
            "plan",
            "implement",
            "archive",
            "review",
            "doubt_review",
            "debug",
            "discuss",
            "batch",
        ),
        help="Classified user intent for structured routing",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate task context JSONL without changing task state",
    )
    parser.add_argument(
        "--list",
        dest="list_tasks",
        action="store_true",
        help="List active tasks without changing task state",
    )
    parser.add_argument(
        "--mine",
        action="store_true",
        help="With --list, show tasks assigned to the current developer",
    )
    parser.add_argument(
        "--status",
        help="With --list, filter tasks by status",
    )


def _add_next_create_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--title", help="Task title for create_task")
    parser.add_argument("--slug", "-s", help="Task slug for create_task")
    parser.add_argument("--assignee", "-a", help="Assignee for create_task")
    parser.add_argument(
        "--priority",
        "-p",
        default="P2",
        help="Priority for create_task (P0-P3)",
    )
    parser.add_argument("--description", "-d", help="Description for create_task")
    parser.add_argument("--parent", help="Parent task directory for create_task")
    parser.add_argument(
        "--from-plan",
        "-f",
        dest="from_plan",
        help=(
            "Plan file to bind to the task: at creation, or as a "
            "planning-phase rebind (repo-relative .cowork-flow/plans path)"
        ),
    )


def _add_next_runtime_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Enable batch mode when running start_task (requires --approved)",
    )
    parser.add_argument(
        "--approved",
        action="store_true",
        help="User has approved the plan for batch start_task",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Auto git commit after archive_task",
    )


def _add_next_command(subparsers: argparse._SubParsersAction) -> None:
    next_parser = subparsers.add_parser(
        "next",
        help="Show or run the next safe workflow action",
    )
    _add_optional_task_dir(next_parser)
    _add_next_output_options(next_parser)
    _add_next_create_inputs(next_parser)
    _add_next_runtime_inputs(next_parser)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Task workflow router for cowork-flow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[build_internal_execution_context_parser()],
    )
    subparsers = parser.add_subparsers(
        dest="command",
        help="Commands",
    )
    _add_next_command(subparsers)
    return parser


def show_usage() -> None:
    print(USAGE_TEXT)
