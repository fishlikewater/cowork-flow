#!/usr/bin/env python3
"""Plan skeleton generation and readiness finalization CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from adapters.cli.execution_context_args import (
    build_internal_execution_context_parser,
    execution_context_from_namespace,
)
from adapters.cli.task_support import (
    Colors,
    colored,
    resolve_task_dir,
    slugify,
)
from infra.paths import FILE_TASK_JSON, get_repo_root
from runtime.session_state import (
    PROVENANCE_PROCESS_FALLBACK,
    get_active_task,
)
from services.plan_readiness import PlanReadinessError, PlanReadinessService
from services.plan_scaffold import PlanScaffoldError, PlanScaffoldService


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a plan skeleton or finalize planning artifacts",
        parents=[build_internal_execution_context_parser()],
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser(
        "new",
        help="Create a plan skeleton from the installed localized template",
    )
    new_parser.add_argument("--title", required=True, help="Plan title")
    new_parser.add_argument(
        "--slug",
        help="ASCII plan slug; defaults to the title when it slugifies",
    )
    new_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing plan file",
    )
    new_parser.add_argument(
        "--date",
        help="Plan date prefix in YYYY-MM-DD form (default: today)",
    )

    finalize_parser = subparsers.add_parser(
        "finalize",
        help="Validate planning artifacts and record the plan-ready snapshot",
    )
    finalize_parser.add_argument(
        "dir",
        nargs="?",
        help="Task directory or name; defaults to the active task",
    )
    finalize_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the plan-ready snapshot as JSON",
    )
    return parser


def _resolve_task(args: argparse.Namespace, repo_root: Path) -> Path | None:
    target = getattr(args, "dir", None)
    if target:
        task_dir = resolve_task_dir(target, repo_root)
    else:
        active = get_active_task(repo_root)
        if not active.context_key:
            print(
                colored(
                    "Error: Missing session context. Set "
                    "COWORK_FLOW_CONTEXT_ID or pass a task dir.",
                    Colors.RED,
                ),
                file=sys.stderr,
            )
            return None
        if active.task_path and active.provenance == PROVENANCE_PROCESS_FALLBACK:
            print(
                colored(
                    "Error: Session binding is process-fallback (shared); "
                    "set COWORK_FLOW_CONTEXT_ID to the session value shown "
                    "in the workflow-state header, or pass a task dir "
                    "explicitly.",
                    Colors.RED,
                ),
                file=sys.stderr,
            )
            return None
        if not active.task_path:
            print(
                colored(
                    "Error: No active task set for this session",
                    Colors.RED,
                ),
                file=sys.stderr,
            )
            return None
        task_dir = repo_root / active.task_path

    if not task_dir.is_dir() or not (task_dir / FILE_TASK_JSON).is_file():
        print(
            colored(
                f"Error: Task not found or task.json missing: {task_dir}",
                Colors.RED,
            ),
            file=sys.stderr,
        )
        return None
    return task_dir


def _cmd_new(args: argparse.Namespace, repo_root: Path) -> int:
    slug = args.slug or slugify(args.title)
    if not slug:
        print(
            colored(
                "Error: could not generate an ASCII slug from the title; "
                "pass --slug <ascii-slug>",
                Colors.RED,
            ),
            file=sys.stderr,
        )
        return 1
    try:
        plan_path = PlanScaffoldService(repo_root).create(
            args.title,
            slug,
            force=bool(args.force),
            date_prefix=args.date,
        )
    except PlanScaffoldError as error:
        print(
            colored(
                f"Error: Failed to create plan skeleton [{error.code}]: "
                f"{error.detail}",
                Colors.RED,
            ),
            file=sys.stderr,
        )
        return 1
    try:
        display = plan_path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        display = str(plan_path)
    print(display)
    return 0


def _cmd_finalize(args: argparse.Namespace, repo_root: Path) -> int:
    task_dir = _resolve_task(args, repo_root)
    if task_dir is None:
        return 1
    try:
        snapshot = PlanReadinessService(repo_root).finalize(task_dir)
    except PlanReadinessError as error:
        print(
            colored("Error: Plan is not ready for review", Colors.RED),
            file=sys.stderr,
        )
        for blocker in error.blockers:
            print(f"  - {blocker}", file=sys.stderr)
        print(
            "Hint: fill the planning artifacts, then rerun "
            "`./.cowork-flow/run plan finalize <task-dir>`.",
            file=sys.stderr,
        )
        return 1

    if getattr(args, "json", False):
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    else:
        print(colored("Plan is ready for human review.", Colors.GREEN))
        print(f"  planDigest: {snapshot['planDigest']}")
        print(f"  anchorDigest: {snapshot['anchorDigest']}")
        print(f"  readyAt: {snapshot['readyAt']}")
        print(
            "  Next: review the plan and anchor, then start the task. "
            "Start will reject any later edit to either file."
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    execution_context = execution_context_from_namespace(args)
    if not execution_context.is_default:
        print(
            colored(
                "Error: plan commands must run in the main session; "
                "delegated contexts cannot finalize a task.",
                Colors.RED,
            ),
            file=sys.stderr,
        )
        return 2

    repo_root = get_repo_root()
    if args.command == "new":
        return _cmd_new(args, repo_root)
    if args.command == "finalize":
        return _cmd_finalize(args, repo_root)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
