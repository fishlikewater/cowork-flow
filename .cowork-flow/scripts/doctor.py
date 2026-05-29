#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cowork-flow diagnostics."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common.paths import get_repo_root


REQUIRED_START_SNIPPETS = [
    "This skill is for the main session",
    "bounded delegated task should use `entry-boundary`",
    "Main repository changes follow `Plan -> Implement -> Check -> Finish`",
]

REQUIRED_ENTRY_BOUNDARY_SNIPPETS = [
    "MAIN_SESSION",
    "DELEGATED_SUBTASK",
    "UNCERTAIN",
    "Classify the actual task message",
    "Active task: <task-dir>",
    "Follow the delegated prompt first",
    "Do not run unscoped `.cowork-flow/run resume`",
    "Do not spawn or manage more agents",
]


def _check_file_contains(path: Path, snippets: list[str], errors: list[str]) -> None:
    if not path.is_file():
        errors.append(f"missing file: {path}")
        return
    text = path.read_text(encoding="utf-8")
    for snippet in snippets:
        if snippet not in text:
            errors.append(f"{path} missing snippet: {snippet}")


def cmd_subagent_safety(_: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    errors: list[str] = []
    for rel in (
        ".agent/skills/start/SKILL.md",
        "template/.agent/skills/start/SKILL.md",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_START_SNIPPETS, errors)
    for rel in (
        ".agent/skills/entry-boundary/SKILL.md",
        "template/.agent/skills/entry-boundary/SKILL.md",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_ENTRY_BOUNDARY_SNIPPETS, errors)
    for rel in (
        ".cowork-flow/scripts/subagent.py",
        "template/.cowork-flow/scripts/subagent.py",
        ".cowork-flow/scripts/common/execution_context.py",
        "template/.cowork-flow/scripts/common/execution_context.py",
    ):
        if not (repo_root / rel).is_file():
            errors.append(f"missing file: {rel}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("subagent safety checks passed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="cowork-flow diagnostics")
    parser.add_argument("--subagent-safety", action="store_true", help="Check subagent safety wiring")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.subagent_safety:
        return cmd_subagent_safety(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
