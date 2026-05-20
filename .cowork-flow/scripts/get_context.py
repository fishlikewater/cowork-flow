#!/usr/bin/env python3
"""
Get Session Context for AI Agent.

Usage:
    ./.cowork-flow/run get-context           Output context in text format
    ./.cowork-flow/run get-context --json    Output context in JSON format
"""

from __future__ import annotations

from common.git_context import main


if __name__ == "__main__":
    main()
