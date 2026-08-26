#!/usr/bin/env python3
"""Skill-owned Batch action runtime entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from batch_execution import BatchExecutionService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="batch-action")
    subparsers = parser.add_subparsers(dest="action", required=True)
    start = subparsers.add_parser("start")
    start.add_argument("root_task")
    resume = subparsers.add_parser("resume")
    resume.add_argument("operation_id")
    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("operation_id")
    record = subparsers.add_parser("record-result")
    record.add_argument("operation_id")
    record.add_argument("file", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    service = BatchExecutionService(Path.cwd())
    try:
        if args.action == "start":
            state = service.start(args.root_task)
        elif args.action == "resume":
            state = service.resume(args.operation_id)
        elif args.action == "inspect":
            state = service.inspect(args.operation_id)
        else:
            payload = json.loads(args.file.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Batch result JSON must be an object")
            state = service.record_result(args.operation_id, payload)
    except Exception as error:
        print(f"Error [{getattr(error, 'code', 'BATCH-RUNTIME-ERROR')}]: {getattr(error, 'detail', error)}", file=sys.stderr)
        return 2
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 2 if state.get("phase") == "paused" else 0


if __name__ == "__main__":
    raise SystemExit(main())
