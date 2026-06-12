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
    with FlowStore(db_path) as store:
        warnings: list[str] = []
        dir_to_id: dict[str, str] = {}
        records: list[dict] = []

        valid_dirs = [d for d in sorted(tasks_dir.iterdir()) if d.is_dir() and d.name != "archive"]
        if not valid_dirs:
            return True, [], {"tasks_migrated": 0}

        # Parse every task first so SQL failures can roll back the whole batch.
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

            records.append(
                {
                    "dir_name": d.name,
                    "id": task_id,
                    "data": data,
                    "meta": meta,
                }
            )

        id_set = {record["id"] for record in records}

        def _resolve_task_ref(value) -> str | None:
            if not isinstance(value, str) or not value.strip():
                return None
            ref = value.strip()
            if ref in dir_to_id:
                return dir_to_id[ref]
            if ref in id_set:
                return ref
            return None

        edges: list[tuple[str, str, int]] = []
        seen_edges: set[tuple[str, str]] = set()

        def _add_edge(parent_id: str | None, child_id: str | None, sort_order: int) -> None:
            if not parent_id or not child_id or parent_id == child_id:
                return
            key = (parent_id, child_id)
            if key in seen_edges:
                return
            seen_edges.add(key)
            edges.append((parent_id, child_id, sort_order))

        for record in records:
            child_id = record["id"]
            parent_ref = record["data"].get("parent")
            if parent_ref:
                parent_id = _resolve_task_ref(parent_ref)
                if parent_id:
                    _add_edge(parent_id, child_id, 0)
                else:
                    warnings.append(f"orphan parent: {child_id} -> {parent_ref} (directory missing)")

        for record in records:
            parent_id = record["id"]
            children = record["data"].get("children", [])
            if not isinstance(children, list):
                continue
            for sort_order, child_ref in enumerate(children):
                child_id = _resolve_task_ref(child_ref)
                if child_id:
                    _add_edge(parent_id, child_id, sort_order)
                else:
                    warnings.append(f"orphan child: {parent_id} -> {child_ref} (directory missing)")

        def _do_migrate():
            now = _now()
            for record in records:
                data = record["data"]
                meta_json = json.dumps(record["meta"], ensure_ascii=False)
                store.db.execute(
                    """INSERT INTO task (id, artifact_dir, title, description, status,
                       pattern, priority, creator, assignee, level, parent_id,
                       commit_sha, created_at, updated_at, meta)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        record["id"],
                        record["dir_name"],
                        data.get("title", ""),
                        data.get("description", ""),
                        data.get("status", "planning"),
                        data.get("pattern", "generic"),
                        data.get("priority", "P2"),
                        data.get("creator", "migration"),
                        data.get("assignee", "migration"),
                        data.get("level", "L1"),
                        None,
                        data.get("commit"),
                        now,
                        now,
                        meta_json,
                    ),
                )
                store.db.execute(
                    "INSERT INTO audit (task_id, from_status, to_status, operator, reason, created_at) VALUES (?,?,?,?,?,?)",
                    (record["id"], None, data.get("status", "planning"), "migration", "", now),
                )
            for parent_id, child_id, sort_order in edges:
                store.db.execute(
                    "INSERT INTO task_child (parent_id, child_id, sort_order) VALUES (?,?,?)",
                    (parent_id, child_id, sort_order),
                )
                store.db.execute(
                    "UPDATE task SET parent_id = ?, updated_at = ? WHERE id = ?",
                    (parent_id, now, child_id),
                )
            return True

        store._transaction(_do_migrate)

        return True, warnings, {"tasks_migrated": len(records)}


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
