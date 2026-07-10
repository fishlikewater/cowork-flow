#!/usr/bin/env python3
"""Public entry for the recoverable task-graph Batch scheduler."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from application.batch_execution import (
    BatchExecutionError,
    BatchExecutionService,
)


BATCH_APPROVAL_REQUIRED_CODE = "BATCH-APPROVAL-REQUIRED"
BATCH_REJECTED_EXIT_CODE = 2


def confirm_batch_eligible(
    repo_root: Path,
    task_dir: Path,
    args: argparse.Namespace,
) -> tuple[bool, str]:
    """Require explicit approval before creating Batch runtime state."""
    del repo_root, task_dir
    if not getattr(args, "approved", False):
        return False, "Batch mode requires --approved"
    return True, ""


def run_batch_entry(
    repo_root: Path,
    first_task_dir: Path,
    args: argparse.Namespace,
) -> int:
    """Create or load Batch state and publish its next Host action."""
    eligible, detail = confirm_batch_eligible(
        repo_root,
        first_task_dir,
        args,
    )
    if not eligible:
        print(
            f"Error [{BATCH_APPROVAL_REQUIRED_CODE}]: {detail}",
            file=sys.stderr,
        )
        return BATCH_REJECTED_EXIT_CODE
    try:
        state = BatchExecutionService(repo_root).start(
            first_task_dir.name
        )
    except BatchExecutionError as error:
        print(f"Error [{error.code}]: {error.detail}", file=sys.stderr)
        return BATCH_REJECTED_EXIT_CODE
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0
