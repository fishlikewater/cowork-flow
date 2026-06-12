#!/usr/bin/env python3
"""task.json to SQLite migration script."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.time_utils import now_utc_iso
from flow.store import FlowStore


def _now():
    return now_utc_iso()


def run_migration(tasks_dir: Path, db_path: str):
    """Migrate task.json files to SQLite.

    Returns (success: bool, warnings: list[str], detail: dict).
    """
    store = FlowStore(db_path)
    warnings: list[str] = []
    dir_to_id: dict[str, str] = {}

    valid_dirs = [d for d in sorted(tasks_dir.iterdir()) if d.is_dir() and d.name != "archive"]
    if not valid_dirs:
        return True, [], {"tasks_migrated": 0}

    # Pass 1: import tasks
    for d in valid_dirs:
        json_path = d / "task.json"
        if not json_path.is_file():
            warnings.append(f"skip {d.name}: no task.json")
            continue
        data = json.loads(json_path.read_text(encoding="utf-8"))
        task_id = data.get("id") or data.get("name") or d.name.split("-", 2)[-1] or d.name
        dir_to_id[d.name] = task_id

        meta = {}
        for key in ("dev_type", "scope", "notes"):
            if data.get(key):
                meta[key] = data[key]
        if data.get("relatedFiles"):
            meta["relatedFiles"] = data["relatedFiles"]

        store.create_task(
            id=task_id,
            title=data.get("title", ""),
            description=data.get("description", ""),
            status=data.get("status", "planning"),
            priority=data.get("priority", "P2"),
            creator=data.get("creator", "migration"),
            assignee=data.get("assignee", "migration"),
            parent_id=data.get("parent"),
            commit_sha=data.get("commit"),
            meta=meta,
        )

    # Pass 2: link children
    for d in valid_dirs:
        json_path = d / "task.json"
        if not json_path.is_file():
            continue
        data = json.loads(json_path.read_text(encoding="utf-8"))
        parent_id = dir_to_id.get(d.name)
        if not parent_id:
            continue
        for child_dir_name in data.get("children", []):
            child_id = dir_to_id.get(child_dir_name)
            if child_id:
                store.link_child(parent_id, child_id)
            else:
                warnings.append(f"orphan child: {parent_id} -> {child_dir_name} (directory missing)")

    return True, warnings, {"tasks_migrated": len(valid_dirs)}


if __name__ == "__main__":
    from common.paths import get_tasks_dir, get_repo_root, get_db_path
    repo_root = get_repo_root()
    tasks_dir = get_tasks_dir(repo_root)
    if not tasks_dir.exists():
        print("Error: tasks/ directory not found", file=sys.stderr)
        sys.exit(1)
    db_path = get_db_path()
    success, warnings, detail = run_migration(tasks_dir, str(db_path))
    if success:
        print(f"Migrated {detail['tasks_migrated']} tasks")
        for w in warnings:
            print(f"WARN: {w}")
        backup = tasks_dir.with_name("tasks.backup")
        if backup.exists():
            print(f"Error: backup already exists: {backup}", file=sys.stderr)
            sys.exit(1)
        tasks_dir.rename(backup)
        print(f"Backup: {backup}")
        # Recreate empty tasks dir for new artifact dirs
        tasks_dir.mkdir(parents=True)
        (tasks_dir / "archive").mkdir(exist_ok=True)
        # .gitignore
        gitignore = repo_root / ".gitignore"
        content = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
        for line in ["tasks.backup/", ".cowork-flow/cowork-flow.db"]:
            if line not in content:
                content += line + "\n"
        gitignore.write_text(content, encoding="utf-8")
        print("Updated .gitignore")
        sys.exit(0)
    else:
        print("Migration failed", file=sys.stderr)
        sys.exit(1)