#!/usr/bin/env python3
"""
Get Session Context for AI Agent.

Usage:
    ./.cowork-flow/run get-context           Output context in text format
    ./.cowork-flow/run get-context --json    Output context in JSON format
"""

from __future__ import annotations

if __package__:
    from . import _bootstrap as _bootstrap  # noqa: F401
else:
    import _bootstrap  # noqa: F401
from adapters.git.git_context import main


if __name__ == "__main__":
    main()
