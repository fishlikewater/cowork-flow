#!/usr/bin/env python3
"""
Initialize developer for workflow.

Usage:
    ./.cowork-flow/run init-developer <developer-name>

This creates:
    - .cowork-flow/.developer file with developer info
"""

from __future__ import annotations

import sys

if __package__:
    from . import _bootstrap as _bootstrap  # noqa: F401
else:
    import _bootstrap  # noqa: F401
from infra.paths import (
    DIR_WORKFLOW,
    FILE_DEVELOPER,
    get_developer,
)
from infra.developer_profile import init_developer


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <developer-name>")
        print()
        print("Example:")
        print(f"  {sys.argv[0]} john")
        sys.exit(1)

    name = sys.argv[1]

    # Check if already initialized
    existing = get_developer()
    if existing:
        print(f"Developer already initialized: {existing}")
        print()
        print(f"To reinitialize, remove {DIR_WORKFLOW}/{FILE_DEVELOPER} first")
        sys.exit(0)

    if init_developer(name):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
