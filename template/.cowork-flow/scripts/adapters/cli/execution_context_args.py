"""CLI argument adapters for execution context flags."""

from __future__ import annotations

import argparse

from runtime.execution_context import (
    MODE_COORDINATOR,
    MODE_NONE,
    MODE_SUBAGENT,
    MODE_WORKER,
    ExecutionContext,
    ExecutionContextError,
    execution_context_from_values,
)


PUBLIC_CONTEXT_FLAGS = {
    "--mode",
    "--assignment",
    "--task-dir",
    "--prompt-file",
    "--context-file",
}


def _build_parser(
    *,
    add_help: bool,
    mode_flag: str,
    assignment_flag: str,
    task_dir_flag: str,
    prompt_file_flag: str,
    context_file_flag: str,
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=add_help)
    parser.add_argument(
        mode_flag,
        choices=[MODE_NONE, MODE_COORDINATOR, MODE_WORKER, MODE_SUBAGENT],
        help=argparse.SUPPRESS,
    )
    parser.add_argument(assignment_flag, help=argparse.SUPPRESS)
    parser.add_argument(task_dir_flag, help=argparse.SUPPRESS)
    parser.add_argument(prompt_file_flag, help=argparse.SUPPRESS)
    parser.add_argument(context_file_flag, help=argparse.SUPPRESS)
    return parser


def build_public_execution_context_parser(add_help: bool = False) -> argparse.ArgumentParser:
    return _build_parser(
        add_help=add_help,
        mode_flag="--mode",
        assignment_flag="--assignment",
        task_dir_flag="--task-dir",
        prompt_file_flag="--prompt-file",
        context_file_flag="--context-file",
    )


def build_internal_execution_context_parser(add_help: bool = False) -> argparse.ArgumentParser:
    return _build_parser(
        add_help=add_help,
        mode_flag="--execution-mode",
        assignment_flag="--execution-assignment",
        task_dir_flag="--execution-task-dir",
        prompt_file_flag="--execution-prompt-file",
        context_file_flag="--execution-context-file",
    )


def parse_public_execution_context_args(argv: list[str]) -> tuple[ExecutionContext, list[str]]:
    parser = build_public_execution_context_parser(add_help=False)
    leading: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in PUBLIC_CONTEXT_FLAGS:
            if index + 1 >= len(argv):
                raise ExecutionContextError(f"missing value for {token}")
            leading.extend([token, argv[index + 1]])
            index += 2
            continue
        break

    namespace, leftover = parser.parse_known_args(leading)
    if leftover:
        raise ExecutionContextError(f"unsupported execution context arguments: {' '.join(leftover)}")
    context = execution_context_from_values(
        mode=getattr(namespace, "mode", None),
        assignment=getattr(namespace, "assignment", None),
        task_dir=getattr(namespace, "task_dir", None),
        prompt_file=getattr(namespace, "prompt_file", None),
        context_file=getattr(namespace, "context_file", None),
    )
    return context, argv[index:]


def execution_context_from_namespace(namespace: argparse.Namespace) -> ExecutionContext:
    return execution_context_from_values(
        mode=getattr(namespace, "execution_mode", None),
        assignment=getattr(namespace, "execution_assignment", None),
        task_dir=getattr(namespace, "execution_task_dir", None),
        prompt_file=getattr(namespace, "execution_prompt_file", None),
        context_file=getattr(namespace, "execution_context_file", None),
    )


def context_to_internal_cli_args(context: ExecutionContext) -> list[str]:
    if context.is_default:
        return []
    if context.context_file:
        return ["--execution-context-file", context.context_file]

    args = ["--execution-mode", context.mode]
    if context.task_dir:
        args.extend(["--execution-task-dir", context.task_dir])
    if context.assignment:
        args.extend(["--execution-assignment", context.assignment])
    if context.prompt_file:
        args.extend(["--execution-prompt-file", context.prompt_file])
    return args
