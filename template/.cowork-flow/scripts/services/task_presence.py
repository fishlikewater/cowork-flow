#!/usr/bin/env python3
"""Facts and guidance for a binding whose task directory vanished.

Both the host injection body and the CLI blockers render from this module so
a branch or worktree switch cannot describe the same fact two different ways.
"""

from __future__ import annotations


MISSING_TASK_FACT = "task directory not found: {task_path}"
MISSING_TASK_NEXT_STEP = (
    "the bound task may live on another branch or worktree; switch back to "
    "that branch or rebind explicitly — do not create a duplicate task"
)


def missing_task_fact(task_path: str) -> str:
    return MISSING_TASK_FACT.format(task_path=task_path)


def missing_task_blockers(task_path: str) -> list[str]:
    return [missing_task_fact(task_path), MISSING_TASK_NEXT_STEP]


def missing_task_body(task_path: str) -> str:
    return "\n".join(
        [
            f"Session 指向的任务目录不存在（{task_path}）。",
            "不要自动创建重复任务：该任务可能在其他分支或 worktree；"
            "先切回原分支，或显式重新绑定后再继续。",
        ]
    )
