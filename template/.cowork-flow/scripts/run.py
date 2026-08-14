#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared cowork-flow command dispatcher."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from adapters.cli.encoding import configure_cli_encoding
from adapters.cli.execution_context_args import (
    context_to_internal_cli_args,
    parse_public_execution_context_args,
)
from runtime.execution_context import ExecutionContextError
from infra.process import runtime_pythonpath_env
from infra.skill_manifest import SkillManifestError, skill_command_scripts

configure_cli_encoding()

COMMAND_SCRIPTS = {
    "resume": "adapters/cli/resume.py",
    "task": "adapters/cli/task.py",
    "get-context": "adapters/cli/get_context.py",
    "get_context": "adapters/cli/get_context.py",
    "get-developer": "adapters/cli/get_developer.py",
    "get_developer": "adapters/cli/get_developer.py",
    "init-developer": "adapters/cli/init_developer.py",
    "init_developer": "adapters/cli/init_developer.py",
    "subagent": "adapters/cli/subagent.py",
}
RESERVED_COMMAND_NAMES = (*COMMAND_SCRIPTS, "python", "help", "-h", "--help")

CONTEXT_AWARE_COMMANDS = {"resume", "task", "subagent"}


def print_usage() -> None:
    print(
        """Usage:
  ./.cowork-flow/run <command> [args...]
  ./.cowork-flow/run --context-file <assignment-context.json> <command> [args...]
  ./.cowork-flow/run --mode worker --task-dir <task-dir> --assignment <id> <command> [args...]
  ./.cowork-flow/run python [python-args...]

Common commands:
  resume
  task
  get-context
  get-developer
  init-developer
  subagent
  doctor
  party-v2
""".rstrip()
    )


def scripts_dir() -> Path:
    return Path(__file__).resolve().parent


def project_root() -> Path:
    return scripts_dir().parents[1].resolve()


def resolve_project_python_script(command: str) -> Path | None:
    candidate = Path(command)
    if candidate.is_absolute() or candidate.suffix.lower() != ".py":
        return None

    root = project_root()
    script_path = (root / candidate).resolve()
    try:
        script_path.relative_to(root)
    except ValueError:
        return None
    return script_path if script_path.is_file() else None


def run_python(args: list[str], *, pythonpath: Path | None = None) -> int:
    env = None
    if pythonpath is not None:
        env = runtime_pythonpath_env(pythonpath)
    completed = subprocess.run([sys.executable, *args], check=False, env=env)
    return int(completed.returncode)


def run_script(script_name: str, args: list[str]) -> int:
    script_path = scripts_dir() / script_name
    if not script_path.is_file():
        print(f"Error: script not found: {script_path}", file=sys.stderr)
        return 2
    return run_python([str(script_path), *args], pythonpath=scripts_dir())


def run_skill_script(script_path: Path, args: list[str]) -> int:
    return run_python([str(script_path), *args], pythonpath=scripts_dir())


def reject_context_flags_for(command_label: str) -> int:
    print(
        f"Error: execution context flags are not supported with {command_label}.",
        file=sys.stderr,
    )
    return 2


def reject_non_context_aware_command() -> int:
    print(
        f"Error: execution context flags are only supported for: {', '.join(sorted(CONTEXT_AWARE_COMMANDS))}",
        file=sys.stderr,
    )
    return 2


def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if not raw_args:
        print_usage()
        return 2

    try:
        context, args = parse_public_execution_context_args(raw_args)
    except ExecutionContextError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    if not args:
        print_usage()
        return 2

    command = args[0]
    rest = args[1:]
    if command in {"-h", "--help", "help"}:
        print_usage()
        return 0
    if command == "python":
        if not context.is_default:
            return reject_context_flags_for("the `python` passthrough command")
        return run_python(rest, pythonpath=scripts_dir())

    project_script = resolve_project_python_script(command)
    if project_script is not None:
        if not context.is_default:
            return reject_context_flags_for("project Python scripts")
        return run_python([str(project_script), *rest], pythonpath=scripts_dir())

    try:
        skill_script = skill_command_scripts(
            project_root(),
            reserved_names=RESERVED_COMMAND_NAMES,
        ).get(command)
    except SkillManifestError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    if skill_script is not None:
        if not context.is_default:
            return reject_non_context_aware_command()
        return run_skill_script(skill_script, rest)

    script_name = COMMAND_SCRIPTS.get(command)
    if script_name is None:
        print(f"Error: unknown cowork-flow command: {command}", file=sys.stderr)
        print_usage()
        return 2

    if not context.is_default and command not in CONTEXT_AWARE_COMMANDS:
        return reject_non_context_aware_command()

    return run_script(script_name, [*context_to_internal_cli_args(context), *rest])


if __name__ == "__main__":
    sys.exit(main())
