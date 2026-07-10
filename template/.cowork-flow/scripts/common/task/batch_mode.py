#!/usr/bin/env python3
"""Fail-closed Batch mode entry until the real scheduler is available."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


BATCH_DISABLED_CODE = "BATCH-SCHEDULER-NOT-IMPLEMENTED"
BATCH_DISABLED_EXIT_CODE = 2
BATCH_DISABLED_MESSAGE = (
    "Batch mode is disabled until the task-graph scheduler executes the real "
    "start, implement, review, check, complete, and commit lifecycle."
)


def confirm_batch_eligible(
    repo_root: Path,
    task_dir: Path,
    args: argparse.Namespace,
) -> tuple[bool, str]:
    """Reject every Batch request while the scheduler is unavailable."""
    del repo_root, task_dir, args
    return False, BATCH_DISABLED_MESSAGE


def run_batch_entry(
    repo_root: Path,
    first_task_dir: Path,
    args: argparse.Namespace,
) -> int:
    """Return a stable fail-closed result without mutating workflow state."""
    del repo_root, first_task_dir, args
    print(
        f"Error [{BATCH_DISABLED_CODE}]: {BATCH_DISABLED_MESSAGE}",
        file=sys.stderr,
    )
    return BATCH_DISABLED_EXIT_CODE
