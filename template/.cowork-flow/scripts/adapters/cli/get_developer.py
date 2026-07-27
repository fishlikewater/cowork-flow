#!/usr/bin/env python3
"""
Get current developer name.

This is a wrapper that uses kernel/paths.py
"""

from __future__ import annotations

import sys

if __package__:
    from . import _bootstrap as _bootstrap  # noqa: F401
else:
    import _bootstrap  # noqa: F401
from infra.paths import get_developer


def main() -> None:
    """CLI entry point."""
    developer = get_developer()
    if developer:
        print(developer)
    else:
        print("Developer not initialized", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
