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
    # The skill script imports `services.*` / `infra.*` from
    # the runtime, so the runtime scripts dir goes on
    # PYTHONPATH before spawning (same bootstrap as run.py):
    # the child then resolves this adapter's runtime, not the
    # ambient path. `cache_bytecode=False` is run.py's
    # skill-script rule: in a source checkout the runtime is
    # the shipped `template/` tree.
    env = runtime_pythonpath_env(cache_bytecode=False)
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


def confirm_batch_eligible(args: argparse.Namespace) -> tuple[bool, str]:
    """Require explicit approval before creating Batch runtime state."""
    if not getattr(args, "approved", False):
        return False, "Batch mode requires --approved"
    return True, ""


def run_batch_entry(
    repo_root: Path,
    first_task_dir: Path,
    args: argparse.Namespace,
) -> int:
    """Create or load Batch state and publish its next Host action."""
    eligible, detail = confirm_batch_eligible(args)
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
