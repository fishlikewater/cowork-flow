#!/usr/bin/env python3
"""Flow 持久化存储层。（骨架 — Task 1.2 完整实现）"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def cmd_init_db(args: argparse.Namespace) -> int:
    """Initialize cowork-flow.db with schema from schema.sql."""
    from common.paths import get_db_path

    db_path = get_db_path()
    if Path(db_path).exists():
        print(f"Database already exists: {db_path}", file=sys.stderr)
        return 1

    schema = Path(__file__).resolve().parent / "schema.sql"
    db = sqlite3.connect(str(db_path))
    db.executescript(schema.read_text(encoding="utf-8"))
    db.commit()
    db.close()
    print(f"Database created: {db_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Flow store operations")
    sub = parser.add_subparsers(dest="flow_command")

    init_cmd = sub.add_parser("init-db", help="Initialize SQLite database")
    init_cmd.set_defaults(func=cmd_init_db)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())