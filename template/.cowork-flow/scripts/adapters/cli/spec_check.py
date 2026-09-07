#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`run spec-check [--phase edit|lifecycle] [--file <path>...] [--json]`.

Executes user-declared spec checks (frontmatter `checks:`) and prints a
normalized one-line summary unless `--json`/`--verbose` asks for more. See
services/spec_check.py for the three-state contract (pass/violation/unchecked).
"""

from __future__ import annotations

import argparse
import json
import sys

if __package__:
    from . import _bootstrap as _bootstrap  # noqa: F401
else:
    import _bootstrap  # noqa: F401

from infra.paths import get_repo_root
from services.spec_check import SpecCheckError, run_checks, summary_has


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="spec-check",
        description=(
            "Run user-declared spec checks (frontmatter checks:) for one phase."
        ),
    )
    parser.add_argument(
        "--phase",
        choices=("edit", "lifecycle"),
        default="lifecycle",
        help="edit: only declarations matching the given files (3s clamp); "
        "lifecycle: every declaration honoring its files scope.",
    )
    parser.add_argument(
        "--file",
        action="append",
        default=None,
        help="Changed file path to match against declaration files filters; "
        "repeatable. Drives the edit-phase filter and single-file queries.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print full command output per result (query mode only).",
    )
    parser.add_argument(
        "--throttled",
        action="store_true",
        help="Editor-phase mode: single-line report for one file, throttled "
        "per file (empty output when nothing to report).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print the machine-readable report.",
    )
    args = parser.parse_args()

    repo_root = get_repo_root()

    if args.throttled:
        from services.spec_check import run_edit_checks

        files = args.file or []
        if len(files) != 1:
            print("Error: --throttled requires exactly one --file", file=sys.stderr)
            return 2
        print(run_edit_checks(repo_root, files[0]))
        return 0

    try:
        report = run_checks(
            repo_root,
            phase=args.phase,
            changed_files=args.file or [],
        )
    except SpecCheckError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if args.verbose:
        for result in report.get("results", []):
            print(f"--- {result.get('spec')} :: {result.get('cmd')}")
            for line in result.get("output", []):
                print(line)
            if result.get("reason"):
                print(f"reason: {result['reason']}")

    from services.spec_check import normalized_one_line

    line = normalized_one_line(report)
    if line:
        print(line)
    else:
        summary = report.get("summary", {})
        print(
            "spec-check: {pass} passed, {violation} violations, "
            "{unchecked} unchecked".format(
                **{**{"pass": 0, "violation": 0, "unchecked": 0}, **summary}
            )
        )

    if summary_has(report, "violation"):
        return 1
    if summary_has(report, "unchecked"):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
