#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared cowork-flow command dispatcher."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

COMMAND_SCRIPTS = {
    "resume": "resume.py",
    "task": "task.py",
    "change": "change.py",
    "get-context": "get_context.py",
    "get_context": "get_context.py",
    "get-developer": "get_developer.py",
    "get_developer": "get_developer.py",
    "init-developer": "init_developer.py",
    "init_developer": "init_developer.py",
    "add-session": "add_session.py",
    "add_session": "add_session.py",
    "agent-team": "agent_team.py",
    "agent_team": "agent_team.py",
}


def print_usage() -> None:
    print(
        """Usage:
  ./.cowork-flow/run <command> [args...]
  ./.cowork-flow/run python [python-args...]

Common commands:
  resume
  task
  change
  get-context
  get-developer
  init-developer
  add-session
  agent-team
""".rstrip()
    )


def scripts_dir() -> Path:
    return Path(__file__).resolve().parent


def run_python(args: list[str]) -> int:
    completed = subprocess.run([sys.executable, *args], check=False)
    return int(completed.returncode)


def run_script(script_name: str, args: list[str]) -> int:
    script_path = scripts_dir() / script_name
    if not script_path.is_file():
        print(f"Error: script not found: {script_path}", file=sys.stderr)
        return 2
    return run_python([str(script_path), *args])


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print_usage()
        return 2

    command = args[0]
    rest = args[1:]
    if command in {"-h", "--help", "help"}:
        print_usage()
        return 0
    if command == "python":
        return run_python(rest)

    script_name = COMMAND_SCRIPTS.get(command)
    if script_name is None:
        candidate = scripts_dir() / f"{command}.py"
        if candidate.is_file():
            script_name = candidate.name
        else:
            print(f"Error: unknown cowork-flow command: {command}", file=sys.stderr)
            print_usage()
            return 2

    return run_script(script_name, rest)


if __name__ == "__main__":
    raise SystemExit(main())
