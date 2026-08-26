#!/usr/bin/env python3
"""Thin adapter for the Batch-execution Skill runtime."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from infra.process import runtime_pythonpath_env
from infra.skill_manifest import SkillManifestError, skill_command_scripts


BATCH_APPROVAL_REQUIRED_CODE = "BATCH-APPROVAL-REQUIRED"
BATCH_REJECTED_EXIT_CODE = 2


class BatchExecutionError(RuntimeError):
    """Raised when the Skill runtime cannot be loaded."""

    code = "BATCH-RUNTIME-UNAVAILABLE"

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def _batch_action_script(repo_root: Path) -> Path:
    try:
        script = skill_command_scripts(repo_root).get("batch-action")
    except SkillManifestError as error:
        raise BatchExecutionError(f"Skill manifest invalid: {error}") from error
    if script is None:
        raise BatchExecutionError("batch-action Skill command is missing")
    return script


def _run_batch_action(
    repo_root: Path,
    *args: str,
) -> int:
    script = _batch_action_script(repo_root)
    # The skill script imports `services.*` / `infra.*` from the runtime.
    # Inject the runtime scripts dir via PYTHONPATH before spawning (shared
    # bootstrap with run.py) so the child resolves the same runtime this
    # adapter came from instead of relying on the ambient path.
    env = runtime_pythonpath_env()
    try:
        completed = subprocess.run(
            [sys.executable, str(script), *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
        )
    except OSError as error:
        raise BatchExecutionError(f"cannot execute batch-action: {error}") from error
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    return int(completed.returncode)


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
    eligible, detail = confirm_batch_eligible(repo_root, first_task_dir, args)
    if not eligible:
        print(f"Error [{BATCH_APPROVAL_REQUIRED_CODE}]: {detail}", file=sys.stderr)
        return BATCH_REJECTED_EXIT_CODE
    try:
        return _run_batch_action(repo_root, "start", first_task_dir.name)
    except BatchExecutionError as error:
        code = getattr(error, "code", "BATCH-RUNTIME-ERROR")
        detail = getattr(error, "detail", str(error))
        print(f"Error [{code}]: {detail}", file=sys.stderr)
        return BATCH_REJECTED_EXIT_CODE
