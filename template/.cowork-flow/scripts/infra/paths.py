#!/usr/bin/env python3
"""
Common path utilities for Cowork Flow workflow.

Provides:
    get_repo_root          - Get repository root directory
    get_developer          - Get developer name
    get_tasks_dir          - Get tasks directory
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


# =============================================================================
# Path Constants (change here to rename directories)
# =============================================================================

# Directory names
DIR_WORKFLOW = ".cowork-flow"
DIR_AGENTS = ".agents"
DIR_TASKS = "tasks"
DIR_ARCHIVE = "archive"
DIR_SPEC = "spec"
DIR_SCRIPTS = "scripts"

# File names
FILE_DEVELOPER = ".developer"
FILE_TASK_JSON = "task.json"
TASK_DATE_PREFIX_PATTERN = re.compile(r"^\d{2}-\d{2}-")
FULL_DATE_PREFIX_PATTERN = re.compile(r"^\d{4}-(\d{2}-\d{2}-)")


# =============================================================================
# Repository Root
# =============================================================================

def get_repo_root(start_path: Path | None = None) -> Path:
    """Find the nearest directory containing .cowork-flow/ folder.

    This handles nested git repos correctly (e.g., test project inside another repo).

    Args:
        start_path: Starting directory to search from. Defaults to current directory.

    Returns:
        Path to repository root, or current directory if no .cowork-flow/ found.
    """
    current = (start_path or Path.cwd()).absolute()

    while current != current.parent:
        if (current / DIR_WORKFLOW).is_dir():
            return current
        current = current.parent

    # Fallback to current directory if no .cowork-flow/ found
    return Path.cwd().absolute()


# =============================================================================
# Developer
# =============================================================================

def get_developer(repo_root: Path | None = None) -> str | None:
    """Get developer name from .developer file.

    Args:
        repo_root: Repository root path. Defaults to auto-detected.

    Returns:
        Developer name or None if not initialized.
    """
    if repo_root is None:
        repo_root = get_repo_root()

    dev_file = repo_root / DIR_WORKFLOW / FILE_DEVELOPER

    if not dev_file.is_file():
        return None

    try:
        content = dev_file.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.startswith("name="):
                name = line.split("=", 1)[1].strip()
                if not name or (name.startswith("<") and name.endswith(">")):
                    return None
                return name
    except (OSError, IOError):
        pass

    return None


def check_developer(repo_root: Path | None = None) -> bool:
    """Check if developer is initialized.

    Args:
        repo_root: Repository root path. Defaults to auto-detected.

    Returns:
        True if developer is initialized.
    """
    return get_developer(repo_root) is not None


# =============================================================================
# Tasks Directory
# =============================================================================

def get_tasks_dir(repo_root: Path | None = None) -> Path:
    """Get tasks directory path.

    Args:
        repo_root: Repository root path. Defaults to auto-detected.

    Returns:
        Path to tasks directory.
    """
    if repo_root is None:
        repo_root = get_repo_root()
    return repo_root / DIR_WORKFLOW / DIR_TASKS



    try:
        with file_path.open("r", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


# =============================================================================
# Task ID Generation
# =============================================================================

def generate_task_date_prefix() -> str:
    """Generate task ID based on date (MM-DD format).

    Returns:
        Date prefix string (e.g., "01-21").
    """
    return datetime.now().strftime("%m-%d")


def ensure_task_date_prefix(slug: str) -> str:
    """Return slug with exactly one MM-DD prefix.

    A full YYYY-MM-DD- prefix is normalized to MM-DD-; a bare slug
    gets today's MM-DD prefix.
    """
    full = FULL_DATE_PREFIX_PATTERN.match(slug)
    if full:
        return full.group(1) + slug[full.end():]
    if TASK_DATE_PREFIX_PATTERN.match(slug):
        return slug
    return f"{generate_task_date_prefix()}-{slug}"


# =============================================================================
# Main Entry (for testing)
# =============================================================================

if __name__ == "__main__":
    repo = get_repo_root()
    print(f"Repository root: {repo}")
    print(f"Developer: {get_developer(repo)}")
    print(f"Tasks dir: {get_tasks_dir(repo)}")
