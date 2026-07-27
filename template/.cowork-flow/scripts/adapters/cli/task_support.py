#!/usr/bin/env python3
"""Shared delivery helpers for task commands."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

from infra.config import get_hooks
from services.task_repository import TaskRepository


class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    CYAN = "\033[0;36m"
    NC = "\033[0m"


def colored(text: str, color: str) -> str:
    return f"{color}{text}{Colors.NC}"


def run_hooks(event: str, task_json_path: Path, repo_root: Path) -> None:
    """Run configured lifecycle hooks with UTF-8 subprocess decoding."""
    commands = get_hooks(event, repo_root)
    if not commands:
        return

    env = {**os.environ, "TASK_JSON_PATH": str(task_json_path)}
    for command in commands:
        try:
            result = subprocess.run(
                shlex.split(command),
                cwd=repo_root,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode != 0:
                print(
                    colored(
                        f"[WARN] Hook failed ({event}): {command}",
                        Colors.YELLOW,
                    ),
                    file=sys.stderr,
                )
                if result.stderr.strip():
                    print(f"  {result.stderr.strip()}", file=sys.stderr)
        except Exception as error:
            print(
                colored(
                    f"[WARN] Hook error ({event}): {command} - {error}",
                    Colors.YELLOW,
                ),
                file=sys.stderr,
            )


def slugify(title: str) -> str:
    result = title.lower()
    result = re.sub(r"[^a-z0-9]", "-", result)
    result = re.sub(r"-+", "-", result)
    return result.strip("-")


def resolve_task_dir(target_dir: str | Path, repo_root: Path) -> Path:
    return TaskRepository(repo_root).resolve(target_dir)
