#!/usr/bin/env python3
"""恢复 cowork-flow 会话的最小入口。"""

from __future__ import annotations

import argparse

from common.execution_context import (
    build_internal_execution_context_parser,
    build_subagent_resume_text,
    build_worker_resume_text,
    execution_context_from_namespace,
)
from common.git_context import get_context_text
from common.paths import get_repo_root
from common.worker_detection import (
    find_subagents,
    find_workers,
    has_active_work,
    last_worker_sentinel,
)


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

    # Default path — check for active delegated work
    repo_root = get_repo_root()
    if has_active_work(repo_root):
        last_cf: str | None = None
        sentinel = last_worker_sentinel(repo_root)
        if sentinel.is_file():
            try:
                last_cf = sentinel.read_text(encoding="utf-8").strip() or None
            except (OSError, UnicodeDecodeError):
                last_cf = None

        print("========================================")
        print("COWORK-FLOW RESUME")
        print("========================================")
        print("[!] Active delegated work detected. If you are a worker subagent,")
        print("    use scoped recovery with your assignment context file:")
        if last_cf:
            print(f"    ./.cowork-flow/run --context-file {last_cf} resume  (last spawned)")
        for w in find_workers(repo_root):
            cf = w["context_file"]
            if cf != last_cf:
                print(f"    ./.cowork-flow/run --context-file {cf} resume")
        for s in find_subagents(repo_root):
            cf = s.get("contextFile", "")
            if cf and cf != last_cf:
                print(f"    ./.cowork-flow/run --context-file {cf} resume")
        print("")
        print("    Coordinators: use --mode coordinator to skip this warning.")
        print("========================================")
        print("")
    else:
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
