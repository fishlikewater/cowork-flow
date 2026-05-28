#!/usr/bin/env python3
"""Resume cowork-flow session context."""

from __future__ import annotations

import argparse

from common.execution_context import (
    build_internal_execution_context_parser,
    build_subagent_resume_text,
    build_worker_resume_text,
    execution_context_from_namespace,
)
from common.git_context import get_context_text


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
