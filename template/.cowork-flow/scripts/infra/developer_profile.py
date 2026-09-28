#!/usr/bin/env python3
"""Developer identity in .cowork-flow/.developer."""

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


def init_developer(name: str, repo_root: Path | None = None) -> bool:
    """Write .developer; a failure is reported and returned, not raised."""
    if not name:
        print("Error: developer name cannot be empty.", file=sys.stderr)
        return False

    if repo_root is None:
        repo_root = get_repo_root()

    dev_file = repo_root / DIR_WORKFLOW / FILE_DEVELOPER

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
    """Exit 1 with the init command when no developer is set."""
    if repo_root is None:
        repo_root = get_repo_root()

    if not check_developer(repo_root):
        print("Error: developer identity has not been initialized.", file=sys.stderr)
        print(f"Run: ./{DIR_WORKFLOW}/run init-developer <your-name>", file=sys.stderr)
        sys.exit(1)


def show_developer_info(repo_root: Path | None = None) -> None:
    """Print the developer name, or the not-initialized notice."""
    if repo_root is None:
        repo_root = get_repo_root()

    developer = get_developer(repo_root)

    if not developer:
        print("Developer: not initialized")
    else:
        print(f"Developer: {developer}")
        print(f"Tasks directory: {DIR_WORKFLOW}/{DIR_TASKS}/")


if __name__ == "__main__":
    show_developer_info()
