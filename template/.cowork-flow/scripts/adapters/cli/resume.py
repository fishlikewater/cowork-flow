#!/usr/bin/env python3
"""Resume cowork-flow session context."""

from __future__ import annotations

import argparse

if __package__:
    from . import _bootstrap as _bootstrap  # noqa: F401
else:
    import _bootstrap  # noqa: F401
from adapters.cli.execution_resume import (
    build_subagent_resume_text,
    build_worker_resume_text,
)
from adapters.cli.execution_context_args import (
    build_internal_execution_context_parser,
    execution_context_from_namespace,
)
from adapters.git.git_context import get_context_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Resume cowork-flow session context",
        parents=[build_internal_execution_context_parser()],
    )
    args = parser.parse_args(argv)
    context = execution_context_from_namespace(args)

    if context.is_worker:
        print("========================================")
        print("COWORK-FLOW WORKER RESUME")
        print("========================================")
        print("Use this only when a dispatched worker needs assignment-scoped recovery.")
        print("Do not switch back into the coordinator workflow from this entrypoint.")
        print("")
        print(build_worker_resume_text(context))
        return 0

    if context.is_subagent:
        print(build_subagent_resume_text(context))
        return 0

    if context.is_coordinator:
        print("========================================")
        print("COWORK-FLOW RESUME (COORDINATOR)")
        print("========================================")
        print("")
        print(get_context_text())
        return 0

    print("========================================")
    print("COWORK-FLOW RESUME")
    print("========================================")
    print("Use this after new sessions, long-task resumes, or context compression.")
    print("Read RESUME CHECKLIST first; load details on demand.")
    print("")
    print(get_context_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
