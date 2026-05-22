#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cowork Flow change 管理脚本。"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

from common.archive_utils import archive_directory_resumable
from common.paths import (
    DIR_ARCHIVE,
    DIR_CHANGES,
    DIR_WORKFLOW,
    generate_task_date_prefix,
    get_repo_root,
)


SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VALID_LEVELS = {"L1", "L2"}
VALID_STATUSES = {"draft", "active", "archived"}


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _changes_dir(repo_root: Path) -> Path:
    return repo_root / DIR_WORKFLOW / DIR_CHANGES


def _change_dir(repo_root: Path, slug: str) -> Path:
    return _changes_dir(repo_root) / slug


def _archive_dir(repo_root: Path) -> Path:
    return _changes_dir(repo_root) / DIR_ARCHIVE


def _validate_slug(slug: str) -> bool:
    if SLUG_PATTERN.fullmatch(slug):
        return True
    print(
        "Error: slug must match lowercase hyphenated pattern "
        "^[a-z0-9]+(?:-[a-z0-9]+)*$",
        file=sys.stderr,
    )
    return False


def _metadata_path(change_dir: Path) -> Path:
    return change_dir / "change.yaml"


def _format_scalar(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _write_metadata(change_dir: Path, metadata: dict[str, object]) -> None:
    lines = [f"{key}: {_format_scalar(value)}\n" for key, value in metadata.items()]
    _metadata_path(change_dir).write_text("".join(lines), encoding="utf-8")


def _parse_scalar(value: str) -> object:
    if value == "null":
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    return value


def _read_metadata(change_dir: Path) -> dict[str, object]:
    path = _metadata_path(change_dir)
    data: dict[str, object] = {}
    if not path.is_file():
        return data

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = _parse_scalar(value.strip())
    return data


def _has_text(path: Path) -> bool:
    return path.is_file() and bool(path.read_text(encoding="utf-8").strip())


def _spec_file(change_dir: Path) -> Path:
    return change_dir / "spec.md"


def _resolve_link(repo_root: Path, base_dir: str, value: object) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None

    raw_path = Path(value)
    if raw_path.is_absolute():
        return raw_path

    direct = repo_root / raw_path
    workflow_base = Path(DIR_WORKFLOW) / base_dir
    if direct.exists() or raw_path.parts[:2] == workflow_base.parts:
        return direct
    return repo_root / workflow_base / raw_path


def _archived_task_link(repo_root: Path, task_name: str) -> str | None:
    archive_root = repo_root / DIR_WORKFLOW / "tasks" / DIR_ARCHIVE
    if not archive_root.is_dir():
        return None

    matches = [path for path in archive_root.glob(f"*/{task_name}") if path.is_dir()]
    if len(matches) != 1:
        return None

    relative = matches[0].relative_to(archive_root)
    return str(Path(DIR_ARCHIVE) / relative).replace("\\", "/")


def _normalize_task_link(repo_root: Path, value: object) -> object:
    if not isinstance(value, str) or not value.strip():
        return value

    target = _resolve_link(repo_root, "tasks", value)
    tasks_root = repo_root / DIR_WORKFLOW / "tasks"
    archive_root = tasks_root / DIR_ARCHIVE
    if target is None:
        return value

    if not target.exists():
        return _archived_task_link(repo_root, target.name) or value

    try:
        relative = target.resolve().relative_to(archive_root.resolve())
    except ValueError:
        return value

    return str(Path(DIR_ARCHIVE) / relative).replace("\\", "/")


def _normalize_archive_metadata(repo_root: Path, change_dir: Path) -> None:
    metadata = _read_metadata(change_dir)
    normalized_task = _normalize_task_link(repo_root, metadata.get("task"))
    if normalized_task != metadata.get("task"):
        metadata["task"] = normalized_task
        _write_metadata(change_dir, metadata)


def _validate_link(repo_root: Path, metadata: dict[str, object], field: str, base_dir: str) -> str | None:
    target = _resolve_link(repo_root, base_dir, metadata.get(field))
    if target is not None and not target.exists():
        return f"{field} points to missing path: {target}"
    return None


def validate_change(repo_root: Path, slug: str, quiet: bool = False) -> bool:
    if not _validate_slug(slug):
        return False

    change_dir = _change_dir(repo_root, slug)
    errors: list[str] = []

    if not change_dir.is_dir():
        errors.append(f"change not found: {slug}")
    else:
        metadata = _read_metadata(change_dir)
        if not metadata:
            errors.append("missing change.yaml")

        if metadata.get("slug") != slug:
            errors.append("change.yaml slug does not match directory name")

        status = metadata.get("status")
        if status not in VALID_STATUSES:
            errors.append("change.yaml status must be draft, active, or archived")

        level = metadata.get("level")
        if level not in VALID_LEVELS:
            errors.append("change.yaml level must be L1 or L2")

        if not _has_text(change_dir / "proposal.md"):
            errors.append("proposal.md is missing or empty")

        documentation_only = metadata.get("documentation_only") is True
        if not documentation_only and not _has_text(_spec_file(change_dir)):
            errors.append("spec.md is missing or empty")

        if level == "L2" and not _has_text(change_dir / "design.md"):
            errors.append("design.md is required for L2 changes")

        plan_error = _validate_link(repo_root, metadata, "plan", "plans")
        if plan_error:
            errors.append(plan_error)

        task_error = _validate_link(repo_root, metadata, "task", "tasks")
        if task_error:
            errors.append(task_error)

    if errors:
        for error in errors:
            print(f"Error: {error}", file=sys.stderr)
        return False

    if not quiet:
        print(f"{slug} valid")
    return True


def create_change(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    slug = args.slug
    if not _validate_slug(slug):
        return 2

    dir_name = f"{generate_task_date_prefix()}-{slug}"
    change_dir = _change_dir(repo_root, dir_name)
    if change_dir.exists():
        print(f"Error: change already exists: {dir_name}", file=sys.stderr)
        return 1

    change_dir.mkdir(parents=True)
    (change_dir / "proposal.md").write_text(
        f"# {dir_name}\n\nDescribe the proposed behavior change.\n",
        encoding="utf-8",
    )
    (change_dir / "design.md").write_text("", encoding="utf-8")
    _spec_file(change_dir).write_text("", encoding="utf-8")
    _write_metadata(
        change_dir,
        {
            "slug": dir_name,
            "status": "draft",
            "level": args.level,
            "created_at": _now_iso(),
            "documentation_only": False,
            "plan": None,
            "task": None,
        },
    )

    print(f"created {dir_name}")
    return 0


def validate_command(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    return 0 if validate_change(repo_root, args.slug) else 1


def archive_change(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    slug = args.slug
    source = _change_dir(repo_root, slug)
    if source.is_dir():
        _normalize_archive_metadata(repo_root, source)

    if not validate_change(repo_root, slug, quiet=True):
        return 1

    month = datetime.now().astimezone().strftime("%Y-%m")
    destination = _archive_dir(repo_root) / month / slug
    result = archive_directory_resumable(source, destination)
    if not result.ok:
        level = "Warning" if result.partial else "Error"
        print(f"{level}: {result.message}", file=sys.stderr)
        return 1

    metadata = _read_metadata(destination)
    metadata["status"] = "archived"
    metadata["archived_at"] = _now_iso()
    metadata["task"] = _normalize_task_link(repo_root, metadata.get("task"))
    _write_metadata(destination, metadata)

    print(f"archived {slug}")
    return 0


def _change_rows(repo_root: Path) -> list[tuple[str, dict[str, object]]]:
    rows: list[tuple[str, dict[str, object]]] = []
    changes_dir = _changes_dir(repo_root)

    if changes_dir.is_dir():
        for path in sorted(changes_dir.iterdir()):
            if not path.is_dir() or path.name == DIR_ARCHIVE:
                continue
            rows.append((path.name, _read_metadata(path)))

    archive_dir = _archive_dir(repo_root)
    if archive_dir.is_dir():
        for metadata_path in sorted(archive_dir.glob("*/*/change.yaml")):
            change_dir = metadata_path.parent
            rows.append((change_dir.name, _read_metadata(change_dir)))

    return rows


def list_changes(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    rows = _change_rows(repo_root)
    if not rows:
        print("No changes")
        return 0

    for slug, metadata in rows:
        status = metadata.get("status", "unknown")
        level = metadata.get("level", "unknown")
        plan = metadata.get("plan")
        task = metadata.get("task")
        print(
            f"{slug}\tstatus={status}\tlevel={level}\t"
            f"plan={_format_scalar(plan)}\ttask={_format_scalar(task)}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Cowork Flow changes")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("slug")
    create_parser.add_argument("--level", choices=sorted(VALID_LEVELS), default="L1")
    create_parser.set_defaults(func=create_change)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("slug")
    validate_parser.set_defaults(func=validate_command)

    archive_parser = subparsers.add_parser("archive")
    archive_parser.add_argument("slug")
    archive_parser.set_defaults(func=archive_change)

    list_parser = subparsers.add_parser("list")
    list_parser.set_defaults(func=list_changes)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
