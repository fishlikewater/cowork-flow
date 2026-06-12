#!/usr/bin/env python3
"""Flow persistent store layer — SQLite-backed task management."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_FLOW_STORE_INSTANCES: dict[str, "FlowStore"] = {}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class FlowStore:
    """SQLite persistence layer for the Flow system.

    This is the single write-entry point for cowork-flow.db.
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self._ensure_schema()

    def __del__(self):
        try:
            self.db.close()
        except Exception:
            pass

    def _ensure_schema(self) -> None:
        schema_path = Path(__file__).resolve().parent / "schema.sql"
        if schema_path.is_file():
            self.db.executescript(schema_path.read_text(encoding="utf-8"))

    # --- Task CRUD ---

    def create_task(self, *,
        id: str, title: str,
        description: str = "", status: str = "planning",
        pattern: str = "generic", priority: str = "P2",
        creator: str, assignee: str, level: str = "L1",
        parent_id: str | None = None,
        commit_sha: str | None = None,
        meta: dict | None = None,
    ) -> str:
        now = _now()
        artifact_dir = f"{datetime.now().strftime('%m-%d')}-{id}"
        meta_json = json.dumps(meta or {}, ensure_ascii=False)
        self.db.execute(
            """INSERT INTO task (id, artifact_dir, title, description, status,
               pattern, priority, creator, assignee, level, parent_id,
               commit_sha, created_at, updated_at, meta)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (id, artifact_dir, title, description, status,
             pattern, priority, creator, assignee, level, parent_id,
             commit_sha, now, now, meta_json),
        )
        self.db.execute(
            "INSERT INTO audit (task_id, from_status, to_status, operator, reason, created_at) VALUES (?,?,?,?,?,?)",
            (id, None, status, creator, "", now),
        )
        if parent_id:
            self.db.execute(
                "INSERT OR IGNORE INTO task_child (parent_id, child_id) VALUES (?,?)",
                (parent_id, id),
            )
        self.db.commit()
        return id

    def get_task(self, task_id: str):
        row = self.db.execute("SELECT * FROM task WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        return _row_to_taskview(row)

    def update_status(self, task_id: str, new_status: str,
                      operator: str, reason: str = "") -> bool:
        now = _now()
        old = self.db.execute("SELECT status FROM task WHERE id = ?", (task_id,)).fetchone()
        if old is None:
            return False
        old_status = old["status"]
        self.db.execute(
            "UPDATE task SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, now, task_id),
        )
        self.db.execute(
            "INSERT INTO audit (task_id, from_status, to_status, operator, reason, created_at) VALUES (?,?,?,?,?,?)",
            (task_id, old_status, new_status, operator, reason, now),
        )
        if new_status == "completed":
            self.db.execute("UPDATE task SET completed_at = ? WHERE id = ?", (now, task_id))
        self.db.commit()
        return True

    def update_meta(self, task_id: str, meta: dict) -> bool:
        meta_json = json.dumps(meta, ensure_ascii=False)
        now = _now()
        for attempt in range(3):
            try:
                self.db.execute("BEGIN IMMEDIATE")
                self.db.execute(
                    "UPDATE task SET meta = ?, updated_at = ? WHERE id = ?",
                    (meta_json, now, task_id),
                )
                self.db.commit()
                return True
            except sqlite3.OperationalError:
                self.db.rollback()
                if attempt < 2:
                    time.sleep(0.1)
                else:
                    raise

    def list_tasks(self, status: str | None = None):
        if status:
            rows = self.db.execute(
                "SELECT * FROM task WHERE status = ? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = self.db.execute("SELECT * FROM task ORDER BY created_at DESC").fetchall()
        return [_row_to_taskview(r) for r in rows]

    def list_children(self, parent_id: str):
        rows = self.db.execute(
            """SELECT t.* FROM task t
               JOIN task_child tc ON t.id = tc.child_id
               WHERE tc.parent_id = ? ORDER BY tc.sort_order""",
            (parent_id,),
        ).fetchall()
        return [_row_to_taskview(r) for r in rows]

    def link_child(self, parent_id: str, child_id: str, sort_order: int = 0) -> bool:
        self.db.execute(
            "INSERT OR IGNORE INTO task_child (parent_id, child_id, sort_order) VALUES (?,?,?)",
            (parent_id, child_id, sort_order),
        )
        self.db.execute(
            "UPDATE task SET parent_id = ?, updated_at = ? WHERE id = ?",
            (parent_id, _now(), child_id),
        )
        self.db.commit()
        return True

    def unlink_child(self, parent_id: str, child_id: str) -> bool:
        self.db.execute(
            "DELETE FROM task_child WHERE parent_id = ? AND child_id = ?",
            (parent_id, child_id),
        )
        self.db.execute(
            "UPDATE task SET parent_id = NULL, updated_at = ? WHERE id = ?",
            (_now(), child_id),
        )
        self.db.commit()
        return True

    def all_children_done(self, parent_id: str) -> bool:
        count = self.db.execute(
            """SELECT COUNT(*) FROM task t
               JOIN task_child tc ON t.id = tc.child_id
               WHERE tc.parent_id = ? AND t.status NOT IN ('completed','archived')""",
            (parent_id,),
        ).fetchone()[0]
        return count == 0

    # --- Block ---

    def block_task(self, task_id: str, reason: str) -> bool:
        now = _now()
        self.db.execute(
            "INSERT INTO block (task_id, reason, blocked_at) VALUES (?,?,?)",
            (task_id, reason, now),
        )
        self.db.commit()
        return self.update_status(task_id, "blocked", "system", reason)

    def unblock_task(self, task_id: str, decision: str = "", decided_by: str = "") -> bool:
        now = _now()
        self.db.execute(
            "UPDATE block SET decision = ?, decided_by = ?, resolved_at = ? WHERE task_id = ? AND resolved_at IS NULL",
            (decision, decided_by, now, task_id),
        )
        self.db.commit()
        return self.update_status(task_id, "in_progress", decided_by or "system")

    def get_active_block(self, task_id: str):
        row = self.db.execute(
            "SELECT * FROM block WHERE task_id = ? AND resolved_at IS NULL ORDER BY id DESC LIMIT 1",
            (task_id,),
        ).fetchone()
        return dict(row) if row else None

    # --- Agent Run ---

    def create_agent_run(self, *,
        id: str, task_id: str, agent_type: str,
        status: str = "pending",
        host_context_key: str | None = None,
        created_at: str,
    ) -> str:
        self.db.execute(
            "INSERT INTO agent_run (id, task_id, agent_type, status, host_context_key, created_at) VALUES (?,?,?,?,?,?)",
            (id, task_id, agent_type, status, host_context_key, created_at),
        )
        self.db.commit()
        return id

    def update_agent_run_status(self, run_id: str, status: str) -> bool:
        self.db.execute("UPDATE agent_run SET status = ? WHERE id = ?", (status, run_id))
        self.db.commit()
        return True

    def get_active_agent_run(self, task_id: str):
        row = self.db.execute(
            "SELECT * FROM agent_run WHERE task_id = ? AND status != 'closed' ORDER BY created_at DESC LIMIT 1",
            (task_id,),
        ).fetchone()
        return dict(row) if row else None

    def list_agent_runs_for_parent(self, parent_id: str):
        rows = self.db.execute(
            """SELECT ar.* FROM agent_run ar
               JOIN task_child tc ON ar.task_id = tc.child_id
               WHERE tc.parent_id = ? ORDER BY ar.created_at""",
            (parent_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Audit ---

    def get_audit_trail(self, task_id: str):
        rows = self.db.execute(
            "SELECT * FROM audit WHERE task_id = ? ORDER BY created_at", (task_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Dashboard ---

    def board_view(self) -> dict:
        statuses = ["planning", "in_progress", "review", "blocked", "completed", "archived"]
        columns = []
        for st in statuses:
            rows = self.db.execute(
                """SELECT t.id, t.title, t.status, t.pattern, t.priority, t.assignee,
                   COALESCE((SELECT COUNT(*) FROM task_child WHERE parent_id = t.id), 0) AS child_total,
                   COALESCE((SELECT COUNT(*) FROM task_child tc JOIN task ct ON tc.child_id = ct.id
                     WHERE tc.parent_id = t.id AND ct.status IN ('completed','archived')), 0) AS child_done
                   FROM task t WHERE t.status = ? ORDER BY t.priority, t.created_at""",
                (st,),
            ).fetchall()
            columns.append({"status": st, "tasks": [dict(r) for r in rows]})
        return {"columns": columns}


def _row_to_taskview(row):
    meta = json.loads(row["meta"])
    return type("TaskView", (), {
        "id": row["id"],
        "artifact_dir": row["artifact_dir"],
        "title": row["title"],
        "status": row["status"],
        "pattern": row["pattern"],
        "priority": row["priority"] if "priority" in row.keys() else "P2",
        "creator": row["creator"] if "creator" in row.keys() else "",
        "assignee": row["assignee"] if "assignee" in row.keys() else "",
        "parent_id": row["parent_id"],
        "children": [],
        "meta": meta,
        "block_reason": None,
    })()


# --- CLI entrypoint ---

def cmd_init_db(args: argparse.Namespace) -> int:
    from common.paths import get_db_path
    db_path = get_db_path()
    if Path(db_path).exists():
        print(f"Database already exists: {db_path}", file=sys.stderr)
        return 1
    store = FlowStore(str(db_path))
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