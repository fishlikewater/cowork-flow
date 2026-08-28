#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`run state [task] [--json]` — the fact-layer read entry.

Assembles one machine-readable fact view per task (task.json, decision-anchor
essentials, plan binding, bound sessions, trusted snapshot). See
services/fact_view.py and docs/direction.md stage 1.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__:
    from . import _bootstrap as _bootstrap  # noqa: F401
else:
    import _bootstrap  # noqa: F401

from infra.paths import get_repo_root
from runtime.session_state import get_active_task
from services.fact_view import build_fact_view
from services.task_repository import TaskRepository, TaskRepositoryError


def _human_summary(view: dict) -> str:
    task = view.get("task") or {}
    lines = [
        f"Task: {view.get('taskPath')}",
        f"Status: {task.get('status')}",
    ]
    anchor = view.get("decisionAnchor") or {}
    if anchor.get("exists"):
        goal = anchor.get("goal") or ""
        lines.append(f"Goal: {goal.splitlines()[0] if goal else ''}")
        criteria = anchor.get("acceptanceCriteria") or []
        lines.append(f"Acceptance criteria: {len(criteria)}")
        rejected = anchor.get("rejectedOptions") or []
        if rejected:
            lines.append(f"Rejected options: {len(rejected)}")
    plan = view.get("plan") or {}
    if plan.get("bound"):
        lines.append(f"Plan: {plan.get('file')}")
    sessions = view.get("sessions") or []
    lines.append(f"Bound sessions: {len(sessions)}")
    snapshot = view.get("snapshot")
    lines.append(
        f"Snapshot: {snapshot.get('status') if snapshot else 'none'}"
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="state",
        description="Show the fact view for a task (machine-readable with --json).",
    )
    parser.add_argument(
        "task",
        nargs="?",
        default=None,
        help="Task directory or name; defaults to the session-bound active task.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print the fact view as JSON.",
    )
    args = parser.parse_args()

    repo_root = get_repo_root()
    target = args.task
    if target is None:
        active = get_active_task(repo_root)
        target = active.task_path
        if not target:
            if args.as_json:
                print(
                    json.dumps(
                        {
                            "schemaVersion": 1,
                            "task": None,
                            "reason": "no-active-task",
                        },
                        ensure_ascii=False,
                    )
                )
                return 0
            print(
                "No active task bound to this session; pass a task directory "
                "or name.",
                file=sys.stderr,
            )
            return 1

    try:
        task_dir = TaskRepository(repo_root).resolve(target)
    except TaskRepositoryError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    if not (Path(task_dir) / "task.json").is_file():
        print(f"Error: task.json not found under {task_dir}", file=sys.stderr)
        return 1

    view = build_fact_view(repo_root, Path(task_dir))
    if args.as_json:
        print(json.dumps(view, ensure_ascii=False, indent=2))
    else:
        print(_human_summary(view))
    return 0


if __name__ == "__main__":
    sys.exit(main())