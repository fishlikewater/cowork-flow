#!/usr/bin/env python3
"""
Developer management utilities.

Provides:
    init_developer     - Initialize developer
    ensure_developer   - Ensure developer is initialized (exit if not)
    show_developer_info - Show developer information
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from infra.paths import (
    DIR_WORKFLOW,
    DIR_TASKS,
    FILE_DEVELOPER,
    get_repo_root,
    get_developer,
    check_developer,
)


# =============================================================================
# Developer Initialization
# =============================================================================


def init_developer(name: str, repo_root: Path | None = None) -> bool:
    """Initialize developer.

    Creates:
        - .cowork-flow/.developer file with developer info

    Args:
        name: Developer name.
        repo_root: Repository root path. Defaults to auto-detected.

    Returns:
        True on success, False on error.
    """
    if not name:
        print("Error: developer name cannot be empty.", file=sys.stderr)
        return False

    if repo_root is None:
        repo_root = get_repo_root()

    dev_file = repo_root / DIR_WORKFLOW / FILE_DEVELOPER

    # Create .developer file
    initialized_at = datetime.now().isoformat()
    try:
        dev_file.write_text(
            f"name={name}\ninitialized_at={initialized_at}\n",
            encoding="utf-8"
        )
    except (OSError, IOError) as e:
        print(f"Error: failed to create .developer file: {e}", file=sys.stderr)
        return False


    print(f"Developer initialized: {name}")
    print(f"  .developer file: {dev_file}")

    return True


def ensure_developer(repo_root: Path | None = None) -> None:
    """Ensure developer is initialized, exit if not.

    Args:
        repo_root: Repository root path. Defaults to auto-detected.
    """
    if repo_root is None:
        repo_root = get_repo_root()

    if not check_developer(repo_root):
        print("Error: developer identity has not been initialized.", file=sys.stderr)
        print(f"Run: ./{DIR_WORKFLOW}/run init-developer <your-name>", file=sys.stderr)
        sys.exit(1)


def show_developer_info(repo_root: Path | None = None) -> None:
    """Show developer information.

    Args:
        repo_root: Repository root path. Defaults to auto-detected.
    """
    if repo_root is None:
        repo_root = get_repo_root()

    developer = get_developer(repo_root)

    if not developer:
        print("Developer: not initialized")
    else:
        print(f"Developer: {developer}")
        print(f"Tasks directory: {DIR_WORKFLOW}/{DIR_TASKS}/")


# =============================================================================
# Main Entry (for testing)
# =============================================================================

if __name__ == "__main__":
    show_developer_info()
